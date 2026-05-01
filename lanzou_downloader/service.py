from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests

from .client import LanzouClient
from .config import LanzouConfig
from .exceptions import DownloadError, LanzouError


def _noop_message(_message):
    pass


def _noop_progress(_progress):
    pass


@dataclass
class DownloadCallbacks:
    on_message: Callable[[str], None] = _noop_message
    on_progress: Callable[[int], None] = _noop_progress


class LanzouDownloadService:
    def __init__(self, client=None, config=None):
        self.config = config or LanzouConfig()
        self.client = client or LanzouClient(config=self.config)

    def download(self, task, callbacks=None):
        callbacks = callbacks or DownloadCallbacks()
        task = task.normalized()
        if not task.share_url:
            raise LanzouError("Share link is required.")

        callbacks.on_progress(0)
        callbacks.on_message("Getting file list...")
        entries = self.client.list_files(task)
        if not entries:
            raise LanzouError("No downloadable files found in this share link.")

        callbacks.on_message("Found %d files." % len(entries))
        callbacks.on_message("Resolving download URLs...")
        resolved_entries = self._resolve_entries(task, entries, callbacks)
        if not resolved_entries:
            raise LanzouError("No file URLs were resolved successfully.")

        callbacks.on_message("-" * 50)
        callbacks.on_message("Start downloading...")
        downloaded_paths = self._download_entries(task, resolved_entries, callbacks)
        if not downloaded_paths:
            raise LanzouError("All downloads failed.")
        callbacks.on_message("Download finished.")
        return downloaded_paths

    def _resolve_entries(self, task, entries, callbacks):
        resolved = []
        for entry in entries:
            try:
                resolved_entry = self.client.resolve_file(task, entry)
            except LanzouError as exc:
                callbacks.on_message("Get %s URL failed: %s" % (entry.name, exc))
                continue

            callbacks.on_message("Get %s URL success." % resolved_entry.name)
            resolved.append(resolved_entry)
        return resolved

    def _download_entries(self, task, entries, callbacks):
        downloaded_paths = []
        total = len(entries)
        for index, entry in enumerate(entries, start=1):
            try:
                path, skipped = self._download_one(task, entry)
                downloaded_paths.append(path)
                if skipped:
                    callbacks.on_message("%s already exists." % entry.name)
                else:
                    callbacks.on_message("%s downloaded." % entry.name)
            except LanzouError as exc:
                callbacks.on_message("Download %s failed: %s" % (entry.name, exc))
            finally:
                callbacks.on_progress(int(index / total * 100))
        return downloaded_paths

    def _download_one(self, task, entry):
        if not entry.download_url.startswith("http"):
            raise DownloadError("Resolved URL is invalid.")

        target_dir = Path(task.target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / safe_filename(entry.name)
        if target_path.exists():
            return target_path, True

        partial_path = target_path.with_name(target_path.name + ".part")
        try:
            with self.client.session.get(
                entry.download_url,
                headers=self.client.headers(task.share_url),
                stream=True,
                timeout=self.config.request_timeout,
            ) as response:
                response.raise_for_status()
                with partial_path.open("wb") as file:
                    for chunk in response.iter_content(chunk_size=self.config.chunk_size):
                        if chunk:
                            file.write(chunk)
            partial_path.replace(target_path)
            return target_path, False
        except (OSError, requests.RequestException) as exc:
            try:
                partial_path.unlink()
            except FileNotFoundError:
                pass
            raise DownloadError(str(exc)) from exc


def safe_filename(filename):
    invalid_chars = '<>:"/\\|?*'
    cleaned = "".join(
        "_" if char in invalid_chars or ord(char) < 32 else char
        for char in filename
    ).strip()
    cleaned = cleaned.rstrip(". ")
    return cleaned or "download.bin"
