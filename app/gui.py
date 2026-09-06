import queue
import tkinter.messagebox as messagebox

import customtkinter as ctk
import sounddevice as sd

from . import actions
from . import learning
from . import theme
from .hud_canvas import HudBackground

MEDIA_KEY_OPTIONS = [
    "volume up",
    "volume down",
    "volume mute",
    "play/pause media",
    "next track",
    "previous track",
]

ACTION_LABELS = {
    "hotkey": "Tastenkombination",
    "launch": "Programm öffnen",
    "media": "Lautstärke/Medien",
    "mouse_click": "Mausklick",
    "mouse_scroll": "Scrollen",
    "shell": "Shell-Befehl",
}


def _card(parent, **kwargs):
    defaults = dict(fg_color=theme.CARD, corner_radius=14,
                     border_width=1, border_color=theme.GLOW_DIM)
    defaults.update(kwargs)
    return ctk.CTkFrame(parent, **defaults)


class CommandDialog(ctk.CTkToplevel):
    def __init__(self, parent, command=None):
        super().__init__(parent)
        self.title("Befehl bearbeiten" if command else "Neuer Befehl")
        self.geometry("440x520")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG)
        self.result = None
        command = command or {"phrase": "", "response": "", "action": {"type": "hotkey", "keys": []}}

        pad = dict(padx=20, pady=(14, 0))

        ctk.CTkLabel(self, text="Sprachbefehl (ohne Wake-Word)", anchor="w",
                     text_color=theme.TEXT_MUTED, font=(theme.FONT_FAMILY, 12)).pack(fill="x", **pad)
        self.phrase_var = ctk.StringVar(value=command["phrase"])
        ctk.CTkEntry(self, textvariable=self.phrase_var, height=36).pack(fill="x", padx=20, pady=(4, 0))

        ctk.CTkLabel(self, text="Gesprochene Antwort", anchor="w",
                     text_color=theme.TEXT_MUTED, font=(theme.FONT_FAMILY, 12)).pack(fill="x", **pad)
        self.response_var = ctk.StringVar(value=command.get("response", ""))
        ctk.CTkEntry(self, textvariable=self.response_var, height=36).pack(fill="x", padx=20, pady=(4, 0))

        ctk.CTkLabel(self, text="Beschreibung für die KI (optional, hilft beim Verstehen)", anchor="w",
                     text_color=theme.TEXT_MUTED, font=(theme.FONT_FAMILY, 12)).pack(fill="x", **pad)
        self.description_var = ctk.StringVar(value=command.get("description", ""))
        ctk.CTkEntry(self, textvariable=self.description_var, height=36).pack(fill="x", padx=20, pady=(4, 0))

        ctk.CTkLabel(self, text="Aktionstyp", anchor="w",
                     text_color=theme.TEXT_MUTED, font=(theme.FONT_FAMILY, 12)).pack(fill="x", **pad)
        self.type_var = ctk.StringVar(value=command["action"].get("type", "hotkey"))
        ctk.CTkOptionMenu(
            self, variable=self.type_var, values=list(ACTION_LABELS.keys()),
            command=lambda _: self._render_action_fields(),
            fg_color=theme.CARD_HOVER, button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
        ).pack(fill="x", padx=20, pady=(4, 0))

        self.fields_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.fields_frame.pack(fill="x", padx=20, pady=(14, 0))
        self._action_vars = {}
        self._existing_action = command["action"]
        self._render_action_fields()

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=20, pady=20, side="bottom")
        ctk.CTkButton(btns, text="Abbrechen", fg_color=theme.CARD_HOVER, hover_color=theme.CARD,
                      text_color=theme.TEXT, command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(btns, text="Speichern", fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      text_color="#0a0a0f", command=self._on_save).pack(side="right")

        self.transient(parent)
        self.grab_set()

    def _labeled_entry(self, label_text, value):
        ctk.CTkLabel(self.fields_frame, text=label_text, anchor="w",
                     text_color=theme.TEXT_MUTED, font=(theme.FONT_FAMILY, 12)).pack(fill="x")
        var = ctk.StringVar(value=value)
        ctk.CTkEntry(self.fields_frame, textvariable=var, height=36).pack(fill="x", pady=(4, 0))
        return var

    def _render_action_fields(self):
        for child in self.fields_frame.winfo_children():
            child.destroy()
        self._action_vars = {}
        action_type = self.type_var.get()
        existing = self._existing_action if self._existing_action.get("type") == action_type else {}

        if action_type == "hotkey":
            self._action_vars["keys"] = self._labeled_entry(
                "Tasten (mit + getrennt, z.B. ctrl+alt+t)", "+".join(existing.get("keys", [])))

        elif action_type == "launch":
            self._action_vars["target"] = self._labeled_entry(
                "Pfad, Datei oder URL", existing.get("target", ""))

        elif action_type == "media":
            ctk.CTkLabel(self.fields_frame, text="Medientaste", anchor="w",
                         text_color=theme.TEXT_MUTED, font=(theme.FONT_FAMILY, 12)).pack(fill="x")
            var = ctk.StringVar(value=existing.get("key", MEDIA_KEY_OPTIONS[0]))
            ctk.CTkOptionMenu(self.fields_frame, variable=var, values=MEDIA_KEY_OPTIONS,
                              fg_color=theme.CARD_HOVER, button_color=theme.ACCENT,
                              button_hover_color=theme.ACCENT_HOVER).pack(fill="x", pady=(4, 0))
            self._action_vars["key"] = var

        elif action_type == "mouse_click":
            row = ctk.CTkFrame(self.fields_frame, fg_color="transparent")
            row.pack(fill="x")
            x_var = ctk.StringVar(value=str(existing.get("x", 0)))
            y_var = ctk.StringVar(value=str(existing.get("y", 0)))
            button_var = ctk.StringVar(value=existing.get("button", "left"))
            ctk.CTkLabel(row, text="X", text_color=theme.TEXT_MUTED, width=20).grid(row=0, column=0)
            ctk.CTkEntry(row, textvariable=x_var, width=70, height=32).grid(row=0, column=1, padx=(2, 10))
            ctk.CTkLabel(row, text="Y", text_color=theme.TEXT_MUTED, width=20).grid(row=0, column=2)
            ctk.CTkEntry(row, textvariable=y_var, width=70, height=32).grid(row=0, column=3, padx=(2, 10))
            ctk.CTkOptionMenu(row, variable=button_var, values=["left", "right", "middle"], width=90,
                              fg_color=theme.CARD_HOVER, button_color=theme.ACCENT,
                              button_hover_color=theme.ACCENT_HOVER).grid(row=0, column=4)
            self._action_vars["x"] = x_var
            self._action_vars["y"] = y_var
            self._action_vars["button"] = button_var

        elif action_type == "mouse_scroll":
            self._action_vars["amount"] = self._labeled_entry(
                "Betrag (negativ = runter)", str(existing.get("amount", 1)))

        elif action_type == "shell":
            self._action_vars["command"] = self._labeled_entry(
                "Befehlszeile (wird lokal ausgeführt)", existing.get("command", ""))

    def _on_save(self):
        phrase = self.phrase_var.get().strip()
        if not phrase:
            messagebox.showerror("Fehler", "Bitte einen Sprachbefehl eingeben.")
            return

        action_type = self.type_var.get()
        action = {"type": action_type}
        try:
            if action_type == "hotkey":
                keys = [k.strip() for k in self._action_vars["keys"].get().split("+") if k.strip()]
                if not keys:
                    raise ValueError("Mindestens eine Taste angeben.")
                action["keys"] = keys
            elif action_type == "launch":
                target = self._action_vars["target"].get().strip()
                if not target:
                    raise ValueError("Pfad/URL darf nicht leer sein.")
                action["target"] = target
            elif action_type == "media":
                action["key"] = self._action_vars["key"].get()
            elif action_type == "mouse_click":
                action["x"] = int(self._action_vars["x"].get())
                action["y"] = int(self._action_vars["y"].get())
                action["button"] = self._action_vars["button"].get()
            elif action_type == "mouse_scroll":
                action["amount"] = int(self._action_vars["amount"].get())
            elif action_type == "shell":
                command = self._action_vars["command"].get().strip()
                if not command:
                    raise ValueError("Befehl darf nicht leer sein.")
                action["command"] = command
        except ValueError as exc:
            messagebox.showerror("Fehler", str(exc))
            return

        self.result = {
            "phrase": phrase,
            "response": self.response_var.get().strip(),
            "description": self.description_var.get().strip(),
            "action": action,
        }
        self.destroy()


class CommandRow(ctk.CTkFrame):
    def __init__(self, parent, command, on_edit, on_delete):
        super().__init__(parent, fg_color=theme.CARD, corner_radius=10, height=54,
                          border_width=1, border_color=theme.GLOW_DIM)
        self.pack_propagate(False)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

        text_col = ctk.CTkFrame(self, fg_color="transparent")
        text_col.pack(side="left", fill="both", expand=True, padx=16, pady=8)
        text_col.bind("<Enter>", self._on_enter)
        text_col.bind("<Leave>", self._on_leave)
        phrase_label = ctk.CTkLabel(text_col, text=f'"{command["phrase"]}"', anchor="w",
                                     font=(theme.FONT_FAMILY, 14, "bold"), text_color=theme.TEXT)
        phrase_label.pack(anchor="w")
        phrase_label.bind("<Enter>", self._on_enter)
        phrase_label.bind("<Leave>", self._on_leave)
        ctk.CTkLabel(text_col, text=ACTION_LABELS.get(command["action"]["type"], command["action"]["type"]),
                     anchor="w", font=(theme.FONT_FAMILY, 11), text_color=theme.TEXT_MUTED).pack(anchor="w")

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(side="right", padx=10)
        ctk.CTkButton(btns, text="Bearbeiten", width=90, height=30, fg_color=theme.CARD_HOVER,
                      hover_color=theme.ACCENT, text_color=theme.TEXT, command=on_edit).pack(side="left", padx=4)
        ctk.CTkButton(btns, text="Löschen", width=80, height=30, fg_color=theme.CARD_HOVER,
                      hover_color=theme.DANGER, text_color=theme.TEXT, command=on_delete).pack(side="left")

    def _on_enter(self, _event=None):
        self.configure(border_color=theme.ACCENT)

    def _on_leave(self, _event=None):
        self.configure(border_color=theme.GLOW_DIM)


class HistoryRow(ctk.CTkFrame):
    def __init__(self, parent, entry, command_phrases, on_correct):
        super().__init__(parent, fg_color=theme.CARD, corner_radius=10,
                          border_width=1, border_color=theme.GLOW_DIM)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(top, text=f'"{entry["utterance"]}"', anchor="w",
                     font=(theme.FONT_FAMILY, 13, "bold"), text_color=theme.TEXT).pack(side="left")

        matched = entry.get("matched_phrase")
        result_text = f'-> "{matched}"' if matched else "-> kein Treffer"
        result_color = theme.ACCENT if matched else theme.TEXT_MUTED
        ctk.CTkLabel(top, text=f'{result_text}  ({entry.get("confidence", "?")})', anchor="e",
                     font=(theme.FONT_FAMILY, 12), text_color=result_color).pack(side="right")

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=14, pady=(0, 10))
        ctk.CTkLabel(bottom, text="Richtiger Befehl war eigentlich:", anchor="w",
                     text_color=theme.TEXT_MUTED, font=(theme.FONT_FAMILY, 11)).pack(side="left")
        self._choice_var = ctk.StringVar(value=matched or (command_phrases[0] if command_phrases else ""))
        ctk.CTkOptionMenu(bottom, variable=self._choice_var, values=command_phrases or ["(keine Befehle)"],
                          width=180, fg_color=theme.CARD_HOVER, button_color=theme.ACCENT,
                          button_hover_color=theme.ACCENT_HOVER).pack(side="left", padx=8)
        ctk.CTkButton(bottom, text="Als richtig merken", height=28, width=140, fg_color=theme.ACCENT,
                      hover_color=theme.ACCENT_HOVER, text_color="#0a0a0f",
                      command=lambda: on_correct(entry["utterance"], self._choice_var.get())).pack(side="left")


