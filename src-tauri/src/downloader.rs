use std::fs::{self, File};
use std::io::{Read, Write};
use std::path::Path;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;

use reqwest::blocking::Client;

use crate::client::{request_headers, LanzouClient, LanzouConfig};
use crate::errors::{LanzouError, LanzouResult};
use crate::models::{DownloadEvent, DownloadTask, DownloadedFile, FileEntry};

type DownloadEmitter = Arc<dyn Fn(DownloadEvent) + Send + Sync + 'static>;
pub type CancellationToken = Arc<AtomicBool>;

pub struct LanzouDownloadService {
    config: LanzouConfig,
    client: LanzouClient,
}

impl Default for LanzouDownloadService {
    fn default() -> Self {
        let config = LanzouConfig::default();
        let client = LanzouClient::new(config.clone()).expect("HTTP client should initialize");
        Self { config, client }
    }
}

impl LanzouDownloadService {
    pub fn download(
        &self,
        task: DownloadTask,
        emit: DownloadEmitter,
        cancel: CancellationToken,
    ) -> LanzouResult<Vec<DownloadedFile>> {
        let task = task.normalized();
        if task.share_url.is_empty() {
            return Err(LanzouError::Download("Share link is required.".to_string()));
        }

        ensure_not_cancelled(&cancel)?;
        emit_total(&emit, 0);
        emit_message(&emit, "Getting file list...");
        let entries = self.client.list_files(&task)?;
        ensure_not_cancelled(&cancel)?;
        if entries.is_empty() {
            return Err(LanzouError::Download(
                "No downloadable files found in this share link.".to_string(),
            ));
        }

        emit_message(&emit, &format!("Found {} files.", entries.len()));
        emit_message(&emit, "Resolving download URLs...");
        let resolved_entries = self.resolve_entries(&task, &entries, emit.clone(), &cancel)?;
        if resolved_entries.is_empty() {
            return Err(LanzouError::Download(
                "No file URLs were resolved successfully.".to_string(),
            ));
        }

        emit_message(&emit, "--------------------------------------------------");
        emit_message(&emit, "Start downloading...");
        let downloaded = if task.process_count <= 1 {
            self.download_entries_single(&task, &resolved_entries, emit.clone(), cancel.clone())?
        } else {
            self.download_entries_parallel(&task, resolved_entries, emit.clone(), cancel.clone())?
        };

        if downloaded.is_empty() {
            ensure_not_cancelled(&cancel)?;
            return Err(LanzouError::Download("All downloads failed.".to_string()));
        }
        ensure_not_cancelled(&cancel)?;
        emit_message(&emit, "Download finished.");
        emit_total(&emit, 100);
        Ok(downloaded)
    }

    fn resolve_entries(
        &self,
        task: &DownloadTask,
        entries: &[FileEntry],
        emit: DownloadEmitter,
        cancel: &CancellationToken,
    ) -> LanzouResult<Vec<FileEntry>> {
        let mut resolved = Vec::new();
        for entry in entries {
            ensure_not_cancelled(cancel)?;
            match self.client.resolve_file(task, entry) {
                Ok(resolved_entry) => {
                    ensure_not_cancelled(cancel)?;
                    emit_message(&emit, &format!("Get {} URL success.", resolved_entry.name));
                    resolved.push(resolved_entry);
                }
                Err(error) => {
                    if error.is_cancelled() {
                        return Err(error);
                    }
                    emit_message(&emit, &format!("Get {} URL failed: {}", entry.name, error));
                }
            }
        }
        Ok(resolved)
    }

    fn download_entries_single(
        &self,
        task: &DownloadTask,
        entries: &[FileEntry],
        emit: DownloadEmitter,
        cancel: CancellationToken,
    ) -> LanzouResult<Vec<DownloadedFile>> {
        let mut downloaded = Vec::new();
        let total = entries.len();
        let http = download_client(&self.config)?;
        for (index, entry) in entries.iter().enumerate() {
            ensure_not_cancelled(&cancel)?;
            emit_process(&emit, 1, &entry.name, 0, "下载中");
            emit_message(
                &emit,
                &format!("Downloading {} ({}/{})...", entry.name, index + 1, total),
            );
            match download_one(
                &http,
                &self.config,
                task,
                entry,
                1,
                emit.clone(),
                &cancel,
            ) {
                Ok((file, skipped)) => {
                    if skipped {
                        emit_message(&emit, &format!("{} already exists.", entry.name));
                        emit_process(&emit, 1, &entry.name, 100, "已跳过");
                    } else {
                        emit_message(&emit, &format!("{} downloaded.", entry.name));
                        emit_process(&emit, 1, &entry.name, 100, "已完成");
                    }
                    downloaded.push(file);
                }
                Err(error) => {
                    if error.is_cancelled() {
                        return Err(error);
                    }
                    emit_message(&emit, &format!("Download {} failed: {}", entry.name, error));
                    emit_process(&emit, 1, &entry.name, 100, "失败");
                }
            }
            emit_total(&emit, percent(index + 1, total));
        }
        Ok(downloaded)
    }

