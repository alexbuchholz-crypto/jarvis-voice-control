"""Executes configured actions. Every action runs locally against this machine only."""

import os
import subprocess

import keyboard
import mouse

ACTION_TYPES = ["hotkey", "launch", "media", "mouse_click", "mouse_scroll", "shell"]

MEDIA_KEYS = {
    "volume up",
    "volume down",
    "volume mute",
    "play/pause media",
    "next track",
    "previous track",
}


def execute(action: dict):
    """Runs one configured action. Raises ValueError for a malformed action dict."""
    action_type = action.get("type")

    if action_type == "hotkey":
        keys = action.get("keys") or []
        if not keys:
            raise ValueError("hotkey action needs a non-empty 'keys' list")
        keyboard.send("+".join(keys))

    elif action_type == "launch":
        target = action.get("target")
        if not target:
            raise ValueError("launch action needs a 'target' path or URL")
        os.startfile(target)

    elif action_type == "media":
        key = action.get("key")
        if key not in MEDIA_KEYS:
            raise ValueError(f"unknown media key: {key!r}")
        keyboard.send(key)

    elif action_type == "mouse_click":
        x, y = action.get("x"), action.get("y")
        button = action.get("button", "left")
        if x is None or y is None:
            raise ValueError("mouse_click action needs 'x' and 'y'")
        mouse.move(x, y, absolute=True, duration=0)
        mouse.click(button)

    elif action_type == "mouse_scroll":
        amount = action.get("amount", 1)
        mouse.wheel(amount)

    elif action_type == "shell":
        command = action.get("command")
        if not command:
            raise ValueError("shell action needs a 'command' string")
        subprocess.Popen(command, shell=True)

    else:
        raise ValueError(f"unknown action type: {action_type!r}")
