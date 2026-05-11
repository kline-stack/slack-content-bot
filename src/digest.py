"""
Daily digest — reads all channels and DMs a summary to the manager.
Run manually: python src/digest.py
Run via GitHub Actions: on cron schedule
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from channel_reader import read_all_channels
from slack_client import send_dm
import json

CONFIG_PATH = Path(__file__).parent.parent / "config" / "channels.json"


def load_manager_id() -> str:
    config = json.loads(CONFIG_PATH.read_text())
    return config["manager"]["user_id"]


def build_digest(articles: list[dict]) -> str:
    now = datetime.now(tz=timezone.utc)
    today_str = now.strftime("%A, %B %d")

    drafts_waiting = [a for a in articles if a["status"] == "draft_waiting"]
    in_progress = [a for a in articles if a["status"] == "in_progress"]
    revisions = [a for a in articles if a["status"] == "revisions_requested"]
    approved = [a for a in articles if a["status"] == "approved"]
    overdue = [a for a in articles if a["status"] == "overdue"]

    lines = [f"*📋 Content Digest — {today_str}*\n"]

    # --- Drafts waiting on review ---
    if drafts_waiting:
        lines.append("*🔵 Drafts Waiting on Your Review*")
        for a in drafts_waiting:
            waiting = a.get("draft_waiting_days", 0) or 0
            flag = " 🚨 *overdue review*" if waiting > 2 else ""
            lines.append(
                f"• *{a['freelancer']}* — {a['topic']}\n"
                f"  Waiting {waiting:.0f}d{flag} · <{a['thread_link']}|View thread>"
            )
        lines.append("")

    # --- Revisions requested ---
    if revisions:
        lines.append("*🟡 Revisions Requested (Ball in freelancer's court)*")
        for a in revisions:
            lines.append(
                f"• *{a['freelancer']}* — {a['topic']}\n"
                f"  Due: {a['due_date']} · <{a['thread_link']}|View thread>"
            )
        lines.append("")

    # --- In progress ---
    if in_progress:
        lines.append("*🟢 In Progress*")
        for a in in_progress:
            dr = a.get("days_remaining")
            if dr is not None:
                if dr < 0:
                    due_str = f"Due: {a['due_date']} ⚠️ overdue by {abs(dr)}d"
                elif dr == 0:
                    due_str = f"Due: *today*"
                else:
                    due_str = f"Due: {a['due_date']} ({dr}d remaining)"
            else:
                due_str = f"Due: {a['due_date']}"
            lines.append(
                f"• *{a['freelancer']}* — {a['topic']}\n"
                f"  {due_str} · <{a['thread_link']}|View thread>"
            )
        lines.append("")

    # --- Overdue ---
    if overdue:
        lines.append("*🔴 Overdue — No Draft Submitted*")
        for a in overdue:
            lines.append(
                f"• *{a['freelancer']}* — {a['topic']}\n"
                f"  Was due: {a['due_date']} · <{a['thread_link']}|View thread>"
            )
        lines.append("")

    # --- Approved this week ---
    if approved:
        lines.append("*✅ Approved*")
        for a in approved:
            lines.append(f"• *{a['freelancer']}* — {a['topic']}")
        lines.append("")

    if len(lines) == 1:
        lines.append("_Nothing active right now. All clear! 🎉_")

    return "\n".join(lines)


def main():
    print("Reading channels...")
    articles = read_all_channels()
    print(f"Found {len(articles)} assignment thread(s)")

    if not articles:
        print("No assignments found. Sending empty digest.")

    digest_text = build_digest(articles)
    manager_id = load_manager_id()

    print("Sending digest DM...")
    send_dm(manager_id, digest_text)
    print("✓ Digest sent!")
    print("\n--- Preview ---")
    print(digest_text)


if __name__ == "__main__":
    main()
