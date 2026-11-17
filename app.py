import asyncio
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from pathlib import Path

import qrcode
from PIL import Image, ImageTk
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import ReactionEmoji

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
ENV_FILE = APP_DIR / "config.env"
SESSION_FILE = APP_DIR / "banana_session"
load_dotenv(ENV_FILE)

BG = "#FFF9E8"
PANEL = "#FFFFFF"
INK = "#253018"
MUTED = "#738064"
GREEN = "#315C2B"
LIME = "#D7F36A"
GOLD = "#FFC928"
LINE = "#E8EBD9"


class BananaReactApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BANANA REACT")
        self.root.geometry("900x650")
        self.root.minsize(780, 580)
        self.root.configure(bg=BG)
        self.events = queue.Queue()
        self.loop = None
        self.loop_ready = threading.Event()
        self.client = None
        self.worker = None
        self.dialogs = []
        self.qr_photo = None
        self.password_future = None
        self.connected = False
        self._build_ui()
        self.root.after(150, self._poll_events)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self):
        header = tk.Frame(self.root, bg=GREEN, height=112)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🍌  BANANA REACT", bg=GREEN, fg="#FFFFFF",
                 font=("Segoe UI", 25, "bold")).pack(anchor="w", padx=28, pady=(20, 0))
        tk.Label(header, text="Your Telegram. Your chats. Banana reactions on autopilot.",
                 bg=GREEN, fg="#E6F4D0", font=("Segoe UI", 10)).pack(anchor="w", padx=32, pady=(3, 0))

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=18)

        left = tk.Frame(body, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        left.pack(side="left", fill="y", padx=(0, 16))
        left.configure(width=285)
        left.pack_propagate(False)
        tk.Label(left, text="CONNECTION", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18, pady=(18, 8))
        tk.Label(left, text="Telegram API ID", bg=PANEL, fg=INK,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18)
        self.api_id = tk.StringVar(value=os.getenv("API_ID", ""))
        ttk.Entry(left, textvariable=self.api_id).pack(fill="x", padx=18, pady=(4, 10))
        tk.Label(left, text="Telegram API HASH", bg=PANEL, fg=INK,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18)
        self.api_hash = tk.StringVar(value=os.getenv("API_HASH", ""))
        ttk.Entry(left, textvariable=self.api_hash, show="•").pack(fill="x", padx=18, pady=(4, 12))

        self.connect_btn = tk.Button(left, text="CONNECT TELEGRAM", command=self.connect,
            bg=GOLD, fg=INK, activebackground="#F2B900", relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2", pady=11)
        self.connect_btn.pack(fill="x", padx=18)
        self.status = tk.Label(left, text="●  Not connected", bg=PANEL, fg=MUTED,
                               font=("Segoe UI", 9))
        self.status.pack(anchor="w", padx=18, pady=(12, 6))
        tk.Frame(left, bg=LINE, height=1).pack(fill="x", padx=18, pady=12)
        tk.Label(left, text="QUICK GUIDE", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=18)
        guide = "1. Enter API ID and API HASH\n2. Connect and scan the QR in Telegram\n3. Enter your 2-step password if asked\n4. Choose chats on the right\n5. Switch on banana reactions"
        tk.Label(left, text=guide, bg=PANEL, fg=INK, justify="left",
                 font=("Segoe UI", 9), lineSpacing=7).pack(anchor="w", padx=18, pady=10)
        tk.Label(left, text="Credentials and session stay on this PC.",
                 bg=PANEL, fg=MUTED, wraplength=240, justify="left",
                 font=("Segoe UI", 8)).pack(side="bottom", anchor="w", padx=18, pady=16)

        right = tk.Frame(body, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        right.pack(side="left", fill="both", expand=True)
        top = tk.Frame(right, bg=PANEL)
        top.pack(fill="x", padx=20, pady=(18, 8))
        tk.Label(top, text="Choose your chats", bg=PANEL, fg=INK,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(top, text="Select one or more chats. Only new incoming messages are reacted to.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))

        self.qr_area = tk.Frame(right, bg="#FFFDF5", highlightbackground=LINE, highlightthickness=1)
        self.qr_area.pack(fill="x", padx=20, pady=12)
        self.qr_label = tk.Label(self.qr_area, text="Your Telegram QR code will appear here",
                                 bg="#FFFDF5", fg=MUTED, font=("Segoe UI", 10), pady=30)
        self.qr_label.pack()

        list_frame = tk.Frame(right, bg=PANEL)
        list_frame.pack(fill="both", expand=True, padx=20, pady=(4, 10))
        tk.Label(list_frame, text="YOUR CHATS", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 6))
        self.chat_list = tk.Listbox(list_frame, selectmode=tk.EXTENDED, activestyle="none",
            bg="#FFFDF5", fg=INK, selectbackground="#DDF18B", selectforeground=INK,
            relief="flat", highlightthickness=1, highlightbackground=LINE,
            font=("Segoe UI", 10), exportselection=False)
        self.chat_list.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.chat_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.chat_list.configure(yscrollcommand=scrollbar.set)

        footer = tk.Frame(right, bg=PANEL)
        footer.pack(fill="x", padx=20, pady=(0, 18))
        self.start_btn = tk.Button(footer, text="🍌  ENABLE BANANA REACTIONS",
            command=self.enable_reactions, state="disabled", bg=GREEN, fg="white",
            activebackground="#24451F", relief="flat", font=("Segoe UI", 10, "bold"),
            cursor="hand2", pady=12)
        self.start_btn.pack(fill="x")
        self.stop_btn = tk.Button(footer, text="STOP", command=self.stop_reactions,
            state="disabled", bg="#F1F2EA", fg=INK, relief="flat",
            font=("Segoe UI", 9, "bold"), pady=8)
        self.stop_btn.pack(fill="x", pady=(7, 0))

    def _save_settings(self):
        api_id = self.api_id.get().strip()
        api_hash = self.api_hash.get().strip()
        if not api_id.isdigit() or not api_hash:
            messagebox.showerror("Missing settings", "Enter your API ID and API HASH from my.telegram.org.")
            return False
        ENV_FILE.write_text(f"API_ID={api_id}\nAPI_HASH={api_hash}\n", encoding="utf-8")
        os.environ["API_ID"] = api_id
        os.environ["API_HASH"] = api_hash
        return True

    def _start_worker(self):
        if self.loop and self.loop.is_running():
            return
        def runner():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop_ready.set()
            self.loop.run_forever()
        self.worker = threading.Thread(target=runner, daemon=True)
        self.worker.start()

    def connect(self):
        if self.connected:
            return
        if not self._save_settings():
            return
        self.connect_btn.configure(state="disabled", text="CONNECTING…")
        self.status.configure(text="●  Connecting…", fg="#A07800")
        self._start_worker()
        self.loop_ready.wait(timeout=10)
        asyncio.run_coroutine_threadsafe(self._connect_task(int(self.api_id.get().strip()), self.api_hash.get().strip()), self.loop)

    async def _connect_task(self, api_id, api_hash):
        try:
            self.client = TelegramClient(str(SESSION_FILE), api_id, api_hash)
            await self.client.connect()
            if not await self.client.is_user_authorized():
                qr_login = await self.client.qr_login()
                qr_path = APP_DIR / "login_qr.png"
                while True:
                    qrcode.make(qr_login.url).save(qr_path)
                    self.events.put(("qr", str(qr_path)))
                    try:
                        await qr_login.wait(timeout=35)
                        break
                    except asyncio.TimeoutError:
                        await qr_login.recreate()
                    except SessionPasswordNeededError:
                        future = self.loop.create_future()
                        self.password_future = future
                        self.events.put(("need_password", future))
                        password = await future
                        await self.client.sign_in(password=password)
                        break
            me = await self.client.get_me()
            self.events.put(("connected", getattr(me, "first_name", "Telegram")))
            dialogs = await self.client.get_dialogs()
            self.dialogs = [(d.id, d.name or "Unnamed chat") for d in dialogs]
            self.events.put(("chats", self.dialogs))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def enable_reactions(self):
        selected = self.chat_list.curselection()
        if not selected:
            messagebox.showinfo("Choose chats", "Select at least one chat first.")
            return
        chat_ids = {self.dialogs[i][0] for i in selected}
        asyncio.run_coroutine_threadsafe(self._install_handler(chat_ids), self.loop)

    async def _install_handler(self, chat_ids):
        try:
            if hasattr(self, "_handler"):
                self.client.remove_event_handler(self._handler)
            async def handler(event):
                if event.chat_id not in chat_ids or event.out:
                    return
                try:
                    await self.client(SendReactionRequest(
                        peer=await event.get_input_chat(),
                        msg_id=event.message.id,
                        reaction=[ReactionEmoji(emoticon="🍌")]
                    ))
                    self.events.put(("reaction", event.chat_id))
                except Exception as exc:
                    self.events.put(("notice", f"Reaction failed: {exc}"))
            self._handler = handler
            self.client.add_event_handler(handler, events.NewMessage(incoming=True))
            self.events.put(("active", len(chat_ids)))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def stop_reactions(self):
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self._stop_task(), self.loop)

    async def _stop_task(self):
        if self.client and hasattr(self, "_handler"):
            self.client.remove_event_handler(self._handler)
            del self._handler
        self.events.put(("stopped", None))

    def _poll_events(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "qr":
                    image = Image.open(data)
                    image.thumbnail((190, 190))
                    self.qr_photo = ImageTk.PhotoImage(image)
                    self.qr_label.configure(image=self.qr_photo, text="")
                elif kind == "need_password":
                    self.password_future = data
                    password = simpledialog.askstring("Telegram 2-step verification",
                        "Enter your Telegram 2-step verification password:",
                        show="•", parent=self.root)
                    if password:
                        self.loop.call_soon_threadsafe(data.set_result, password)
                    else:
                        self.loop.call_soon_threadsafe(data.set_exception,
                            RuntimeError("2-step verification was cancelled."))
                elif kind == "connected":
                    self.connected = True
                    self.status.configure(text=f"●  Connected as {data}", fg=GREEN)
                    self.qr_label.configure(image="", text="✓  Telegram connected successfully",
                                            fg=GREEN, font=("Segoe UI", 11, "bold"), pady=24)
                    self.connect_btn.configure(text="CONNECTED", state="disabled")
                elif kind == "chats":
                    self.dialogs = data
                    self.chat_list.delete(0, tk.END)
                    for _, name in data:
                        self.chat_list.insert(tk.END, name)
                    self.start_btn.configure(state="normal")
                elif kind == "active":
                    self.status.configure(text=f"●  Banana reactions ON · {data} chats", fg=GREEN)
                    self.start_btn.configure(state="disabled")
                    self.stop_btn.configure(state="normal")
                elif kind == "stopped":
                    self.status.configure(text="●  Connected · reactions paused", fg=MUTED)
                    self.start_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                elif kind == "reaction":
                    self.status.configure(text="🍌  Reaction sent", fg=GREEN)
                elif kind == "notice":
                    self.status.configure(text=str(data)[:80], fg="#A07800")
                elif kind == "error":
                    self.status.configure(text="●  Connection error", fg="#B42318")
                    self.connect_btn.configure(state="normal", text="TRY AGAIN")
                    messagebox.showerror("BANANA REACT", data)
        except queue.Empty:
            pass
        self.root.after(150, self._poll_events)

    def _close(self):
        if self.loop and self.loop.is_running() and self.client:
            asyncio.run_coroutine_threadsafe(self.client.disconnect(), self.loop)
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = BananaReactApp(root)
    root.mainloop()
