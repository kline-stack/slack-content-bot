import os
import json
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

_client = None

def get_client() -> WebClient:
    global _client
    if _client is None:
        token = os.environ.get("SLACK_BOT_TOKEN")
        if not token:
            raise ValueError("SLACK_BOT_TOKEN environment variable is not set")
        _client = WebClient(token=token)
    return _client


def send_dm(user_id: str, text: str, blocks: list = None) -> dict:
    client = get_client()
    resp = client.conversations_open(users=user_id)
    channel_id = resp["channel"]["id"]
    kwargs = {"channel": channel_id, "text": text}
    if blocks:
        kwargs["blocks"] = blocks
    return client.chat_postMessage(**kwargs)


def send_dm_reply(user_id: str, thread_ts: str, text: str) -> dict:
    client = get_client()
    resp = client.conversations_open(users=user_id)
    channel_id = resp["channel"]["id"]
    return client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=text)


def post_to_channel(channel_id: str, text: str, blocks: list = None) -> dict:
    client = get_client()
    kwargs = {"channel": channel_id, "text": text}
    if blocks:
        kwargs["blocks"] = blocks
    return client.chat_postMessage(**kwargs)


def post_reply(channel_id: str, thread_ts: str, text: str) -> dict:
    client = get_client()
    return client.chat_postMessage(channel=channel_id, thread_ts=thread_ts, text=text)


def get_channel_history(channel_id: str, limit: int = 100) -> list:
    client = get_client()
    resp = client.conversations_history(channel=channel_id, limit=limit)
    return resp.get("messages", [])


def get_thread_replies(channel_id: str, thread_ts: str) -> list:
    client = get_client()
    resp = client.conversations_replies(channel=channel_id, ts=thread_ts)
    messages = resp.get("messages", [])
    return messages[1:] if len(messages) > 1 else []


def get_reactions(channel_id: str, message_ts: str) -> list:
    client = get_client()
    try:
        resp = client.reactions_get(channel=channel_id, timestamp=message_ts)
        return resp.get("message", {}).get("reactions", [])
    except SlackApiError:
        return []


def lookup_user_by_display_name(display_name: str) -> dict | None:
    client = get_client()
    resp = client.users_list()
    members = resp.get("members", [])
    name_lower = display_name.lower()
    for member in members:
        profile = member.get("profile", {})
        if (
            member.get("name", "").lower() == name_lower
            or profile.get("display_name", "").lower() == name_lower
            or profile.get("real_name", "").lower() == name_lower
        ):
            return member
    return None


def get_dm_history(user_id: str, limit: int = 50) -> list:
    client = get_client()
    resp = client.conversations_open(users=user_id)
    channel_id = resp["channel"]["id"]
    resp2 = client.conversations_history(channel=channel_id, limit=limit)
    return resp2.get("messages", [])


def find_channel_id(channel_name: str) -> str | None:
    client = get_client()
    name = channel_name.lstrip("#")
    cursor = None
    while True:
        kwargs = {"types": "private_channel,public_channel", "limit": 200}
        if cursor:
            kwargs["cursor"] = cursor
        resp = client.conversations_list(**kwargs)
        for ch in resp.get("channels", []):
            if ch.get("name") == name:
                return ch["id"]
        meta = resp.get("response_metadata", {})
        cursor = meta.get("next_cursor")
        if not cursor:
            break
    return None
