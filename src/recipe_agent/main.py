"""入口：uv run python -m recipe_agent"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from .bot import RecipeBot
from .config import Config, ConfigError, load_config
from .record_store import RecordFileProblem, RecordStore


def _setup_logging(config: Config) -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    console = logging.StreamHandler()  # 警告會印在終端機
    console.setFormatter(fmt)
    file_handler = RotatingFileHandler(config.logs_dir / "agent.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(console)
    root.addHandler(file_handler)
    logging.getLogger("discord").setLevel(logging.WARNING)  # token 不會被印出


def main() -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"[設定有問題] {exc}", file=sys.stderr)
        return 1

    _setup_logging(config)
    store = RecordStore(config.excel_path, config.pending_path)
    try:
        store.check_readable()
    except RecordFileProblem as exc:
        print(
            f"[設定有問題] {config.excel_path} 已經存在但打不開（檔案可能壞了）：{exc}",
            file=sys.stderr,
        )
        print("為避免覆蓋你的紀錄，agent 不會啟動。請先把這個檔案移走或修好。", file=sys.stderr)
        return 1
    store.flush_pending()  # 上次寫不進去的紀錄，開機時補寫

    bot = RecipeBot(config, store)
    bot.run(config.discord_token, log_handler=None)  # log_handler=None：用我們自己的 logging 設定
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
