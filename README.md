# BANANA REACT 🍌

A Windows desktop user-client for your own Telegram account. Sign in with Telegram QR login, search and select conversations, add 🍌 reactions to the existing message history, and keep reacting to new messages.

## Download

Open **Actions → Build BANANA REACT → latest successful run → Artifacts** and download `BANANA-REACT-Windows`. Extract the ZIP and run `BANANA_REACT.exe`.

## First launch

1. Create a local file named `config.env` in the same folder as `BANANA_REACT.exe`.
2. Add your Telegram API credentials to that file:
   ```env
   API_ID=your_api_id
   API_HASH=your_api_hash
   ```
3. Get the values from https://my.telegram.org. The app does not show these values in its interface. Do not share the file or commit it to GitHub.
4. Click **Connect Telegram**. In Telegram, open **Settings → Devices → Link Desktop Device**, then scan the QR code shown in the app.
5. If Telegram asks for your 2-step verification password, enter it in the app's secure prompt.
6. Search chats by name, select one or more conversations (or select all currently visible results), then activate banana reactions.
7. The app scans the existing history in each selected chat and attempts to add 🍌 to eligible messages. It then keeps reacting to new incoming and outgoing messages while the app remains open.

The Telegram session is stored locally in `banana_session.session` next to the app. Keep this file private. Anyone who obtains it may be able to access your Telegram account. Never upload or send it to anyone.

## Build locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean --windowed --name BANANA_REACT --collect-all telethon --collect-all qrcode --collect-all PIL app.py
```

GitHub Actions builds the Windows package automatically on every push to `main`.

## Notes

- This is a personal Telegram user-client, not a Telegram bot. You do not need to add a bot to chats.
- Reactions are attempted for existing messages in selected chats during the initial history scan, and for new incoming and outgoing messages while the app is running.
- Telegram may reject reactions in chats or on messages where reactions are unavailable, and may temporarily rate-limit large history scans. The app waits when Telegram returns a flood-wait instruction.
- Use the live chat search to filter conversations by name; selection is preserved while you change the search.
- The API credentials and session remain local to your computer. Avoid excessive automation and follow Telegram's terms and each chat's rules.
