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
from telethon import TelegramClient, events, utils
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import ReactionEmoji

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
ENV_FILE = APP_DIR / "config.env"
SESSION_FILE = APP_DIR / "banana_session"

# Gen Z palette: midnight graphite, acid lime, electric violet
BG = "#0D1014"
SURFACE = "#151A20"
SURFACE_ALT = "#1C232C"
SURFACE_SOFT = "#252E39"
TEXT = "#F4F7F2"
MUTED = "#9AA6B2"
GOLD = "#C7F36B"
GOLD_HOVER = "#D9FF83"
GREEN = "#A7E58B"
RED = "#FF7D87"
BORDER = "#303B47"
VIOLET = "#A78BFA"
CYAN = "#67E8F9"


class BananaReactApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BANANA REACT — Telegram reactions")
        self.root.geometry("1180x820")
        self.root.minsize(1020, 740)
        self.root.configure(bg=BG)

        self.events = queue.Queue()
        self.loop = None
        self.loop_ready = threading.Event()
        self.client = None
        self.worker = None
        self.dialogs = []
        self.visible_dialog_indices = []
        self.search_var = tk.StringVar()
        self.qr_photo = None
        self.connected = False
        self.reactions_active = False
        self._pulse_on = False
        self._build_ui()
        self.root.after(120, self._poll_events)
        self.root.after(700, self._animate)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _label(self, parent, text, size=10, color=TEXT, weight="normal", **kwargs):
        return tk.Label(parent, text=text, bg=kwargs.pop("bg", parent.cget("bg")),
                        fg=color, font=("Segoe UI", size, weight), **kwargs)

    def _button(self, parent, text, command, primary=False, **kwargs):
        bg = GOLD if primary else SURFACE_SOFT
        fg = "#17191E" if primary else TEXT
        hover = GOLD_HOVER if primary else "#303642"
        btn = tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                        activebackground=hover, activeforeground=fg,
                        disabledforeground="#666B75", relief="flat", bd=0,
                        font=("Segoe UI", 10, "bold"), cursor="hand2",
                        padx=18, pady=12, highlightthickness=0, **kwargs)
        btn.bind("<Enter>", lambda _e: btn.configure(bg=hover) if btn["state"] != "disabled" else None)
        btn.bind("<Leave>", lambda _e: btn.configure(bg=bg) if btn["state"] != "disabled" else None)
        return btn

    def _card(self, parent, **kwargs):
        return tk.Frame(parent, bg=SURFACE, highlightbackground=BORDER,
                        highlightthickness=1, **kwargs)

    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=34, pady=(27, 23))

        brand = tk.Frame(header, bg=BG)
        brand.pack(side="left")
        mark = tk.Canvas(brand, width=42, height=42, bg=BG, highlightthickness=0)
        mark.pack(side="left", padx=(0, 12))
        mark.create_oval(2, 2, 40, 40, fill="#29251B", outline="#51452A", width=1)
        mark.create_text(21, 21, text="🍌", font=("Segoe UI Emoji", 19))
        titlebox = tk.Frame(brand, bg=BG)
        titlebox.pack(side="left")
        self._label(titlebox, "BANANA REACT", 22, TEXT, "bold").pack(anchor="w")
        self._label(titlebox, "YOUR TELEGRAM. YOUR VIBE. 🍌", 9, GOLD, "bold").pack(anchor="w", pady=(3, 0))

        righthead = tk.Frame(header, bg=BG)
        righthead.pack(side="right", anchor="center")
        self.status_dot = tk.Label(righthead, text="●", bg=BG, fg="#777D89", font=("Segoe UI", 10))
        self.status_dot.pack(side="left", padx=(0, 8))
        self.status = self._label(righthead, "NOT CONNECTED", 9, MUTED, "bold", bg=BG)
        self.status.pack(side="left")

        # Main columns
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=34, pady=(0, 30))
        body.grid_columnconfigure(0, weight=4, uniform="main")
        body.grid_columnconfigure(1, weight=6, uniform="main")
        body.grid_rowconfigure(0, weight=1)

        # Left column: welcome + connection
        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        hero = self._card(left)
        hero.pack(fill="x")
        self._label(hero, "AUTOMATE THE VIBE", 9, GOLD, "bold").pack(anchor="w", padx=23, pady=(23, 12))
        self._label(hero, "Every chat.\nMore 🍌 energy.", 27, TEXT, "bold", justify="left").pack(anchor="w", padx=23)
        self._label(hero, "Your personal Telegram sidekick. Pick the chats, switch it on, and let the reactions roll.", 10, MUTED, wraplength=330, justify="left").pack(anchor="w", padx=23, pady=(12, 21))
        self.connect_btn = self._button(hero, "Connect Telegram  ↗", self.connect, primary=True)
        self.connect_btn.pack(fill="x", padx=23, pady=(0, 22))

        # Connection guide
        guide = self._card(left)
        guide.pack(fill="x", pady=(14, 0))
        self._label(guide, "THE QUICK SETUP", 9, TEXT, "bold").pack(anchor="w", padx=21, pady=(19, 13))
        steps = [
            ("01", "Connect", "Scan the QR code in Telegram"),
            ("02", "Choose chats", "Select where reactions belong"),
            ("03", "Go live", "History + new messages get 🍌"),
        ]
        for num, name, desc in steps:
            line = tk.Frame(guide, bg=SURFACE)
            line.pack(fill="x", padx=20, pady=7)
            chip = tk.Label(line, text=num, bg="#302B20", fg=GOLD,
                            font=("Segoe UI", 8, "bold"), padx=9, pady=7)
            chip.pack(side="left", padx=(0, 12))
            words = tk.Frame(line, bg=SURFACE)
            words.pack(side="left", fill="x", expand=True)
            self._label(words, name, 10, TEXT, "bold").pack(anchor="w")
            self._label(words, desc, 8, MUTED).pack(anchor="w", pady=(2, 0))
        self._label(guide, "⌁  Your login session stays on this PC.", 8, MUTED).pack(anchor="w", padx=21, pady=(15, 19))

        # Right column workspace
        right = self._card(body)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(2, weight=1)
        right.grid_columnconfigure(0, weight=1)

        workspace_head = tk.Frame(right, bg=SURFACE)
        workspace_head.grid(row=0, column=0, sticky="ew", padx=23, pady=(21, 13))
        self._label(workspace_head, "Workspace", 17, TEXT, "bold").pack(anchor="w")
        self._label(workspace_head, "Your connected account and selected conversations.", 9, MUTED).pack(anchor="w", pady=(4, 0))

        # QR / account state panel
        self.qr_area = tk.Frame(right, bg=SURFACE_ALT, highlightbackground=BORDER, highlightthickness=1, height=225)
        self.qr_area.grid(row=1, column=0, sticky="ew", padx=23, pady=(0, 17))
        self.qr_area.grid_propagate(False)
        self.qr_label = tk.Label(self.qr_area, text="QR LOGIN", bg=SURFACE_ALT, fg=GOLD,
                                 font=("Segoe UI", 9, "bold"), justify="center")
        self.qr_label.pack(expand=True, fill="both", pady=12)
        self.qr_hint = self._label(self.qr_area, "Your secure Telegram sign-in will appear here.", 8, MUTED, bg=SURFACE_ALT)
        self.qr_hint.place(relx=0.5, rely=0.87, anchor="center")

        # Chat list
        chats = tk.Frame(right, bg=SURFACE)
        chats.grid(row=2, column=0, sticky="nsew", padx=23)
        chats.grid_rowconfigure(2, weight=1)
        chats.grid_columnconfigure(0, weight=1)
        chathead = tk.Frame(chats, bg=SURFACE)
        chathead.grid(row=0, column=0, sticky="ew", pady=(0, 9))
        self._label(chathead, "YOUR CHATS", 10, TEXT, "bold").pack(side="left")
        self.chat_count = self._label(chathead, "NOT LOADED", 8, GOLD, "bold")
        self.chat_count.pack(side="right")

        search_wrap = tk.Frame(chats, bg=SURFACE_ALT, highlightbackground=BORDER, highlightthickness=1)
        search_wrap.grid(row=1, column=0, sticky="ew", pady=(0, 9))
        self._label(search_wrap, "⌕", 18, GOLD, "bold", bg=SURFACE_ALT).pack(side="left", padx=(12, 7), pady=5)
        self.search_entry = tk.Entry(
            search_wrap, textvariable=self.search_var, bg=SURFACE_ALT, fg=TEXT,
            insertbackground=GOLD, relief="flat", bd=0, font=("Segoe UI", 11),
            highlightthickness=0
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 12), pady=10)
        self.search_entry.insert(0, "Search chats by name…")
        self.search_entry.configure(fg=MUTED)
        self.search_entry.bind("<FocusIn>", self._search_focus_in)
        self.search_entry.bind("<FocusOut>", self._search_focus_out)
        self.search_var.trace_add("write", self._filter_chats)

        listwrap = tk.Frame(chats, bg=SURFACE_ALT, highlightbackground=BORDER, highlightthickness=1)
        listwrap.grid(row=2, column=0, sticky="nsew")
        listwrap.grid_rowconfigure(0, weight=1)
        listwrap.grid_columnconfigure(0, weight=1)
        self.chat_list = tk.Listbox(listwrap, selectmode=tk.EXTENDED, activestyle="none",
            bg=SURFACE_ALT, fg=TEXT, selectbackground="#51452A", selectforeground=GOLD,
            relief="flat", highlightthickness=0, font=("Segoe UI", 10),
            exportselection=False, selectborderwidth=0, borderwidth=0)
        self.chat_list.grid(row=0, column=0, sticky="nsew", padx=10, pady=8)
        scroll = ttk.Scrollbar(listwrap, orient="vertical", command=self.chat_list.yview)
        scroll.grid(row=0, column=1, sticky="ns", pady=8, padx=(0, 5))
        self.chat_list.configure(yscrollcommand=scroll.set)
        self.chat_list.insert(tk.END, "Connect Telegram to load your chats")

        # Action bar
        selection_bar = tk.Frame(right, bg=SURFACE)
        selection_bar.grid(row=3, column=0, sticky="ew", padx=23, pady=(10, 0))
        self._button(selection_bar, "Select visible", self._select_visible).pack(side="left")
        self._button(selection_bar, "Clear", self._clear_selection).pack(side="left", padx=(8, 0))

        actions = tk.Frame(right, bg=SURFACE)
        actions.grid(row=4, column=0, sticky="ew", padx=23, pady=(12, 21))
        self.start_btn = self._button(actions, "🍌   Activate reactions", self.enable_reactions, primary=True)
        self.start_btn.pack(fill="x")
        self.start_btn.configure(state="disabled")
        self.stop_btn = self._button(actions, "Pause reactions", self.stop_reactions)
        self.stop_btn.pack(fill="x", pady=(8, 0))
        self.stop_btn.configure(state="disabled")

        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill="x", padx=35, pady=(0, 13))
        self._label(footer, "BANANA REACT  /  PERSONAL TELEGRAM CLIENT", 8, "#686E79", "bold").pack(side="left")
        self._label(footer, "PRIVATE SESSION  •  LOCAL STORAGE", 8, "#686E79", "bold").pack(side="right")

    def _search_focus_in(self, _event=None):
        if self.search_entry.get() == "Search chats by name…":
            self.search_entry.delete(0, tk.END)
            self.search_entry.configure(fg=TEXT)

    def _search_focus_out(self, _event=None):
        if not self.search_entry.get().strip():
            self.search_entry.insert(0, "Search chats by name…")
            self.search_entry.configure(fg=MUTED)

    def _filter_chats(self, *_args):
        if not hasattr(self, "chat_list"):
            return
        query = self.search_var.get().strip().lower()
        if query == "search chats by name…":
            query = ""
        self._render_chat_list(query)

    def _render_chat_list(self, query=""):
        selected_ids = set()
        if hasattr(self, "visible_dialog_indices"):
            for row in self.chat_list.curselection():
                if row < len(self.visible_dialog_indices):
                    selected_ids.add(self.dialogs[self.visible_dialog_indices[row]][0])
        self.visible_dialog_indices = [
            i for i, (_chat_id, name) in enumerate(self.dialogs)
            if query in name.lower()
        ]
        self.chat_list.delete(0, tk.END)
        for i in self.visible_dialog_indices:
            chat_id, name = self.dialogs[i]
            self.chat_list.insert(tk.END, "  " + name)
            if chat_id in selected_ids:
                self.chat_list.selection_set(tk.END)
        if hasattr(self, "chat_count"):
            total = len(self.dialogs)
            shown = len(self.visible_dialog_indices)
            self.chat_count.configure(text=f"{shown}/{total} CHATS" if query else f"{total} CHATS")

    def _select_visible(self):
        if self.visible_dialog_indices:
            self.chat_list.selection_set(0, tk.END)

    def _clear_selection(self):
        self.chat_list.selection_clear(0, tk.END)

    def _set_status(self, text, color=MUTED):
        self.status.configure(text=text.upper(), fg=color)

    def _save_settings(self):
        load_dotenv(ENV_FILE, override=True)
        api_id = os.getenv("API_ID", "").strip()
        api_hash = os.getenv("API_HASH", "").strip()
        if not api_id.isdigit() or not api_hash:
            messagebox.showerror(
                "Setup required",
                "Telegram API settings were not found.\n\n"
                "Create config.env next to BANANA_REACT.exe with these two lines:\n"
                "API_ID=your_api_id\nAPI_HASH=your_api_hash\n\n"
                "Get them from https://my.telegram.org.\n"
                "The values are never displayed in the app or uploaded by it."
            )
            return False
        self._api_id_value = api_id
        self._api_hash_value = api_hash
        return True

    def _start_worker(self):
        if self.loop and self.loop.is_running():
            return
        self.loop_ready.clear()
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
        self.connect_btn.configure(state="disabled", text="Connecting…")
        self._set_status("Connecting", GOLD)
        self.qr_label.configure(image="", text="PREPARING SECURE QR LOGIN", fg=GOLD,
                                font=("Segoe UI", 9, "bold"))
        self.qr_hint.configure(text="Open Telegram → Settings → Devices → Link Desktop Device")
        self._start_worker()
        if not self.loop_ready.wait(timeout=10):
            self.events.put(("error", "The background connection worker did not start."))
            return
        asyncio.run_coroutine_threadsafe(
            self._connect_task(int(self._api_id_value), self._api_hash_value), self.loop
        )

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
                        self.events.put(("need_password", future))
                        password = await future
                        await self.client.sign_in(password=password)
                        break
            me = await self.client.get_me()
            self.events.put(("connected", getattr(me, "first_name", "Telegram")))
            dialogs = await self.client.get_dialogs()
            self.events.put(("chats", [(utils.get_peer_id(d.entity), d.name or "Unnamed chat") for d in dialogs]))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def enable_reactions(self):
        selected = self.chat_list.curselection()
        if not selected:
            messagebox.showinfo("Choose chats", "Select at least one chat to activate reactions.")
            return
        chat_ids = {self.dialogs[self.visible_dialog_indices[i]][0] for i in selected}
        asyncio.run_coroutine_threadsafe(self._install_handler(chat_ids), self.loop)

    async def _install_handler(self, chat_ids):
        try:
            if hasattr(self, "_handler"):
                self.client.remove_event_handler(self._handler)
            async def handler(event):
                try:
                    chat_id = event.chat_id
                    direction = "Outgoing" if event.out else "Incoming"
                    self.events.put(("notice", f"{direction} message detected · chat {chat_id}"))
                    if chat_id not in chat_ids:
                        self.events.put(("notice", f"Message received, but chat {chat_id} is not selected"))
                        return
                    await self.client(SendReactionRequest(
                        peer=await event.get_input_chat(),
                        msg_id=event.message.id,
                        reaction=[ReactionEmoji(emoticon="🍌")]
                    ))
                    self.events.put(("reaction", chat_id))
                except Exception as exc:
                    self.events.put(("notice", f"Reaction failed: {type(exc).__name__}: {exc}"))
            self._handler = handler
            self.client.add_event_handler(handler, events.NewMessage())
            self.events.put(("active", len(chat_ids)))
            # Backfill: add the banana to existing messages in every selected chat.
            total_done = 0
            total_failed = 0
            for chat_id in chat_ids:
                try:
                    entity = await self.client.get_input_entity(chat_id)
                    async for message in self.client.iter_messages(entity):
                        if not message or not getattr(message, "id", None):
                            continue
                        while True:
                            try:
                                await self.client(SendReactionRequest(
                                    peer=entity,
                                    msg_id=message.id,
                                    reaction=[ReactionEmoji(emoticon="🍌")]
                                ))
                                total_done += 1
                                break
                            except FloodWaitError as exc:
                                self.events.put(("notice", f"Telegram rate limit: waiting {exc.seconds}s"))
                                await asyncio.sleep(exc.seconds + 1)
                            except Exception as exc:
                                total_failed += 1
                                if total_failed == 1:
                                    self.events.put(("notice", f"Some messages cannot be reacted to: {type(exc).__name__}: {exc}"))
                                break
                        if total_done and total_done % 25 == 0:
                            self.events.put(("notice", f"History scan: {total_done} messages processed"))
                except Exception as exc:
                    total_failed += 1
                    self.events.put(("notice", f"Could not scan chat {chat_id}: {type(exc).__name__}: {exc}"))
            self.events.put(("notice", f"History scan finished · {total_done} reacted · {total_failed} failed"))
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

    def _animate(self):
        self._pulse_on = not self._pulse_on
        if self.connected:
            self.status_dot.configure(fg=GREEN if self._pulse_on else "#5D8D66")
        elif self.status.cget("text") != "NOT CONNECTED":
            self.status_dot.configure(fg=GOLD if self._pulse_on else "#8B7444")
        else:
            self.status_dot.configure(fg="#777D89")
        self.root.after(700, self._animate)

    def _poll_events(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "qr":
                    image = Image.open(data)
                    image.thumbnail((176, 176))
                    self.qr_photo = ImageTk.PhotoImage(image)
                    self.qr_label.configure(image=self.qr_photo, text="")
                    self.qr_hint.configure(text="Scan with Telegram → Settings → Devices")
                elif kind == "need_password":
                    password = simpledialog.askstring(
                        "Telegram verification",
                        "Enter your Telegram 2-step verification password:",
                        show="•", parent=self.root
                    )
                    if password:
                        self.loop.call_soon_threadsafe(data.set_result, password)
                    else:
                        self.loop.call_soon_threadsafe(
                            data.set_exception, RuntimeError("2-step verification was cancelled.")
                        )
                elif kind == "connected":
                    self.connected = True
                    self._set_status(f"Connected · {data}", GREEN)
                    self.qr_label.configure(image="", text="✓", fg=GREEN, font=("Segoe UI", 36, "bold"))
                    self.qr_hint.configure(text=f"Signed in as {data}")
                    self.connect_btn.configure(text="Telegram connected", state="disabled")
                elif kind == "chats":
                    self.dialogs = data
                    self.search_var.set("")
                    self.search_entry.delete(0, tk.END)
                    self.search_entry.insert(0, "Search chats by name…")
                    self.search_entry.configure(fg=MUTED)
                    self._render_chat_list()
                    self.chat_count.configure(text=f"{len(data)} CHATS")
                    self.start_btn.configure(state="normal")
                elif kind == "active":
                    self.reactions_active = True
                    self._set_status(f"Reactions active · {data} chats", GREEN)
                    self.start_btn.configure(state="disabled")
                    self.stop_btn.configure(state="normal")
                elif kind == "stopped":
                    self.reactions_active = False
                    self._set_status("Connected · reactions paused", MUTED)
                    self.start_btn.configure(state="normal")
                    self.stop_btn.configure(state="disabled")
                elif kind == "reaction":
                    self._set_status("Banana reaction sent", GREEN)
                elif kind == "notice":
                    self._set_status(str(data)[:75], VIOLET)
                elif kind == "error":
                    self._set_status("Connection error", RED)
                    self.connect_btn.configure(state="normal", text="Try again")
                    messagebox.showerror("BANANA REACT", data)
        except queue.Empty:
            pass
        self.root.after(120, self._poll_events)

    def _close(self):
        if self.loop and self.loop.is_running():
            if self.client:
                asyncio.run_coroutine_threadsafe(self.client.disconnect(), self.loop)
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = BananaReactApp(root)
    root.mainloop()
