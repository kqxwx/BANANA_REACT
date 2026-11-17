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
        self.root.geometry("1040x760")
        self.root.minsize(900, 680)
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
        # Modern dark UI — credentials are loaded silently from config.env.
        BG = "#10131D"
        CARD = "#1A2030"
        CARD2 = "#20283A"
        TEXT = "#F4F7FF"
        MUTED = "#929DB5"
        LIME = "#D7FF4F"
        PURPLE = "#9B8CFF"
        self.root.configure(bg=BG)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Banana.Vertical.TScrollbar",
                        background=CARD2, troughcolor=BG, bordercolor=BG,
                        arrowcolor=TEXT, relief="flat")

        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=28, pady=(22, 16))
        brand = tk.Frame(header, bg=BG)
        brand.pack(side="left", fill="x", expand=True)
        tk.Label(brand, text="🍌  BANANA REACT", bg=BG, fg=TEXT,
                 font=("Segoe UI", 23, "bold")).pack(anchor="w")
        tk.Label(brand, text="YOUR TELEGRAM. YOUR RULES. INSTANT REACTIONS.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(3, 0))
        self.status = tk.Label(header, text="●  OFFLINE", bg=CARD2, fg=MUTED,
                               font=("Segoe UI", 9, "bold"), padx=14, pady=9)
        self.status.pack(side="right", anchor="center")

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=28, pady=(0, 24))

        left = tk.Frame(body, bg=CARD, highlightbackground="#2B3449", highlightthickness=1)
        left.pack(side="left", fill="y", padx=(0, 16))
        left.configure(width=270)
        left.pack_propagate(False)

        tk.Label(left, text="✦  CONTROL CENTER", bg=CARD, fg=LIME,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=20, pady=(22, 16))
        tk.Label(left, text="Ready to go bananas?", bg=CARD, fg=TEXT,
                 font=("Segoe UI", 17, "bold"), wraplength=220,
                 justify="left").pack(anchor="w", padx=20)
        tk.Label(left, text="Connect your Telegram account with a QR code. No phone number entry.",
                 bg=CARD, fg=MUTED, font=("Segoe UI", 9), wraplength=220,
                 justify="left").pack(anchor="w", padx=20, pady=(8, 18))

        self.connect_btn = tk.Button(left, text="  CONNECT TELEGRAM  ↗",
            command=self.connect, bg=LIME, fg="#151A22",
            activebackground="#C6EF3F", activeforeground="#151A22",
            relief="flat", bd=0, font=("Segoe UI", 10, "bold"),
            cursor="hand2", pady=14)
        self.connect_btn.pack(fill="x", padx=20)

        tk.Frame(left, bg="#30394D", height=1).pack(fill="x", padx=20, pady=20)
        tk.Label(left, text="HOW IT WORKS", bg=CARD, fg=PURPLE,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=20, pady=(0, 10))
        steps = [
            ("01", "Connect", "Scan the QR in Telegram"),
            ("02", "Pick chats", "Choose where to react"),
            ("03", "Activate", "Bananas on every new message"),
        ]
        for number, title, desc in steps:
            line = tk.Frame(left, bg=CARD)
            line.pack(fill="x", padx=20, pady=7)
            tk.Label(line, text=number, bg=CARD2, fg=LIME,
                     font=("Segoe UI", 9, "bold"), padx=8, pady=6).pack(side="left", padx=(0, 10))
            words = tk.Frame(line, bg=CARD)
            words.pack(side="left", fill="x", expand=True)
            tk.Label(words, text=title, bg=CARD, fg=TEXT,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w")
            tk.Label(words, text=desc, bg=CARD, fg=MUTED,
                     font=("Segoe UI", 8)).pack(anchor="w")

        tk.Label(left, text="🔒  Session stays on this computer",
                 bg=CARD, fg=MUTED, font=("Segoe UI", 8),
                 wraplength=220, justify="left").pack(side="bottom", anchor="w",
                                                       padx=20, pady=20)

        right = tk.Frame(body, bg=CARD, highlightbackground="#2B3449", highlightthickness=1)
        right.pack(side="left", fill="both", expand=True)

        top = tk.Frame(right, bg=CARD)
        top.pack(fill="x", padx=22, pady=(20, 12))
        tk.Label(top, text="Your workspace", bg=CARD, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(top, text="Choose the chats where BANANA REACT should be active.",
                 bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))

        self.qr_area = tk.Frame(right, bg=CARD2, highlightbackground="#343E55", highlightthickness=1)
        self.qr_area.pack(fill="x", padx=22, pady=(4, 14))
        self.qr_label = tk.Label(self.qr_area,
            text="QR CODE WILL APPEAR HERE\n\nConnect Telegram to get started",
            bg=CARD2, fg=MUTED, font=("Segoe UI", 10), pady=25, justify="center")
        self.qr_label.pack()

        list_frame = tk.Frame(right, bg=CARD)
        list_frame.pack(fill="both", expand=True, padx=22, pady=(0, 12))
        list_head = tk.Frame(list_frame, bg=CARD)
        list_head.pack(fill="x", pady=(0, 8))
        tk.Label(list_head, text="YOUR CHATS", bg=CARD, fg=TEXT,
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Label(list_head, text="MULTI-SELECT", bg=CARD, fg=PURPLE,
                 font=("Segoe UI", 8, "bold")).pack(side="right")

        self.chat_list = tk.Listbox(list_frame, selectmode=tk.EXTENDED, activestyle="none",
            bg="#151B28", fg=TEXT, selectbackground="#39472A", selectforeground=LIME,
            relief="flat", highlightthickness=1, highlightbackground="#30394D",
            font=("Segoe UI", 10), exportselection=False,
            selectborderwidth=0)
        self.chat_list.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical",
                                  command=self.chat_list.yview,
                                  style="Banana.Vertical.TScrollbar")
        scrollbar.pack(side="right", fill="y")
        self.chat_list.configure(yscrollcommand=scrollbar.set)

        footer = tk.Frame(right, bg=CARD)
        footer.pack(fill="x", padx=22, pady=(0, 20))
        self.start_btn = tk.Button(footer, text="🍌   ACTIVATE BANANA REACTIONS",
            command=self.enable_reactions, state="disabled", bg=LIME, fg="#151A22",
            activebackground="#C6EF3F", relief="flat", bd=0,
            font=("Segoe UI", 10, "bold"), cursor="hand2", pady=13)
        self.start_btn.pack(fill="x")
        self.stop_btn = tk.Button(footer, text="PAUSE REACTIONS",
            command=self.stop_reactions, state="disabled", bg=CARD2, fg=TEXT,
            activebackground="#30394D", relief="flat", bd=0,
            font=("Segoe UI", 9, "bold"), pady=10)
        self.stop_btn.pack(fill="x", pady=(8, 0))

    def _save_settings(self):
        # API credentials are not shown in the UI; load them from config.env.
        load_dotenv(ENV_FILE, override=True)
        api_id = os.getenv("API_ID", "").strip()
        api_hash = os.getenv("API_HASH", "").strip()
        if not api_id.isdigit() or not api_hash:
            messagebox.showerror(
                "Configuration missing",
                "Telegram connection settings are not configured. "
                "A config.env file with API_ID and API_HASH must be placed "
                "next to the application. These fields are intentionally hidden."
            )
            return False
        self._api_id_value = api_id
        self._api_hash_value = api_hash
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
        asyncio.run_coroutine_threadsafe(self._connect_task(int(self._api_id_value), self._api_hash_value), self.loop)

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
