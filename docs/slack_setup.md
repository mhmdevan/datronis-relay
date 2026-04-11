# datronis-relay — Slack Setup Walkthrough (v0.3.0)

Phase 3 adds a Slack adapter using **Bolt Socket Mode**. Socket Mode opens an outbound websocket from your bot host to Slack, so you don't need a public webhook URL — it works behind NAT and in typical self-hosted deployments, just like the Telegram long-polling adapter.

This guide walks you from zero to `/help` replying in a Slack DM.

---

## 1. Create the Slack app

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps) and click **Create New App** → **From scratch**.
2. Name it (e.g. `datronis-relay`) and pick the target workspace.
3. Click **Create App**.

---

## 2. Enable Socket Mode

1. In the left sidebar, open **Settings → Socket Mode**.
2. Toggle **Enable Socket Mode** → **On**.
3. Slack prompts for an **App-Level Token**:
   - Name it `datronis-relay-socket`.
   - Add the scope **`connections:write`**.
   - Click **Generate**.
4. Copy the token — it starts with **`xapp-`**. This is your `slack.app_token` in `config.yaml`.

---

## 3. Configure Bot Token Scopes

1. In the sidebar, open **Features → OAuth & Permissions**.
2. Scroll to **Scopes → Bot Token Scopes** and add these:

| Scope | Why |
|---|---|
| `app_mentions:read` | Receive `@datronis-relay` mentions |
| `chat:write` | Reply with `say(...)` |
| `im:history` | Read DM history (required for the `message.im` event) |
| `im:read` | List DM conversations |
| `im:write` | Open DMs back to the user |
| `users:read` | Resolve Slack user ids (optional; useful for display names later) |

3. Scroll up and click **Install to Workspace** → **Allow**.
4. Back on the same page, copy the **Bot User OAuth Token** — it starts with **`xoxb-`**. This is your `slack.bot_token` in `config.yaml`.

---

## 4. Subscribe to bot events

1. In the sidebar, open **Features → Event Subscriptions**.
2. Toggle **Enable Events** → **On**.
   (Socket Mode replaces the Request URL — you don't need to fill one in.)
3. Under **Subscribe to bot events**, add:
   - **`app_mention`** — so channel mentions reach the bot
   - **`message.im`** — so direct messages reach the bot
4. Click **Save Changes**.
5. If Slack prompts you to reinstall the app, do it — new scopes + events need a reinstall.

---

## 5. Get your Slack user id (for the allowlist)

datronis-relay's `users[].id` must be in the form `slack:<user_id>`.

1. In the Slack client, click your profile picture → **Profile**.
2. Click the **⋯ More** menu → **Copy member ID**.
3. The id looks like `U0XXXXXXX` (or `W…` in Enterprise Grid).

Add it to `config.yaml`:

```yaml
users:
  - id: "slack:U0XXXXXXX"
    display_name: "Mohammad"
    allowed_tools: ["Read", "Bash"]
    rate_limit:
      per_minute: 20
      per_day: 1000
```

---

## 6. Wire the tokens into `config.yaml`

```yaml
slack:
  enabled: true
  bot_token: "xoxb-..."
  app_token: "xapp-..."
```

Or keep them out of the YAML file and use env vars (recommended for production):

```env
DATRONIS_SLACK_BOT_TOKEN=xoxb-...
DATRONIS_SLACK_APP_TOKEN=xapp-...
```

Setting either env var **also flips `slack.enabled` to true**, so you don't need to edit the YAML at all for a tokens-in-env deployment.

---

## 7. Start the bot

```bash
datronis-relay
```

You should see two log lines:

```json
{"event": "adapter.enabled", "adapter": "telegram", ...}
{"event": "adapter.enabled", "adapter": "slack", ...}
{"event": "slack.adapter.start", ...}
```

If Slack rejects the token you'll see an error from `slack_bolt` with the correlation id.

---

## 8. Try it

1. In Slack, open a DM with your bot and send `/help`.
2. You should get the same reply the Telegram bot gives.
3. In a channel where the bot has been invited, send `@datronis-relay explain WAL mode` — the mention is stripped and the remainder becomes the prompt.

### Known v0.3 limitations

- **Markdown formatting.** Claude emits standard Markdown; Slack uses `mrkdwn` which is subtly different (`*bold*` vs `**bold**`, link format). v0.3 sends plain text on both platforms — you may see `**bold**` literally in the reply. Per-platform formatting lands in Phase 4.
- **No typing indicator.** Slack's Socket Mode doesn't expose a first-class typing API we can drive from the bot. Telegram still gets the 4-second typing loop.
- **Channel messages without a mention are ignored.** Only direct messages (`message.im`) and mentions (`app_mention`) reach the pipeline. Ambient channel chatter stays out of scope — you almost never want a chat-ops bot accidentally running commands from a conversation it wasn't explicitly addressed in.

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `not_authed` error on startup | The `xoxb-` token is wrong or the app isn't installed to the workspace | Reinstall the app at **OAuth & Permissions → Install to Workspace** |
| Nothing happens when I DM the bot | `message.im` event isn't subscribed, or the app wasn't reinstalled after adding the event | Add `message.im` under **Event Subscriptions → Subscribe to bot events**, reinstall |
| `[AUTH]` reply in Slack | Your Slack user id isn't in `users[]` (or it's missing the `slack:` prefix) | Add `slack:U0XXXXXXX` to `config.yaml` |
| Bolt closes with `missing_scope` | A scope wasn't granted before install | Add the missing scope, reinstall |
| `slack_bolt.error.BoltError: failed to establish socket` | The `xapp-` token is missing `connections:write`, or the token is malformed | Regenerate at **Socket Mode → App-Level Tokens** with the correct scope |
