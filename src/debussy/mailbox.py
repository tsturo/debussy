"""File-based mailbox system for agent communication."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import MAILBOX_ROOT


class Mailbox:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.inbox = MAILBOX_ROOT / agent_name / "inbox"
        self.processed = MAILBOX_ROOT / agent_name / "processed"

    def ensure_dirs(self):
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.processed.mkdir(parents=True, exist_ok=True)

    def send(self, recipient: str, subject: str, body: str = "",
             bead_id: Optional[str] = None, priority: int = 2) -> str:
        recipient_inbox = MAILBOX_ROOT / recipient / "inbox"
        recipient_inbox.mkdir(parents=True, exist_ok=True)

        msg_id = f"msg-{int(time.time() * 1000)}"
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        safe_subject = "".join(c if c.isalnum() or c in "-_" else "_" for c in subject[:30])
        filename = f"{priority}_{timestamp}_{safe_subject}.json"

        msg = {
            "id": msg_id,
            "sender": self.agent_name,
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "priority": priority,
            "created_at": timestamp
        }
        if bead_id:
            msg["bead_id"] = bead_id

        with open(recipient_inbox / filename, 'w') as f:
            json.dump(msg, f, indent=2)

        return msg_id

    def count(self) -> int:
        if not self.inbox.exists():
            return 0
        return len(list(self.inbox.glob("*.json")))

    def peek(self) -> Optional[dict]:
        if not self.inbox.exists():
            return None
        files = sorted(self.inbox.glob("*.json"))
        if not files:
            return None
        with open(files[0]) as f:
            return json.load(f)

    def pop(self) -> Optional[dict]:
        if not self.inbox.exists():
            return None
        files = sorted(self.inbox.glob("*.json"))
        if not files:
            return None
        filepath = files[0]
        with open(filepath) as f:
            msg = json.load(f)
        self.processed.mkdir(parents=True, exist_ok=True)
        filepath.rename(self.processed / filepath.name)
        return msg

    def list_messages(self) -> list[dict]:
        if not self.inbox.exists():
            return []
        messages = []
        for filepath in sorted(self.inbox.glob("*.json")):
            with open(filepath) as f:
                messages.append(json.load(f))
        return messages
