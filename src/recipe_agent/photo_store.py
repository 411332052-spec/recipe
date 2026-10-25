"""照片存放：判斷真實格式、命名、存進 DATA_DIR/photos。

檔名規則：YYYY-MM-DD hh-mm-ss 主要食材簡稱.副檔名（用 - 不用冒號，Windows 才存得了）。
同一秒撞名時，在簡稱後面加 -2、-3。
"""

from __future__ import annotations

import itertools
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_MAX_NAME = 20
_UNSAFE_CHARS = re.compile(r'[\x00-\x1f\x7f/\\:*?"<>|]')
_DOTS = re.compile(r"\.{2,}")
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


@dataclass
class SourcePhoto:
    """暫存資料夾裡等著被存檔的一張照片。"""

    path: Path
    ext: str  # 含點，例如 ".jpg"
    short_name: str  # Claude 回傳的簡稱，尚未清洗


def sniff_image_ext(data: bytes) -> str | None:
    """看檔案開頭判斷真實格式，不信上傳者給的副檔名。"""
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def save_photos(photos_dir: Path, when: datetime, sources: list[SourcePhoto]) -> list[str]:
    """把照片存進 photos_dir，回傳存下來的檔名清單。任何失敗都丟例外（由呼叫端走失敗流程）。"""
    photos_dir.mkdir(parents=True, exist_ok=True)
    stamp = when.strftime("%Y-%m-%d %H-%M-%S")
    saved: list[str] = []

    for src in sources:
        short_name = src.short_name  # 沒有防護 3 時：Claude 回來的簡稱原封不動拿去當檔名

        # ==== 防護 3：主要食材簡稱清洗　開始 ====
        name = unicodedata.normalize("NFKC", short_name)  # 全形的 ／ ＼ 先變半形，下面才清得掉
        name = _UNSAFE_CHARS.sub("", name)  # / \ : * ? " < > | 與控制字元
        name = _DOTS.sub("", name)  # ..
        name = name.strip(" .")  # Windows 會悄悄吃掉開頭結尾的空白與句點
        name = name[:_MAX_NAME].strip(" .")
        if not name or name.upper() in _RESERVED:
            name = "未命名"
        # 最後一道獨立檢查：組出來的路徑必須真的落在 photos_dir 裡面
        if (photos_dir / f"{stamp} {name}").resolve().parent != photos_dir.resolve():
            raise ValueError("檔名會讓路徑跑到照片資料夾外面")
        short_name = name
        # ==== 防護 3 結束 ====

        data = src.path.read_bytes()
        for n in itertools.count(1):
            suffix = "" if n == 1 else f"-{n}"
            dest = photos_dir / f"{stamp} {short_name}{suffix}{src.ext}"
            try:
                handle = open(dest, "xb")  # x：檔案已存在就失敗，不會覆蓋別人的
            except FileExistsError:
                continue
            with handle:
                handle.write(data)
            saved.append(dest.name)
            break
    return saved
