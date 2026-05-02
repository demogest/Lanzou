use std::collections::HashMap;
use std::sync::Mutex;
use std::time::Duration;

use base64::{engine::general_purpose::STANDARD, Engine as _};
use regex::Regex;
use reqwest::blocking::Client;
use reqwest::header::{
    HeaderMap, HeaderValue, ACCEPT, ACCEPT_ENCODING, ACCEPT_LANGUAGE, COOKIE, REFERER, USER_AGENT,
};
use reqwest::Method;
use scraper::{Html, Selector};
use serde_json::Value;
use url::Url;

use crate::errors::{LanzouError, LanzouResult};
use crate::models::{DownloadTask, FileEntry};

const USER_AGENT_VALUE: &str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
    (KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36";
const ACCEPT_VALUE: &str = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,\
    image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9";

#[derive(Debug, Clone)]
pub struct LanzouConfig {
    pub base_url: String,
    pub connect_timeout: Duration,
    pub request_timeout: Duration,
    pub chunk_size: usize,
}

impl Default for LanzouConfig {
    fn default() -> Self {
        Self {
            base_url: "https://www.lanzoux.com".to_string(),
            connect_timeout: Duration::from_secs(8),
            request_timeout: Duration::from_secs(60),
            chunk_size: 1024 * 256,
        }
    }
}

pub struct LanzouClient {
    config: LanzouConfig,
    http: Client,
    challenge_cookies: Mutex<HashMap<String, String>>,
}

impl LanzouClient {
    pub fn new(config: LanzouConfig) -> LanzouResult<Self> {
        let http = Client::builder()
            .connect_timeout(config.connect_timeout)
            .timeout(config.request_timeout)
            .cookie_store(true)
            .build()?;
        Ok(Self {
            config,
            http,
            challenge_cookies: Mutex::new(HashMap::new()),
        })
    }

    pub fn list_files(&self, task: &DownloadTask) -> LanzouResult<Vec<FileEntry>> {
        let task = task.normalized();
        let html = self.request_text(Method::GET, &task.share_url, Some(&task.share_url), None, true)?;

        if self.is_single_file_page(&html) {
            return Ok(vec![self.single_file_entry(&task.share_url, &html)]);
        }

        self.raise_if_unsupported_page(&html)?;

        let tokens: Vec<String> = Regex::new(r#"var [\w]{6} = '([\w]+?)';"#)
            .expect("valid regex")
            .captures_iter(&html)
            .filter_map(|capture| capture.get(1).map(|value| value.as_str().to_string()))
            .collect();
        if tokens.len() < 2 {
            return Err(LanzouError::Parse(
                "Cannot find folder token parameters in the share page.".to_string(),
            ));
        }

        let mut data = vec![
            ("lx".to_string(), first_match(r#"'lx':(\d+?),"#, &html, "lx")?),
            ("fid".to_string(), first_match(r#"'fid':(\d+?),"#, &html, "fid")?),
            ("uid".to_string(), first_match(r#"'uid':'(\d+?)',"#, &html, "uid")?),
            ("pg".to_string(), first_match(r#"pgs\s*=\s*(\d+?);"#, &html, "pgs")?),
            ("t".to_string(), tokens[0].clone()),
            ("k".to_string(), tokens[1].clone()),
        ];

        if self.page_requires_password(&html) {
            if task.password.is_empty() {
                return Err(LanzouError::Password(
                    "This share link requires a password.".to_string(),
                ));
            }
            data.push(("pwd".to_string(), task.password.clone()));
        }

        let payload = self.post_json(
            &self.endpoint(&task.share_url, "filemoreajax.php")?,
            &data,
            Some(&task.share_url),
        )?;
        if !is_success(&payload) {
            let message = value_text(payload.get("info"))
                .or_else(|| value_text(payload.get("inf")))
                .unwrap_or_else(|| "Failed to get file list.".to_string());
            return Err(LanzouError::Password(message));
        }

        let items = payload
            .get("text")
            .and_then(Value::as_array)
            .ok_or_else(|| LanzouError::Parse("Unexpected file list response from Lanzou.".to_string()))?;

        let files = items
            .iter()
            .filter_map(|item| {
                let page_path = value_text(item.get("id")).unwrap_or_default();
                let name = value_text(item.get("name_all")).unwrap_or_default();
                if page_path.trim().is_empty() || name.trim().is_empty() {
                    None
                } else {
                    Some(FileEntry::new(page_path.trim().to_string(), name.trim().to_string()))
                }
            })
            .collect();
        Ok(files)
    }

    fn is_single_file_page(&self, html: &str) -> bool {
        !self.is_folder_page(html)
            && (self.page_requires_password(html)
                || Html::parse_document(html)
                    .select(&Selector::parse("iframe").expect("valid selector"))
                    .next()
                    .is_some())
    }

    fn single_file_entry(&self, share_url: &str, html: &str) -> FileEntry {
        FileEntry::new(
            share_url.to_string(),
            single_file_name(html).unwrap_or_else(|| fallback_file_name(share_url)),
        )
    }

    pub fn resolve_file(&self, task: &DownloadTask, entry: &FileEntry) -> LanzouResult<FileEntry> {
        let task = task.normalized();
        let page_url = self.entry_page_url(&task.share_url, entry)?;
        let html = self.request_text(Method::GET, &page_url, Some(&task.share_url), None, true)?;

        if self.page_requires_password(&html) {
            return Ok(entry.with_download_url(self.unlock_file(&task, &page_url)?));
        }

        let iframe_url = self.iframe_url(&html, &page_url, &entry.name)?;
        let iframe_html = self.request_text(Method::GET, &iframe_url, Some(&page_url), None, true)?;
        let data = self.download_request_data(&iframe_html)?;
        let payload = self.post_json(
            &self.ajax_endpoint(&iframe_html, &iframe_url)?,
            &data,
            Some(&iframe_url),
        )?;
        if !is_success(&payload) {
            let message = value_text(payload.get("inf"))
                .unwrap_or_else(|| "Failed to resolve download URL.".to_string());
            return Err(LanzouError::Parse(message));
        }

        Ok(entry.with_download_url(self.download_url_from_payload(&payload)?))
    }

    pub fn page_requires_password(&self, html: &str) -> bool {
        let document = Html::parse_document(html);
        let selector = Selector::parse("input#pwd[name=pwd]").expect("valid selector");
        document.select(&selector).next().is_some()
    }

    fn unlock_file(&self, task: &DownloadTask, page_url: &str) -> LanzouResult<String> {
        if task.password.is_empty() {
            return Err(LanzouError::Password(
                "This file requires a password.".to_string(),
            ));
        }

        let html = self.request_text(Method::GET, page_url, Some(&task.share_url), None, true)?;
        let data = vec![
            (
                "action".to_string(),
                first_match(r#"action=([\S]*?)&"#, &html, "password action")?,
            ),
            (
                "sign".to_string(),
                first_match(r#"sign=([\S]{15,})&"#, &html, "password sign")?,
            ),
            ("p".to_string(), task.password.clone()),
        ];
        let payload = self.post_json(
            &self.endpoint(page_url, "ajaxm.php")?,
            &data,
            Some(page_url),
        )?;
        if !is_success(&payload) {
            let message = value_text(payload.get("inf")).unwrap_or_else(|| "Password rejected.".to_string());
            return Err(LanzouError::Password(message));
        }
        self.download_url_from_payload(&payload)
    }

    fn post_json(&self, url: &str, data: &[(String, String)], referer: Option<&str>) -> LanzouResult<Value> {
        let text = self.request_text(Method::POST, url, referer, Some(data), true)?;
        serde_json::from_str(&text)
            .map_err(|_| LanzouError::Parse("Lanzou returned an invalid JSON response.".to_string()))
    }

    fn request_text(
        &self,
        method: Method,
        url: &str,
        referer: Option<&str>,
        form: Option<&[(String, String)]>,
        challenge_retry: bool,
    ) -> LanzouResult<String> {
        let mut request = self
            .http
            .request(method.clone(), url)
            .headers(self.headers_for_url(url, referer)?);
        if let Some(form) = form {
            request = request.form(form);
        }

        let response = request.send()?.error_for_status()?;
        let final_url = response.url().clone();
        let text = response.text()?;

        if challenge_retry && self.looks_like_cookie_challenge(&text) {
            let cookie_value = self.solve_cookie_challenge(&text)?;
            if let Some(host) = final_url.host_str() {
                self.challenge_cookies
                    .lock()
                    .map_err(|_| LanzouError::Parse("Cannot store Lanzou challenge cookie.".to_string()))?
                    .insert(host.to_string(), cookie_value);
            }
            return self.request_text(method, url, referer, form, false);
        }

        Ok(text)
    }

    fn headers_for_url(&self, url: &str, referer: Option<&str>) -> LanzouResult<HeaderMap> {
        let cookie = self.challenge_cookie_for(url)?;
        request_headers(referer, cookie.as_deref())
    }

    fn challenge_cookie_for(&self, url: &str) -> LanzouResult<Option<String>> {
        let host = Url::parse(url).ok().and_then(|parsed| parsed.host_str().map(str::to_string));
        let Some(host) = host else {
            return Ok(None);
        };
        Ok(self
            .challenge_cookies
            .lock()
            .map_err(|_| LanzouError::Parse("Cannot read Lanzou challenge cookie.".to_string()))?
            .get(&host)
            .cloned())
    }

    fn entry_page_url(&self, share_url: &str, entry: &FileEntry) -> LanzouResult<String> {
        if entry.page_path.starts_with("http://") || entry.page_path.starts_with("https://") {
            return Ok(entry.page_path.clone());
        }
        join_url(&(self.origin(share_url)? + "/"), &entry.page_path)
    }

    fn iframe_url(&self, html: &str, page_url: &str, file_name: &str) -> LanzouResult<String> {
        let document = Html::parse_document(html);
        let selector = Selector::parse("iframe").expect("valid selector");
        let src = document
            .select(&selector)
            .find_map(|node| node.value().attr("src"))
            .ok_or_else(|| LanzouError::Parse(format!("Cannot find download iframe for {file_name}.")))?;
        join_url(page_url, src)
    }

    fn download_request_data(&self, iframe_html: &str) -> LanzouResult<Vec<(String, String)>> {
        let ajaxdata = first_match(r#"ajaxdata\s*=\s*'([^']*?)';"#, iframe_html, "ajaxdata")?;
        if let Some(wp_sign) = capture_optional(r#"wp_sign\s*=\s*'([^']*?)';"#, iframe_html) {
            return Ok(vec![
                ("action".to_string(), "downprocess".to_string()),
                ("websignkey".to_string(), ajaxdata.clone()),
                ("signs".to_string(), ajaxdata),
                ("sign".to_string(), wp_sign),
                ("websign".to_string(), String::new()),
                ("kd".to_string(), "1".to_string()),
                ("ves".to_string(), "1".to_string()),
            ]);
        }

        Ok(vec![
            (
                "action".to_string(),
                first_match(r#"'action'\s*:\s*'(\w*?)',"#, iframe_html, "action")?,
            ),
            (
                "sign".to_string(),
                first_match(r#"'sign'\s*:\s*'([^']*?)',"#, iframe_html, "sign")?,
            ),
            ("ves".to_string(), "1".to_string()),
            ("signs".to_string(), ajaxdata),
            (
                "websignkey".to_string(),
                first_match(r#"wsk_sign\s*=\s*'([^']*?)';"#, iframe_html, "wsk_sign")?,
            ),
            (
                "websign".to_string(),
                first_match(r#"ws_sign\s*=\s*'([^']*?)';"#, iframe_html, "ws_sign")?,
            ),
        ])
    }

    fn ajax_endpoint(&self, iframe_html: &str, iframe_url: &str) -> LanzouResult<String> {
        let url_re = Regex::new(r#"url\s*:\s*['"](/?ajaxm\.php\?file=\d+)"#).expect("valid regex");
        if let Some(path) = url_re
            .captures_iter(iframe_html)
            .filter_map(|capture| capture.get(1).map(|value| value.as_str().to_string()))
            .last()
        {
            return join_url(&(self.origin(iframe_url)? + "/"), path.trim_start_matches('/'));
        }

        if let Some(path) = capture_optional(r#"(/?ajaxm\.php\?file=\d+)"#, iframe_html) {
            return join_url(&(self.origin(iframe_url)? + "/"), path.trim_start_matches('/'));
        }

        self.endpoint(iframe_url, "ajaxm.php")
    }

    fn download_url_from_payload(&self, payload: &Value) -> LanzouResult<String> {
        let domain = value_text(payload.get("dom")).unwrap_or_default();
        let path = value_text(payload.get("url")).unwrap_or_default();
        let domain = domain.trim_end_matches('/');
        let path = path.trim_start_matches('/');
        if domain.is_empty() || path.is_empty() {
            return Err(LanzouError::Parse(
                "Download URL response is missing required fields.".to_string(),
            ));
        }
        Ok(format!("{domain}/file/{path}"))
    }

    fn raise_if_unsupported_page(&self, html: &str) -> LanzouResult<()> {
        if self.is_folder_page(html) {
            return Ok(());
        }

        let document = Html::parse_document(html);
        let selector = Selector::parse("iframe").expect("valid selector");
        if document.select(&selector).next().is_some() {
            return Err(LanzouError::UnsupportedLink(
                "Single-file share links are not supported yet.".to_string(),
            ));
        }
        Err(LanzouError::Parse(
            "Cannot find folder metadata in the share page.".to_string(),
        ))
    }

    fn is_folder_page(&self, html: &str) -> bool {
        Regex::new(r#"'fid':\d+?,"#)
            .expect("valid regex")
            .is_match(html)
    }

    fn endpoint(&self, url: &str, endpoint: &str) -> LanzouResult<String> {
        join_url(&(self.origin(url)? + "/"), endpoint)
    }

    fn origin(&self, url: &str) -> LanzouResult<String> {
        let parsed = Url::parse(url).or_else(|_| Url::parse(&self.config.base_url))?;
        let host = parsed
            .host_str()
            .ok_or_else(|| LanzouError::Parse("Cannot determine Lanzou host.".to_string()))?;
        let mut origin = format!("{}://{host}", parsed.scheme());
        if let Some(port) = parsed.port() {
            origin.push_str(&format!(":{port}"));
        }
        Ok(origin)
    }

    fn looks_like_cookie_challenge(&self, html: &str) -> bool {
        html.contains("acw_sc__v2") && html.contains("var arg1=") && html.contains("function a0i()")
    }

    fn solve_cookie_challenge(&self, html: &str) -> LanzouResult<String> {
        let arg1 = first_match(r#"var arg1='([^']+)'"#, html, "challenge arg1")?;
        let values_source = first_match(r#"var N=(\[[^\]]+\])"#, html, "challenge strings")?;
        let mut strings = parse_js_string_array(&values_source)?;
        let target_hex = first_match(
            r#"\}\}\}\([A-Za-z_$][\w$]*,0x([0-9a-fA-F]+)\)"#,
            html,
            "challenge target",
        )?;
        let target = i64::from_str_radix(&target_hex, 16)
            .map_err(|_| LanzouError::Parse("Cannot parse Lanzou access challenge.".to_string()))?;

        let mut solved = false;
        for _ in 0..(strings.len() * 3) {
            if let Ok(score) = self.challenge_score(&strings) {
                if (score - target as f64).abs() < 1e-6 {
                    solved = true;
                    break;
                }
            }
            strings.rotate_left(1);
        }
        if !solved {
            return Err(LanzouError::Parse(
                "Cannot solve Lanzou access challenge.".to_string(),
            ));
        }

        let key = self.decode_challenge_string(
            strings
                .get(0x115 - 0xfb)
                .ok_or_else(|| LanzouError::Parse("Cannot solve Lanzou access challenge.".to_string()))?,
        )?;
        let order = [
            0xf, 0x23, 0x1d, 0x18, 0x21, 0x10, 0x1, 0x26, 0xa, 0x9, 0x13, 0x1f, 0x28, 0x1b,
            0x16, 0x17, 0x19, 0xd, 0x6, 0xb, 0x27, 0x12, 0x14, 0x8, 0xe, 0x15, 0x20, 0x1a,
            0x2, 0x1e, 0x7, 0x4, 0x11, 0x5, 0x3, 0x1c, 0x22, 0x25, 0xc, 0x24,
        ];
        let mut shuffled = vec![None; order.len()];
        for (source_index, character) in arg1.chars().enumerate() {
            for (target_index, position) in order.iter().enumerate() {
                if *position == source_index + 1 {
                    shuffled[target_index] = Some(character);
                }
            }
        }

        let text: String = shuffled.into_iter().flatten().collect();
        let text_bytes = text.as_bytes();
        let key_bytes = key.as_bytes();
        let limit = text_bytes.len().min(key_bytes.len());
        let mut cookie_value = String::new();
        for index in (0..limit.saturating_sub(1)).step_by(2) {
            let text_pair = std::str::from_utf8(&text_bytes[index..index + 2])
                .map_err(|_| LanzouError::Parse("Cannot solve Lanzou access challenge.".to_string()))?;
            let key_pair = std::str::from_utf8(&key_bytes[index..index + 2])
                .map_err(|_| LanzouError::Parse("Cannot solve Lanzou access challenge.".to_string()))?;
            let value = u8::from_str_radix(text_pair, 16)
                .and_then(|left| u8::from_str_radix(key_pair, 16).map(|right| left ^ right))
                .map_err(|_| LanzouError::Parse("Cannot solve Lanzou access challenge.".to_string()))?;
            cookie_value.push_str(&format!("{value:02x}"));
        }
        Ok(cookie_value)
    }

    fn challenge_score(&self, strings: &[String]) -> LanzouResult<f64> {
        Ok(
            -(self.challenge_int(strings, 0x117)? as f64) / 1.0
                * ((self.challenge_int(strings, 0x111)? as f64) / 2.0)
                + -(self.challenge_int(strings, 0xfb)? as f64) / 3.0
                    * ((self.challenge_int(strings, 0x10e)? as f64) / 4.0)
                + -(self.challenge_int(strings, 0x101)? as f64) / 5.0
                    * (-(self.challenge_int(strings, 0xfd)? as f64) / 6.0)
                + -(self.challenge_int(strings, 0x102)? as f64) / 7.0
                    * ((self.challenge_int(strings, 0x122)? as f64) / 8.0)
                + (self.challenge_int(strings, 0x112)? as f64) / 9.0
                + (self.challenge_int(strings, 0x11d)? as f64) / 10.0
                    * ((self.challenge_int(strings, 0x11c)? as f64) / 11.0)
                + (self.challenge_int(strings, 0x114)? as f64) / 12.0,
        )
    }

    fn challenge_int(&self, strings: &[String], code: usize) -> LanzouResult<i64> {
        let value = self.decode_challenge_string(
            strings
                .get(code - 0xfb)
                .ok_or_else(|| LanzouError::Parse("Cannot parse Lanzou access challenge.".to_string()))?,
        )?;
        let number = first_match(r#"\s*([+-]?\d+)"#, &value, "challenge value")?;
        number
            .parse::<i64>()
            .map_err(|_| LanzouError::Parse("Challenge value is not numeric.".to_string()))
    }

    fn decode_challenge_string(&self, value: &str) -> LanzouResult<String> {
        let source_alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/=";
        let target_alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=";
        let mut translated = String::new();
        for character in value.chars() {
            if let Some(index) = source_alphabet.find(character) {
                translated.push(
                    target_alphabet
                        .as_bytes()
                        .get(index)
                        .copied()
                        .map(char::from)
                        .unwrap_or(character),
                );
            }
        }
        while translated.len() % 4 != 0 {
            translated.push('=');
        }
        let decoded = STANDARD
            .decode(translated.as_bytes())
            .map_err(|_| LanzouError::Parse("Cannot decode Lanzou access challenge.".to_string()))?;
        Ok(String::from_utf8_lossy(&decoded).into_owned())
    }
}

pub fn request_headers(referer: Option<&str>, cookie: Option<&str>) -> LanzouResult<HeaderMap> {
    let mut headers = HeaderMap::new();
    headers.insert(USER_AGENT, HeaderValue::from_static(USER_AGENT_VALUE));
    headers.insert(ACCEPT, HeaderValue::from_static(ACCEPT_VALUE));
    headers.insert(ACCEPT_ENCODING, HeaderValue::from_static("gzip, deflate, br"));
    headers.insert(ACCEPT_LANGUAGE, HeaderValue::from_static("zh-CN,zh;q=0.9"));
    if let Some(referer) = referer {
        headers.insert(
            REFERER,
            HeaderValue::from_str(referer)
                .map_err(|_| LanzouError::Parse("Invalid request referer.".to_string()))?,
        );
    }
    if let Some(cookie) = cookie {
        headers.insert(
            COOKIE,
            HeaderValue::from_str(&format!("acw_sc__v2={cookie}"))
                .map_err(|_| LanzouError::Parse("Invalid Lanzou challenge cookie.".to_string()))?,
        );
    }
    Ok(headers)
}

fn first_match(pattern: &str, text: &str, field_name: &str) -> LanzouResult<String> {
    Regex::new(pattern)
        .expect("valid regex")
        .captures(text)
        .and_then(|capture| capture.get(1).map(|value| value.as_str().to_string()))
        .ok_or_else(|| {
            LanzouError::Parse(format!(
                "Cannot find {field_name}. Lanzou page markup may have changed."
            ))
        })
}

fn capture_optional(pattern: &str, text: &str) -> Option<String> {
    Regex::new(pattern)
        .expect("valid regex")
        .captures(text)
        .and_then(|capture| capture.get(1).map(|value| value.as_str().to_string()))
}

fn single_file_name(html: &str) -> Option<String> {
    let document = Html::parse_document(html);
    for selector in [
        "#filenajax",
        ".filethetext",
        ".n_file_info .n_file_name",
        ".n_box_3fn",
        ".b #sp_name",
        "title",
    ] {
        let selector = Selector::parse(selector).expect("valid selector");
        if let Some(name) = document
            .select(&selector)
            .find_map(|node| clean_file_name(&node.text().collect::<String>()))
        {
            return Some(name);
        }
    }
    None
}

fn clean_file_name(name: &str) -> Option<String> {
    let mut value = name
        .replace("_蓝奏云", "")
        .replace("- 蓝奏云", "")
        .replace("| 蓝奏云", "")
        .replace("蓝奏云", "")
        .trim()
        .trim_matches('-')
        .trim()
        .to_string();
    value = value.split_whitespace().collect::<Vec<_>>().join(" ");
    if value.is_empty() {
        None
    } else {
        Some(value)
    }
}

fn fallback_file_name(share_url: &str) -> String {
    Url::parse(share_url)
        .ok()
        .and_then(|url| {
            url.path_segments()
                .and_then(|mut segments| segments.next_back().map(str::to_string))
        })
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| "download.bin".to_string())
}

fn join_url(base: &str, path: &str) -> LanzouResult<String> {
    Ok(Url::parse(base)?.join(path)?.to_string())
}

fn is_success(payload: &Value) -> bool {
    value_text(payload.get("zt")).is_some_and(|value| value == "1")
}

fn value_text(value: Option<&Value>) -> Option<String> {
    match value? {
        Value::String(text) => Some(text.clone()),
        Value::Number(number) => Some(number.to_string()),
        Value::Bool(value) => Some(value.to_string()),
        Value::Null => Some(String::new()),
        other => Some(other.to_string()),
    }
}

fn parse_js_string_array(source: &str) -> LanzouResult<Vec<String>> {
    let mut values = Vec::new();
    let mut chars = source.chars().peekable();
    while let Some(character) = chars.next() {
        if character != '\'' && character != '"' {
            continue;
        }
        let quote = character;
        let mut value = String::new();
        while let Some(next) = chars.next() {
            if next == '\\' {
                if let Some(escaped) = chars.next() {
                    value.push(escaped);
                }
            } else if next == quote {
                break;
            } else {
                value.push(next);
            }
        }
        values.push(value);
    }

    if values.is_empty() {
        Err(LanzouError::Parse(
            "Cannot parse Lanzou access challenge.".to_string(),
        ))
    } else {
        Ok(values)
    }
}
