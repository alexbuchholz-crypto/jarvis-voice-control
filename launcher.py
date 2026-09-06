import os
import shutil
import subprocess
import sys

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MAIN_SCRIPT = os.path.join(BASE_DIR, "main.py")
FALLBACK_PYTHONW = r"C:\Users\alexb\AppData\Local\Programs\Python\Python313\pythonw.exe"
FALLBACK_PYTHON = r"C:\Users\alexb\AppData\Local\Programs\Python\Python313\python.exe"


def _find_interpreter():
    found = shutil.which("pythonw")
    if found:
        return found
    if os.path.exists(FALLBACK_PYTHONW):
        return FALLBACK_PYTHONW
    found = shutil.which("python")
    if found:
        return found
    return FALLBACK_PYTHON


if __name__ == "__main__":
    interpreter = _find_interpreter()
    subprocess.Popen(
        [interpreter, MAIN_SCRIPT],
        cwd=BASE_DIR,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
