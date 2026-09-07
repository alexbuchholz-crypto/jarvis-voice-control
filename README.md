# Jarvis Voice Control

Lokale, sprachgesteuerte Fernbedienung für deinen PC. Läuft komplett offline
(Vosk-Spracherkennung + lokales Ollama-Sprachmodell + lokale KI-Sprachausgabe
per Voice-Cloning) und legt sich als Tray-Icon in die Taskleiste, damit du
z.B. beim Spielen nicht aus dem Fenster tappen musst.

Alles läuft lokal auf diesem Rechner — die einzigen Netzwerkanfragen gehen an
`127.0.0.1` (Loopback, das lokale Ollama), verlassen also nie den PC. Einzige
Ausnahme sind die einmaligen Modell-Downloads beim Setup.

## Schnellstart für neue Installationen (z.B. Familie)

Reihenfolge einhalten, sonst gibt's Versionskonflikte:

1. **Python 3.13** installieren: `winget install Python.Python.3.13`
2. **Ollama** installieren und Modell laden:
   ```bash
   winget install Ollama.Ollama
   ollama pull qwen2.5:7b-instruct
   ```
3. **Deutsches Vosk-Sprachmodell** herunterladen und in `models/` entpacken:
   https://alphacephei.com/vosk/models/vosk-model-de-0.21.zip (ca. 2 GB)
   → Ordner `vosk-model-de-0.21` muss direkt unter `models/` liegen.
4. **Python-Abhängigkeiten** installieren:
   ```bash
   pip install -r requirements.txt
   pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
   pip install transformers==4.57.0
   pip install torchcodec
   ```
   (Ohne NVIDIA-GPU: den `torch`-Befehl weglassen, dann läuft die
   Sprachausgabe auf der CPU — deutlich langsamer, aber funktioniert.)
5. Starten: `python main.py` (erster Start dauert wegen der Modelle
   1-2 Minuten, danach ist alles bereit).

