#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod client;
mod downloader;
mod errors;
mod models;
mod storage;

use std::path::PathBuf;
use std::sync::Arc;

use downloader::LanzouDownloadService;
use models::{AppSettings, DownloadEvent, DownloadTask, DownloadedFile, HistoryRecord, InitialState};
use tauri::{AppHandle, Emitter};

#[tauri::command]
fn initial_state(app: AppHandle) -> Result<InitialState, String> {
    storage::initial_state(&app).map_err(|error| error.to_string())
}

#[tauri::command]
fn save_settings(app: AppHandle, settings: AppSettings) -> Result<AppSettings, String> {
    storage::save_settings(&app, settings).map_err(|error| error.to_string())
}

#[tauri::command]
fn load_history(app: AppHandle) -> Result<Vec<HistoryRecord>, String> {
    storage::load_history(&app).map_err(|error| error.to_string())
}

#[tauri::command]
fn delete_history(app: AppHandle, index: usize) -> Result<Vec<HistoryRecord>, String> {
    storage::delete_history(&app, index).map_err(|error| error.to_string())
}

#[tauri::command]
fn clear_history(app: AppHandle) -> Result<Vec<HistoryRecord>, String> {
    storage::clear_history(&app).map_err(|error| error.to_string())
}

#[tauri::command]
fn choose_directory(current_dir: Option<String>) -> Result<Option<String>, String> {
    let mut dialog = rfd::FileDialog::new();
    if let Some(current_dir) = current_dir.filter(|value| !value.trim().is_empty()) {
        dialog = dialog.set_directory(current_dir);
    }
    Ok(dialog.pick_folder().map(|path| path.to_string_lossy().into_owned()))
}

#[tauri::command]
fn open_folder(path: String) -> Result<(), String> {
    let path = PathBuf::from(path);
    open::that_detached(path).map_err(|error| error.to_string())
}

#[tauri::command]
async fn start_download(app: AppHandle, task: DownloadTask) -> Result<Vec<DownloadedFile>, String> {
    let download_app = app.clone();
    tauri::async_runtime::spawn_blocking(move || {
        let emit_app = download_app.clone();
        let emitter = Arc::new(move |event: DownloadEvent| {
            let _ = emit_app.emit("download-event", event);
        });

        let service = LanzouDownloadService::default();
        let files = service.download(task.clone(), emitter)?;
        storage::append_history(&download_app, &task.normalized(), &files)?;
        Ok::<Vec<DownloadedFile>, errors::LanzouError>(files)
    })
    .await
    .map_err(|error| error.to_string())?
    .map_err(|error| error.to_string())
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            initial_state,
            save_settings,
            load_history,
            delete_history,
            clear_history,
            choose_directory,
            open_folder,
            start_download
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
