# Slack Content Bot

Automates content workflow management for freelance writers via Slack.

---

## Prerequisites

- Python 3.11+
- A Slack workspace where you (or an admin) can install apps
- An Anthropic API key from [console.anthropic.com](https://console.anthropic.com)
- A GitHub account (for Actions-based scheduling)

---

## Step 1: Create the Slack App

Have your workspace admin do the following at [api.slack.com/apps](https://api.slack.com/apps):

### 1a. Create the app

1. Click **Create New App** → **From scratch**
2. Name it: `Content Bot`
3. Select workspace: `searchactions`
4. Click **Create App**

### 1b. Add Bot Token Scopes

Go to **OAuth & Permissions** → **Scopes** → **Bot Token Scopes** and add:

| Scope | Why |
|---|---|
| `groups:history` | Read messages in private freelancer channels |
| `groups:read` | List private channels the bot is in |
| `im:history` | Read DMs (for `brief:` trigger + approval flow) |
| `im:read` | List DM channels |
| `im:write` | Open DM conversations to send messages |
| `chat:write` | Post messages to channels and DMs |
| `reactions:read` | Detect 📄 and ✅ reactions |
| `users:read` | Look up freelancer user IDs by name |

### 1c. Install the app

1. **OAuth & Permissions** → **Install to Workspace** → Allow
2. Copy the **Bot User OAuth Token** (starts with `xoxb-`) — you'll need this

### 1d. Add the bot to each freelancer channel

In Slack, open each private channel and invite the bot:
```
/invite @Content Bot
```
Do this for: `#content-eilaf`, `#content-meeba`, `#content-jp`, `#content-noelle`

---

## Step 2: Local setup

```bash
cd slack-content-bot
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — fill in SLACK_BOT_TOKEN and SLACK_MY_USER_ID
```

**Finding your Slack user ID:**
Slack → click your profile photo → View full profile → three-dot menu (⋯) → Copy member ID

### Resolve user IDs (one-time)

```bash
python setup_lookup.py
```

This looks up all freelancer user IDs and channel IDs and saves them to `config/channels.json`. Run it once after the bot is installed.

### Hello world test

```bash
python hello_world.py
```

You should receive a DM from the bot in Slack. If you do, Step 1 is complete.

---

## Step 3: GitHub Actions setup

1. Push this repo to GitHub (can be private)
2. Go to **Settings** → **Secrets and variables** → **Actions**
3. Add these secrets:
   - `SLACK_BOT_TOKEN`
   - `SLACK_MY_USER_ID`
   - `ANTHROPIC_API_KEY`

The workflows in `.github/workflows/` will run automatically on schedule.

---

## Adding a new freelancer

1. Add them to `config/channels.json` following the existing format (leave `user_id` and `channel_id` blank)
2. Create their private channel in Slack and invite the bot: `/invite @Content Bot`
3. Run `python setup_lookup.py` to resolve their IDs
4. Commit and push

---

## Triggering a brief

DM the bot:
```
brief: [keyword] for @[freelancer first name] due [date]
```
Example:
```
brief: hormone optimization for women for @eilaf due nov 20
```

The bot will:
1. Generate a brief using Claude and your template
2. DM it to you as a draft
3. Wait for you to react 👍 or reply `send`
4. Post it to the freelancer's channel as a `📝 Topic` assignment thread

---

## Switching to a new client

1. Create a new company profile file in `config/` (e.g. `company_profile_newclient.txt`)
2. Update `COMPANY_PROFILE_FILE=company_profile_newclient.txt` in your `.env` / GitHub secret
3. No other changes needed