    fn download_entries_parallel(
        &self,
        task: &DownloadTask,
        entries: Vec<FileEntry>,
        emit: DownloadEmitter,
        cancel: CancellationToken,
    ) -> LanzouResult<Vec<DownloadedFile>> {
        let total = entries.len();
        let process_count = task.process_count.min(total).max(1);
        fs::create_dir_all(&task.target_dir)?;
        emit_message(&emit, &format!("Threaded mode enabled: {} workers.", process_count));
        emit_message(&emit, &format!("Preparing {} download jobs...", total));
        for slot in 1..=process_count {
            emit_process(&emit, slot, "", 0, "等待任务");
        }

        let entries = Arc::new(entries);
        let next_index = Arc::new(AtomicUsize::new(0));
        let finished = Arc::new(AtomicUsize::new(0));
        let downloaded = Arc::new(Mutex::new(Vec::new()));
        let mut handles = Vec::new();

        for slot in 1..=process_count {
            let task = task.clone();
            let config = self.config.clone();
            let entries = Arc::clone(&entries);
            let next_index = Arc::clone(&next_index);
            let finished = Arc::clone(&finished);
            let downloaded = Arc::clone(&downloaded);
            let emit = emit.clone();
            let cancel = cancel.clone();

            handles.push(thread::spawn(move || -> LanzouResult<()> {
                let http = download_client(&config)?;
                loop {
                    if is_cancelled(&cancel) {
                        emit_process(&emit, slot, "", 0, "已取消");
                        return Err(LanzouError::Cancelled);
                    }
                    let index = next_index.fetch_add(1, Ordering::SeqCst);
                    if index >= entries.len() {
                        emit_process(&emit, slot, "", 0, "等待任务");
                        break;
                    }

                    let entry = &entries[index];
                    emit_process(&emit, slot, &entry.name, 0, "下载中");
                    match download_one(&http, &config, &task, entry, slot, emit.clone(), &cancel) {
                        Ok((file, skipped)) => {
                            if skipped {
                                emit_message(&emit, &format!("{} already exists.", entry.name));
                                emit_process(&emit, slot, &entry.name, 100, "已跳过");
                            } else {
                                emit_message(&emit, &format!("{} downloaded.", entry.name));
                                emit_process(&emit, slot, &entry.name, 100, "已完成");
                            }
                            downloaded
                                .lock()
                                .map_err(|_| LanzouError::Download("Cannot update download results.".to_string()))?
                                .push(file);
                        }
                        Err(error) => {
                            if error.is_cancelled() {
                                emit_process(&emit, slot, &entry.name, 100, "已取消");
                                return Err(error);
                            }
                            emit_message(&emit, &format!("Download {} failed: {}", entry.name, error));
                            emit_process(&emit, slot, &entry.name, 100, "失败");
                        }
                    }
                    let done = finished.fetch_add(1, Ordering::SeqCst) + 1;
                    emit_total(&emit, percent(done, total));
                }
                Ok(())
            }));
        }

        let mut first_error = None;
        for handle in handles {
            match handle.join() {
                Ok(Ok(())) => {}
                Ok(Err(error)) => {
                    if first_error.is_none() {
                        first_error = Some(error);
                    }
                }
                Err(_) => {
                    if first_error.is_none() {
                        first_error = Some(LanzouError::Download(
                            "A download worker panicked.".to_string(),
                        ));
                    }
                }
            }
        }

        if let Some(error) = first_error {
            return Err(error);
        }

        let files = Arc::try_unwrap(downloaded)
            .map_err(|_| LanzouError::Download("Cannot collect download results.".to_string()))?
            .into_inner()
            .map_err(|_| LanzouError::Download("Cannot collect download results.".to_string()))?;
        Ok(files)
    }
}

