"""
Step 1 test: verifies the bot can DM you.
Run: python hello_world.py
Expected: you receive a DM in Slack from the bot.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent / "src"))
from slack_client import send_dm

def main():
    my_user_id = os.environ.get("SLACK_MY_USER_ID")
    if not my_user_id:
        print("ERROR: SLACK_MY_USER_ID is not set in your .env file")
        sys.exit(1)

    print(f"Sending test DM to {my_user_id}...")
    resp = send_dm(my_user_id, "👋 Bot connected! Everything is working. You'll receive your daily digest here.")
    print(f"✓ DM sent. Message timestamp: {resp['ts']}")
    print("Check Slack — you should have a new DM from the bot.")

if __name__ == "__main__":
    main()
