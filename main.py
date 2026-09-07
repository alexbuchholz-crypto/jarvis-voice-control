import os
import sys
import threading

import customtkinter as ctk
from PIL import Image, ImageDraw
import pystray

from app import config as config_module
from app import ollama_manager
from app.gui import App
from app import listener as listener_module
from app.listener import VoiceListener
from app.llm_matcher import LlmMatcher
from app.overlay import WakeOverlay
from app.tts import TextToSpeech

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class Controller:
    def __init__(self):
        self.config = config_module.load_config()
        self.listener = None
        self.tts = TextToSpeech()
        self.tts.start()

        self._ollama_process = None
        threading.Thread(target=self._start_ollama, daemon=True).start()

        self._vosk_model = None
        threading.Thread(target=self._preload_vosk_model, daemon=True).start()

        self.root = ctk.CTk()
        self.wake_overlay = WakeOverlay(self.root)
        self.app = App(
            self.root,
            self.config,
            save_config=config_module.save_config,
            on_start=self.start_listener,
            on_pause=self.pause_listener,
            on_resume=self.resume_listener,
            on_apply_settings=self.apply_settings,
        )

    def _start_ollama(self):
        self._ollama_process = ollama_manager.start_background()
        if ollama_manager.is_running():
            LlmMatcher().warmup()

    def _preload_vosk_model(self):
        model_path = self.config.get("language_model_path")
        if os.path.isdir(model_path):
            self._vosk_model = listener_module.load_model(self.config)

    def apply_settings(self, config):
        self.config = config

    def start_listener(self):
        model_path = self.config.get("language_model_path")
        if not os.path.isdir(model_path):
            self.app.push_status(f"Sprachmodell fehlt: {model_path}")
            return
        if self.listener and self.listener.is_alive():
            return
        if self._vosk_model is None:
            self.app.push_status("Sprachmodell wird noch geladen...")
        self.listener = VoiceListener(
            self.config, tts=self.tts, on_status=self.app.push_status,
            on_wake_word=self.wake_overlay.show,
            on_command_done=self.wake_overlay.hide,
            model=self._vosk_model,
        )
        self.listener.start()

    def pause_listener(self):
        if self.listener:
            self.listener.pause()

    def resume_listener(self):
        if self.listener:
            self.listener.resume()

    def stop_listener(self):
        if self.listener:
            self.listener.stop()

    def make_tray_icon(self):
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((4, 4, 60, 60), outline=(0, 212, 255, 255), width=5)
        draw.ellipse((26, 20, 38, 32), fill=(0, 212, 255, 255))
        draw.rectangle((30, 32, 34, 46), fill=(0, 212, 255, 255))

        menu = pystray.Menu(
            pystray.MenuItem("Einstellungen anzeigen", lambda: self.root.after(0, self.app.show), default=True),
            pystray.MenuItem("Lauschen starten", lambda: self.root.after(0, self.start_listener)),
            pystray.MenuItem("Beenden", self.quit),
        )
        return pystray.Icon("jarvis-voice-control", image, "Jarvis Voice Control", menu)

    def quit(self, icon=None, item=None):
        self.stop_listener()
        self.tts.stop()
        ollama_manager.stop(self._ollama_process)
        if icon:
            icon.stop()
        self.root.after(0, self.root.destroy)

    def run(self):
        icon = self.make_tray_icon()
        tray_thread = threading.Thread(target=icon.run, daemon=True)
        tray_thread.start()
        self.root.mainloop()


if __name__ == "__main__":
    Controller().run()
