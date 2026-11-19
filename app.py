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
        self.selected_chat_ids = set()
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
        # Dashboard layout inspired by the supplied reference screenshot.
        self.root.title("BANANA REACT — Telegram dashboard")
        self.root.geometry("1194x664")
        self.root.minsize(1000, 620)
        self.root.configure(bg=BG)

        shell = tk.Frame(self.root, bg=BG)
        shell.pack(fill="both", expand=True)

        # Slim icon rail
        rail = tk.Frame(shell, bg="#050705", width=52)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)
        tk.Label(rail, text="◈", bg="#050705", fg=GREEN,
                 font=("Segoe UI", 20, "bold")).pack(pady=(14, 3))
        tk.Label(rail, text="BANANA\nREACT", bg="#050705", fg=TEXT,
                 font=("Segoe UI", 6, "bold"), justify="center").pack(pady=(0, 20))
        for glyph in ("⌂", "➤", "♡", "⚙", "▤"):
            tk.Label(rail, text=glyph, bg="#050705", fg="#778477",
                     font=("Segoe UI Symbol", 15), pady=10).pack(fill="x")

        # Navigation column
        nav = tk.Frame(shell, bg="#0C110C", width=188)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)
        nav_head = tk.Frame(nav, bg="#0C110C")
        nav_head.pack(fill="x", padx=12, pady=(17, 12))
        tk.Label(nav_head, text="BANANA REACT", bg="#0C110C", fg=TEXT,
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        tk.Label(nav_head, text="●", bg="#0C110C", fg=GREEN,
                 font=("Segoe UI", 11)).pack(side="right")
        self.connect_btn = self._button(nav, "＋  Add Telegram account", self.connect, primary=True)
        self.connect_btn.pack(fill="x", padx=10, pady=(4, 15))
        tk.Label(nav, text="HOME", bg="#0C110C", fg="#738073",
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", padx=14, pady=(2, 7))
        for item in ("▣  DASHBOARD", "♧  TELEGRAM ACCOUNT", "◉  CHAT SELECTION",
                     "✦  REACTION SETTINGS", "▤  ACTIVITY LOG"):
            active = item.startswith("▣")
            tk.Label(nav, text=item, bg="#142014" if active else "#0C110C",
                     fg=GREEN if active else "#A0ACA0",
                     font=("Segoe UI", 8, "bold"), anchor="w",
                     padx=10, pady=10).pack(fill="x", padx=7, pady=2)
        tk.Label(nav, text=" ", bg="#0C110C").pack(expand=True, fill="both")
        tk.Label(nav, text="LOCAL SESSION\nPRIVATE STORAGE", bg="#0C110C",
                 fg="#5E6B5E", font=("Segoe UI", 7, "bold"),
                 justify="left").pack(anchor="w", padx=13, pady=14)

        # Main workspace
        main = tk.Frame(shell, bg=BG)
        main.pack(side="left", fill="both", expand=True, padx=(12, 12), pady=10)
        main.grid_columnconfigure(0, weight=55, uniform="columns")
        main.grid_columnconfigure(1, weight=45, uniform="columns")
        main.grid_rowconfigure(2, weight=1)

        title_row = tk.Frame(main, bg=BG)
        title_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 9))
        tk.Label(title_row, text="Dashboard", bg=BG, fg=TEXT,
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        self.status_dot = tk.Label(title_row, text="●", bg=BG, fg="#657065",
                                   font=("Segoe UI", 9))
        self.status_dot.pack(side="right", padx=(0, 6))
        self.status = tk.Label(title_row, text="NOT CONNECTED", bg=BG, fg=MUTED,
                               font=("Segoe UI", 8, "bold"))
        self.status.pack(side="right")

        # Six compact statistic tiles
        stats = tk.Frame(main, bg=BG)
        stats.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        for i in range(6):
            stats.grid_columnconfigure(i, weight=1, uniform="stats")
        stat_specs = [
            ("TELEGRAM", "OFFLINE", GREEN),
            ("TOTAL CHATS", "0", "#D9B36B"),
            ("SELECTED", "0", "#D9D36B"),
            ("REACTIONS", "0", "#72A9E8"),
            ("HISTORY", "READY", "#D96B6B"),
            ("VERSION", "1.0", "#A66BE0"),
        ]
        self.stat_values = []
        for i, (caption, value, accent) in enumerate(stat_specs):
            tile = tk.Frame(stats, bg="#111611", highlightbackground="#273127",
                            highlightthickness=1)
            tile.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 5, 0))
            tk.Label(tile, text=caption, bg="#111611", fg=accent,
                     font=("Segoe UI", 6, "bold")).pack(anchor="w", padx=9, pady=(7, 2))
            val = tk.Label(tile, text=value, bg="#111611", fg=TEXT,
                           font=("Segoe UI", 12, "bold"))
            val.pack(anchor="w", padx=9, pady=(0, 7))
            self.stat_values.append(val)

        # Left settings panel
        settings = tk.Frame(main, bg="#101510", highlightbackground="#263226",
                            highlightthickness=1)
        settings.grid(row=2, column=0, sticky="nsew", padx=(0, 6))
        settings.grid_columnconfigure(0, weight=1)
        tk.Label(settings, text="SETTINGS", bg="#101510", fg=TEXT,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(10, 7))

        account_box = tk.Frame(settings, bg="#151D15")
        account_box.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
        account_box.grid_columnconfigure(0, weight=1)
        tk.Label(account_box, text="TELEGRAM ACCOUNT", bg="#151D15", fg=GREEN,
                 font=("Segoe UI", 7, "bold")).grid(row=0, column=0, sticky="w", padx=9, pady=(7, 2))
        self.qr_area = tk.Frame(account_box, bg="#151D15", height=88)
        self.qr_area.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 3))
        self.qr_area.grid_propagate(False)
        self.qr_label = tk.Label(self.qr_area, text="QR LOGIN", bg="#151D15",
                                 fg=GREEN, font=("Segoe UI", 9, "bold"))
        self.qr_label.pack(expand=True, fill="both")
        self.qr_hint = tk.Label(account_box, text="Scan a secure QR code to connect",
                                bg="#151D15", fg=MUTED, font=("Segoe UI", 7))
        self.qr_hint.grid(row=2, column=0, sticky="w", padx=9, pady=(0, 7))

        tk.Label(settings, text="REACTION SETTINGS", bg="#101510", fg=TEXT,
                 font=("Segoe UI", 8, "bold")).grid(row=2, column=0, sticky="w", padx=12, pady=(3, 7))
        opts = tk.Frame(settings, bg="#101510")
        opts.grid(row=3, column=0, sticky="ew", padx=10)
        opts.grid_columnconfigure(0, weight=1)
        opts.grid_columnconfigure(1, weight=1)
        for row, (label, value) in enumerate((
            ("Reaction", "🍌  Banana"),
            ("Messages", "All available history"),
            ("New messages", "Incoming + outgoing"),
            ("Chat scope", "Selected chats only"),
        )):
            for col, text in enumerate((label, value)):
                tk.Label(opts, text=text, bg="#151D15" if col else "#121812",
                         fg=TEXT if col else MUTED, font=("Segoe UI", 7),
                         anchor="w", padx=8, pady=7).grid(row=row, column=col, sticky="ew",
                                                          padx=(0, 3) if col == 0 else (3, 0),
                                                          pady=2)

        tk.Label(settings, text="CHAT SELECTION", bg="#101510", fg=TEXT,
                 font=("Segoe UI", 8, "bold")).grid(row=4, column=0, sticky="w", padx=12, pady=(8, 5))
        selection_bar = tk.Frame(settings, bg="#101510")
        selection_bar.grid(row=5, column=0, sticky="ew", padx=10)
        self.chat_count = tk.Label(selection_bar, text="NOT LOADED", bg="#101510",
                                   fg=GREEN, font=("Segoe UI", 7, "bold"))
        self.chat_count.pack(side="left")
        self._button(selection_bar, "Select all", self._select_visible).pack(side="right", padx=(4, 0))
        self._button(selection_bar, "Clear", self._clear_selection).pack(side="right")

        actions = tk.Frame(settings, bg="#101510")
        actions.grid(row=6, column=0, sticky="ew", padx=10, pady=(10, 10))
        self.start_btn = self._button(actions, "▶  ACTIVATE REACTIONS", self.enable_reactions, primary=True)
        self.start_btn.pack(fill="x")
        self.start_btn.configure(state="disabled")
        self.stop_btn = self._button(actions, "■  PAUSE REACTIONS", self.stop_reactions)
        self.stop_btn.pack(fill="x", pady=(6, 0))
        self.stop_btn.configure(state="disabled")

        # Right side: searchable chats, results and action log
        right = tk.Frame(main, bg=BG)
        right.grid(row=2, column=1, sticky="nsew", padx=(6, 0))
        right.grid_rowconfigure(1, weight=5)
        right.grid_rowconfigure(3, weight=2)
        right.grid_columnconfigure(0, weight=1)

        chat_panel = tk.Frame(right, bg="#101510", highlightbackground="#263226",
                              highlightthickness=1)
        chat_panel.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        chat_panel.grid_columnconfigure(0, weight=1)
        tk.Label(chat_panel, text="LIST OF CHATS", bg="#101510", fg=TEXT,
                 font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 5))
        search_wrap = tk.Frame(chat_panel, bg="#171E17", highlightbackground="#293629",
                               highlightthickness=1)
        search_wrap.grid(row=1, column=0, sticky="ew", padx=9, pady=(0, 7))
        tk.Label(search_wrap, text="⌕", bg="#171E17", fg=GREEN,
                 font=("Segoe UI", 13)).pack(side="left", padx=(8, 4))
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_wrap, textvariable=self.search_var,
                                     bg="#171E17", fg=TEXT, insertbackground=GREEN,
                                     relief="flat", bd=0, font=("Segoe UI", 8))
        self.search_entry.pack(side="left", fill="x", expand=True, padx=5, pady=7)
        self.search_entry.insert(0, "Search chats by name…")
        self.search_entry.configure(fg=MUTED)
        self.search_entry.bind("<FocusIn>", self._search_focus_in)
        self.search_entry.bind("<FocusOut>", self._search_focus_out)
        self.search_var.trace_add("write", self._filter_chats)

        listwrap = tk.Frame(chat_panel, bg="#171E17", highlightbackground="#293629",
                            highlightthickness=1)
        listwrap.grid(row=2, column=0, sticky="nsew", padx=9, pady=(0, 9))
        chat_panel.grid_rowconfigure(2, weight=1)
        listwrap.grid_rowconfigure(0, weight=1)
        listwrap.grid_columnconfigure(0, weight=1)
        self.chat_list = tk.Listbox(listwrap, selectmode=tk.EXTENDED, activestyle="none",
            bg="#171E17", fg=TEXT, selectbackground="#245D1E", selectforeground="#8CFF70",
            relief="flat", highlightthickness=0, font=("Segoe UI", 8),
            exportselection=False, selectborderwidth=0, borderwidth=0)
        self.chat_list.grid(row=0, column=0, sticky="nsew", padx=7, pady=5)
        self.chat_list.bind("<<ListboxSelect>>", self._on_chat_select)
        scroll = ttk.Scrollbar(listwrap, orient="vertical", command=self.chat_list.yview)
        scroll.grid(row=0, column=1, sticky="ns", pady=5, padx=(0, 4))
        self.chat_list.configure(yscrollcommand=scroll.set)
        self.chat_list.insert(tk.END, "Connect Telegram to load your chats")

        results_panel = tk.Frame(right, bg="#101510", highlightbackground="#263226",
                                 highlightthickness=1)
        results_panel.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        results_panel.grid_columnconfigure(0, weight=1)
        results_panel.grid_rowconfigure(1, weight=1)
        tk.Label(results_panel, text="RESULTS", bg="#101510", fg=TEXT,
                 font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=7)
        self.results_text = tk.Text(results_panel, bg="#0B0E0B", fg="#9DA99D",
                                    insertbackground=GREEN, relief="flat", bd=0,
                                    font=("Consolas", 7), height=3, wrap="word",
                                    state="disabled")
        self.results_text.grid(row=1, column=0, sticky="nsew", padx=9, pady=(0, 8))

        log_panel = tk.Frame(right, bg="#101510", highlightbackground="#263226",
                             highlightthickness=1)
        log_panel.grid(row=2, column=0, sticky="nsew")
        log_panel.grid_columnconfigure(0, weight=1)
        log_panel.grid_rowconfigure(1, weight=1)
        tk.Label(log_panel, text="PROGRAM ACTIONS", bg="#101510", fg=TEXT,
                 font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=7)
        self.activity_text = tk.Text(log_panel, bg="#0B0E0B", fg="#9DA99D",
                                     insertbackground=GREEN, relief="flat", bd=0,
                                     font=("Consolas", 7), height=5, wrap="word",
                                     state="disabled")
        self.activity_text.grid(row=1, column=0, sticky="nsew", padx=9, pady=(0, 8))
        self._append_log("ready", "BANANA REACT dashboard ready")

    def _append_log(self, kind, data):
        line = f"[{kind.upper()}] {data}"
        for widget in (getattr(self, "results_text", None), getattr(self, "activity_text", None)):
            if widget is None:
                continue
            widget.configure(state="normal")
            widget.insert("end", line + "\\n")
            widget.see("end")
            widget.configure(state="disabled")

    def _update_stats(self):
        if not hasattr(self, "stat_values"):
            return
        self.stat_values[0].configure(text="ONLINE" if self.connected else "OFFLINE")
        self.stat_values[1].configure(text=str(len(self.dialogs)))
        self.stat_values[2].configure(text=str(len(self.selected_chat_ids)))
        self.stat_values[3].configure(text="ACTIVE" if self.reactions_active else "IDLE")
        self.stat_values[4].configure(text="SCANNING" if self.reactions_active else "READY")

    def _search_focus_in(self, _event=None):
        if self.search_entry.get() == "Search chats by name…":
            self.search_entry.delete(0, tk.END)
            self.search_entry.configure(fg=TEXT)

    def _search_focus_out(self, _event=None):
        if not self.search_entry.get().strip():
            self.search_entry.insert(0, "Search chats by name…")
            self.search_entry.configure(fg=MUTED)

    def _sync_visible_selection(self):
        visible_ids = {
            self.dialogs[i][0] for i in self.visible_dialog_indices
        }
        current_ids = {
            self.dialogs[self.visible_dialog_indices[row]][0]
            for row in self.chat_list.curselection()
            if row < len(self.visible_dialog_indices)
        }
        self.selected_chat_ids.difference_update(visible_ids)
        self.selected_chat_ids.update(current_ids)

    def _on_chat_select(self, _event=None):
        self._sync_visible_selection()

    def _filter_chats(self, *_args):
        if not hasattr(self, "chat_list"):
            return
        self._sync_visible_selection()
        query = self.search_var.get().strip().lower()
        if query == "search chats by name…":
            query = ""
        self._render_chat_list(query)

    def _render_chat_list(self, query=""):
        if query == "search chats by name…":
            query = ""
        self.visible_dialog_indices = [
            i for i, (_chat_id, name) in enumerate(self.dialogs)
            if query in name.lower()
        ]
        self.chat_list.delete(0, tk.END)
        for i in self.visible_dialog_indices:
            chat_id, name = self.dialogs[i]
            self.chat_list.insert(tk.END, "  " + name)
            if chat_id in self.selected_chat_ids:
                self.chat_list.selection_set(tk.END)
        if hasattr(self, "chat_count"):
            total = len(self.dialogs)
            shown = len(self.visible_dialog_indices)
            self.chat_count.configure(text=f"{shown}/{total} CHATS" if query else f"{total} CHATS")

    def _select_visible(self):
        self._sync_visible_selection()
        self.selected_chat_ids.update(
            self.dialogs[i][0] for i in self.visible_dialog_indices
        )
        self._render_chat_list(self.search_var.get().strip().lower())

    def _clear_selection(self):
        self.selected_chat_ids.clear()
        self._render_chat_list(self.search_var.get().strip().lower())

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
        self._sync_visible_selection()
        if not self.selected_chat_ids:
            messagebox.showinfo("Choose chats", "Select at least one chat to activate reactions.")
            return
        chat_ids = set(self.selected_chat_ids)
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
