# Lanzou Downloader

Rust + Tauri desktop app for batch downloading files from a Lanzou share folder.

一个使用 Rust 与 Tauri 构建的蓝奏云批量下载工具。

## Features

- Resolve files from a Lanzou folder share link.
- Supports optional extraction password.
- Choose the target download directory.
- Configure concurrent download workers.
- Show total progress, per-worker progress, and event logs.
- Keep local download history.

## Requirements

- Rust toolchain with Cargo
- Node.js and npm

## Development

Install dependencies:

```shell
npm install
```

Run in development mode:

```shell
npm run tauri:dev
```

Build frontend assets:

```shell
npm run build
```

Check the Rust backend:

```shell
cd src-tauri
cargo check
```

## Packaging

Build a desktop installer:

```shell
npm run tauri:build
```

Build artifacts are written under `src-tauri/target/release/`.

## Project Structure

- `src/`: Tauri frontend built with Vite and plain JavaScript.
- `src-tauri/`: Rust backend, Tauri commands, settings/history storage, and download workflow.
- `icon.png` / `icon.ico`: application icons used by the Tauri bundle.

## Notice

- Running downloads are not cancellable yet.
- Single-file share links are not supported yet; folder share links are supported.
