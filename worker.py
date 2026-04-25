"""Worker bot module — handles file downloads, ZIP creation, and uploads.

Each worker is a separate Pyrogram Client that:
  1. Polls MongoDB for unclaimed tasks
  2. Claims a task atomically
  3. Processes it (download from channel, zip, upload TO channel)
  4. Main bot picks up results from channel and forwards to user
"""

import os
import time
import asyncio
import shutil
import aiohttp

from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from task_manager import task_mgr
from tools import (
    get_file_size_info,
    Timer,
    is_compressed,
    cleanup_user_directory,
)
from stats_manager import stats_manager
import config


# ─── Size Formatter ───────────────────────────────────────────────────────────

def _fmt_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.2f} MB"
    return f"{size_bytes / (1024 ** 3):.2f} GB"


# ─── Worker Bot ───────────────────────────────────────────────────────────────

class WorkerBot:
    """A worker bot that processes file tasks from MongoDB."""

    def __init__(self, token: str, worker_id: str, api_id: int, api_hash: str):
        self.token = token
        self.worker_id = worker_id
        self.client = Client(
            f"worker_{worker_id}",
            api_id=api_id,
            api_hash=api_hash,
            bot_token=token,
            in_memory=True,
            no_updates=True,  # Workers don't need to receive updates
        )
        self.channel_id: int | None = None
        self.running = False

    async def start(self, channel_id: int):
        """Start the worker bot and begin processing tasks."""
        self.channel_id = channel_id
        await self.client.start()
        me = await self.client.get_me()
        print(f"  Worker {self.worker_id} started: @{me.username}")
        self.running = True
        asyncio.create_task(self._task_loop())

    async def stop(self):
        self.running = False
        try:
            await self.client.stop()
        except Exception:
            pass

    # ─── Channel Messaging ────────────────────────────────────────────────

    async def _send_to_channel(self, text: str) -> int:
        """Send a text result to the processing channel. Returns message ID."""
        msg = await self.client.send_message(self.channel_id, text)
        return msg.id

    async def _send_doc_to_channel(
        self, file_path: str, caption: str, progress=None,
    ) -> int:
        """Send a document to the processing channel. Returns message ID."""
        msg = await self.client.send_document(
            self.channel_id,
            file_path,
            caption=caption,
            progress=progress,
        )
        return msg.id

    # ─── Task Loop ────────────────────────────────────────────────────────

    async def _task_loop(self):
        """Continuously poll MongoDB for tasks and process them."""
        print(f"  Worker {self.worker_id}: task loop started")
        last_cleanup = 0
        while self.running:
            try:
                now = time.time()
                if now - last_cleanup > 60 and self == worker_manager.workers[0]:
                    live_ids = [w.worker_id for w in worker_manager.workers if w.running]
                    task_mgr.cleanup_stale_tasks(live_worker_ids=live_ids)
                    last_cleanup = now

                task = task_mgr.claim_task(self.worker_id)
                if task:
                    await self._handle_task(task)
                else:
                    await asyncio.sleep(2)  # No tasks, wait before polling again
            except Exception as e:
                print(f"  Worker {self.worker_id} error in task loop: {e}")
                await asyncio.sleep(5)

    async def _handle_task(self, task: dict):
        """Dispatch a claimed task to the appropriate handler."""
        task_type = task["type"]
        task_id = task["task_id"]
        print(f"  Worker {self.worker_id}: claimed task {task_id} ({task_type})")

        task_mgr.update_status(task_id, "processing")

        try:
            if task_type == "download":
                await self._handle_download(task)
            elif task_type == "link_download":
                await self._handle_link_download(task)
            elif task_type == "zip":
                await self._handle_zip(task)
            else:
                task_mgr.fail_task(task_id, f"Unknown task type: {task_type}")
        except Exception as e:
            print(f"  Worker {self.worker_id}: task {task_id} failed: {e}")
            task_mgr.fail_task(task_id, str(e))
            # Notify via channel
            try:
                result_msg_id = await self._send_to_channel(
                    f"❌ Processing failed: {e}\nPlease try again.",
                )
                task_mgr.update_status(
                    task_id, "failed",
                    error=str(e), result_msg_id=result_msg_id,
                    user_id=task["user_id"],
                )
            except Exception:
                pass

    # ─── Download from Channel ────────────────────────────────────────────

    async def _handle_download(self, task: dict):
        """Download a file from the processing channel to the user's directory."""
        user_id = task["user_id"]
        task_id = task["task_id"]
        channel_id = task["channel_id"]
        channel_msg_id = task["channel_msg_id"]
        max_storage = task["max_storage"]

        user_dir = f"{config.ggg}/zipper/{user_id}"
        os.makedirs(user_dir, exist_ok=True)

        file_name = task.get("file_name", "file")

        try:
            # Get the message from the channel and download the file
            print(f"[WORKER {self.worker_id}] Attempting to fetch message {channel_msg_id} from channel {channel_id}...")
            channel_msg = await self.client.get_messages(channel_id, channel_msg_id)
            print(f"[WORKER {self.worker_id}] Successfully fetched message. id={getattr(channel_msg, 'id', None)}, empty={getattr(channel_msg, 'empty', True)}, media={getattr(channel_msg, 'media', None)}")
            
            last_update_time = time.time()
            async def progress_callback(current, total):
                nonlocal last_update_time
                if time.time() - last_update_time > 3:
                    task_mgr.update_status(task_id, "downloading", current=current, total=total)
                    last_update_time = time.time()
            
            print(f"[WORKER {self.worker_id}] Attempting to download media from message {channel_msg_id}...")
            file_path = await asyncio.wait_for(
                channel_msg.download(
                    file_name=f"zipper/{user_id}/",
                    progress=progress_callback
                ),
                timeout=1500,  # 25 minutes
            )
            print(f"[WORKER {self.worker_id}] Download completed successfully! Saved to {file_path}")

            await stats_manager.update_stats(user_id, "files_sent")

            filename_only = os.path.basename(file_path) if file_path else "file"
            dl_size = (
                os.path.getsize(file_path)
                if file_path and os.path.exists(file_path)
                else 0
            )
            _, remaining, _ = get_file_size_info(user_dir, max_storage)
            used = max_storage - remaining

            result_text = (
                f"✅ **Finished downloading**\n"
                f"📄 `{filename_only}` — {_fmt_size(dl_size)}\n"
                f"💾 Used: {_fmt_size(used)} / Available: {_fmt_size(remaining)}\n"
                f"/my_files to see your files"
            )

            if file_path and is_compressed(file_path):
                result_text += (
                    "\n\n🗜️ **Compressed file detected!**\n"
                    "Use /unzip to uncompress it."
                )

            task_mgr.complete_task(task_id, result_text=result_text, user_id=user_id)

        except asyncio.TimeoutError:
            task_mgr.fail_task(task_id, "❌ **Download timed out**\n\nThis file took more than 25 minutes and was auto-cancelled.", user_id=user_id)
        except Exception as e:
            task_mgr.fail_task(task_id, f"❌ Download failed: {e}", user_id=user_id)

    # ─── Link Download ────────────────────────────────────────────────────

    async def _handle_link_download(self, task: dict):
        """Download a file from a URL to the user's directory."""
        user_id = task["user_id"]
        task_id = task["task_id"]
        url = task["url"]
        content_length = task["content_length"]
        max_storage = task["max_storage"]

        user_dir = f"{config.ggg}/zipper/{user_id}"
        os.makedirs(user_dir, exist_ok=True)

        filename = url.split("/")[-1] or f"download_{int(time.time())}"
        file_path = os.path.join(user_dir, filename)

        try:
            timeout = aiohttp.ClientTimeout(total=1500)
            last_update_time = time.time()
            downloaded = 0
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        task_mgr.fail_task(task_id, f"❌ Download failed (HTTP {resp.status}). Please check the URL.", user_id=user_id)
                        return

                    with open(file_path, "wb") as f:
                        while True:
                            chunk = await resp.content.read(8192)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if time.time() - last_update_time > 3:
                                task_mgr.update_status(task_id, "downloading", current=downloaded, total=content_length)
                                last_update_time = time.time()

            await stats_manager.update_stats(user_id, "files_sent")

            dl_size = os.path.getsize(file_path)
            _, remaining, _ = get_file_size_info(user_dir, max_storage)
            used = max_storage - remaining

            result_text = (
                f"✅ **Downloaded successfully**\n"
                f"📄 `{filename}` — {_fmt_size(dl_size)}\n"
                f"💾 Used: {_fmt_size(used)} / Available: {_fmt_size(remaining)}\n"
                f"/my_files to check all your files"
            )

            if is_compressed(file_path):
                result_text += (
                    "\n\n🗜️ **Compressed file detected!**\n"
                    "Use /unzip to uncompress it."
                )

            task_mgr.complete_task(task_id, result_text=result_text, user_id=user_id)

        except asyncio.TimeoutError:
            task_mgr.fail_task(task_id, "❌ **Download timed out** (25 min limit)", user_id=user_id)
        except Exception as e:
            task_mgr.fail_task(task_id, f"❌ Download failed: {e}", user_id=user_id)

    # ─── ZIP Processing ───────────────────────────────────────────────────

    async def _handle_zip(self, task: dict):
        """Create a ZIP from the user's files, upload to channel, clean up."""
        user_id = task["user_id"]
        task_id = task["task_id"]
        pass_protect = task.get("pass_protect", False)
        zip_file_name = task.get("zip_file_name", "archive.zip")
        password = task.get("zip_password", "")

        user_dir = f"{config.ggg}/zipper/{user_id}"
        if not os.path.exists(user_dir):
            task_mgr.fail_task(task_id, "❌ No files to zip.", user_id=user_id)
            return

        files = os.listdir(user_dir)
        if not files:
            task_mgr.fail_task(task_id, "❌ No files to zip.", user_id=user_id)
            return

        if not zip_file_name.endswith(".zip"):
            zip_file_name = f"{zip_file_name}.zip"
        zip_path = os.path.join(user_dir, zip_file_name)

        # Calculate original size
        original_size = sum(
            os.path.getsize(os.path.join(user_dir, fn))
            for fn in files
            if os.path.isfile(os.path.join(user_dir, fn))
        )

        import zipfile
        import pyminizip

        error_text = None
        result_msg_id = None
        result_text = None

        try:
            task_mgr.update_status(task_id, "zipping", current_file=0, total_files=len(files))
            if pass_protect and password:
                file_paths = [os.path.join(user_dir, fn) for fn in files]
                prefixes = [""] * len(files)
                pyminizip.compress_multiple(
                    file_paths, prefixes, zip_path, password, 4
                )
            else:
                last_update_time = time.time()
                with zipfile.ZipFile(
                    zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=5
                ) as zipf:
                    for idx, fn in enumerate(files):
                        zipf.write(os.path.join(user_dir, fn), fn)
                        
                        if time.time() - last_update_time > 3:
                            task_mgr.update_status(task_id, "zipping", current_file=idx + 1, total_files=len(files))
                            last_update_time = time.time()
                            await asyncio.sleep(0)  # yield control to the event loop

            compressed_size = (
                os.path.getsize(zip_path) if os.path.exists(zip_path) else 0
            )
            savings = (
                (1 - compressed_size / original_size) * 100
                if original_size > 0
                else 0
            )
            lock_icon = "🔐 " if pass_protect and password else ""

            # Upload the ZIP to channel (main bot will forward to user)
            if compressed_size <= 2_000_000_000:
                caption_text = (
                    f"✅ {lock_icon}**ZIP created & uploaded!**\n\n"
                    f"📂 Original: `{_fmt_size(original_size)}`\n"
                    f"📦 Compressed: `{_fmt_size(compressed_size)}`\n"
                    f"💾 Saved: `{savings:.1f}%`\n\n"
                    f"zip by @FILEs_COMPRESSOR_BOT"
                )

                last_update_time = time.time()
                async def progress_callback(current, total):
                    nonlocal last_update_time
                    if time.time() - last_update_time > 3:
                        task_mgr.update_status(task_id, "uploading", current=current, total=total)
                        last_update_time = time.time()

                result_msg_id = await self._send_doc_to_channel(
                    zip_path, caption_text, progress=progress_callback
                )
            else:
                # Large file → upload to gofile and send link via channel
                try:
                    import subprocess
                    import requests

                    resp = requests.get("https://api.gofile.io/servers")
                    server = resp.json()["data"]["servers"][0]["name"]
                    transfer_url = f"https://{server}.gofile.io/uploadFile"
                    proc = subprocess.Popen(
                        ["curl", "-F", f"file=@{zip_path}", transfer_url],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                    )
                    line = ""
                    for line in proc.stdout:
                        line = line.strip()
                    start_idx = line.find("https://gofile.io")
                    end_idx = line.find('"', start_idx)
                    link = line[start_idx:end_idx]
                    result_text = f"📤 **File too large for Telegram.**\nDownload here: {link}"
                except Exception as e:
                    error_text = f"❌ External upload failed: {e}"

            # Clean up user directory
            if os.path.exists(user_dir):
                shutil.rmtree(user_dir, ignore_errors=True)
                os.makedirs(user_dir, exist_ok=True)

            if error_text:
                task_mgr.fail_task(task_id, error_text, user_id=user_id)
            elif result_msg_id:
                task_mgr.complete_task(task_id, result_msg_id=result_msg_id, user_id=user_id)
            elif result_text:
                task_mgr.complete_task(task_id, result_text=result_text, user_id=user_id)
            else:
                task_mgr.fail_task(task_id, "❌ ZIP created but delivery failed.", user_id=user_id)

        except Exception as e:
            task_mgr.fail_task(task_id, f"❌ Error creating ZIP: {e}", user_id=user_id)


