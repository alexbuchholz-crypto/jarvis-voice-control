import json
import os

APPDATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "JarvisVoiceControl")
CONFIG_PATH = os.path.join(APPDATA_DIR, "config.json")

DEFAULT_CONFIG = {
    "wake_word": "jarvis",
    "mic_device": None,
    "language_model_path": "models/vosk-model-small-de-0.15",
    "match_threshold": 0.6,
    "speak_responses": True,
    "commands": [
        {
            "phrase": "lauter",
            "description": "Systemlautstärke erhöhen/aufdrehen",
            "response": "Lautstärke wird erhöht",
            "action": {"type": "media", "key": "volume up"},
        },
        {
            "phrase": "leiser",
            "description": "Systemlautstärke verringern/runterdrehen/dimmen",
            "response": "Lautstärke wird verringert",
            "action": {"type": "media", "key": "volume down"},
        },
        {
            "phrase": "stumm",
            "description": "Ton komplett stummschalten",
            "response": "Stummgeschaltet",
            "action": {"type": "media", "key": "volume mute"},
        },
        {
            "phrase": "musik pause",
            "description": "Musik oder Wiedergabe pausieren/anhalten",
            "response": "Pausiert",
            "action": {"type": "media", "key": "play/pause media"},
        },
        {
            "phrase": "naechster titel",
            "description": "Zum nächsten Musiktitel/Song springen/skippen",
            "response": "Nächster Titel",
            "action": {"type": "media", "key": "next track"},
        },
        {
            "phrase": "mach einen screenshot",
            "description": "Einen Screenshot/Bildschirmfoto aufnehmen",
            "response": "Screenshot gemacht",
            "action": {"type": "hotkey", "keys": ["windows", "shift", "s"]},
        },
    ],
}


def _ensure_dir():
    os.makedirs(APPDATA_DIR, exist_ok=True)


def load_config():
    _ensure_dir()
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    for key, value in DEFAULT_CONFIG.items():
        config.setdefault(key, value)
    return config


def save_config(config):
    _ensure_dir()
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
