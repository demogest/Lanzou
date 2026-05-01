from dataclasses import dataclass
from typing import Tuple


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,"
        "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"
    ),
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


@dataclass(frozen=True)
class LanzouConfig:
    base_url: str = "https://www.lanzoux.com"
    request_timeout: Tuple[int, int] = (8, 60)
    chunk_size: int = 1024 * 256

    @property
    def prefix(self):
        return self.base_url.rstrip("/") + "/"

    @property
    def ajax_url(self):
        return self.base_url.rstrip("/") + "/ajaxm.php"

    @property
    def file_more_ajax_url(self):
        return self.base_url.rstrip("/") + "/filemoreajax.php"
