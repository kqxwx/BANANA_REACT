# BANANA REACT 🍌

Windows desktop app that signs in to your own Telegram account using Telegram QR login, lets you choose chats, and automatically adds 🍌 to incoming messages in those chats.

## Download

After the GitHub Actions build finishes, open **Actions → Build BANANA REACT → latest successful run → Artifacts** and download `BANANA-REACT-Windows`. Extract the ZIP and run `BANANA_REACT.exe`.

## First launch

1. Get your Telegram API ID and API hash from https://my.telegram.org.
2. Enter them in the app's settings. They are saved locally in `config.env` next to the executable and are not uploaded anywhere by this project.
3. Click **Connect Telegram**, then scan the QR in Telegram → Settings → Devices → Link Desktop Device.
4. If Telegram asks for your 2-step verification password, enter it in the app.
5. Select chats and click **Enable banana reactions**.

The Telegram session is stored locally in `banana_session.session` next to the app. Keep this file private. Anyone who obtains it may be able to access your Telegram account. Do not upload it or send it to anyone.

## Build locally

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean --windowed --name BANANA_REACT --collect-all telethon --collect-all qrcode --collect-all PIL app.py
```

The GitHub Actions workflow builds the Windows executable automatically on each push to `main`.

## Notes

- This is a user-account client, not a Telegram bot. No bot needs to be added to chats.
- Reactions are sent only to new incoming messages in chats you select.
- Respect Telegram's terms and the rules of each chat. Avoid excessive automation.
