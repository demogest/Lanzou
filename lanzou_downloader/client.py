import ast
import base64
import json
import re
from urllib.parse import unquote, urljoin, urlparse

import bs4 as bs
import requests

from .config import DEFAULT_HEADERS, LanzouConfig
from .exceptions import NetworkError, ParseError, PasswordError, UnsupportedLinkError
from .models import FileEntry


class LanzouClient:
    def __init__(self, config=None, session=None):
        self.config = config or LanzouConfig()
        self.session = session or requests.Session()

    def headers(self, referer=None):
        headers = DEFAULT_HEADERS.copy()
        if referer:
            headers["Referer"] = referer
        return headers

    def list_files(self, task):
        task = task.normalized()
        response = self._request("GET", task.share_url, referer=task.share_url)
        html = response.text
        self._raise_if_unsupported_page(html)

        tokens = re.findall(r"var [\w]{6} = '([\w]+?)';", html)
        if len(tokens) < 2:
            raise ParseError("Cannot find folder token parameters in the share page.")

        data = {
            "lx": self._first_match(r"'lx':(\d+?),", html, "lx"),
            "fid": self._first_match(r"'fid':(\d+?),", html, "fid"),
            "uid": self._first_match(r"'uid':'(\d+?)',", html, "uid"),
            "pg": self._first_match(r"pgs\s*=\s*(\d+?);", html, "pgs"),
            "t": tokens[0],
            "k": tokens[1],
        }
        if self.page_requires_password(html):
            if not task.password:
                raise PasswordError("This share link requires a password.")
            data["pwd"] = task.password

        payload = self._post_json(
            self._endpoint(task.share_url, "filemoreajax.php"),
            data=data,
            referer=task.share_url,
        )
        if not self._is_success(payload):
            message = payload.get("info") or payload.get("inf") or "Failed to get file list."
            raise PasswordError(message)

        items = payload.get("text") or []
        if not isinstance(items, list):
            raise ParseError("Unexpected file list response from Lanzou.")

        files = []
        for item in items:
            page_path = str(item.get("id", "")).strip()
            name = str(item.get("name_all", "")).strip()
            if page_path and name:
                files.append(FileEntry(page_path=page_path, name=name))
        return files

    def resolve_file(self, task, entry):
        task = task.normalized()
        page_url = self._entry_page_url(task.share_url, entry)
        response = self._request("GET", page_url, referer=task.share_url)

        if self.page_requires_password(response.text):
            return entry.with_download_url(self._unlock_file(task, page_url))

        iframe_url = self._iframe_url(response.text, page_url, entry.name)
        iframe_response = self._request("GET", iframe_url, referer=page_url)
        iframe_html = iframe_response.text

        data = self._download_request_data(iframe_html)
        payload = self._post_json(
            self._ajax_endpoint(iframe_html, iframe_url),
            data=data,
            referer=iframe_url,
        )
        if not self._is_success(payload):
            message = payload.get("inf") or "Failed to resolve download URL."
            raise ParseError(message)

        download_url = self._download_url_from_payload(payload)
        return entry.with_download_url(download_url)

    def page_requires_password(self, html):
        soup = bs.BeautifulSoup(html, "html.parser")
        return soup.find("input", {"id": "pwd", "name": "pwd"}) is not None

    def _unlock_file(self, task, page_url):
        if not task.password:
            raise PasswordError("This file requires a password.")

        response = self._request("GET", page_url, referer=task.share_url)
        data = {
            "action": self._first_match(r"action=([\S]*?)&", response.text, "password action"),
            "sign": self._first_match(r"sign=([\S]{15,})&", response.text, "password sign"),
            "p": task.password,
        }
        payload = self._post_json(
            self._endpoint(page_url, "ajaxm.php"),
            data=data,
            referer=page_url,
        )
        if not self._is_success(payload):
            message = payload.get("inf") or "Password rejected."
            raise PasswordError(message)
        return self._download_url_from_payload(payload)

    def _post_json(self, url, data, referer=None):
        response = self._request("POST", url, data=data, referer=referer)
        try:
            return json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise ParseError("Lanzou returned an invalid JSON response.") from exc

    def _request(self, method, url, referer=None, _challenge_retry=True, **kwargs):
        try:
            response = self.session.request(
                method,
                url,
                headers=self.headers(referer),
                timeout=self.config.request_timeout,
                **kwargs
            )
            response.raise_for_status()
            if _challenge_retry and self._looks_like_cookie_challenge(response.text):
                cookie_value = self._solve_cookie_challenge(response.text)
                parsed = urlparse(response.url)
                self.session.cookies.set(
                    "acw_sc__v2",
                    cookie_value,
                    domain=parsed.hostname,
                    path="/",
                )
                return self._request(
                    method,
                    url,
                    referer=referer,
                    _challenge_retry=False,
                    **kwargs
                )
            return response
        except requests.RequestException as exc:
            raise NetworkError("Request failed: %s" % url) from exc

    def _entry_page_url(self, share_url, entry):
        if entry.page_path.startswith("http"):
            return entry.page_path
        return urljoin(self._origin(share_url) + "/", entry.page_path)

    def _iframe_url(self, html, page_url, file_name):
        soup = bs.BeautifulSoup(html, "html.parser")
        iframe = soup.find("iframe")
        if not iframe or not iframe.get("src"):
            raise ParseError("Cannot find download iframe for %s." % file_name)
        return urljoin(page_url, iframe["src"])

    def _download_request_data(self, iframe_html):
        ajaxdata = self._first_match(r"ajaxdata\s*=\s*'([^']*?)';", iframe_html, "ajaxdata")
        wp_sign = re.search(r"wp_sign\s*=\s*'([^']*?)';", iframe_html)
        if wp_sign:
            return {
                "action": "downprocess",
                "websignkey": ajaxdata,
                "signs": ajaxdata,
                "sign": wp_sign.group(1),
                "websign": "",
                "kd": 1,
                "ves": 1,
            }

        return {
            "action": self._first_match(r"'action'\s*:\s*'(\w*?)',", iframe_html, "action"),
            "sign": self._first_match(r"'sign'\s*:\s*'([^']*?)',", iframe_html, "sign"),
            "ves": 1,
            "signs": ajaxdata,
            "websignkey": self._first_match(r"wsk_sign\s*=\s*'([^']*?)';", iframe_html, "wsk_sign"),
            "websign": self._first_match(r"ws_sign\s*=\s*'([^']*?)';", iframe_html, "ws_sign"),
        }

    def _ajax_endpoint(self, iframe_html, iframe_url):
        ajax_paths = re.findall(r"url\s*:\s*['\"](/?ajaxm\.php\?file=\d+)", iframe_html)
        if ajax_paths:
            return urljoin(self._origin(iframe_url) + "/", ajax_paths[-1].lstrip("/"))

        ajax_path = re.search(r"(/?ajaxm\.php\?file=\d+)", iframe_html)
        if ajax_path:
            return urljoin(self._origin(iframe_url) + "/", ajax_path.group(1).lstrip("/"))
        return self._endpoint(iframe_url, "ajaxm.php")

    def _download_url_from_payload(self, payload):
        domain = str(payload.get("dom", "")).rstrip("/")
        path = str(payload.get("url", "")).lstrip("/")
        if not domain or not path:
            raise ParseError("Download URL response is missing required fields.")
        return domain + "/file/" + path

    def _raise_if_unsupported_page(self, html):
        if re.search(r"'fid':\d+?,", html):
            return
        soup = bs.BeautifulSoup(html, "html.parser")
        if soup.find("iframe"):
            raise UnsupportedLinkError("Single-file share links are not supported yet.")
        raise ParseError("Cannot find folder metadata in the share page.")

    def _endpoint(self, url, endpoint):
        return urljoin(self._origin(url) + "/", endpoint)

    def _origin(self, url):
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return "%s://%s" % (parsed.scheme, parsed.netloc)
        return self.config.base_url.rstrip("/")

    def _is_success(self, payload):
        return str(payload.get("zt")) == "1"

    def _first_match(self, pattern, text, field_name):
        match = re.search(pattern, text)
        if not match:
            raise ParseError("Cannot find %s. Lanzou page markup may have changed." % field_name)
        return match.group(1)

    def _looks_like_cookie_challenge(self, html):
        return (
            "acw_sc__v2" in html
            and "var arg1=" in html
            and "function a0i()" in html
        )

    def _solve_cookie_challenge(self, html):
        try:
            arg1 = self._first_match(r"var arg1='([^']+)'", html, "challenge arg1")
            values = ast.literal_eval(
                self._first_match(r"var N=(\[[^\]]+\])", html, "challenge strings")
            )
            target = int(
                self._first_match(r"\}\}\}\([A-Za-z_$][\w$]*,0x([0-9a-fA-F]+)\)", html, "challenge target"),
                16,
            )
        except (ValueError, SyntaxError) as exc:
            raise ParseError("Cannot parse Lanzou access challenge.") from exc

        strings = list(values)
        for _index in range(len(strings) * 3):
            try:
                if self._challenge_score(strings) == target:
                    break
            except (ValueError, IndexError):
                pass
            strings.append(strings.pop(0))
        else:
            raise ParseError("Cannot solve Lanzou access challenge.")

        key = self._decode_challenge_string(strings[0x115 - 0xfb])
        order = [
            0xf, 0x23, 0x1d, 0x18, 0x21, 0x10, 0x1, 0x26, 0xa, 0x9,
            0x13, 0x1f, 0x28, 0x1b, 0x16, 0x17, 0x19, 0xd, 0x6, 0xb,
            0x27, 0x12, 0x14, 0x8, 0xe, 0x15, 0x20, 0x1a, 0x2, 0x1e,
            0x7, 0x4, 0x11, 0x5, 0x3, 0x1c, 0x22, 0x25, 0xc, 0x24,
        ]
        shuffled = [""] * len(order)
        for source_index, char in enumerate(arg1):
            for target_index, position in enumerate(order):
                if position == source_index + 1:
                    shuffled[target_index] = char

        text = "".join(shuffled)
        cookie_value = ""
        for index in range(0, min(len(text), len(key)), 2):
            token = format(
                int(text[index:index + 2], 16) ^ int(key[index:index + 2], 16),
                "x",
            )
            cookie_value += token.zfill(2)
        return cookie_value

    def _challenge_score(self, strings):
        return (
            -self._challenge_int(strings, 0x117) / 1 * (self._challenge_int(strings, 0x111) / 2)
            + -self._challenge_int(strings, 0xfb) / 3 * (self._challenge_int(strings, 0x10e) / 4)
            + -self._challenge_int(strings, 0x101) / 5 * (-self._challenge_int(strings, 0xfd) / 6)
            + -self._challenge_int(strings, 0x102) / 7 * (self._challenge_int(strings, 0x122) / 8)
            + self._challenge_int(strings, 0x112) / 9
            + self._challenge_int(strings, 0x11d) / 10 * (self._challenge_int(strings, 0x11c) / 11)
            + self._challenge_int(strings, 0x114) / 12
        )

    def _challenge_int(self, strings, code):
        value = self._decode_challenge_string(strings[code - 0xfb])
        match = re.match(r"\s*([+-]?\d+)", value)
        if not match:
            raise ValueError("Challenge value is not numeric.")
        return int(match.group(1))

    def _decode_challenge_string(self, value):
        source_alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/="
        target_alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
        translated = "".join(
            target_alphabet[source_alphabet.index(char)]
            for char in value
            if char in source_alphabet
        )
        translated += "=" * ((4 - len(translated) % 4) % 4)
        decoded = base64.b64decode(translated)
        return unquote("".join("%%%02x" % byte for byte in decoded))
