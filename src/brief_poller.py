"""
Brief poller — checks your DMs for "brief:" requests and handles the approval flow.

Trigger format (DM the bot):
  brief: [keyword] for @[freelancer first name] due [date]

Example:
  brief: hormone therapy for women for @meeba due may 30

Flow:
  1. Detects "brief:" in your DMs
  2. Generates brief via Claude
  3. DMs you the brief + instructions
  4. On next poll: if you reacted 👍 or replied "send", posts to freelancer channel
  5. Saves state in state/pending_briefs.json

Run via GitHub Actions every 5 minutes.
"""
import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from slack_client import (
    get_dm_history, send_dm, get_reactions,
    post_to_channel, get_client
)
from brief_generator import generate_brief
import slack_client

CONFIG_PATH = Path(__file__).parent.parent / "config" / "channels.json"
STATE_PATH = Path(__file__).parent.parent / "state" / "pending_briefs.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def load_state() -> list:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return []


def save_state(state: list):
    STATE_PATH.write_text(json.dumps(state, indent=2))


def get_manager_id() -> str:
    return load_config()["manager"]["user_id"]


def find_freelancer(config: dict, name_hint: str) -> dict | None:
    """Match freelancer by first name (case-insensitive)."""
    hint = name_hint.lstrip("@").lower()
    for f in config["freelancers"]:
        if f["name"].lower().startswith(hint) or hint in f["name"].lower():
            return f
    return None


def resolve_slack_mention(text: str, config: dict) -> str:
    """Replace <@UID> mentions with the freelancer's name hint."""
    uid_map = {f["user_id"]: f["name"] for f in config["freelancers"] if f.get("user_id")}
    def replace(m):
        uid = m.group(1)
        return uid_map.get(uid, uid)
    return re.sub(r"<@([A-Z0-9]+)>", replace, text)


def parse_brief_request(text: str, config: dict = None) -> dict | None:
    """
    Parses: brief: [keyword] for @[name] due [date]
    Returns dict with keyword, freelancer_hint, due_date or None if no match.
    """
    text = text.strip()
    if not text.lower().startswith("brief:"):
        return None

    # Replace Slack <@UID> mentions with real names before parsing
    if config:
        text = resolve_slack_mention(text, config)

    body = text[6:].strip()

    # Try pattern: "keyword for @name due date"
    m = re.search(
        r"^(.+?)\s+for\s+@?([\w.]+)\s+due\s+(.+)$",
        body,
        re.IGNORECASE,
    )
    if m:
        return {
            "keyword": m.group(1).strip(),
            "freelancer_hint": m.group(2).strip(),
            "due_date": m.group(3).strip(),
        }

    # Fallback: "keyword for @name" with no due date
    m = re.search(r"^(.+?)\s+for\s+@?([\w.]+)$", body, re.IGNORECASE)
    if m:
        return {
            "keyword": m.group(1).strip(),
            "freelancer_hint": m.group(2).strip(),
            "due_date": "TBD",
        }

    return None


def get_dm_channel_id(user_id: str) -> str:
    client = get_client()
    resp = client.conversations_open(users=user_id)
    return resp["channel"]["id"]


def check_approval(dm_channel_id: str, brief_ts: str, manager_id: str) -> str | None:
    """
    Returns 'approved' if manager reacted 👍 or replied 'send'.
    Returns 'rejected' if replied 'cancel'.
    Returns None if no decision yet.
    """
    # Check reactions on the brief message
    reactions = get_reactions(dm_channel_id, brief_ts)
    print(f"    [debug] reactions found: {[r.get('name') for r in reactions]}")
    approved_reactions = {"+1", "thumbsup", "white_check_mark"}
    for r in reactions:
        if r.get("name") in approved_reactions:
            return "approved"

    # Check replies in the DM channel (not thread — DMs don't thread like channels)
    client = get_client()
    # Get recent DM messages and look for approval reply after the brief
    resp = client.conversations_history(channel=dm_channel_id, oldest=brief_ts, limit=20)
    messages = resp.get("messages", [])
    print(f"    [debug] messages after brief: {len(messages)}")
    for msg in messages:
        if msg.get("ts") == brief_ts:
            continue  # skip the brief itself
        if msg.get("user") == manager_id:
            reply_text = msg.get("text", "").strip().lower()
            print(f"    [debug] manager message: '{reply_text}'")
            if reply_text in ("send", "yes", "approve", "approved", "✅"):
                return "approved"
            if reply_text in ("cancel", "no", "reject", "rejected"):
                return "rejected"

    return None


def format_brief_for_slack(brief_text: str, keyword: str, freelancer_name: str, due_date: str) -> str:
    """Wraps the brief with header and approval instructions."""
    header = (
        f"*📝 Brief Draft — {keyword}*\n"
        f"_For: {freelancer_name} | Due: {due_date}_\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    footer = (
        f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"React 👍 to this message or reply `send` to post it to #{freelancer_name.lower()}'s channel.\n"
        f"Reply `cancel` to discard."
    )
    return header + brief_text + footer


