"""
One-time setup script. Run this after the bot is installed in your workspace.
It resolves all display names → Slack user IDs and channel names → channel IDs,
then writes them back into config/channels.json.

Usage:
    python setup_lookup.py
"""
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent / "src"))
from slack_client import lookup_user_by_display_name, find_channel_id

CONFIG_PATH = Path(__file__).parent / "config" / "channels.json"


def main():
    config = json.loads(CONFIG_PATH.read_text())
    changed = False

    print("Looking up freelancer user IDs and channel IDs...")
    for f in config["freelancers"]:
        name = f["name"]

        if not f.get("user_id"):
            user = lookup_user_by_display_name(f["display_name"])
            if user:
                f["user_id"] = user["id"]
                print(f"  ✓ {name}: user_id = {user['id']}")
                changed = True
            else:
                print(f"  ✗ {name}: could not find user '{f['display_name']}' — check the display_name in channels.json")

        if not f.get("channel_id"):
            ch_id = find_channel_id(f["channel_name"])
            if ch_id:
                f["channel_id"] = ch_id
                print(f"  ✓ {name}: channel_id = {ch_id}")
                changed = True
            else:
                print(f"  ✗ {name}: could not find channel '{f['channel_name']}' — make sure the bot is added to that channel")

    print("\nLooking up manager user ID...")
    mgr = config["manager"]
    if not mgr.get("user_id"):
        user = lookup_user_by_display_name(mgr["display_name"])
        if user:
            mgr["user_id"] = user["id"]
            print(f"  ✓ {mgr['name']}: user_id = {user['id']}")
            changed = True
        else:
            print(f"  ✗ {mgr['name']}: could not find user '{mgr['display_name']}' — check the display_name in channels.json")

    if changed:
        CONFIG_PATH.write_text(json.dumps(config, indent=2))
        print(f"\nSaved to {CONFIG_PATH}")
    else:
        print("\nNo changes needed — all IDs already populated.")

    missing = [
        f["name"] for f in config["freelancers"]
        if not f.get("user_id") or not f.get("channel_id")
    ]
    if not mgr.get("user_id"):
        missing.append(mgr["name"])

    if missing:
        print(f"\n⚠ Still missing IDs for: {', '.join(missing)}")
        print("  You can set them manually in config/channels.json or add the bot to the relevant channels and re-run.")
        sys.exit(1)
    else:
        print("\n✓ All IDs resolved. Ready to run.")


if __name__ == "__main__":
    main()
