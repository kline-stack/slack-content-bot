"""
Deadline reminders — posts directly to each freelancer's private channel.
Checks all 4 channels and sends reminders based on due date and draft status.

Reminder types:
  - 2 days before due: friendly nudge
  - Day of: due today notice
  - 1 day overdue with no draft: check-in

Run manually: python src/reminders.py
Run via GitHub Actions: on cron schedule
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from channel_reader import read_all_channels
from slack_client import post_to_channel
import json

CONFIG_PATH = Path(__file__).parent.parent / "config" / "channels.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def get_channel_id_for_freelancer(config: dict, name: str) -> str | None:
    for f in config["freelancers"]:
        if f["name"].lower() == name.lower():
            return f.get("channel_id")
    return None


def build_reminder(reminder_type: str, freelancer: str, topic: str, due_date: str) -> str:
    first_name = freelancer.split()[0]

    if reminder_type == "2_days":
        return (
            f"Hey {first_name}! Just a heads up — your draft for *{topic}* is due in 2 days ({due_date}). "
            f"Let me know if you need anything! 🙌"
        )
    elif reminder_type == "due_today":
        return (
            f"Hi {first_name}! Your draft for *{topic}* is due today. "
            f"Looking forward to reading it! 📄"
        )
    elif reminder_type == "overdue":
        return (
            f"Hey {first_name}, just checking in on *{topic}* — it was due yesterday and I don't see a draft yet. "
            f"Update on this task? Do you need help to finish it? 😊"
        )
    return ""


def check_and_send_reminders():
    config = load_config()
    articles = read_all_channels()
    now = datetime.now(tz=timezone.utc)
    sent = 0

    for article in articles:
        status = article["status"]
        freelancer = article["freelancer"]
        topic = article["topic"]
        due_date_str = article["due_date"]
        days_remaining = article.get("days_remaining")
        channel_id = get_channel_id_for_freelancer(config, freelancer)

        if not channel_id:
            print(f"  Skipping {freelancer} — no channel_id")
            continue

        # Skip approved articles
        if status == "approved":
            continue

        # Skip if no due date
        if days_remaining is None:
            continue

        reminder_type = None

        if days_remaining == 2 and status in ("in_progress", "revisions_requested"):
            reminder_type = "2_days"
        elif days_remaining == 0 and status in ("in_progress", "revisions_requested"):
            reminder_type = "due_today"
        elif days_remaining == -1 and status in ("in_progress", "overdue"):
            reminder_type = "overdue"

        if reminder_type:
            msg = build_reminder(reminder_type, freelancer, topic, due_date_str)
            print(f"  Sending '{reminder_type}' reminder to {freelancer} for '{topic}'")
            post_to_channel(channel_id, msg)
            sent += 1

    return sent


def main():
    print("Checking deadlines and sending reminders...")
    sent = check_and_send_reminders()
    if sent == 0:
        print("No reminders needed today.")
    else:
        print(f"✓ Sent {sent} reminder(s).")


if __name__ == "__main__":
    main()
