# Discord Role Manager (Local Script)

A one-shot, local command-line script that adds or removes a Discord role
from every user who reacted to a message, or voted on a poll message.

It is **not** a persistent bot — you run it, it does the job, prints a log,
and exits.

---

## Features

- Add or remove a role based on:
  - Emoji reactions on a message
  - Votes on a Discord poll message
- Works from the command line with simple flags
- Uses environment variables for the bot token (never hardcoded)
- Skips users who already have/don't have the role, without crashing
- Skips bot accounts by default (`--include-bots` to include them)
- Prints a clear summary log of who was added, removed, skipped, or failed

---

## 1. Create a Discord Bot & Get a Token

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application**, give it a name.
3. Go to the **Bot** tab → **Add Bot**.
4. Under **Privileged Gateway Intents**, enable:
   - **Server Members Intent**
5. Click **Reset Token** (or **Copy**) to get your bot token. Keep this secret.
6. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`
   - Bot Permissions: `View Channels`, `Read Message History`, `Manage Roles`
7. Open the generated URL and invite the bot to your test server.
8. **Important:** In your server's role list, drag the bot's role **above**
   the role it needs to manage (Discord only lets a bot manage roles
   ranked below its own highest role).

---

## 2. Get the IDs You Need

Enable Developer Mode in Discord: **User Settings → Advanced → Developer Mode**.

Then right-click to copy:
- **Server ID** (right-click server icon)
- **Message ID** (right-click the message with the reactions/poll)
- **Role ID** (right-click the role in Server Settings → Roles)
- *(Optional)* **Channel ID** — speeds things up; if omitted, the script
  will search all text channels for the message.

---

## 3. Setup

```bash
git clone <this-repo-url>
cd discord-role-script

python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# then open .env and paste your bot token in
```

---

## 4. Usage

```bash
python role_manager.py \
  --guild-id 123456789012345678 \
  --message-id 987654321098765432 \
  --role-id 111222333444555666 \
  --action add
```

To remove the role instead:

```bash
python role_manager.py \
  --guild-id 123456789012345678 \
  --message-id 987654321098765432 \
  --role-id 111222333444555666 \
  --action remove
```

Optional flags:

| Flag              | Description                                                        |
|-------------------|---------------------------------------------------------------------|
| `--channel-id`    | Skip searching every channel by pointing directly to the message's channel |
| `--include-bots`  | Also apply the role change to bot accounts that reacted/voted      |

### Example output

```
Connected. Working in server: My Test Server (123456789012345678)
Found target message (ID: 987654321098765432) in #announcements
Found 5 reactor(s) and 0 poll voter(s) (5 unique user(s) total).

==================================================
RESULTS
==================================================

Role ADDED to 3 user(s):
  + user_one (ID: 111111111111111111)
  + user_two (ID: 222222222222222222)
  + user_three (ID: 333333333333333333)

Skipped 2 user(s) (no change needed):
  ~ user_four (ID: 444444444444444444) — already has the role
  ~ user_five (ID: 555555555555555555) — already has the role

==================================================
Total users processed: 5
==================================================
```

---

## How It Works

1. Logs into Discord with your bot token.
2. Locates the server and the target message (searching all text channels
   if no `--channel-id` is given).
3. Collects every unique user who either reacted to the message with any
   emoji, or voted on any answer if the message is a poll.
4. For each user, checks their current roles and adds/removes the target
   role as needed — skipping anyone who's already in the correct state.
5. Prints a full log, then disconnects and exits.

---

## Notes & Limitations

- The bot's role must be positioned **above** the role it's managing in
  the server's role hierarchy, or role changes will fail with a
  "Missing Permissions" error (this will be logged per-user, not crash
  the script).
- The bot must have `View Channels` and `Read Message History` in the
  channel containing the target message.
- For reactions, Discord only returns users currently in the server
  (if someone reacted then left, they'll be skipped automatically).
- Poll voter fetching requires `discord.py >= 2.4.0`.

---

## License

MIT
