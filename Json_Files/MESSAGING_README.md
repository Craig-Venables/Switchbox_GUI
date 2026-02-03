# Telegram / Messaging configuration

**Do not put real bot tokens in `messaging_data.json`** (it may be committed to git).

## Secure setup

1. **Recommended**: Copy `messaging_data.json.example` to **`messaging_data.local.json`** and put your real tokens there.  
   `messaging_data.local.json` is gitignored and is loaded in preference to `messaging_data.json`.

2. **Optional**: Set **`MESSAGING_CONFIG_PATH`** to a full path to your config file (e.g. outside the repo).

3. **Optional**: Use environment variables per profile (name sanitized to env key):
   - `TELEGRAM_TOKEN_CRAIG`, `TELEGRAM_CHATID_CRAIG`
   - `TELEGRAM_TOKEN_DAN`, `TELEGRAM_CHATID_DAN`

Format of the JSON file: one object per profile, each with `"token"` and `"chatid"` (or `"chat_id"`).
