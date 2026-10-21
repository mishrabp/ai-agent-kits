# Installs the kit's third-party packages on first use, because Claude Code installs plugins without running any
# install step. Packages go into a private folder (the plugin's data directory), never into the user's Python.
# Standard library only: this runs before anything is installed. Nothing here may print to stdout, which carries
# the MCP protocol.
import importlib
import os
import shutil
import subprocess
import sys
import threading
import time

REQUIREMENTS = ["yfinance>=0.2.54", "ddgs>=9", "beautifulsoup4>=4.12"]
IMPORTS = ["yfinance", "ddgs", "bs4"]


def data_dir():
    v = os.environ.get("OPTIONS_KIT_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
    if not v or v.startswith("${"):  # an unresolved plugin variable arrives as literal text
        v = os.path.join(os.path.expanduser("~"), ".cache", "options-analyst-kit")
    return v


TARGET = os.path.join(data_dir(), f"pylib-py{sys.version_info.major}{sys.version_info.minor}")
_ready = threading.Event()
_error = None


def _importable():
    importlib.invalidate_caches()
    try:
        for name in IMPORTS:
            importlib.import_module(name)
        return True
    except ImportError:
        return False


def _install():
    os.makedirs(TARGET, exist_ok=True)
    lock = os.path.join(TARGET, ".installing")
    # Another session may be installing right now: wait for it rather than install twice.
    for _ in range(600):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if time.time() - os.path.getmtime(lock) > 900:
                os.remove(lock)  # a crashed install left it behind
            time.sleep(1)
            if _importable():
                return
    try:
        uv = shutil.which("uv")
        if uv:
            cmd = [uv, "pip", "install", "--quiet", "--python", sys.executable, "--target", TARGET, *REQUIREMENTS]
        else:
            cmd = [sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
                   "--target", TARGET, *REQUIREMENTS]
        print(f"options-analyst-kit: installing {', '.join(REQUIREMENTS)} into {TARGET}", file=sys.stderr)
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                "Could not install the kit's Python packages. Install `uv` or `pip` for this Python, or run:\n"
                f"  {sys.executable} -m pip install --target \"{TARGET}\" {' '.join(REQUIREMENTS)}\n\n{proc.stdout[-2000:]}"
            )
    finally:
        try:
            os.remove(lock)
        except FileNotFoundError:
            pass


def _ensure():
    global _error
    try:
        if TARGET not in sys.path:
            sys.path.insert(0, TARGET)
        if not _importable():
            _install()
            if not _importable():
                raise RuntimeError(f"Packages installed into {TARGET} but still can't be imported.")
    except Exception as err:  # noqa: BLE001 - reported to Claude on the next tool call
        _error = err
    finally:
        _ready.set()


def start():
    """Begin making the packages available in the background, so the MCP server can answer immediately."""
    threading.Thread(target=_ensure, daemon=True).start()


def wait(timeout=600):
    """Block a tool call until the packages are ready (the first install can take a minute or two)."""
    if not _ready.wait(timeout):
        raise RuntimeError("Still installing the kit's Python packages; try again in a minute.")
    if _error:
        raise RuntimeError(str(_error))
