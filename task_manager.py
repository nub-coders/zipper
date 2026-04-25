"""MongoDB-backed task queue for multi-bot worker coordination.

Task lifecycle: pending → claimed → processing → completed / failed
Task types: download, zip
"""

import time
from uuid import uuid4
from pymongo import ReturnDocument
from config import db


class TaskManager:
    """Manage distributed tasks across worker bots via MongoDB."""

    def __init__(self):
        self.tasks = db["worker_tasks"]
        # Create indexes for efficient queries
        self.tasks.create_index("status")
        self.tasks.create_index("user_id")
        self.tasks.create_index([("status", 1), ("created_at", 1)])
        self.tasks.create_index([("worker_id", 1), ("status", 1), ("created_at", 1)])

    # ─── Task Creation ────────────────────────────────────────────────────

    def create_download_task(
        self,
        user_id: int,
        channel_msg_id: int,
        channel_id: int,
        file_name: str,
        file_size: int,
        max_storage: int,
        max_file_size: int,
        is_verified: bool,
        main_bot_reply_id: int | None = None,
        worker_id: str | None = None,
    ) -> dict:
        """Create a task for a worker to download a file from the channel."""
        task = {
            "task_id": str(uuid4()),
            "type": "download",
            "user_id": user_id,
            "status": "pending",
            "worker_id": worker_id,
            "channel_id": channel_id,
            "channel_msg_id": channel_msg_id,
            "file_name": file_name,
            "file_size": file_size,
            "max_storage": max_storage,
            "max_file_size": max_file_size,
            "is_verified": is_verified,
            "main_bot_reply_id": main_bot_reply_id,
            "created_at": time.time(),
            "claimed_at": None,
            "completed_at": None,
            "error": None,
        }
        self.tasks.insert_one(task)
        return task

    def create_link_download_task(
        self,
        user_id: int,
        url: str,
        max_storage: int,
        max_file_size: int,
        is_verified: bool,
        content_length: int,
        main_bot_reply_id: int | None = None,
        worker_id: str | None = None,
    ) -> dict:
        """Create a task for a worker to download a file from a URL."""
        task = {
            "task_id": str(uuid4()),
            "type": "link_download",
            "user_id": user_id,
            "status": "pending",
            "worker_id": worker_id,
            "url": url,
            "content_length": content_length,
            "max_storage": max_storage,
            "max_file_size": max_file_size,
            "is_verified": is_verified,
            "main_bot_reply_id": main_bot_reply_id,
            "created_at": time.time(),
            "claimed_at": None,
            "completed_at": None,
            "error": None,
        }
        self.tasks.insert_one(task)
        return task

    def create_zip_task(
        self,
        user_id: int,
        pass_protect: bool = False,
        password: str | None = None,
        zip_file_name: str = "archive.zip",
        main_bot_reply_id: int | None = None,
        worker_id: str | None = None,
    ) -> dict:
        """Create a task for a worker to compress a user's directory."""
        task = {
            "task_id": str(uuid4()),
            "type": "zip",
            "user_id": user_id,
            "status": "pending",
            "worker_id": worker_id,
            "pass_protect": pass_protect,
            "zip_password": password,
            "zip_file_name": zip_file_name,
            "main_bot_reply_id": main_bot_reply_id,
            "created_at": time.time(),
            "claimed_at": None,
            "completed_at": None,
            "error": None,
        }
        self.tasks.insert_one(task)
        return task

    # ─── Task Claiming ────────────────────────────────────────────────────

    def claim_task(self, worker_id: str) -> dict | None:
        """Atomically claim the oldest pending task.

        Returns the claimed task document, or None if nothing is available.
        """
        return self.tasks.find_one_and_update(
            {
                "status": "pending",
                "worker_id": worker_id,
            },
            {
                "$set": {
                    "status": "claimed",
                    "worker_id": worker_id,
                    "claimed_at": time.time(),
                }
            },
            sort=[("created_at", 1)],
            return_document=ReturnDocument.AFTER,
        )

    # ─── Task Status Updates ──────────────────────────────────────────────

    def update_status(self, task_id: str, status: str, **extra):
        """Update task status with optional extra fields."""
        update = {"status": status}
        update.update(extra)
        self.tasks.update_one(
            {"task_id": task_id},
            {"$set": update},
        )

    def complete_task(self, task_id: str, **kwargs):
        self.update_status(task_id, "completed", completed_at=time.time(), **kwargs)

    def fail_task(self, task_id: str, error: str, **kwargs):
        self.update_status(task_id, "failed", error=error, completed_at=time.time(), **kwargs)

    # ─── Queries ──────────────────────────────────────────────────────────

    def get_user_pending_count(self, user_id: int) -> int:
        """Count pending/claimed tasks for a user."""
        return self.tasks.count_documents(
            {"user_id": user_id, "status": {"$in": ["pending", "claimed"]}}
        )

    def cancel_user_tasks(self, user_id: int) -> int:
        """Cancel all pending tasks for a user. Returns count cancelled."""
        result = self.tasks.update_many(
            {"user_id": user_id, "status": "pending"},
            {"$set": {"status": "cancelled", "completed_at": time.time()}},
        )
        return result.modified_count

    def cleanup_stale_tasks(self, timeout_seconds: int = 1800, live_worker_ids: list[str] | None = None):
        """Re-queue tasks that have been claimed for too long (worker died).

        If live_worker_ids is provided, reassigns stale tasks round-robin
        to live workers. Otherwise just resets them to pending.
        """
        cutoff = time.time() - timeout_seconds
        stale = self.tasks.find(
            {"status": "claimed", "claimed_at": {"$lt": cutoff}}
        )
        for i, task in enumerate(stale):
            update = {"status": "pending", "claimed_at": None}
            if live_worker_ids:
                update["worker_id"] = live_worker_ids[i % len(live_worker_ids)]
            self.tasks.update_one({"_id": task["_id"]}, {"$set": update})


# Singleton
task_mgr = TaskManager()
