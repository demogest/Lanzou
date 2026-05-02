#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod client;
mod downloader;
mod errors;
mod models;
mod storage;

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use downloader::LanzouDownloadService;
use models::{AppSettings, DownloadEvent, DownloadTask, DownloadedFile, HistoryRecord, InitialState};
use tauri::{AppHandle, Emitter, State};

struct DownloadRuntime {
    running: AtomicBool,
    cancel: Arc<AtomicBool>,
}

impl Default for DownloadRuntime {
    fn default() -> Self {
        Self {
            running: AtomicBool::new(false),
            cancel: Arc::new(AtomicBool::new(false)),
        }
    }
}

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
fn cancel_download(app: AppHandle, runtime: State<DownloadRuntime>) -> Result<bool, String> {
    if runtime.running.load(Ordering::SeqCst) {
        runtime.cancel.store(true, Ordering::SeqCst);
        let _ = app.emit(
            "download-event",
            DownloadEvent::Message {
                message: "Cancellation requested.".to_string(),
            },
        );
        Ok(true)
    } else {
        Ok(false)
    }
}

#[tauri::command]
async fn start_download(
    app: AppHandle,
    runtime: State<'_, DownloadRuntime>,
    task: DownloadTask,
) -> Result<Vec<DownloadedFile>, String> {
    runtime
        .running
        .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
        .map_err(|_| "A download task is already running.".to_string())?;
    runtime.cancel.store(false, Ordering::SeqCst);
    let cancel = runtime.cancel.clone();
    let download_app = app.clone();
    let result = tauri::async_runtime::spawn_blocking(move || {
        let emit_app = download_app.clone();
        let emitter = Arc::new(move |event: DownloadEvent| {
            let _ = emit_app.emit("download-event", event);
        });

        let service = LanzouDownloadService::default();
        let files = service.download(task.clone(), emitter, cancel)?;
        storage::append_history(&download_app, &task.normalized(), &files)?;
        Ok::<Vec<DownloadedFile>, errors::LanzouError>(files)
    })
    .await
    .map_err(|error| error.to_string())?
    .map_err(|error| error.to_string());
    runtime.running.store(false, Ordering::SeqCst);
    runtime.cancel.store(false, Ordering::SeqCst);
    result
}

fn main() {
    tauri::Builder::default()
        .manage(DownloadRuntime::default())
        .invoke_handler(tauri::generate_handler![
            initial_state,
            save_settings,
            load_history,
            delete_history,
            clear_history,
            choose_directory,
            open_folder,
            cancel_download,
            start_download
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
