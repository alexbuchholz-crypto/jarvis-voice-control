"""LLM-based intent matching via a local Ollama server (loopback only,
http://127.0.0.1:11434 — never leaves this machine).

Given a rough spoken utterance, asks a local instruction-tuned model to pick
the configured command that best matches the user's *intent* (not the exact
wording), optionally using previously learned correction examples as
few-shot context so it keeps improving from real usage.
"""

import json
import re

import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL_NAME = "qwen2.5:7b-instruct"

SYSTEM_PROMPT = """Du bist die Intent-Erkennung einer lokalen Sprachsteuerung für einen Windows-PC.
Der Nutzer spricht einen Satz. Du bekommst eine nummerierte Liste verfügbarer Befehle.
Wähle den Befehl, der am besten zur Absicht des Nutzers passt — auch wenn die Formulierung
ganz anders ist als der Befehlstext.

Prüfe IMMER zuerst, ob einer der Befehle in der Liste (auch sinngemäß, auch bei
ganz anderer Formulierung) passt — das hat Vorrang. Nutze "open_app" NUR, wenn
der Nutzer erkennbar ein bestimmtes, konkretes Programm/App öffnen/starten
möchte (z.B. "oeffne epic games", "starte discord") UND kein Befehl aus der
Liste inhaltlich dazu passt. Allgemeine Formulierungen wie "spiel musik" oder
"mach musik an" sind Wiedergabesteuerung, KEIN App-Öffnen — dafür gilt der
passende Befehl aus der Liste, falls vorhanden.

Wenn der Nutzer nach der aktuellen Uhrzeit fragt (z.B. "wie spaet ist es",
"wieviel uhr ist es"), setze "system_query" auf "time". Wenn er nach dem
heutigen Datum oder Wochentag fragt (z.B. "welcher tag ist heute",
"welches datum haben wir", "welcher wochentag ist heute", "der wievielte
ist heute"), setze "system_query" auf "date".

Wenn nichts davon passt, gib alle drei Felder als null zurück.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt, ohne weitere Erklärung, in genau diesem Format:
{"command_index": <Zahl oder null>, "open_app": <Programmname oder null>, "system_query": "time"|"date"|null, "confidence": "high"|"medium"|"low"}
"""


def _build_user_message(utterance: str, commands: list, learned_examples: list) -> str:
    lines = ["Verfügbare Befehle:"]
    for i, cmd in enumerate(commands):
        desc = cmd.get("description") or cmd["phrase"]
        lines.append(f'{i}: "{cmd["phrase"]}" ({desc})')

    if learned_examples:
        lines.append("\nGelernte Beispiele aus früheren Korrekturen (Satz -> richtiger Befehl):")
        for ex in learned_examples:
            lines.append(f'"{ex["utterance"]}" -> "{ex["phrase"]}"')

    lines.append(f'\nSatz des Nutzers: "{utterance}"')
    return "\n".join(lines)


def _extract_json(text: str):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


class LlmMatcher:
    def __init__(self, model_name: str = MODEL_NAME, timeout: float = 15.0):
        self.model_name = model_name
        self.timeout = timeout

    def is_reachable(self) -> bool:
        try:
            requests.get("http://127.0.0.1:11434/api/version", timeout=2)
            return True
        except requests.RequestException:
            return False

    def warmup(self):
        """Fires a minimal real request so the model gets loaded into GPU
        memory ahead of time, instead of on the user's first real command
        (which would otherwise take up to a minute)."""
        try:
            requests.post(
                OLLAMA_URL,
                json={
                    "model": self.model_name,
                    "messages": [{"role": "user", "content": "hallo"}],
                    "stream": False,
                    "options": {"temperature": 0.0},
                    "keep_alive": "30m",
                },
                timeout=120,
            )
        except requests.RequestException:
            pass

    def best_match(self, utterance: str, commands: list, learned_examples: list):
        """Returns (command_dict_or_None, confidence_str)."""
        if not commands or not utterance:
            return None, "low"

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_message(utterance, commands, learned_examples)},
            ],
            "stream": False,
            "options": {"temperature": 0.0},
            "keep_alive": "30m",
        }
        response = requests.post(OLLAMA_URL, json=payload, timeout=self.timeout)
        response.raise_for_status()
        content = response.json()["message"]["content"]

        parsed = _extract_json(content)
        if not parsed:
            return None, "low"

        confidence = parsed.get("confidence", "low")

        idx = parsed.get("command_index")
        if isinstance(idx, int) and 0 <= idx < len(commands):
            return commands[idx], confidence

        app_name = parsed.get("open_app")
        if isinstance(app_name, str) and app_name.strip():
            synthetic_command = {
                "phrase": app_name,
                "response": f"{app_name} wird geöffnet",
                "action": {"type": "open_app", "target": app_name.strip()},
            }
            return synthetic_command, confidence

        system_query = parsed.get("system_query")
        if system_query in ("time", "date"):
            synthetic_command = {
                "phrase": f"system:{system_query}",
                "response": None,
                "action": {"type": "system_info", "query": system_query},
            }
            return synthetic_command, confidence

        return None, confidence
