import queue
import threading

import pyttsx3


class TextToSpeech(threading.Thread):
    """Runs pyttsx3 (offline, Windows SAPI voices) on its own thread so
    speaking a response never blocks the audio-recognition loop."""

    def __init__(self):
        super().__init__(daemon=True)
        self._queue = queue.Queue()
        self._stop_event = threading.Event()

    def speak(self, text: str):
        self._queue.put(text)

    def stop(self):
        self._stop_event.set()
        self._queue.put(None)

    def run(self):
        engine = pyttsx3.init()
        while not self._stop_event.is_set():
            text = self._queue.get()
            if text is None:
                continue
            engine.say(text)
            engine.runAndWait()
