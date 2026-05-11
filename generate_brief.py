"""
Generate a content brief from the command line.

Usage:
    python generate_brief.py "keyword" freelancer_name "due date"

Examples:
    python generate_brief.py "testosterone and heart health" meeba "may 30"
    python generate_brief.py "hormone therapy for women" eilaf "june 10"
    python generate_brief.py "weight loss peptides" noelle "may 25"

The brief will be DMed to you for review.
React 👍 to it or reply "send", then run:
    python approve_briefs.py
"""
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent / "src"))

from brief_generator import generate_brief
from brief_poller import (
    load_config, get_manager_id, find_freelancer,
    format_brief_for_slack, get_dm_channel_id
)
from slack_client import send_dm

STATE_PATH = Path(__file__).parent / "state" / "pending_briefs.json"


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return []


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2))


def main():
    if len(sys.argv) < 4:
        print("Usage: python generate_brief.py \"keyword\" freelancer_name \"due date\"")
        print("Example: python generate_brief.py \"testosterone and heart health\" meeba \"may 30\"")
        sys.exit(1)

    keyword = sys.argv[1]
    freelancer_hint = sys.argv[2]
    due_date = sys.argv[3]

    config = load_config()
    manager_id = get_manager_id()

    freelancer = find_freelancer(config, freelancer_hint)
    if not freelancer:
        print(f"❌ No freelancer found matching '{freelancer_hint}'")
        print(f"Available: {[f['name'] for f in config['freelancers']]}")
        sys.exit(1)

    freelancer_name = freelancer["name"]
    channel_id = freelancer.get("channel_id")

    print(f"Generating brief for: '{keyword}'")
    print(f"Freelancer: {freelancer_name} | Due: {due_date}")
    print("Calling Claude... (this takes ~15 seconds)")

    brief_text = generate_brief(keyword, freelancer_name, due_date)
    formatted = format_brief_for_slack(brief_text, keyword, freelancer_name, due_date)

    # Send to manager DM (split if over Slack limit)
    if len(formatted) > 3900:
        resp = send_dm(manager_id, formatted[:3900] + "\n_(continued...)_")
        brief_ts = resp["ts"]
        send_dm(manager_id, formatted[3900:])
    else:
        resp = send_dm(manager_id, formatted)
        brief_ts = resp["ts"]

    dm_channel_id = get_dm_channel_id(manager_id)

    # Save to pending state
    state = load_state()
    state.append({
        "trigger_ts": brief_ts,
        "brief_ts": brief_ts,
        "dm_channel_id": dm_channel_id,
        "keyword": keyword,
        "freelancer_name": freelancer_name,
        "freelancer_channel_id": channel_id,
        "due_date": due_date,
        "brief_text": brief_text,
        "status": "pending",
    })
    save_state(state)

    print(f"\n✓ Brief sent to your Slack DM!")
    print(f"  React 👍 to it or reply 'send', then run:")
    print(f"  python approve_briefs.py")


if __name__ == "__main__":
    main()