# ─── Worker Manager ──────────────────────────────────────────────────────────

class WorkerManager:
    """Manages multiple worker bots — validates channels, starts workers."""

    def __init__(self):
        self.workers = []
        self.available = False
        self.active_channel = None
        self._next_worker_idx = 0

    def get_next_worker_id(self) -> str | None:
        if not self.workers:
            return None
        worker_id = self.workers[self._next_worker_idx].worker_id
        self._next_worker_idx = (self._next_worker_idx + 1) % len(self.workers)
        return worker_id

    async def initialize(self, api_id: int, api_hash: str, channel_ids: list[int] = None):
        """Start worker bots, check channel permissions, and pick the best channel."""
        worker_tokens = config.WORKER_BOT_TOKENS
        channel_ids = channel_ids or config.PROCESS_CHANNEL_IDS

        if not worker_tokens:
            print("⚠️  No worker bot tokens configured. Running in single-bot mode.")
            return

        if not channel_ids:
            print("⚠️  No processing channel IDs configured. Running in single-bot mode.")
            return

        print(f"\n🔧 Initializing {len(worker_tokens)} worker bot(s)…")

        # Step 1: Start all worker clients (temporary, just to validate)
        temp_workers = []
        for i, token in enumerate(worker_tokens):
            token = token.strip()
            if not token:
                continue
            worker_id = f"w{i + 1}"
            try:
                worker = WorkerBot(token, worker_id, api_id, api_hash)
                await worker.client.start()
                me = await worker.client.get_me()
                print(f"  ✅ Bot {worker_id}: @{me.username}")
                temp_workers.append(worker)
            except Exception as e:
                print(f"  ❌ Bot {worker_id} failed to start: {e}")

        if not temp_workers:
            print("⚠️  No worker bots could start. Running in single-bot mode.")
            return

        # Step 2: Check which bots can access which channels
        channel_access = {}  # channel_id → list of workers that can access it
        for ch_id in channel_ids:
            channel_access[ch_id] = []
            for worker in temp_workers:
                try:
                    chat = await worker.client.get_chat(ch_id)
                    channel_access[ch_id].append(worker)
                    print(f"  ✅ {worker.worker_id} can access channel {ch_id} ({chat.title})")
                except Exception as e:
                    print(f"  ❌ {worker.worker_id} cannot access channel {ch_id}: {e}")

        # Step 3: Pick the channel accessible by the most bots
        best_channel = None
        best_count = 0
        for ch_id, workers in channel_access.items():
            if len(workers) > best_count:
                best_count = len(workers)
                best_channel = ch_id

        if not best_channel or best_count == 0:
            print("⚠️  No channel accessible by any worker bot. Running in single-bot mode.")
            for w in temp_workers:
                await w.stop()
            return

        self.active_channel = best_channel
        valid_workers = channel_access[best_channel]
        print(f"\n✅ Selected channel {best_channel} ({best_count} worker(s) can access it)")

        # Stop workers that can't access the selected channel
        for w in temp_workers:
            if w not in valid_workers:
                print(f"  ⏹️  Stopping {w.worker_id} (no channel access)")
                await w.stop()
            else:
                await w.client.stop()  # Stop temporarily, will restart with task loop

        # Step 4: Restart valid workers with task processing
        for worker in valid_workers:
            try:
                await worker.start(best_channel)
                self.workers.append(worker)
            except Exception as e:
                print(f"  ❌ Failed to restart {worker.worker_id}: {e}")

        if self.workers:
            self.available = True
            print(f"\n🚀 {len(self.workers)} worker(s) ready on channel {best_channel}\n")
        else:
            print("⚠️  No workers could start. Running in single-bot mode.")

    async def stop_all(self):
        for w in self.workers:
            await w.stop()
        self.workers.clear()
        self.available = False


# Global singleton
worker_manager = WorkerManager()