class App:
    def __init__(self, root, config, save_config, on_start, on_pause, on_resume, on_apply_settings):
        self.root = root
        self.config = config
        self.save_config = save_config
        self.on_start = on_start
        self.on_pause = on_pause
        self.on_resume = on_resume
        self.on_apply_settings = on_apply_settings
        self.status_queue = queue.Queue()
        self._running = False

        root.title("Jarvis Voice Control")
        root.geometry("640x640")
        root.configure(fg_color=theme.BG)
        root.protocol("WM_DELETE_WINDOW", self.hide)

        self._glow_phase = 0.0
        self._glow_direction = 1

        # Animated HUD background, drawn first so real content stacks on top of it
        self.hud = HudBackground(root)
        self.hud.place(x=0, y=0, relwidth=1, relheight=1)

        # Title is drawn directly onto the HUD canvas (no opaque panel behind it)

        # Glowing status/control bar
        self.glow_frame = ctk.CTkFrame(root, fg_color=theme.CARD, corner_radius=16,
                                        border_width=2, border_color=theme.GLOW_OFF)
        self.glow_frame.pack(fill="x", padx=24, pady=(64, 16))
        status_row = ctk.CTkFrame(self.glow_frame, fg_color="transparent")
        status_row.pack(fill="x", padx=18, pady=14)

        self.status_dot = ctk.CTkLabel(status_row, text="●", font=(theme.FONT_FAMILY, 16),
                                        text_color=theme.TEXT_MUTED, width=16)
        self.status_dot.pack(side="left")
        self.status_label = ctk.CTkLabel(status_row, text="Gestoppt", font=(theme.FONT_FAMILY, 13),
                                          text_color=theme.TEXT_MUTED, anchor="w")
        self.status_label.pack(side="left", padx=(6, 0))

        self.start_btn = ctk.CTkButton(status_row, text="▶  Start", height=36, width=130,
                                        fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                                        text_color="#0a0a0f", font=(theme.FONT_FAMILY, 13, "bold"),
                                        command=self._start)
        self.start_btn.pack(side="right")
        self.pause_btn = ctk.CTkButton(status_row, text="Pause", height=36, width=100,
                                        fg_color=theme.CARD_HOVER, hover_color=theme.CARD,
                                        text_color=theme.TEXT, state="disabled", command=self._pause)
        self.pause_btn.pack(side="right", padx=8)

        # Sections as separate tabs — commands live on their own tab, not on the main view
        self.tabs = ctk.CTkTabview(
            root, height=270, fg_color=theme.CARD, segmented_button_fg_color=theme.CARD,
            segmented_button_selected_color=theme.ACCENT,
            segmented_button_selected_hover_color=theme.ACCENT_HOVER,
            segmented_button_unselected_color=theme.CARD,
            segmented_button_unselected_hover_color=theme.CARD_HOVER,
            text_color=theme.TEXT, text_color_disabled=theme.TEXT_MUTED,
            corner_radius=16, border_width=1, border_color=theme.GLOW_DIM,
        )
        self.tabs.pack(fill="x", padx=24, pady=(0, 24), anchor="n")
        self.tabs.pack_propagate(False)
        tab_settings = self.tabs.add("Steuerung")
        tab_commands = self.tabs.add("Befehle")
        tab_history = self.tabs.add("Verlauf")

        # --- Steuerung tab ---
        settings_card = _card(tab_settings)
        settings_card.pack(fill="x", pady=(4, 0))
        inner = ctk.CTkFrame(settings_card, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=16)

        ctk.CTkLabel(inner, text="Wake-Word", text_color=theme.TEXT_MUTED,
                     font=(theme.FONT_FAMILY, 12), anchor="w").grid(row=0, column=0, sticky="w")
        self.wake_word_var = ctk.StringVar(value=config.get("wake_word", "jarvis"))
        ctk.CTkEntry(inner, textvariable=self.wake_word_var, height=34, width=160).grid(
            row=1, column=0, sticky="w", pady=(4, 12))

        ctk.CTkLabel(inner, text="Mikrofon", text_color=theme.TEXT_MUTED,
                     font=(theme.FONT_FAMILY, 12), anchor="w").grid(row=0, column=1, sticky="w", padx=(20, 0))
        self.mic_var = ctk.StringVar()
        self.mic_devices = self._list_input_devices()
        mic_names = [name for _, name in self.mic_devices] or ["Kein Mikrofon gefunden"]
        self.mic_menu = ctk.CTkOptionMenu(inner, variable=self.mic_var, values=mic_names, width=260,
                                           fg_color=theme.CARD_HOVER, button_color=theme.ACCENT,
                                           button_hover_color=theme.ACCENT_HOVER)
        self.mic_menu.grid(row=1, column=1, sticky="w", padx=(20, 0), pady=(4, 12))
        self._select_current_mic()

        self.speak_var = ctk.BooleanVar(value=config.get("speak_responses", True))
        ctk.CTkSwitch(inner, text="Antworten sprechen (TTS)", variable=self.speak_var,
                      progress_color=theme.ACCENT, text_color=theme.TEXT).grid(
            row=2, column=0, columnspan=2, sticky="w")

        ctk.CTkButton(inner, text="Übernehmen", height=34, width=140, fg_color=theme.ACCENT,
                      hover_color=theme.ACCENT_HOVER, text_color="#0a0a0f",
                      command=self._apply_settings).grid(row=2, column=1, sticky="e", padx=(20, 0))
        inner.grid_columnconfigure(1, weight=1)

        # --- Befehle tab ---
        commands_header = ctk.CTkFrame(tab_commands, fg_color="transparent")
        commands_header.pack(fill="x", pady=(4, 10))
        ctk.CTkLabel(commands_header, text="Sprachbefehle", font=(theme.FONT_FAMILY, 16, "bold"),
                     text_color=theme.TEXT).pack(side="left")
        ctk.CTkButton(commands_header, text="+  Neuer Befehl", height=32, fg_color=theme.ACCENT,
                      hover_color=theme.ACCENT_HOVER, text_color="#0a0a0f",
                      command=self._add_command).pack(side="right")

        self.commands_scroll = ctk.CTkScrollableFrame(tab_commands, fg_color="transparent")
        self.commands_scroll.pack(fill="both", expand=True)
        self._refresh_command_list()

        # --- Verlauf tab ---
        history_header = ctk.CTkFrame(tab_history, fg_color="transparent")
        history_header.pack(fill="x", pady=(4, 10))
        ctk.CTkLabel(history_header, text="Erkannte Sätze", font=(theme.FONT_FAMILY, 16, "bold"),
                     text_color=theme.TEXT).pack(side="left")
        ctk.CTkButton(history_header, text="Aktualisieren", height=28, width=110, fg_color=theme.CARD_HOVER,
                      hover_color=theme.ACCENT, text_color=theme.TEXT,
                      command=self._refresh_history).pack(side="right")

        self.history_scroll = ctk.CTkScrollableFrame(tab_history, fg_color="transparent")
        self.history_scroll.pack(fill="both", expand=True)
        self._refresh_history()

        self.root.after(200, self._poll_status)
        self.root.after(50, self._animate_glow)

    def _list_input_devices(self):
        devices = []
        try:
            for idx, dev in enumerate(sd.query_devices()):
                if dev.get("max_input_channels", 0) > 0:
                    devices.append((idx, f"{idx}: {dev['name']}"))
        except Exception:
            pass
        return devices

    def _select_current_mic(self):
        current = self.config.get("mic_device")
        for idx, name in self.mic_devices:
            if idx == current:
                self.mic_var.set(name)
                return
        if self.mic_devices:
            self.mic_var.set(self.mic_devices[0][1])

    def _refresh_command_list(self):
        for child in self.commands_scroll.winfo_children():
            child.destroy()
        for i, cmd in enumerate(self.config.get("commands", [])):
            row = CommandRow(
                self.commands_scroll, cmd,
                on_edit=lambda i=i: self._edit_command(i),
                on_delete=lambda i=i: self._delete_command(i),
            )
            row.pack(fill="x", pady=4)

    def _add_command(self):
        dialog = CommandDialog(self.root)
        self.root.wait_window(dialog)
        if dialog.result:
            self.config.setdefault("commands", []).append(dialog.result)
            self.save_config(self.config)
            self._refresh_command_list()

    def _edit_command(self, idx):
        dialog = CommandDialog(self.root, command=self.config["commands"][idx])
        self.root.wait_window(dialog)
        if dialog.result:
            self.config["commands"][idx] = dialog.result
            self.save_config(self.config)
            self._refresh_command_list()

    def _delete_command(self, idx):
        if messagebox.askyesno("Löschen", "Diesen Befehl wirklich löschen?"):
            del self.config["commands"][idx]
            self.save_config(self.config)
            self._refresh_command_list()

    def _refresh_history(self):
        for child in self.history_scroll.winfo_children():
            child.destroy()
        history = list(reversed(learning.load_history()))
        phrases = [c["phrase"] for c in self.config.get("commands", [])]
        if not history:
            ctk.CTkLabel(self.history_scroll, text="Noch keine erkannten Sätze.",
                         text_color=theme.TEXT_MUTED).pack(pady=20)
            return
        for entry in history:
            row = HistoryRow(self.history_scroll, entry, phrases, on_correct=self._correct_history_entry)
            row.pack(fill="x", pady=4)

    def _correct_history_entry(self, utterance, correct_phrase):
        learning.add_example(utterance, correct_phrase)
        messagebox.showinfo("Gemerkt", f'Jarvis merkt sich: "{utterance}" -> "{correct_phrase}"')
        self._refresh_history()

    def _apply_settings(self):
        self.config["wake_word"] = self.wake_word_var.get().strip() or "jarvis"
        self.config["speak_responses"] = self.speak_var.get()
        for idx, name in self.mic_devices:
            if name == self.mic_var.get():
                self.config["mic_device"] = idx
                break
        self.save_config(self.config)
        self.on_apply_settings(self.config)
        messagebox.showinfo("Gespeichert", "Einstellungen gespeichert. Bei laufendem Betrieb bitte neu starten, damit Mikrofon-änderungen greifen.")

    def _start(self):
        self.on_start()
        self._running = True
        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal", text="Pause")

    def _pause(self):
        if self.pause_btn.cget("text") == "Pause":
            self.on_pause()
            self._running = False
            self.pause_btn.configure(text="Fortsetzen")
        else:
            self.on_resume()
            self._running = True
            self.pause_btn.configure(text="Pause")

    def push_status(self, text: str):
        self.status_queue.put(text)

    def _poll_status(self):
        try:
            while True:
                text = self.status_queue.get_nowait()
                self.status_label.configure(text=text)
        except queue.Empty:
            pass
        self.root.after(200, self._poll_status)

    def _animate_glow(self):
        if self._running:
            self._glow_phase += 0.06 * self._glow_direction
            if self._glow_phase >= 1.0:
                self._glow_phase, self._glow_direction = 1.0, -1
            elif self._glow_phase <= 0.0:
                self._glow_phase, self._glow_direction = 0.0, 1
            color = theme.lerp_color(theme.GLOW_DIM, theme.ACCENT_BRIGHT, self._glow_phase)
            self.glow_frame.configure(border_color=color)
            self.status_dot.configure(text_color=color)
        else:
            self.glow_frame.configure(border_color=theme.GLOW_OFF)
            self.status_dot.configure(text_color=theme.TEXT_MUTED)
        self.root.after(50, self._animate_glow)

    def show(self):
        self.root.deiconify()
        self.root.lift()

    def hide(self):
        self.root.withdraw()
