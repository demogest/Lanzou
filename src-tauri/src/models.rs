use std::path::PathBuf;

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DownloadTask {
    pub share_url: String,
    pub password: String,
    pub target_dir: PathBuf,
    pub process_count: usize,
}

impl DownloadTask {
    pub fn normalized(&self) -> Self {
        let share_url = self.share_url.trim();
        let share_url = if !share_url.is_empty()
            && !share_url.starts_with("http://")
            && !share_url.starts_with("https://")
        {
            format!("https://{share_url}")
        } else {
            share_url.to_string()
        };

        Self {
            share_url,
            password: self.password.trim().to_string(),
            target_dir: self.target_dir.clone(),
            process_count: self.process_count.max(1),
        }
    }
}

#[derive(Debug, Clone)]
pub struct FileEntry {
    pub page_path: String,
    pub name: String,
    pub download_url: String,
}

impl FileEntry {
    pub fn new(page_path: String, name: String) -> Self {
        Self {
            page_path,
            name,
            download_url: String::new(),
        }
    }

    pub fn with_download_url(&self, download_url: String) -> Self {
        Self {
            page_path: self.page_path.clone(),
            name: self.name.clone(),
            download_url,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DownloadedFile {
    pub name: String,
    pub path: String,
    pub size: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AppSettings {
    pub default_download_dir: String,
    pub process_count: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct HistoryRecord {
    pub time: String,
    pub finished_time: String,
    pub share_url: String,
    pub password: String,
    pub target_dir: String,
    pub process_count: usize,
    pub downloaded_count: usize,
    pub files: Vec<DownloadedFile>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct InitialState {
    pub default_download_dir: String,
    pub process_count: usize,
    pub max_processes: usize,
    pub history: Vec<HistoryRecord>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(tag = "type", rename_all = "camelCase")]
pub enum DownloadEvent {
    Message {
        message: String,
    },
    TotalProgress {
        progress: u8,
    },
    ProcessProgress {
        slot: usize,
        #[serde(rename = "fileName")]
        file_name: String,
        progress: u8,
        status: String,
    },
}
