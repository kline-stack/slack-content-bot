"""
Debug script — prints the raw messages the bot sees in each channel.
Run: python debug_channel.py
"""
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent / "src"))
from slack_client import get_channel_history

CONFIG_PATH = Path(__file__).parent / "config" / "channels.json"
config = json.loads(CONFIG_PATH.read_text())

for f in config["freelancers"]:
    channel_id = f.get("channel_id")
    name = f["name"]
    print(f"\n{'='*50}")
    print(f"Channel: #{f['channel_name']} ({channel_id})")
    print(f"{'='*50}")

    if not channel_id:
        print("  No channel_id — skipping")
        continue

    try:
        messages = get_channel_history(channel_id, limit=20)
        if not messages:
            print("  No messages found")
        for msg in messages:
            text = msg.get("text", "")
            ts = msg.get("ts", "")
            user = msg.get("user", "bot")
            # Show first 200 chars of each message
            preview = repr(text[:200])
            has_emoji = "📝" in text
            has_topic = "Topic:" in text
            print(f"\n  [{ts}] user={user}")
            print(f"  text={preview}")
            print(f"  has_📝={has_emoji}  has_Topic={has_topic}")
    except Exception as e:
        print(f"  ERROR: {e}")
