"""一件工作從頭到尾的流程：下載照片 → claude -p 分析 → 檢查 → 存照片 → 回覆 → 寫 Excel。

這裡完全不碰 discord 套件，跟 Discord 的溝通都透過 Messenger，方便獨立測試。
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol

from .claude_runner import run_claude
from .config import Config
from .photo_store import SourcePhoto, save_photos, sniff_image_ext
from .record_store import Record, RecordStore
from .reply_builder import (
    MSG_ONLY_PHOTOS,
    build_reply,
    dish_cell,
    ingredients_cell,
    recipe_cell,
)
from .result_schema import AnalysisResult, InvalidResult, parse_result, unwrap_cli_output

log = logging.getLogger("recipe_agent.worker")

MAX_PHOTO_BYTES = 8 * 1024 * 1024
ANALYZE_ATTEMPTS = 2  # 格式不合格時最多重試 1 次


class Messenger(Protocol):
    async def send_result(self, job: "Job", chunks: list[str]) -> None: ...
    async def send_text(self, job: "Job", text: str) -> None: ...
    async def send_failure(self, job: "Job") -> None: ...
    async def clear_queued_mark(self, job: "Job") -> None: ...


@dataclass
class Job:
    author_id: int
    author_label: str  # 例如「小明 (123456789012345678)」
    mention: str  # 例如「<@123456789012345678>」
    created_at: datetime  # 本機時區
    attachments: list[Any]  # 要有 .size 與 async .read()
    user_text: str = ""
    notes: list[str] = field(default_factory=list)
    message: Any = None  # 給 Messenger 用的原始訊息，這裡不碰


@dataclass
class Context:
    config: Config
    store: RecordStore
    messenger: Messenger
    analyze: Callable[..., Awaitable[str]] = run_claude


async def process_job(job: Job, ctx: Context) -> None:
    """處理一件工作。任何錯誤都只影響這一件，不往外丟。"""
    job_dir = Path(tempfile.mkdtemp(prefix="recipe-job-"))  # 放在系統暫存區，不在 DATA_DIR、不在 repo 底下
    started = time.monotonic()
    log.info("開始處理｜上傳者=%s｜照片=%d 張", job.author_label, len(job.attachments))
    outcome = "失敗"
    try:
        try:
            photos, dropped = await _download(job, job_dir)
            log.info("下載完成｜可用照片=%d 張｜略過=%d 張", len(photos), dropped)
            if dropped:
                job.notes.append(f"有 {dropped} 張照片格式不支援或超過 8 MB，已略過")
            if not photos:
                await ctx.messenger.send_text(job, MSG_ONLY_PHOTOS)
                outcome = "沒有可用的照片"
                return

            result = await _analyze(ctx, job, job_dir, [p for p, _ in photos])

            sources = [SourcePhoto(path, ext, result.name_for(i)) for i, (path, ext) in enumerate(photos, start=1)]
            log.info(
                "分析完成｜是否為食材=%s｜辨識到=%s｜料理=%s",
                "是" if result.is_food else "否",
                "、".join(result.ingredients),
                result.dish_name or "無",
            )
            saved = await asyncio.to_thread(save_photos, ctx.config.photos_dir, job.created_at, sources)
            log.info("照片已存檔｜%s", "；".join(saved))

            notes = list(job.notes)
            if result.skipped_note:
                notes.append(result.skipped_note)
            record = Record(
                when=job.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                uploader=job.author_label,
                is_food="是" if result.is_food else "否",
                ingredients=ingredients_cell(result),
                dish_name=dish_cell(result),
                recipe=recipe_cell(result),
                photo_files="\n".join(saved),
                note="；".join(notes),
            )
            chunks = build_reply(result, notes, job.mention)
        except Exception:
            log.exception("處理失敗（作者 id=%s）", job.author_id)
            await _safely(ctx.messenger.send_failure(job))
            log.warning("已回覆上傳者「分析失敗」；不寫 Excel、不存照片｜上傳者=%s", job.author_label)
            return

        # 回覆不等 Excel；回覆失敗也不影響紀錄
        await _safely(ctx.messenger.send_result(job, chunks))
        log.info("已回覆上傳者｜共 %d 則訊息", len(chunks))
        in_excel = await asyncio.to_thread(ctx.store.append, record)
        if in_excel:
            log.info("已寫入 Excel｜%s", ctx.config.excel_path.name)
        else:
            log.warning("Excel 沒寫進去，這一筆已先存到暫存清單｜%s", ctx.config.pending_path.name)
        outcome = "成功"
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)
        await _safely(ctx.messenger.clear_queued_mark(job))
        log.info("處理結束｜結果=%s｜上傳者=%s｜花了 %.1f 秒", outcome, job.author_label, time.monotonic() - started)


async def _download(job: Job, job_dir: Path) -> tuple[list[tuple[Path, str]], int]:
    kept: list[tuple[Path, str]] = []
    dropped = 0
    for att in job.attachments:
        if getattr(att, "size", 0) > MAX_PHOTO_BYTES:
            dropped += 1
            continue
        data = await att.read()
        ext = sniff_image_ext(data)
        if ext is None or len(data) > MAX_PHOTO_BYTES:
            dropped += 1
            continue
        path = job_dir / f"photo_{len(kept) + 1}{ext}"  # 檔名由程式決定，不用上傳者的檔名
        path.write_bytes(data)
        kept.append((path, ext))
    return kept, dropped


async def _analyze(ctx: Context, job: Job, job_dir: Path, paths: list[Path]) -> AnalysisResult:
    last: InvalidResult | None = None
    for attempt in range(1, ANALYZE_ATTEMPTS + 1):
        stdout = await ctx.analyze(ctx.config, job_dir, paths, job.user_text)
        try:
            return parse_result(unwrap_cli_output(stdout), len(paths))
        except InvalidResult as exc:
            last = exc
            log.warning("claude 的答案不合格（第 %d 次）：%s", attempt, exc)
    assert last is not None
    raise last


async def _safely(awaitable: Awaitable[Any]) -> None:
    try:
        await awaitable
    except Exception:
        log.exception("收尾動作失敗（已略過）")
