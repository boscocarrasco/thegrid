"""Deterministic reset of the desktop between runs.

Every run must start from byte-identical state, otherwise arm differences are
confounded by whatever the previous run left behind (a restored editor
session, a remembered window size, a LibreOffice recovery prompt). There is no
container snapshot available here, so state is reset by wiping the specific
config/cache/session trees the four applications use and rebuilding the
workspace fixtures from scratch.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time

HOME = os.path.expanduser("~")
WORK = os.path.join(HOME, "grid-work")

_APP_STATE = [
    ".config/Mousepad", ".cache/Mousepad", ".local/share/Mousepad",
    ".config/pcmanfm", ".cache/pcmanfm",
    ".config/libreoffice", ".cache/libreoffice",
    ".config/chromium-grid",
    ".config/xfce4",
    ".local/share/recently-used.xbel",
]

_PROCS = ["mousepad", "pcmanfm", "soffice.bin", "oosplash", "chrome",
          "chromium", "libreoffice"]


def kill_apps(wait=1.0):
    for name in _PROCS:
        subprocess.run(["pkill", "-x", name], capture_output=True)
    time.sleep(wait)
    for name in _PROCS:
        subprocess.run(["pkill", "-9", "-x", name], capture_output=True)
    time.sleep(0.4)


def _write_mousepad_config():
    """Turn off session restore so no modal blocks the next run."""
    d = os.path.join(HOME, ".config/Mousepad")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "mousepadrc"), "w") as f:
        f.write(
            "[settings]\n"
            "session-restore=never\n"
            "search-history-size=0\n"
            "[window]\n"
            "statusbar-visible=true\n"
            "toolbar-visible=true\n"
            "menubar-visible=true\n"
        )


def _write_libreoffice_config():
    """Disable the first-run wizard and crash-recovery prompt."""
    d = os.path.join(HOME, ".config/libreoffice/4/user")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "registrymodifications.xcu"), "w") as f:
        f.write(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<oor:items xmlns:oor="http://openoffice.org/2001/registry" '
            'xmlns:xs="http://www.w3.org/2001/XMLSchema">\n'
            '<item oor:path="/org.openoffice.Setup/Office"><prop '
            'oor:name="OfficeRestartInProgress" oor:op="fuse">'
            '<value>false</value></prop></item>\n'
            '<item oor:path="/org.openoffice.Office.Common/Misc"><prop '
            'oor:name="FirstRun" oor:op="fuse"><value>false</value></prop></item>\n'
            '<item oor:path="/org.openoffice.Office.Recovery/RecoveryInfo">'
            '<prop oor:name="Enabled" oor:op="fuse"><value>false</value></prop>'
            '</item>\n'
            '</oor:items>\n'
        )


# ---------------------------------------------------------------- fixtures

def _fixtures():
    """The workspace every task starts from. Kept small and explicit so the
    verifiers can assert exact content."""
    return {
        "notes/alpha.txt": "alpha one\nalpha two\nalpha three\n",
        "notes/beta.txt": "beta line\n",
        "notes/gamma.txt": "gamma line\n",
        "inbox/report-draft.txt": (
            "QUARTERLY REPORT\n"
            "revenue: 1240\n"
            "costs: 830\n"
            "headcount: 12\n"
        ),
        "inbox/readme.txt": "nothing to see here\n",
        "archive/.keep": "",
        "data/values.csv": "item,qty,price\npens,10,1.5\npads,4,3.25\nink,2,7.0\n",
        "data/people.csv": "name,dept\nrosa,eng\nkim,ops\nlee,eng\n",
    }


def reset(extra_files=None, remove=()):
    """Wipe app state and rebuild the workspace. Returns the workspace path."""
    kill_apps()
    for rel in _APP_STATE:
        p = os.path.join(HOME, rel)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
        elif os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass

    _write_mousepad_config()
    _write_libreoffice_config()

    if os.path.isdir(WORK):
        shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)

    files = dict(_fixtures())
    if extra_files:
        files.update(extra_files)
    for rel in remove:
        files.pop(rel, None)
    for rel, content in files.items():
        p = os.path.join(WORK, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(p, mode) as f:
            f.write(content)
    return WORK


# ---------------------------------------------------------------- launching

def _place(pattern, x, y, w, h, tries=12):
    """Force a window to a fixed geometry so coordinates are reproducible."""
    for _ in range(tries):
        r = subprocess.run(["xdotool", "search", "--name", pattern],
                           capture_output=True, text=True)
        wins = [l for l in r.stdout.split() if l.strip()]
        if wins:
            wid = wins[-1]
            subprocess.run(["xdotool", "windowsize", wid, str(w), str(h)],
                           capture_output=True)
            subprocess.run(["xdotool", "windowmove", wid, str(x), str(y)],
                           capture_output=True)
            subprocess.run(["xdotool", "windowactivate", wid], capture_output=True)
            return True
        time.sleep(0.5)
    return False


def launch_editor(path=None, geom=(80, 60, 1000, 700), wait=4.0):
    cmd = ["mousepad"]
    if path:
        cmd.append(path)
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(wait)
    _place("Mousepad", *geom)
    time.sleep(0.6)
    return True


def launch_files(path=None, geom=(60, 40, 980, 720), wait=4.5):
    subprocess.Popen(["pcmanfm", "--new-win", path or WORK],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(wait)
    _place("pcmanfm|File Manager|grid-work", *geom)
    time.sleep(0.6)
    return True


def launch_calc(path=None, geom=(40, 30, 1500, 900), wait=20.0):
    cmd = ["localc", "--norestore", "--nologo", "--nolockcheck"]
    if path:
        cmd.append(path)
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(wait)
    _place("LibreOffice Calc", *geom)
    time.sleep(1.0)
    return True


CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"


def launch_browser(url, geom=(60, 40, 1400, 900), wait=7.0, cdp_port=9222):
    prof = os.path.join(HOME, ".config/chromium-grid")
    os.makedirs(prof, exist_ok=True)
    subprocess.Popen([
        CHROMIUM,
        "--force-renderer-accessibility",
        f"--remote-debugging-port={cdp_port}",
        f"--user-data-dir={prof}",
        "--no-first-run", "--no-default-browser-check",
        "--disable-features=Translate,MediaRouter",
        "--disable-background-networking", "--disable-sync",
        "--window-size=%d,%d" % (geom[2], geom[3]),
        "--window-position=%d,%d" % (geom[0], geom[1]),
        url,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(wait)
    _place("Chromium|chrome", *geom)
    time.sleep(0.8)
    return True
