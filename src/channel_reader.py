"""
Reads all 4 freelancer channels and returns structured article status data.
Infers status from thread activity — no manual tracking needed.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from slack_client import get_channel_history, get_thread_replies, get_reactions

CONFIG_PATH = Path(__file__).parent.parent / "config" / "channels.json"
WORKSPACE = "searchactions"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def ts_to_dt(ts: str) -> datetime:
    return datetime.fromtimestamp(float(ts), tz=timezone.utc)


def days_ago(ts: str) -> float:
    dt = ts_to_dt(ts)
    now = datetime.now(tz=timezone.utc)
    return (now - dt).total_seconds() / 86400


def parse_due_date(text: str) -> datetime | None:
    """Extract due date from assignment message text."""
    import re
    # Look for "Due: YYYY-MM-DD" or "Due: Month DD" or "Due: MonDD"
    patterns = [
        r"Due:\s*(\d{4}-\d{2}-\d{2})",
        r"Due:\s*([A-Za-z]+ \d{1,2},?\s*\d{4})",
        r"Due:\s*([A-Za-z]+ \d{1,2})",
        r"Due:\s*([A-Za-z]{3}\d{1,2})",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            for fmt in ("%Y-%m-%d", "%B %d, %Y", "%B %d %Y", "%B %d", "%b%d", "%b %d"):
                try:
                    dt = datetime.strptime(raw, fmt)
                    if dt.year == 1900:
                        dt = dt.replace(year=datetime.now().year)
                    return dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
    return None


def parse_topic(text: str) -> str:
    """Extract topic title from assignment message."""
    import re
    m = re.search(r"(?:📝|:memo:)\s*Topic:\s*(.+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # fallback: first non-empty line
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line[:80]
    return "Untitled"


def has_reaction(reactions: list, emoji: str) -> bool:
    return any(r.get("name") == emoji for r in reactions)


def thread_link(channel_id: str, thread_ts: str) -> str:
    ts_clean = thread_ts.replace(".", "")
    return f"https://{WORKSPACE}.slack.com/archives/{channel_id}/p{ts_clean}"


def infer_status(
    channel_id: str,
    parent_msg: dict,
    replies: list,
    manager_user_id: str,
) -> dict:
    """
    Returns a status dict with keys:
      status: "approved" | "draft_waiting" | "revisions_requested" |
              "overdue" | "in_progress"
      draft_ts: timestamp of the draft message (if any)
      draft_waiting_days: how long draft has been waiting (if applicable)
    """
    parent_ts = parent_msg["ts"]
    parent_reactions = get_reactions(channel_id, parent_ts)

    # ✅ on parent = approved
    if has_reaction(parent_reactions, "white_check_mark"):
        return {"status": "approved", "draft_ts": None, "draft_waiting_days": None}

    # Find the last 📄 reaction on any reply
    last_draft_ts = None
    last_draft_idx = -1
    for i, reply in enumerate(replies):
        reply_reactions = get_reactions(channel_id, reply["ts"])
        if has_reaction(reply_reactions, "page_facing_up"):
            last_draft_ts = reply["ts"]
            last_draft_idx = i

    # Check if manager replied AFTER the last draft
    if last_draft_ts is not None:
        manager_replied_after = any(
            r.get("user") == manager_user_id and float(r["ts"]) > float(last_draft_ts)
            for r in replies
        )
        if manager_replied_after:
            return {"status": "revisions_requested", "draft_ts": last_draft_ts,
                    "draft_waiting_days": None}
        else:
            waiting_days = days_ago(last_draft_ts)
            return {"status": "draft_waiting", "draft_ts": last_draft_ts,
                    "draft_waiting_days": round(waiting_days, 1)}

    # No draft yet — check if overdue
    due_date = parse_due_date(parent_msg.get("text", ""))
    if due_date:
        now = datetime.now(tz=timezone.utc)
        if now > due_date:
            return {"status": "overdue", "draft_ts": None, "draft_waiting_days": None}

    return {"status": "in_progress", "draft_ts": None, "draft_waiting_days": None}


def is_assignment_message(text: str) -> bool:
    has_emoji = "📝" in text or ":memo:" in text
    return has_emoji and "Topic:" in text


def read_all_channels() -> list[dict]:
    """
    Returns a list of article dicts across all freelancer channels.
    Each dict: {freelancer, topic, status, due_date, thread_ts,
                channel_id, thread_link, draft_waiting_days}
    """
    config = load_config()
    manager_id = config["manager"]["user_id"]
    articles = []

    for f in config["freelancers"]:
        channel_id = f.get("channel_id")
        if not channel_id:
            print(f"  Skipping {f['name']} — no channel_id")
            continue

        messages = get_channel_history(channel_id, limit=200)

        for msg in messages:
            text = msg.get("text", "")
            if not is_assignment_message(text):
                continue

            thread_ts = msg["ts"]
            replies = get_thread_replies(channel_id, thread_ts)
            status_info = infer_status(channel_id, msg, replies, manager_id)
            due_date = parse_due_date(text)
            topic = parse_topic(text)

            days_remaining = None
            if due_date:
                now = datetime.now(tz=timezone.utc)
                days_remaining = (due_date - now).days

            articles.append({
                "freelancer": f["name"],
                "topic": topic,
                "status": status_info["status"],
                "due_date": due_date.strftime("%b %d") if due_date else "No date set",
                "days_remaining": days_remaining,
                "draft_waiting_days": status_info.get("draft_waiting_days"),
                "thread_ts": thread_ts,
                "channel_id": channel_id,
                "thread_link": thread_link(channel_id, thread_ts),
            })

    return articles
