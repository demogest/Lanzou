use std::env;
use std::fs;
use std::path::PathBuf;

use tauri::{AppHandle, Manager};

use crate::errors::{LanzouError, LanzouResult};
use crate::models::{AppSettings, DownloadTask, DownloadedFile, HistoryRecord, InitialState};

const SETTINGS_FILE: &str = "lanzou_settings.json";
const HISTORY_FILE: &str = "lanzou_history.json";
const PORTABLE_DATA_DIR: &str = "lanzou_data";

pub fn initial_state(app: &AppHandle) -> LanzouResult<InitialState> {
    let settings = load_settings(app)?;
    Ok(InitialState {
        default_download_dir: settings.default_download_dir,
        process_count: settings.process_count,
        max_processes: max_processes(),
        history: load_history(app)?,
    })
}

pub fn load_settings(app: &AppHandle) -> LanzouResult<AppSettings> {
    let path = settings_path(app)?;
    let fallback = fallback_download_dir();
    let mut settings = fs::read_to_string(path)
        .ok()
        .and_then(|text| serde_json::from_str::<AppSettings>(&text).ok())
        .unwrap_or(AppSettings {
            default_download_dir: fallback.to_string_lossy().into_owned(),
            process_count: 1,
        });

    if settings.default_download_dir.trim().is_empty() {
        settings.default_download_dir = fallback.to_string_lossy().into_owned();
    }
    settings.process_count = settings.process_count.clamp(1, max_processes());
    Ok(settings)
}

pub fn save_settings(app: &AppHandle, settings: AppSettings) -> LanzouResult<AppSettings> {
    let fallback = fallback_download_dir();
    let normalized = AppSettings {
        default_download_dir: if settings.default_download_dir.trim().is_empty() {
            fallback.to_string_lossy().into_owned()
        } else {
            settings.default_download_dir.trim().to_string()
        },
        process_count: settings.process_count.clamp(1, max_processes()),
    };
    let path = settings_path(app)?;
    fs::write(path, serde_json::to_string_pretty(&normalized)?)?;
    Ok(normalized)
}

pub fn load_history(app: &AppHandle) -> LanzouResult<Vec<HistoryRecord>> {
    let path = history_path(app)?;
    Ok(fs::read_to_string(path)
        .ok()
        .and_then(|text| serde_json::from_str::<Vec<HistoryRecord>>(&text).ok())
        .unwrap_or_default())
}

pub fn delete_history(app: &AppHandle, index: usize) -> LanzouResult<Vec<HistoryRecord>> {
    let mut history = load_history(app)?;
    if index < history.len() {
        history.remove(index);
        save_history(app, &history)?;
    }
    Ok(history)
}

pub fn clear_history(app: &AppHandle) -> LanzouResult<Vec<HistoryRecord>> {
    save_history(app, &[])?;
    Ok(Vec::new())
}

pub fn append_history(
    app: &AppHandle,
    task: &DownloadTask,
    files: &[DownloadedFile],
) -> LanzouResult<()> {
    let now = now_label();
    let mut history = load_history(app)?;
    history.insert(
        0,
        HistoryRecord {
            time: now.clone(),
            finished_time: now,
            share_url: task.share_url.clone(),
            password: task.password.clone(),
            target_dir: task.target_dir.to_string_lossy().into_owned(),
            process_count: task.process_count,
            downloaded_count: files.len(),
            files: files.to_vec(),
        },
    );
    history.truncate(200);
    save_history(app, &history)
}

fn save_history(app: &AppHandle, history: &[HistoryRecord]) -> LanzouResult<()> {
    fs::write(history_path(app)?, serde_json::to_string_pretty(history)?)?;
    Ok(())
}

fn settings_path(app: &AppHandle) -> LanzouResult<PathBuf> {
    Ok(storage_dir(app)?.join(SETTINGS_FILE))
}

fn history_path(app: &AppHandle) -> LanzouResult<PathBuf> {
    Ok(storage_dir(app)?.join(HISTORY_FILE))
}

fn storage_dir(app: &AppHandle) -> LanzouResult<PathBuf> {
    if let Some(dir) = portable_storage_dir() {
        fs::create_dir_all(&dir)?;
        return Ok(dir);
    }

    let dir = app
        .path()
        .app_data_dir()
        .map_err(|error| LanzouError::Storage(error.to_string()))?;
    fs::create_dir_all(&dir)?;
    Ok(dir)
}

fn fallback_download_dir() -> PathBuf {
    if let Some(dir) = portable_root_dir() {
        return dir.join("Downloads");
    }

    if let Ok(userprofile) = env::var("USERPROFILE") {
        return PathBuf::from(userprofile).join("Downloads").join("Lanzou");
    }
    if let Ok(home) = env::var("HOME") {
        return PathBuf::from(home).join("Downloads").join("Lanzou");
    }
    env::current_dir()
        .unwrap_or_else(|_| PathBuf::from("."))
        .join("Download")
}

fn portable_storage_dir() -> Option<PathBuf> {
    portable_root_dir().map(|dir| dir.join(PORTABLE_DATA_DIR))
}

fn portable_root_dir() -> Option<PathBuf> {
    let exe = env::current_exe().ok()?;
    let file_stem = exe.file_stem()?.to_string_lossy();

    if !is_portable_exe_name(&file_stem) {
        return None;
    }

    exe.parent().map(PathBuf::from)
}

fn is_portable_exe_name(name: &str) -> bool {
    name.to_ascii_lowercase().contains("portable")
}

fn max_processes() -> usize {
    std::thread::available_parallelism()
        .map(|value| value.get())
        .unwrap_or(1)
        .max(1)
}

fn now_label() -> String {
    chrono::Local::now().format("%Y-%m-%d %H:%M:%S").to_string()
}

#[cfg(test)]
mod tests {
    use super::is_portable_exe_name;

    #[test]
    fn detects_portable_executable_names() {
        assert!(is_portable_exe_name(
            "Lanzou-Downloader-2.0.0-windows-x64-portable"
        ));
        assert!(is_portable_exe_name("PORTABLE-Lanzou"));
        assert!(!is_portable_exe_name("lanzou-tauri"));
    }
}
