import difflib
import json
import queue
import threading

import sounddevice as sd
import vosk

from . import actions
from . import learning
from .llm_matcher import LlmMatcher

vosk.SetLogLevel(-1)


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


class VoiceListener(threading.Thread):
    """Continuously listens to the microphone, waits for the wake word, then
    figures out which configured command the user means and runs it.
    Everything happens locally (speech recognition + the local Ollama LLM
    running on 127.0.0.1) — no audio or text ever leaves this machine."""

    def __init__(self, config, tts=None, on_status=None):
        super().__init__(daemon=True)
        self.config = config
        self.tts = tts
        self.on_status = on_status or (lambda msg: None)

        self._audio_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._paused = threading.Event()

        self.model = vosk.Model(config["language_model_path"])
        self.samplerate = 16000
        self.recognizer = vosk.KaldiRecognizer(self.model, self.samplerate)

        self.llm_matcher = LlmMatcher()

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            self.on_status(f"Audio-Status: {status}")
        if not self._paused.is_set():
            self._audio_queue.put(bytes(indata))

    def stop(self):
        self._stop_event.set()

    def pause(self):
        self._paused.set()
        self.on_status("Pausiert")

    def resume(self):
        self._paused.clear()
        self.on_status("Lauscht...")

    def is_paused(self):
        return self._paused.is_set()

    def run(self):
        device = self.config.get("mic_device")
        self.on_status("Lauscht...")
        try:
            with sd.RawInputStream(
                samplerate=self.samplerate,
                blocksize=8000,
                device=device,
                dtype="int16",
                channels=1,
                callback=self._audio_callback,
            ):
                while not self._stop_event.is_set():
                    try:
                        data = self._audio_queue.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    if self.recognizer.AcceptWaveform(data):
                        result = json.loads(self.recognizer.Result())
                        text = _normalize(result.get("text", ""))
                        if text:
                            self._handle_utterance(text)
        except Exception as exc:
            self.on_status(f"Fehler: {exc}")

    def _handle_utterance(self, text: str):
        wake_word = _normalize(self.config.get("wake_word", "jarvis"))
        if not text.startswith(wake_word):
            return

        command_text = text[len(wake_word):].strip()
        if not command_text:
            return

        match, confidence = self._resolve_command(command_text)
        learning.add_history_entry(command_text, match["phrase"] if match else None, confidence)

        if match is None:
            self.on_status(f"Kein Befehl erkannt: '{command_text}'")
            return

        self.on_status(f"Befehl: '{match['phrase']}' ({confidence})")
        try:
            actions.execute(match["action"])
            if self.config.get("speak_responses", True) and match.get("response"):
                self._speak(match["response"])
        except Exception as exc:
            self.on_status(f"Aktion fehlgeschlagen: {exc}")
            self._speak("Das hat nicht funktioniert")

    def _resolve_command(self, command_text: str):
        commands = self.config.get("commands", [])
        if not commands:
            return None, "low"

        if self.llm_matcher.is_reachable():
            try:
                examples = learning.relevant_examples(commands)
                match, confidence = self.llm_matcher.best_match(command_text, commands, examples)
                return match, confidence
            except Exception as exc:
                self.on_status(f"KI nicht verfügbar, nutze Text-Abgleich ({exc})")

        return self._literal_best_match(command_text), "literal"

    def _literal_best_match(self, command_text: str):
        commands = self.config.get("commands", [])
        phrases = [_normalize(c["phrase"]) for c in commands]
        threshold = self.config.get("match_threshold", 0.6)
        best_ratio = 0.0
        best_command = None
        for cmd, phrase in zip(commands, phrases):
            ratio = difflib.SequenceMatcher(None, command_text, phrase).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_command = cmd
        if best_ratio >= threshold:
            return best_command
        return None

    def _speak(self, text: str):
        if self.tts is not None:
            self.tts.speak(text)
