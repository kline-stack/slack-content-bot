"""
Check for approved briefs and post them to the freelancer's channel.

Run this after reacting 👍 or replying "send" to a brief in Slack:
    python approve_briefs.py
"""
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent / "src"))

from brief_poller import (
    load_config, get_manager_id,
    process_pending_approvals
)

STATE_PATH = Path(__file__).parent / "state" / "pending_briefs.json"


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return []


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2))


def main():
    manager_id = get_manager_id()
    state = load_state()

    pending = [e for e in state if e.get("status") == "pending"]
    if not pending:
        print("No pending briefs to approve.")
        return

    print(f"Checking {len(pending)} pending brief(s)...")
    state = process_pending_approvals(manager_id, state)
    save_state(state)


if __name__ == "__main__":
    main()
