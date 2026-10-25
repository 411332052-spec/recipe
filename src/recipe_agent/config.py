"""讀取並檢查 .env 設定。缺什麼就用白話說清楚，然後停下，不要半啟動。"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values, find_dotenv


class ConfigError(Exception):
    """設定有問題。訊息直接給人看，所以寫白話。"""


@dataclass(frozen=True)
class Config:
    discord_token: str = field(repr=False)  # repr=False：就算不小心把 Config 印出來，也不會露出 token
    channel_id: int
    claude_model: str
    data_dir: Path
    claude_exe: str

    @property
    def photos_dir(self) -> Path:
        return self.data_dir / "photos"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def excel_path(self) -> Path:
        return self.data_dir / "recipes.xlsx"

    @property
    def pending_path(self) -> Path:
        return self.data_dir / "pending_records.jsonl"


_REQUIRED = ("DISCORD_TOKEN", "CHANNEL_ID", "CLAUDE_MODEL", "DATA_DIR")


def load_config(env_file: str | os.PathLike[str] | None = None) -> Config:
    path = env_file or find_dotenv(usecwd=True)
    if not path or not Path(path).is_file():
        raise ConfigError("找不到 .env 檔。請在專案資料夾（recipe）裡建立 .env，做法見 docs/discord-bot-setup.md 第六節。")

    values = {k: (v or "").strip() for k, v in dotenv_values(path).items()}
    missing = [k for k in _REQUIRED if not values.get(k)]
    if missing:
        raise ConfigError(f".env 裡缺少或沒填這些項目：{'、'.join(missing)}")

    try:
        channel_id = int(values["CHANNEL_ID"])
    except ValueError:
        raise ConfigError("CHANNEL_ID 必須是一串數字（在 Discord 對頻道按右鍵 → 複製頻道 ID）。") from None

    data_dir = Path(values["DATA_DIR"]).expanduser()
    try:
        (data_dir / "photos").mkdir(parents=True, exist_ok=True)
        (data_dir / "logs").mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ConfigError(f"DATA_DIR 資料夾建立不起來（{data_dir}）：{exc}") from None

    claude_exe = shutil.which("claude")
    if not claude_exe:
        raise ConfigError("找不到 claude 指令。請確認 Claude Code 已安裝，且在終端機輸入 claude 能執行。")

    return Config(
        discord_token=values["DISCORD_TOKEN"],
        channel_id=channel_id,
        claude_model=values["CLAUDE_MODEL"],
        data_dir=data_dir.resolve(),
        claude_exe=claude_exe,
    )