Eigene Befehle, Wake-Word usw. lassen sich danach direkt im
Einstellungsfenster anpassen — jede Installation hat ihre eigene, lokale
Konfiguration unter `%APPDATA%\JarvisVoiceControl\`.

## Funktionsweise

1. Das Programm hört über dein Mikrofon ständig mit (lokal, offline).
2. Erst wenn ein Satz mit dem **Wake-Word** beginnt (Standard: "jarvis"),
   wird der Rest des Satzes an ein lokales Sprachmodell (Ollama,
   `qwen2.5:7b-instruct`) übergeben.
3. Das Modell wählt anhand deiner konfigurierten Befehle den am besten
   passenden aus — **du musst den Befehl nicht wortwörtlich sagen**, es
   reicht, sinngemäß zu sagen was passieren soll (z.B. "kannst du das lauter
   machen" statt nur "lauter").
4. Bei einer Übereinstimmung wird die zugehörige Aktion ausgeführt und optional
   eine gesprochene Antwort ausgegeben.

Beispiel: *"Jarvis, lauter"* → Lautstärke wird erhöht, Antwort: "Lautstärke wird erhöht".

### Selbstlernender Abgleich

Im Tab **"Verlauf"** siehst du, was zuletzt erkannt wurde (inkl. nicht
erkannter Sätze). War die Erkennung falsch oder hat gar nicht reagiert,
wähle dort den eigentlich gemeinten Befehl aus und klicke
**"Als richtig merken"** — der Satz wird dauerhaft gespeichert und beim
nächsten Mal als Beispiel mitgegeben. Das ist kein "Neu-Trainieren" der KI
(deren Gewichte bleiben unverändert), sondern ein wachsendes lokales
Gedächtnis aus deinen Korrekturen, das die Trefferquote mit der Zeit
verbessert.

Falls Ollama einmal nicht erreichbar ist, fällt das Programm automatisch auf
einen einfachen Text-Abgleich zurück (dann muss der Befehl wieder näher am
konfigurierten Wortlaut sein).

## Setup

Abhängigkeiten, das deutsche Vosk-Sprachmodell und Ollama sind bereits
installiert. Falls neu aufgesetzt:

```bash
pip install -r requirements.txt
```

Das Vosk-Sprachmodell liegt in `models/vosk-model-small-de-0.15/` (offline
nutzbar, kein erneuter Download nötig).

Für das Verstehen der Befehle wird [Ollama](https://ollama.com) benötigt
(läuft als lokaler Hintergrunddienst, startet automatisch mit Windows):

```bash
winget install Ollama.Ollama
ollama pull qwen2.5:7b-instruct
```

## Starten

```bash
python main.py
```

Öffnet ein Einstellungsfenster und legt ein Tray-Icon an. Über "Start" beginnt
das Zuhören. Das Fenster kann per Kreuz oder Tray-Menü "Einstellungen
anzeigen" geschlossen/geöffnet werden, ohne das Programm zu beenden.

**Ohne sichtbares Konsolenfenster starten** (z.B. für einen Autostart-Eintrag):

```bash
pythonw main.py
```

### Beim Windows-Start automatisch ausführen

1. `Win+R` → `shell:startup` → Enter, öffnet den Autostart-Ordner.
2. Dort eine Verknüpfung anlegen, die auf `pythonw.exe` mit dem Argument
   `main.py` (Arbeitsverzeichnis: dieser Projektordner) zeigt.

## Befehle konfigurieren

Im Einstellungsfenster über "Hinzufügen"/"Bearbeiten"/"Löschen". Jeder Befehl
besteht aus:

- **Sprachbefehl**: Text nach dem Wake-Word, z.B. "lauter".
- **Antwort**: was das Programm optional dazu sagt.
- **Aktionstyp**:
  - `hotkey` — sendet eine Tastenkombination (z.B. `ctrl+alt+t`)
  - `launch` — öffnet ein Programm, eine Datei oder eine URL
  - `media` — Lautstärke/Wiedergabe (volume up/down/mute, play/pause, next/previous track)
  - `mouse_click` — Klick an fester Bildschirmposition
  - `mouse_scroll` — scrollt
  - `shell` — führt eine beliebige Befehlszeile aus (mächtigster, aber am wenigsten
    abgesicherter Typ — nur für eigene, vertrauenswürdige Befehle verwenden)

Die Erkennung toleriert leichte Abweichungen (z.B. Sprachfehler des Modells)
über einen Fuzzy-Match; die Empfindlichkeit lässt sich über `match_threshold`
in der Konfigurationsdatei justieren.

Konfiguration liegt unter `%APPDATA%\JarvisVoiceControl\config.json`.

## Sprachausgabe (TTS)

Jarvis spricht mit einer per KI (Coqui XTTS-v2) geklonten Stimme, GPU-
beschleunigt, komplett lokal. Referenz-Stimme: `tts_models/speaker_samples/
speaker_150.mp3` — ein Sample aus einem offen lizenzierten Sprachdatensatz
(nicht deine eigene Stimme, keine echte fremde Person, kein geschütztes
Charakter-/Promi-Voice-Clone).

Audio wird gestreamt statt komplett vorab berechnet: der erste Ton kommt nach
ca. 0,6-0,8 Sekunden, nicht erst wenn der ganze Satz fertig generiert ist.

**Installation ist ein bisschen speziell** (Python 3.13 + einige ML-Pakete
vertragen sich noch nicht reibungslos), daher diese Reihenfolge:

```bash
pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
pip install coqui-tts
pip install transformers==4.57.0
pip install torchcodec
```

Der erste Start lädt das XTTS-Modell einmalig herunter (~1,9 GB) und lädt es
danach bei jedem Jarvis-Start neu in den GPU-Speicher (~30-40 Sekunden,
bevor die allererste Antwort kommt).

Andere Stimme nehmen: `REFERENCE_VOICE` in `app/tts.py` auf eine andere
`.mp3`/`.wav`-Datei zeigen lassen (mind. ein paar Sekunden klare Sprache).

## Bekannte Einschränkungen

- **Anti-Cheat-Software**: Manche Spiele mit Kernel-Anticheat (z.B. Vanguard,
  EasyAntiCheat, BattlEye) behandeln synthetische Tastatur-/Mauseingaben von
  Fremdprozessen mit Misstrauen — das betrifft grundsätzlich jedes Tool dieser
  Art (AutoHotkey, VoiceAttack, etc.), nicht nur dieses. Im Zweifel vorher
  informieren, ob das jeweilige Spiel das zulässt.
- Manche als Administrator gestartete Spiele nehmen nur Eingaben von ebenfalls
  erhöhten Prozessen an — in dem Fall `main.py` ebenfalls als Administrator
  starten.
- Die Spracherkennungsqualität hängt vom Mikrofon und Hintergrundgeräuschen
  (z.B. Spielsound, Discord) ab. Bei häufigen Fehlerkennungen den Schwellwert
  `match_threshold` erhöhen oder ein größeres Vosk-Modell verwenden.
