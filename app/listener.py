import difflib
import json
import queue
import threading
import time

import numpy as np
import sounddevice as sd
import vosk

from . import actions
from . import learning
from . import system_info
from .llm_matcher import LlmMatcher

vosk.SetLogLevel(-1)

WAKE_WINDOW_SECONDS = 8
MIC_GAIN = 2.5  # amplifies quiet speech so normal speaking volume is enough
WAKE_WORD_FUZZY_THRESHOLD = 0.5  # tolerates Vosk mishearing "Jarvis" quite a bit


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def load_model(config):
    """Loads the Vosk model for this config's language_model_path. The
    larger, more accurate German model can take a good while (~80s) to
    load, so this is meant to be called once ahead of time on a background
    thread (see main.py's preload), not on the same thread as the GUI."""
    return vosk.Model(config["language_model_path"])


def _fuzzy_wake_match(text: str, wake_word: str, threshold: float = WAKE_WORD_FUZZY_THRESHOLD):
    """If the leading word(s) of `text` are a close enough match for the
    wake word (tolerant of mishearing an English name like "Jarvis" in a
    German speech model), returns the remaining text after it. Otherwise
    returns None."""
    words = text.split()
    wake_words = wake_word.split()
    n = len(wake_words)
    if not n or len(words) < n:
        return None
    lead = " ".join(words[:n])
    ratio = difflib.SequenceMatcher(None, lead, wake_word).ratio()
    if ratio >= threshold:
        return " ".join(words[n:]).strip()
    return None


class VoiceListener(threading.Thread):
    """Continuously listens to the microphone, waits for the wake word, then
    figures out which configured command the user means and runs it.
    Everything happens locally (speech recognition + the local Ollama LLM
    running on 127.0.0.1) — no audio or text ever leaves this machine."""

    def __init__(self, config, tts=None, on_status=None, on_wake_word=None, on_command_done=None, model=None):
        super().__init__(daemon=True)
        self.config = config
        self.tts = tts
        self.on_status = on_status or (lambda msg: None)
        self.on_wake_word = on_wake_word or (lambda: None)
        self.on_command_done = on_command_done or (lambda: None)

        self._audio_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._paused = threading.Event()
        self._wake_fired = False
        self._awaiting_command_until = 0.0

        self.model = model or vosk.Model(config["language_model_path"])
        self.samplerate = 16000
        self.recognizer = vosk.KaldiRecognizer(self.model, self.samplerate)

        self.llm_matcher = LlmMatcher()

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            self.on_status(f"Audio-Status: {status}")
        if not self._paused.is_set():
            audio = np.frombuffer(indata, dtype=np.int16).astype(np.float32) * MIC_GAIN
            audio = np.clip(audio, -32768, 32767).astype(np.int16)
            self._audio_queue.put(audio.tobytes())

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
                        self._wake_fired = False
                        if text:
                            self._handle_utterance(text)
                    else:
                        self._check_partial_for_wake_word()
        except Exception as exc:
            self.on_status(f"Fehler: {exc}")

    def _check_partial_for_wake_word(self):
        if self._wake_fired:
            return
        partial = json.loads(self.recognizer.PartialResult())
        partial_text = _normalize(partial.get("partial", ""))
        wake_word = _normalize(self.config.get("wake_word", "jarvis"))
        if wake_word and _fuzzy_wake_match(partial_text, wake_word) is not None:
            self._wake_fired = True
            self._awaiting_command_until = time.time() + WAKE_WINDOW_SECONDS
            self.on_wake_word()

    def _handle_utterance(self, text: str):
        wake_word = _normalize(self.config.get("wake_word", "jarvis"))

        remainder = _fuzzy_wake_match(text, wake_word)
        if remainder is not None:
            command_text = remainder
            if not command_text:
                # Just the wake word alone — keep the window open and wait
                # for the command as its own follow-up utterance.
                self._awaiting_command_until = time.time() + WAKE_WINDOW_SECONDS
                return
        elif time.time() <= self._awaiting_command_until:
            # No wake word this time, but we're still within the window
            # after a recent "Jarvis" — treat this utterance as the command.
            command_text = text
        else:
            return

        self._awaiting_command_until = 0.0
        match, confidence = self._resolve_command(command_text)
        learning.add_history_entry(command_text, match["phrase"] if match else None, confidence)

        if match is None:
            self.on_status(f"Kein Befehl erkannt: '{command_text}'")
            self.on_command_done()
            return

        self.on_status(f"Befehl: '{match['phrase']}' ({confidence})")

        if match["action"]["type"] == "system_info":
            answer = system_info.answer(match["action"]["query"])
            self.on_status(f"Antwort: {answer}")
            self._finish(answer)
            return

        try:
            actions.execute(match["action"])
            self._finish("Okay")
        except Exception as exc:
            self.on_status(f"Aktion fehlgeschlagen: {exc}")
            self._finish("Das hat nicht funktioniert")

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

    def _finish(self, text: str):
        """Speaks the closing response, if any, and only signals the
        command as done once that speech has actually finished playing
        (not just been queued) — otherwise the overlay would disappear
        while Jarvis is still talking."""
        if text and self.tts is not None and self.config.get("speak_responses", True):
            self.tts.speak(text, on_done=self.on_command_done)
        else:
            self.on_command_done()