def format_assignment_post(keyword: str, freelancer_name: str, due_date: str, brief_text: str) -> str:
    """Formats the final assignment message posted to the freelancer's channel."""
    return (
        f":memo: Topic: {keyword}\n"
        f"Assigned to: {freelancer_name}\n"
        f"Due: {due_date}\n\n"
        f"{brief_text}"
    )


def process_new_requests(manager_id: str, config: dict, state: list, processed_ts: set) -> list:
    """Check DMs for new 'brief:' messages and generate briefs."""
    new_entries = []
    messages = get_dm_history(manager_id, limit=20)

    for msg in messages:
        ts = msg.get("ts", "")
        text = msg.get("text", "")
        sender = msg.get("user", "")

        # Only process messages from the manager (not bot replies)
        if sender != manager_id:
            continue

        # Skip already processed
        if ts in processed_ts:
            continue

        parsed = parse_brief_request(text, config)
        if not parsed:
            continue

        keyword = parsed["keyword"]
        freelancer_hint = parsed["freelancer_hint"]
        due_date = parsed["due_date"]

        freelancer = find_freelancer(config, freelancer_hint)
        if not freelancer:
            send_dm(manager_id, f"❌ Couldn't find a freelancer matching `@{freelancer_hint}`. Check your channels.json.")
            new_entries.append({"trigger_ts": ts, "status": "error"})
            continue

        freelancer_name = freelancer["name"]
        channel_id = freelancer.get("channel_id")

        print(f"  Generating brief: '{keyword}' for {freelancer_name} due {due_date}")
        send_dm(manager_id, f"⏳ Generating brief for *{keyword}*... (this takes ~15 seconds)")

        try:
            brief_text = generate_brief(keyword, freelancer_name, due_date)
        except Exception as e:
            send_dm(manager_id, f"❌ Brief generation failed: {e}")
            new_entries.append({"trigger_ts": ts, "status": "error"})
            continue

        formatted = format_brief_for_slack(brief_text, keyword, freelancer_name, due_date)

        # Slack message limit is 4000 chars — split if needed
        if len(formatted) > 3900:
            resp = send_dm(manager_id, formatted[:3900] + "\n_(continued...)_")
            brief_ts = resp["ts"]
            send_dm(manager_id, formatted[3900:])
        else:
            resp = send_dm(manager_id, formatted)
            brief_ts = resp["ts"]

        dm_channel_id = get_dm_channel_id(manager_id)

        new_entries.append({
            "trigger_ts": ts,
            "brief_ts": brief_ts,
            "dm_channel_id": dm_channel_id,
            "keyword": keyword,
            "freelancer_name": freelancer_name,
            "freelancer_channel_id": channel_id,
            "due_date": due_date,
            "brief_text": brief_text,
            "status": "pending",
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        })
        print(f"  Brief sent to DM. Waiting for approval.")

    return new_entries


def process_pending_approvals(manager_id: str, state: list) -> list:
    """Check pending briefs for approval reactions or replies."""
    updated_state = []

    for entry in state:
        if entry.get("status") != "pending":
            updated_state.append(entry)
            continue

        dm_channel_id = entry.get("dm_channel_id")
        brief_ts = entry.get("brief_ts")
        decision = check_approval(dm_channel_id, brief_ts, manager_id)

        if decision == "approved":
            keyword = entry["keyword"]
            freelancer_name = entry["freelancer_name"]
            freelancer_channel_id = entry["freelancer_channel_id"]
            due_date = entry["due_date"]
            brief_text = entry["brief_text"]

            assignment = format_assignment_post(keyword, freelancer_name, due_date, brief_text)

            # Split if over Slack limit
            if len(assignment) > 3900:
                post_to_channel(freelancer_channel_id, assignment[:3900])
                post_to_channel(freelancer_channel_id, assignment[3900:])
            else:
                post_to_channel(freelancer_channel_id, assignment)

            send_dm(manager_id, f"✅ Brief for *{keyword}* posted to {freelancer_name}'s channel!")
            print(f"  Posted brief '{keyword}' to {freelancer_name}'s channel.")
            entry["status"] = "sent"

        elif decision == "rejected":
            send_dm(manager_id, f"🗑 Brief for *{entry['keyword']}* cancelled.")
            print(f"  Brief '{entry['keyword']}' cancelled.")
            entry["status"] = "cancelled"

        updated_state.append(entry)

    return updated_state


def main():
    config = load_config()
    manager_id = get_manager_id()
    state = load_state()

    # Get all already-processed trigger timestamps
    processed_ts = {e["trigger_ts"] for e in state}

    print("Checking for new brief requests...")
    new_entries = process_new_requests(manager_id, config, state, processed_ts)
    state.extend(new_entries)

    print("Checking pending briefs for approvals...")
    state = process_pending_approvals(manager_id, state)

    # Keep only last 50 entries to avoid unbounded growth
    state = state[-50:]
    save_state(state)

    print("Done.")


if __name__ == "__main__":
    main()
