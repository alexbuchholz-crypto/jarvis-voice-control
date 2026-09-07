"""Finds installed programs by name via Windows Start Menu shortcuts, so
Jarvis can open arbitrary apps ("oeffne epic games") without every single
program having to be manually configured as a command."""

import difflib
import os

SEARCH_DIRS = [
    os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"),
                 "Microsoft", "Windows", "Start Menu", "Programs"),
    os.path.join(os.environ.get("APPDATA", ""),
                 "Microsoft", "Windows", "Start Menu", "Programs"),
]


def _list_shortcuts():
    shortcuts = []
    for base_dir in SEARCH_DIRS:
        if not os.path.isdir(base_dir):
            continue
        for root, _dirs, files in os.walk(base_dir):
            for name in files:
                if name.lower().endswith((".lnk", ".url")):
                    display_name = os.path.splitext(name)[0]
                    shortcuts.append((display_name, os.path.join(root, name)))
    return shortcuts


def find_app(query: str, threshold: float = 0.45):
    """Returns the path to the best-matching Start Menu shortcut, or None."""
    query_norm = query.strip().lower()
    if not query_norm:
        return None

    shortcuts = _list_shortcuts()
    best_score, best_path = 0.0, None
    for name, path in shortcuts:
        name_norm = name.lower()
        if name_norm == query_norm:
            score = 1.0
        else:
            score = difflib.SequenceMatcher(None, query_norm, name_norm).ratio()
            if name_norm.startswith(query_norm) or query_norm.startswith(name_norm):
                score = max(score, 0.7)
        if score > best_score:
            best_score, best_path = score, path

    if best_score >= threshold:
        return best_path
    return None
