"""Runs the Ollama server as a hidden background process managed by Jarvis
itself, instead of Ollama's own separate tray app — so there's only one
tray icon to deal with. Only the plain 'ollama.exe serve' binary is used
(no GUI wrapper, no separate window)."""

import os
import subprocess
import time

import requests

OLLAMA_EXE = r"C:\Users\alexb\AppData\Local\Programs\Ollama\ollama.exe"
VERSION_URL = "http://127.0.0.1:11434/api/version"


def is_running() -> bool:
    try:
        requests.get(VERSION_URL, timeout=2)
        return True
    except requests.RequestException:
        return False


def start_background():
    """Starts 'ollama serve' hidden if it isn't already running.
    Returns the Popen handle if we started it (caller may stop it later),
    or None if Ollama was already running (owned by someone/something else,
    so we leave it alone) or if the executable can't be found."""
    if is_running():
        return None
    if not os.path.exists(OLLAMA_EXE):
        return None

    process = subprocess.Popen(
        [OLLAMA_EXE, "serve"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    for _ in range(60):
        if is_running():
            break
        time.sleep(0.5)
    return process


def stop(process):
    if process is not None and process.poll() is None:
        process.terminate()
