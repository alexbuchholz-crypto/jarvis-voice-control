"""Persistent local memory that lets Jarvis improve from your corrections.

Nothing here trains model weights — it keeps a growing, on-disk list of
(utterance -> correct command) examples that get fed back into the LLM
prompt as few-shot context, plus a rolling history of what was recognized
so you can review and correct it in the GUI.
"""

import json
import os
import time

from .config import APPDATA_DIR

EXAMPLES_PATH = os.path.join(APPDATA_DIR, "learned_examples.json")
HISTORY_PATH = os.path.join(APPDATA_DIR, "history.json")
MAX_HISTORY = 50
MAX_EXAMPLES_IN_PROMPT = 20


def _ensure_dir():
    os.makedirs(APPDATA_DIR, exist_ok=True)


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path, data):
    _ensure_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_examples():
    return _load_json(EXAMPLES_PATH, [])


def add_example(utterance: str, phrase: str):
    examples = load_examples()
    examples = [e for e in examples if e["utterance"] != utterance]
    examples.append({"utterance": utterance, "phrase": phrase})
    _save_json(EXAMPLES_PATH, examples)


def relevant_examples(commands: list):
    valid_phrases = {c["phrase"] for c in commands}
    examples = [e for e in load_examples() if e["phrase"] in valid_phrases]
    return examples[-MAX_EXAMPLES_IN_PROMPT:]


def load_history():
    return _load_json(HISTORY_PATH, [])


def add_history_entry(utterance: str, matched_phrase, confidence: str):
    history = load_history()
    history.append({
        "utterance": utterance,
        "matched_phrase": matched_phrase,
        "confidence": confidence,
        "timestamp": time.time(),
    })
    _save_json(HISTORY_PATH, history[-MAX_HISTORY:])
