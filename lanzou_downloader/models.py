from dataclasses import dataclass, replace
from pathlib import Path


@dataclass(frozen=True)
class DownloadTask:
    share_url: str
    password: str
    target_dir: Path
    process_count: int = 1

    def normalized(self):
        return replace(
            self,
            share_url=self.share_url.strip(),
            password=self.password.strip(),
            target_dir=Path(self.target_dir),
            process_count=max(1, int(self.process_count)),
        )


@dataclass(frozen=True)
class FileEntry:
    page_path: str
    name: str
    download_url: str = ""

    def with_download_url(self, download_url):
        return replace(self, download_url=download_url)
