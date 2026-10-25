"""Discord 這一側：收訊息、篩選、一人一件、排隊、上線/下線公告、回覆。"""

from __future__ import annotations

import asyncio
import logging

import discord

from .config import Config
from .record_store import RecordStore
from .reply_builder import (
    MSG_BUSY,
    MSG_FAILED,
    MSG_OFFLINE,
    MSG_ONLINE,
    MSG_ONLY_PHOTOS,
    MSG_SHUTTING_DOWN,
    REACTION_QUEUED,
)
from .result_schema import MAX_PHOTOS
from .worker import Context, Job, process_job

log = logging.getLogger("recipe_agent.bot")

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")
_SHUTDOWN_GRACE_SECONDS = 60


def _is_supported_image(att: discord.Attachment) -> bool:
    ctype = (att.content_type or "").split(";")[0].strip().lower()
    return ctype in _IMAGE_TYPES or att.filename.lower().endswith(_IMAGE_EXTS)


class RecipeBot(discord.Client):
    def __init__(self, config: Config, store: RecordStore) -> None:
        intents = discord.Intents.default()
        intents.message_content = True  # 沒開的話收到的訊息（含附件）會是空的，見 docs/discord-bot-setup.md
        super().__init__(intents=intents)
        self.config = config
        self.queue: asyncio.Queue[Job] = asyncio.Queue()
        self.active_users: set[int] = set()  # 目前有件在處理或排隊的人
        self._ctx = Context(config=config, store=store, messenger=_DiscordMessenger(self))
        self._worker: asyncio.Task | None = None
        self._idle = asyncio.Event()
        self._idle.set()
        self._announced = False
        self._closing = False

    # ---------- 生命週期 ----------

    async def setup_hook(self) -> None:
        self._worker = asyncio.create_task(self._worker_loop(), name="recipe-worker")

    async def on_ready(self) -> None:
        log.info("已登入為 %s，監聽頻道 %s", self.user, self.config.channel_id)
        if self._announced:  # 斷線重連也會再觸發 on_ready，公告只發一次
            return
        self._announced = True
        await self._announce(MSG_ONLINE)

    async def close(self) -> None:
        if not self._closing:
            self._closing = True
            log.info("收到關閉要求，開始收尾（排隊中 %d 件）", self.queue.qsize())
            try:
                await self._graceful_shutdown()
            except Exception:
                log.exception("關閉前的收尾動作失敗")
        await super().close()

    async def _graceful_shutdown(self) -> None:
        # 還在排隊、尚未開始的，各回一句並清掉 ⏳
        while not self.queue.empty():
            job = self.queue.get_nowait()
            await self._ctx.messenger.send_text(job, MSG_SHUTTING_DOWN)
            await self._ctx.messenger.clear_queued_mark(job)
            self.active_users.discard(job.author_id)
        # 進行中的最多再等一下
        try:
            await asyncio.wait_for(self._idle.wait(), _SHUTDOWN_GRACE_SECONDS)
        except asyncio.TimeoutError:
            log.warning("關閉時有一件工作超過 %d 秒還沒做完，放棄等待", _SHUTDOWN_GRACE_SECONDS)
        await self._announce(MSG_OFFLINE)
        if self._worker:
            self._worker.cancel()

    async def _announce(self, text: str) -> None:
        channel = self.get_channel(self.config.channel_id)
        if channel is None:
            log.warning("找不到頻道 %s（CHANNEL_ID 填錯，或 bot 看不到那個頻道？）", self.config.channel_id)
            return
        try:
            await channel.send(text, allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            log.exception("發公告失敗")

    # ---------- 收訊息 ----------

    async def on_message(self, message: discord.Message) -> None:
        if self._closing or message.author.bot:
            return
        if message.channel.id != self.config.channel_id:
            return
        if not message.attachments:  # 純文字訊息完全不理
            return

        images = [a for a in message.attachments if _is_supported_image(a)]
        who = f"{message.author.display_name} ({message.author.id})"
        if not images:
            log.info("收到不支援的附件，已回覆提示｜上傳者=%s｜附件數=%d", who, len(message.attachments))
            await self._reply_text(message, MSG_ONLY_PHOTOS)
            return

        if message.author.id in self.active_users:  # 一人一件
            log.info("上傳者上一件還沒做完，已回覆提示、這次不處理｜上傳者=%s", who)
            await self._reply_text(message, MSG_BUSY)
            return

        notes = []
        if len(images) > MAX_PHOTOS:
            notes.append(f"你傳了 {len(images)} 張，只處理前 {MAX_PHOTOS} 張")

        self.active_users.add(message.author.id)
        job = Job(
            author_id=message.author.id,
            author_label=f"{message.author.display_name} ({message.author.id})",
            mention=f"<@{message.author.id}>",
            created_at=message.created_at.astimezone(),
            attachments=images[:MAX_PHOTOS],
            user_text=message.content or "",
            notes=notes,
            message=message,
        )
        try:
            await message.add_reaction(REACTION_QUEUED)  # ⏳ 表示收到、排隊中
        except discord.HTTPException:
            log.warning("加 ⏳ 反應失敗（bot 可能沒有 Add Reactions 權限）")
        self.queue.put_nowait(job)
        log.info(
            "收到照片訊息，已排隊｜上傳者=%s｜照片=%d 張%s｜前面還有 %d 件",
            who,
            len(job.attachments),
            f"（共傳 {len(images)} 張）" if len(images) > MAX_PHOTOS else "",
            self.queue.qsize() - 1 + (0 if self._idle.is_set() else 1),
        )

    async def _reply_text(self, message: discord.Message, text: str) -> None:
        try:
            await message.reply(text, allowed_mentions=discord.AllowedMentions(users=[message.author], replied_user=False))
        except discord.HTTPException:
            log.exception("回覆失敗")

    # ---------- 工作者：一次只處理一件 ----------

    async def _worker_loop(self) -> None:
        while True:
            job = await self.queue.get()
            self._idle.clear()
            try:
                await process_job(job, self._ctx)
            except Exception:  # process_job 自己會接住，這是最後一道牆
                log.exception("工作者遇到預料外的錯誤")
            finally:
                self.active_users.discard(job.author_id)
                self._idle.set()
                self.queue.task_done()


class _DiscordMessenger:
    """實作 worker.Messenger：把結果送回 Discord。"""

    def __init__(self, bot: RecipeBot) -> None:
        self.bot = bot

    @staticmethod
    def _mentions(job: Job) -> discord.AllowedMentions:
        # 只准 @ 上傳者；Claude 回的文字就算含 @everyone 也不會真的通知到人
        return discord.AllowedMentions(everyone=False, roles=False, users=[discord.Object(id=job.author_id)], replied_user=False)

    async def send_result(self, job: Job, chunks: list[str]) -> None:
        msg: discord.Message = job.message
        for i, chunk in enumerate(chunks):
            if i == 0:
                try:
                    await msg.reply(chunk, allowed_mentions=self._mentions(job))
                    continue
                except discord.HTTPException:  # 原訊息被刪了就直接發在頻道裡
                    log.info("回覆原訊息失敗，改直接發在頻道")
            await msg.channel.send(chunk, allowed_mentions=self._mentions(job) if i == 0 else discord.AllowedMentions.none())

    async def send_text(self, job: Job, text: str) -> None:
        msg: discord.Message = job.message
        try:
            await msg.reply(text, allowed_mentions=self._mentions(job))
        except discord.HTTPException:
            await msg.channel.send(f"{job.mention} {text}", allowed_mentions=self._mentions(job))

    async def send_failure(self, job: Job) -> None:
        await self.send_text(job, MSG_FAILED)

    async def clear_queued_mark(self, job: Job) -> None:
        try:
            await job.message.remove_reaction(REACTION_QUEUED, self.bot.user)
        except discord.HTTPException:
            pass