fn download_one(
    http: &Client,
    config: &LanzouConfig,
    task: &DownloadTask,
    entry: &FileEntry,
    slot: usize,
    emit: DownloadEmitter,
    cancel: &CancellationToken,
) -> LanzouResult<(DownloadedFile, bool)> {
    ensure_not_cancelled(cancel)?;
    if !entry.download_url.starts_with("http://") && !entry.download_url.starts_with("https://") {
        return Err(LanzouError::Download("Resolved URL is invalid.".to_string()));
    }

    fs::create_dir_all(&task.target_dir)?;
    let target_path = task.target_dir.join(safe_filename(&entry.name));
    if target_path.exists() {
        ensure_not_cancelled(cancel)?;
        return Ok((downloaded_file(&target_path), true));
    }

    let partial_path = target_path.with_file_name(format!(
        "{}.part",
        target_path
            .file_name()
            .and_then(|value| value.to_str())
            .unwrap_or("download.bin")
    ));

    let result = (|| -> LanzouResult<()> {
        ensure_not_cancelled(cancel)?;
        let mut response = http
            .get(&entry.download_url)
            .headers(request_headers(Some(&task.share_url), None)?)
            .send()?
            .error_for_status()?;
        ensure_not_cancelled(cancel)?;
        let total_bytes = response.content_length().unwrap_or(0);
        let mut downloaded_bytes = 0_u64;
        let mut last_progress = 0_u8;
        let mut file = File::create(&partial_path)?;
        let mut buffer = vec![0_u8; config.chunk_size];

        loop {
            ensure_not_cancelled(cancel)?;
            let read = response
                .read(&mut buffer)
                .map_err(|error| LanzouError::Download(error.to_string()))?;
            if read == 0 {
                break;
            }
            ensure_not_cancelled(cancel)?;
            file.write_all(&buffer[..read])
                .map_err(|error| LanzouError::Download(error.to_string()))?;
            if total_bytes > 0 {
                downloaded_bytes += read as u64;
                let progress = ((downloaded_bytes * 100) / total_bytes).min(99) as u8;
                if progress > last_progress {
                    last_progress = progress;
                    emit_process(&emit, slot, &entry.name, progress, "下载中");
                }
            }
        }
        ensure_not_cancelled(cancel)?;
        file.flush()
            .map_err(|error| LanzouError::Download(error.to_string()))?;
        fs::rename(&partial_path, &target_path)
            .map_err(|error| LanzouError::Download(error.to_string()))?;
        Ok(())
    })();

    if let Err(error) = result {
        let _ = fs::remove_file(&partial_path);
        return Err(error);
    }

    Ok((downloaded_file(&target_path), false))
}

fn download_client(config: &LanzouConfig) -> LanzouResult<Client> {
    Ok(Client::builder()
        .connect_timeout(config.connect_timeout)
        .timeout(config.request_timeout)
        .build()?)
}

fn is_cancelled(cancel: &CancellationToken) -> bool {
    cancel.load(Ordering::SeqCst)
}

fn ensure_not_cancelled(cancel: &CancellationToken) -> LanzouResult<()> {
    if is_cancelled(cancel) {
        Err(LanzouError::Cancelled)
    } else {
        Ok(())
    }
}

fn emit_message(emit: &DownloadEmitter, message: &str) {
    emit(DownloadEvent::Message {
        message: message.to_string(),
    });
}

fn emit_total(emit: &DownloadEmitter, progress: u8) {
    emit(DownloadEvent::TotalProgress { progress });
}

fn emit_process(emit: &DownloadEmitter, slot: usize, file_name: &str, progress: u8, status: &str) {
    emit(DownloadEvent::ProcessProgress {
        slot,
        file_name: file_name.to_string(),
        progress: progress.min(100),
        status: status.to_string(),
    });
}

fn percent(done: usize, total: usize) -> u8 {
    if total == 0 {
        0
    } else {
        ((done * 100) / total).min(100) as u8
    }
}

fn safe_filename(filename: &str) -> String {
    let invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*'];
    let cleaned = filename
        .chars()
        .map(|character| {
            if invalid_chars.contains(&character) || character.is_control() {
                '_'
            } else {
                character
            }
        })
        .collect::<String>()
        .trim()
        .trim_end_matches(|character| character == '.' || character == ' ')
        .to_string();

    if cleaned.is_empty() {
        "download.bin".to_string()
    } else {
        cleaned
    }
}

fn downloaded_file(path: &Path) -> DownloadedFile {
    DownloadedFile {
        name: path
            .file_name()
            .and_then(|value| value.to_str())
            .unwrap_or("download.bin")
            .to_string(),
        path: path.to_string_lossy().into_owned(),
        size: file_size_label(path),
    }
}

fn file_size_label(path: &Path) -> String {
    match fs::metadata(path).map(|metadata| metadata.len()) {
        Ok(bytes) if bytes >= 1024 * 1024 * 1024 => format!("{:.2} GB", bytes as f64 / 1024_f64.powi(3)),
        Ok(bytes) if bytes >= 1024 * 1024 => format!("{:.2} MB", bytes as f64 / 1024_f64.powi(2)),
        Ok(bytes) if bytes >= 1024 => format!("{:.1} KB", bytes as f64 / 1024_f64),
        Ok(bytes) => format!("{bytes} B"),
        Err(_) => "未知".to_string(),
    }
}
