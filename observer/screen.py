"""Screen capture, region crops, debounce, and the bbox-honesty check.

Capture goes through python-xlib's XGetImage on the Xvfb display, which is
about 25 ms for a full 1920x1080 frame — fast enough that the observer is not
a meaningful share of the step time we are measuring.
"""
from __future__ import annotations

import base64
import hashlib
import io
import time

import numpy as np
from PIL import Image

_display = None


def _get_display():
    global _display
    if _display is None:
        from Xlib import display as xdisplay
        _display = xdisplay.Display()
    return _display


def grab(box=None) -> Image.Image:
    """Full screen, or a region as (x, y, w, h)."""
    d = _get_display()
    root = d.screen().root
    geom = root.get_geometry()
    if box is None:
        x, y, w, h = 0, 0, geom.width, geom.height
    else:
        x, y, w, h = box
        x = max(0, min(int(x), geom.width - 1))
        y = max(0, min(int(y), geom.height - 1))
        w = max(1, min(int(w), geom.width - x))
        h = max(1, min(int(h), geom.height - y))
    raw = root.get_image(x, y, w, h, 0x02, 0xFFFFFFFF)
    im = Image.frombytes("RGB", (w, h), raw.data, "raw", "BGRX")
    return im


def to_png_b64(im: Image.Image) -> tuple:
    """Returns (base64_png, n_bytes, (w, h))."""
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=False, compress_level=3)
    data = buf.getvalue()
    return base64.b64encode(data).decode("ascii"), len(data), im.size


# Anthropic bills images at roughly (w*h)/750 tokens, and downscales anything
# whose long edge exceeds 1568 px before doing so.
def image_tokens(size) -> int:
    w, h = size
    long_edge = max(w, h)
    if long_edge > 1568:
        s = 1568 / long_edge
        w, h = int(w * s), int(h * s)
    return int((w * h) / 750)


ANCHOR_SIZE = (1280, 720)   # ~1229 image tokens; see DECISIONS D3.2


def anchor_capture():
    """Full-screen capture, downscaled to the standard agent resolution."""
    im = grab()
    native = im.size
    small = im.resize(ANCHOR_SIZE, Image.LANCZOS)
    b64, nbytes, size = to_png_b64(small)
    return {
        "b64": b64, "bytes": nbytes, "size": size, "native": native,
        "tokens": image_tokens(size),
        "scale_x": native[0] / size[0], "scale_y": native[1] / size[1],
    }


_CROP_PAD = 6
_CROP_MIN = 24
_CROP_MAX = (640, 400)


def crop_for(bbox, label=""):
    """Crop of an element's region, padded, capped, and labelled.

    The label with absolute coordinates is what makes the crop usable: without
    it the model has a fragment of image with no place on the screen.
    """
    x, y, w, h = bbox
    x -= _CROP_PAD
    y -= _CROP_PAD
    w += 2 * _CROP_PAD
    h += 2 * _CROP_PAD
    if w < _CROP_MIN:
        x -= (_CROP_MIN - w) // 2
        w = _CROP_MIN
    if h < _CROP_MIN:
        y -= (_CROP_MIN - h) // 2
        h = _CROP_MIN
    im = grab((x, y, w, h))
    if im.width > _CROP_MAX[0] or im.height > _CROP_MAX[1]:
        im.thumbnail(_CROP_MAX, Image.LANCZOS)
    b64, nbytes, size = to_png_b64(im)
    return {
        "b64": b64, "bytes": nbytes, "size": size,
        "tokens": image_tokens(size), "label": label,
        "region": (int(x), int(y), int(w), int(h)),
    }


def _fingerprint(im: Image.Image) -> str:
    small = im.resize((80, 45), Image.BILINEAR).convert("L")
    return hashlib.md5(small.tobytes()).hexdigest()


def wait_stable(timeout=3.0, quiet=0.28, poll=0.09) -> dict:
    """Debounce: block until the screen stops moving.

    Returns timing so the cost of debouncing is visible in the results rather
    than hidden inside the step time.
    """
    t0 = time.time()
    last_fp = None
    stable_since = None
    polls = 0
    while time.time() - t0 < timeout:
        fp = _fingerprint(grab())
        polls += 1
        now = time.time()
        if fp == last_fp:
            if stable_since is None:
                stable_since = now
            elif now - stable_since >= quiet:
                return {"stable": True, "waited_s": now - t0, "polls": polls}
        else:
            stable_since = None
            last_fp = fp
        time.sleep(poll)
    return {"stable": False, "waited_s": time.time() - t0, "polls": polls}


def verify_bbox(bbox, declared_text: str) -> bool:
    """Does the region actually contain something consistent with the tree?

    This is the cheap in-the-loop version of the coverage check: an element
    that declares text but whose region is a flat expanse of one colour is a
    tree that is lying, which is the Electron failure mode. Returns True when
    the box looks consistent with what the tree claims.
    """
    x, y, w, h = bbox
    if w <= 2 or h <= 2:
        return False
    try:
        arr = np.asarray(grab((x, y, w, h)).convert("L"), dtype=np.int16)
    except Exception:
        return True  # cannot check -> do not accuse the tree
    if arr.size == 0:
        return False
    spread = float(arr.std())
    if declared_text.strip():
        # Text should produce ink: some contrast inside the box.
        return spread > 3.0
    # No declared text: any box that is not entirely uniform is fine.
    return True
