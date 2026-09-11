"""The task suite and its programmatic verifiers.

Every task ends in a machine check of final state — a file's bytes, a cell's
value, a row count. No model judges success anywhere in this harness.

Coverage required by the brief: file operations, text editing and formatting,
spreadsheet, a browser form, one task spanning two applications, and two or
three tasks whose content is non-textual (a chart, an image, a custom-drawn
control) because those are the ones that should separate arm B from arm C.
"""
from __future__ import annotations

import csv
import io
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Callable

from tasks import workspace as ws

WORK = ws.WORK


@dataclass
class Task:
    id: str
    prompt: str
    setup: Callable          # (seed) -> None ; leaves the desktop ready
    verify: Callable         # () -> (bool, str)
    max_steps: int = 14
    tags: tuple = ()
    apps: tuple = ()
    # Constraints stated explicitly in the prompt, each separately checkable.
    # They feed the persistent task object (§5.3) and the per-constraint
    # verifier decomposition that tells "failed the task" apart from "forgot a
    # constraint".
    constraints: tuple = ()
    # () -> {name: bool}; None means the task has no decomposition.
    verify_constraints: Callable = None


# ------------------------------------------------------------------ helpers

def _read(rel):
    p = os.path.join(WORK, rel)
    if not os.path.exists(p):
        return None
    with open(p, "r", errors="replace") as f:
        return f.read()


def _exists(rel):
    return os.path.exists(os.path.join(WORK, rel))


def _norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


# ============================================================ file operations

def t_save_as_setup(seed):
    ws.reset()
    ws.launch_editor(os.path.join(WORK, "notes/alpha.txt"))


def t_save_as_verify():
    c = _read("archive/alpha-copy.txt")
    if c is None:
        return False, "archive/alpha-copy.txt does not exist"
    if "alpha one" not in c:
        return False, f"content wrong: {c[:60]!r}"
    return True, "ok"


def t_append_setup(seed):
    ws.reset()
    ws.launch_editor(os.path.join(WORK, "notes/beta.txt"))


def t_append_verify():
    c = _read("notes/beta.txt")
    if c is None:
        return False, "file missing"
    if "beta line" not in c:
        return False, "original line lost"
    if "APPROVED" not in c:
        return False, f"APPROVED not found in {c[:80]!r}"
    return True, "ok"


def t_newfile_setup(seed):
    ws.reset()
    ws.launch_editor()


def t_newfile_verify():
    c = _read("notes/shopping.txt")
    if c is None:
        return False, "notes/shopping.txt does not exist"
    want = ["bread", "milk", "olives"]
    got = _norm(c)
    missing = [w for w in want if w not in got]
    if missing:
        return False, f"missing {missing} in {c[:80]!r}"
    return True, "ok"


def t_replace_setup(seed):
    ws.reset()
    ws.launch_editor(os.path.join(WORK, "inbox/report-draft.txt"))


def t_replace_verify():
    c = _read("inbox/report-draft.txt")
    if c is None:
        return False, "file missing"
    if "1240" in c:
        return False, "old value 1240 still present"
    if "1560" not in c:
        return False, f"new value 1560 not found in {c[:100]!r}"
    return True, "ok"


def t_delete_line_setup(seed):
    ws.reset({"notes/todo.txt": "buy milk\nCANCELLED: old task\nwrite report\n"})
    ws.launch_editor(os.path.join(WORK, "notes/todo.txt"))


def t_delete_line_verify():
    c = _read("notes/todo.txt")
    if c is None:
        return False, "file missing"
    if "CANCELLED" in c:
        return False, "cancelled line still present"
    if "buy milk" not in c or "write report" not in c:
        return False, f"other lines lost: {c[:80]!r}"
    return True, "ok"


def t_rename_setup(seed):
    ws.reset()
    ws.launch_files(WORK)


def t_rename_verify():
    if _exists("notes/gamma.txt"):
        return False, "old name still present"
    if not _exists("notes/gamma-final.txt"):
        return False, "notes/gamma-final.txt not found"
    c = _read("notes/gamma-final.txt")
    if "gamma line" not in (c or ""):
        return False, "content changed unexpectedly"
    return True, "ok"


def t_upper_setup(seed):
    ws.reset({"notes/quiet.txt": "the meeting is at noon\n"})
    ws.launch_editor(os.path.join(WORK, "notes/quiet.txt"))


def t_upper_verify():
    c = _read("notes/quiet.txt")
    if c is None:
        return False, "file missing"
    if "THE MEETING IS AT NOON" not in c.upper():
        return False, f"unexpected content {c[:60]!r}"
    if "THE MEETING IS AT NOON" not in c:
        return False, f"text not uppercased: {c[:60]!r}"
    return True, "ok"


# ================================================================ spreadsheet

def t_calc_cell_setup(seed):
    ws.reset()
    ws.launch_calc(os.path.join(WORK, "data/values.csv"))


def _calc_export_check(rel, checks):
    """Read the sheet the agent was told to save as CSV."""
    c = _read(rel)
    if c is None:
        return False, f"{rel} does not exist"
    rows = list(csv.reader(io.StringIO(c)))
    return checks(rows, c)


# The total `calc_total` asks for: the price column, 1.5 + 3.25 + 7.0.
CALC_TOTAL_EXPECTED = 11.75


def _cells(text):
    """Every cell of a CSV as a raw string, however the sheet quoted it."""
    return [c for row in csv.reader(io.StringIO(text or "")) for c in row]


def calc_total_ok(text):
    """The rule `calc_total` is scored on.

    A module-level predicate rather than a closure because the re-scoring pass
    in `analysis/rescore.py` has to apply exactly this rule to the runs the
    earlier, broken version mis-judged; the rule must live in one place or the
    two can drift. See DECISIONS D6.1 for what that version got wrong.

    A decimal comma counts: LibreOffice writes one under some locales, and the
    task is about the arithmetic, not the separator.
    """
    if text is None:
        return False, "data/values-total.csv does not exist"
    flat = _norm(text)
    missing = [it for it in ("pens", "pads", "ink") if it not in flat]
    if missing:
        return False, f"original item rows {missing} lost: {text[:120]!r}"
    for cell in _cells(text):
        try:
            value = float(cell.strip().replace(",", "."))
        except ValueError:
            continue
        if abs(value - CALC_TOTAL_EXPECTED) < 0.005:
            return True, "ok"
    return False, f"total {CALC_TOTAL_EXPECTED} not found in {text[:120]!r}"


def t_calc_cell_verify():
    def chk(rows, raw):
        return calc_total_ok(raw)
    return _calc_export_check("data/values-total.csv", chk)


def t_calc_add_row_setup(seed):
    ws.reset()
    ws.launch_calc(os.path.join(WORK, "data/values.csv"))


def t_calc_add_row_verify():
    def chk(rows, raw):
        for r in rows:
            if r and _norm(r[0]) == "tape":
                if len(r) >= 3 and "6" in r[1] and "2" in r[2]:
                    return True, "ok"
                return False, f"tape row has wrong values: {r}"
        return False, f"no tape row in {raw[:120]!r}"
    return _calc_export_check("data/values-plus.csv", chk)


def t_calc_count_setup(seed):
    ws.reset()
    ws.launch_calc(os.path.join(WORK, "data/people.csv"))


def t_calc_count_verify():
    c = _read("data/eng-count.txt")
    if c is None:
        return False, "data/eng-count.txt does not exist"
    if "2" not in c:
        return False, f"expected 2, got {c[:40]!r}"
    return True, "ok"


# ==================================================================== browser

FORM_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Supplier form</title>
<style>body{font-family:sans-serif;margin:40px;max-width:640px}
label{display:block;margin:14px 0 4px}input,select{font-size:16px;padding:6px;width:320px}
button{margin-top:20px;font-size:16px;padding:8px 18px}
#done{margin-top:20px;font-weight:bold;color:#0a0}</style></head><body>
<h1>Supplier registration</h1>
<form id="f">
<label for="company">Company name</label><input id="company" name="company">
<label for="contact">Contact email</label><input id="contact" name="contact">
<label for="country">Country</label>
<select id="country" name="country">
 <option value="">-- choose --</option>
 <option value="pt">Portugal</option><option value="es">Spain</option>
 <option value="fr">France</option>
</select>
<button type="submit" id="submit">Submit registration</button>
</form>
<div id="done"></div>
<script>
document.getElementById('f').addEventListener('submit',function(e){
 e.preventDefault();
 var d={company:company.value,contact:contact.value,country:country.value};
 document.getElementById('done').textContent='SUBMITTED '+JSON.stringify(d);
 var a=document.createElement('a');
 a.id='result'; a.dataset.payload=JSON.stringify(d); document.body.appendChild(a);
 fetch('/__submit',{method:'POST',body:JSON.stringify(d)}).catch(function(){});
});
</script></body></html>"""


def _serve_dir():
    d = os.path.join(WORK, "www")
    os.makedirs(d, exist_ok=True)
    return d


def t_form_setup(seed):
    ws.reset()
    d = _serve_dir()
    with open(os.path.join(d, "form.html"), "w") as f:
        f.write(FORM_HTML)
    ws.launch_browser("file://" + os.path.join(d, "form.html"))


def _cdp_eval(expr, port=9222):
    """Read state out of the page over CDP. Used only by the verifier."""
    import json
    import urllib.request
    try:
        tabs = json.load(urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json/list", timeout=5))
    except Exception as e:
        return None, f"cdp list failed: {e}"
    page = next((t for t in tabs if t.get("type") == "page"), None)
    if not page:
        return None, "no page target"
    try:
        from websocket import create_connection  # type: ignore
    except Exception:
        return None, "websocket-client not installed"
    try:
        # Chromium's DevTools endpoint rejects a websocket carrying an
        # Origin header with 403, so it must be suppressed.
        ws_ = create_connection(page["webSocketDebuggerUrl"], timeout=8,
                                suppress_origin=True)
        ws_.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                             "params": {"expression": expr,
                                        "returnByValue": True}}))
        for _ in range(10):
            msg = json.loads(ws_.recv())
            if msg.get("id") == 1:
                ws_.close()
                return msg.get("result", {}).get("result", {}).get("value"), ""
        ws_.close()
        return None, "no cdp reply"
    except Exception as e:
        return None, f"cdp eval failed: {e}"


def t_form_verify():
    val, err = _cdp_eval("document.getElementById('done').textContent")
    if val is None:
        return False, err or "could not read page"
    if not val.startswith("SUBMITTED"):
        return False, f"form not submitted (done={val[:60]!r})"
    ok = ("Northwind" in val or "northwind" in val.lower())
    if not ok:
        return False, f"company wrong: {val[:120]}"
    if "ops@northwind" not in val.lower():
        return False, f"email wrong: {val[:120]}"
    if '"country":"es"' not in val.replace(" ", ""):
        return False, f"country wrong: {val[:120]}"
    return True, "ok"


# =========================================================== non-textual tasks
# These exist to separate B from C: the information the agent needs is only in
# pixels, so a text-only delta cannot carry it.

CHART_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Quarterly chart</title><style>body{font-family:sans-serif;margin:30px}
canvas{border:1px solid #999}input{font-size:16px;padding:6px;width:260px}
button{font-size:16px;padding:8px 16px;margin-left:8px}</style></head><body>
<h1>Which quarter is tallest?</h1>
<canvas id="c" width="520" height="300"></canvas>
<p><label>Answer (Q1/Q2/Q3/Q4): <input id="ans"></label>
<button id="go">Submit answer</button></p>
<div id="out"></div>
<script>
var vals={Q1:120,Q2:60,Q3:200,Q4:95};   // Q3 is tallest
var ctx=document.getElementById('c').getContext('2d');
var i=0;
for(var k in vals){
 var h=vals[k];
 ctx.fillStyle=['#4477aa','#66ccee','#228833','#ccbb44'][i];
 ctx.fillRect(40+i*120, 280-h, 80, h);
 ctx.fillStyle='#000'; ctx.font='14px sans-serif';
 ctx.fillText(k, 65+i*120, 296);
 i++;
}
document.getElementById('go').onclick=function(){
 document.getElementById('out').textContent='ANSWER '+
   document.getElementById('ans').value.trim().toUpperCase();
};
</script></body></html>"""


def t_chart_setup(seed):
    ws.reset()
    d = _serve_dir()
    with open(os.path.join(d, "chart.html"), "w") as f:
        f.write(CHART_HTML)
    ws.launch_browser("file://" + os.path.join(d, "chart.html"))


def t_chart_verify():
    val, err = _cdp_eval("document.getElementById('out').textContent")
    if val is None:
        return False, err or "could not read page"
    if not val.startswith("ANSWER"):
        return False, "no answer submitted"
    if "Q3" not in val:
        return False, f"wrong answer: {val!r} (tallest bar is Q3)"
    return True, "ok"


SHAPES_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Custom control</title><style>body{font-family:sans-serif;margin:30px}
canvas{border:1px solid #999}input{font-size:16px;padding:6px;width:200px}
button{font-size:16px;padding:8px 16px;margin-left:8px}</style></head><body>
<h1>Count the filled circles</h1>
<p>Some circles are filled, some are only outlined. How many are filled?</p>
<canvas id="c" width="520" height="220"></canvas>
<p><label>Count: <input id="ans"></label><button id="go">Submit</button></p>
<div id="out"></div>
<script>
var ctx=document.getElementById('c').getContext('2d');
var filled=[1,0,1,1,0,0,1];            // 4 filled
for(var i=0;i<filled.length;i++){
 ctx.beginPath(); ctx.arc(50+i*68,110,26,0,6.284);
 if(filled[i]){ctx.fillStyle='#333';ctx.fill();}
 else{ctx.strokeStyle='#333';ctx.lineWidth=3;ctx.stroke();}
}
document.getElementById('go').onclick=function(){
 document.getElementById('out').textContent='COUNT '+
   document.getElementById('ans').value.trim();
};
</script></body></html>"""


def t_shapes_setup(seed):
    ws.reset()
    d = _serve_dir()
    with open(os.path.join(d, "shapes.html"), "w") as f:
        f.write(SHAPES_HTML)
    ws.launch_browser("file://" + os.path.join(d, "shapes.html"))


def t_shapes_verify():
    val, err = _cdp_eval("document.getElementById('out').textContent")
    if val is None:
        return False, err or "could not read page"
    m = re.search(r"COUNT\s+(\d+)", val)
    if not m:
        return False, f"no count submitted ({val!r})"
    if m.group(1) != "4":
        return False, f"wrong count {m.group(1)}, expected 4"
    return True, "ok"


BADGE_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Status badges</title><style>body{font-family:sans-serif;margin:30px}
.row{margin:10px 0;font-size:18px}
.b{display:inline-block;width:74px;height:26px;border-radius:13px;
   vertical-align:middle;margin-right:14px}
input{font-size:16px;padding:6px;width:200px}
button{font-size:16px;padding:8px 16px;margin-left:8px}</style></head><body>
<h1>Which server is red?</h1>
<p>The badge colour is the status. Report the name of the red one.</p>
<div class="row"><span class="b" style="background:#2ca02c"></span>alpha</div>
<div class="row"><span class="b" style="background:#2ca02c"></span>bravo</div>
<div class="row"><span class="b" style="background:#d62728"></span>charlie</div>
<div class="row"><span class="b" style="background:#ff7f0e"></span>delta</div>
<p><label>Name: <input id="ans"></label><button id="go">Submit</button></p>
<div id="out"></div>
<script>
document.getElementById('go').onclick=function(){
 document.getElementById('out').textContent='NAME '+
   document.getElementById('ans').value.trim().toLowerCase();
};
</script></body></html>"""


def t_badge_setup(seed):
    ws.reset()
    d = _serve_dir()
    with open(os.path.join(d, "badge.html"), "w") as f:
        f.write(BADGE_HTML)
    ws.launch_browser("file://" + os.path.join(d, "badge.html"))


def t_badge_verify():
    val, err = _cdp_eval("document.getElementById('out').textContent")
    if val is None:
        return False, err or "could not read page"
    if not val.startswith("NAME"):
        return False, "no name submitted"
    if "charlie" not in val:
        return False, f"wrong server: {val!r} (red one is charlie)"
    return True, "ok"


# =========================================================== cross-application

def t_cross_setup(seed):
    ws.reset()
    ws.launch_files(WORK)


def t_cross_verify():
    c = _read("archive/summary.txt")
    if c is None:
        return False, "archive/summary.txt does not exist"
    got = _norm(c)
    if "1240" not in got:
        return False, f"revenue value not copied: {c[:80]!r}"
    if "830" not in got:
        return False, f"costs value not copied: {c[:80]!r}"
    return True, "ok"


def t_cross2_setup(seed):
    ws.reset()
    ws.launch_calc(os.path.join(WORK, "data/values.csv"))


def t_cross2_verify():
    c = _read("notes/inventory-note.txt")
    if c is None:
        return False, "notes/inventory-note.txt does not exist"
    if "3" not in c:
        return False, f"expected item count 3 in {c[:60]!r}"
    return True, "ok"


# ==================================================================== registry

def build_suite():
    T = []

    T.append(Task(
        "files_save_as",
        "In the open text editor, save the current document as a new file at "
        f"{WORK}/archive/alpha-copy.txt , keeping its contents.",
        t_save_as_setup, t_save_as_verify, max_steps=14,
        tags=("files",), apps=("mousepad",)))

    T.append(Task(
        "files_new_note",
        "Using the open text editor, create a shopping list containing the "
        "three lines: bread, milk, olives — one per line — and save it as "
        f"{WORK}/notes/shopping.txt",
        t_newfile_setup, t_newfile_verify, max_steps=14,
        tags=("files", "text"), apps=("mousepad",)))

    T.append(Task(
        "files_rename",
        "In the open file manager, go into the 'notes' folder and rename the "
        "file 'gamma.txt' to 'gamma-final.txt'. Do not change its contents.",
        t_rename_setup, t_rename_verify, max_steps=16,
        tags=("files",), apps=("pcmanfm",)))

    T.append(Task(
        "text_append",
        "In the open text editor, add a new line containing exactly APPROVED "
        "at the end of the document, keeping the existing line, and save.",
        t_append_setup, t_append_verify, max_steps=12,
        tags=("text",), apps=("mousepad",)))

    T.append(Task(
        "text_replace",
        "In the open text editor, the revenue figure is wrong. Change the "
        "revenue value from 1240 to 1560, leave everything else as it is, "
        "and save the file.",
        t_replace_setup, t_replace_verify, max_steps=14,
        tags=("text",), apps=("mousepad",)))

    T.append(Task(
        "text_delete_line",
        "In the open text editor, delete the whole line that starts with "
        "CANCELLED, keep the other two lines, and save the file.",
        t_delete_line_setup, t_delete_line_verify, max_steps=14,
        tags=("text",), apps=("mousepad",)))

    T.append(Task(
        "text_uppercase",
        "In the open text editor, rewrite the single line so it is entirely "
        "in capital letters, then save the file.",
        t_upper_setup, t_upper_verify, max_steps=14,
        tags=("text", "format"), apps=("mousepad",)))

    T.append(Task(
        "calc_total",
        "In the open spreadsheet, work out the total of the price column "
        "(1.5 + 3.25 + 7.0) and put that total in cell C5. Then save a copy as "
        f"CSV at {WORK}/data/values-total.csv (File > Save As, keep CSV format).",
        t_calc_cell_setup, t_calc_cell_verify, max_steps=16,
        tags=("spreadsheet",), apps=("soffice",)))

    T.append(Task(
        "calc_add_row",
        "In the open spreadsheet add a new row below the last one with item "
        "'tape', qty 6 and price 2. Then save a copy as CSV at "
        f"{WORK}/data/values-plus.csv (File > Save As, keep CSV format).",
        t_calc_add_row_setup, t_calc_add_row_verify, max_steps=16,
        tags=("spreadsheet",), apps=("soffice",)))

    T.append(Task(
        "calc_count_eng",
        "The open spreadsheet lists people and their department. Count how "
        "many people are in the 'eng' department, then write just that number "
        f"into a new text file at {WORK}/data/eng-count.txt using the text "
        "editor (you can open it from the Applications, or use the editor "
        "already available).",
        t_calc_count_setup, t_calc_count_verify, max_steps=18,
        tags=("spreadsheet", "cross-app"), apps=("soffice", "mousepad")))

    T.append(Task(
        "web_form",
        "Fill in the supplier registration form in the browser: company name "
        "'Northwind', contact email 'ops@northwind.example', country Spain. "
        "Then submit it.",
        t_form_setup, t_form_verify, max_steps=18,
        tags=("browser", "form"), apps=("chromium",)))

    T.append(Task(
        "visual_chart",
        "The page shows a bar chart of four quarters. Work out which quarter "
        "has the tallest bar, type that quarter's label (Q1, Q2, Q3 or Q4) "
        "into the answer box and submit it.",
        t_chart_setup, t_chart_verify, max_steps=14,
        tags=("browser", "visual"), apps=("chromium",)))

    T.append(Task(
        "visual_shapes",
        "The page draws a row of circles; some are filled solid and some are "
        "only outlined. Count how many are filled, type that number into the "
        "count box and submit.",
        t_shapes_setup, t_shapes_verify, max_steps=14,
        tags=("browser", "visual"), apps=("chromium",)))

    T.append(Task(
        "visual_badge",
        "The page lists four servers, each with a coloured status badge. Find "
        "the one whose badge is red, type that server's name into the box and "
        "submit.",
        t_badge_setup, t_badge_verify, max_steps=14,
        tags=("browser", "visual"), apps=("chromium",)))

    T.append(Task(
        "cross_report_summary",
        "Open the file inbox/report-draft.txt from the file manager, read the "
        "revenue and costs figures in it, and then create a new text file at "
        f"{WORK}/archive/summary.txt containing both numbers (revenue and "
        "costs) on separate lines.",
        t_cross_setup, t_cross_verify, max_steps=18,
        tags=("cross-app", "files"), apps=("pcmanfm", "mousepad")))

    T.append(Task(
        "cross_inventory_note",
        "The open spreadsheet lists stock items. Count how many item rows "
        "there are (not counting the header), then write just that number "
        f"into a new text file at {WORK}/notes/inventory-note.txt",
        t_cross2_setup, t_cross2_verify, max_steps=18,
        tags=("cross-app", "spreadsheet"), apps=("soffice", "mousepad")))

    return T


SUITE = build_suite()
BY_ID = {t.id: t for t in SUITE}


# ================================================ mid-task appearance changes
# The first three "visual" tasks failed to separate B from C because all of
# them are answerable from the anchor screenshot alone, so arm B never emitted
# a single crop. These two put the decisive information in an element that
# *appears during the task* and whose meaning is carried only by its
# appearance: the rows all have identical, unremarkable text, and which one
# matters is encoded in a background colour the accessibility tree does not
# report. Arm B crops every `added` element and therefore sees it; arm C is
# told only "added, list item, 'row-3'" and cannot.

ROWS_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Batch status</title><style>
body{font-family:sans-serif;margin:30px}
button{font-size:16px;padding:8px 18px}
#rows{margin-top:18px}
.r{padding:10px 14px;border:1px solid #bbb;margin:5px 0;width:340px;
   font-size:16px;background:#f4f4f4}
.bad{background:#e03030;color:#fff}
input{font-size:16px;padding:6px;width:180px}
</style></head><body>
<h1>Batch status</h1>
<p>Press Load. Six jobs appear. Exactly one is shown with a red background,
meaning it failed. Report which one.</p>
<button id="load">Load</button>
<div id="rows" role="list"></div>
<p><label>Failed job: <input id="ans"></label>
<button id="go">Submit</button></p>
<div id="out"></div>
<script>
var names=['job-alpha','job-bravo','job-charlie','job-delta','job-echo','job-foxtrot'];
var BAD=3;   // job-delta, encoded only in the colour
document.getElementById('load').onclick=function(){
  var c=document.getElementById('rows'); c.innerHTML='';
  names.forEach(function(n,i){
    var d=document.createElement('div');
    d.className='r'+(i===BAD?' bad':''); d.textContent=n;
    d.setAttribute('role','listitem'); d.setAttribute('aria-label',n);
    c.appendChild(d);
  });
};
document.getElementById('go').onclick=function(){
  document.getElementById('out').textContent='FAILED '+
    document.getElementById('ans').value.trim().toLowerCase();
};
</script></body></html>"""


def t_rows_setup(seed):
    ws.reset()
    d = _serve_dir()
    with open(os.path.join(d, "rows.html"), "w") as f:
        f.write(ROWS_HTML)
    ws.launch_browser("file://" + os.path.join(d, "rows.html"))


def t_rows_verify():
    val, err = _cdp_eval("document.getElementById('out').textContent")
    if val is None:
        return False, err or "could not read page"
    if not val.startswith("FAILED"):
        return False, "nothing submitted"
    if "job-delta" not in val:
        return False, f"wrong job: {val!r} (the red one is job-delta)"
    return True, "ok"


BARS_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Capacity meters</title><style>
body{font-family:sans-serif;margin:30px}
button{font-size:16px;padding:8px 18px}
.row{margin:8px 0;font-size:16px}
.lbl{display:inline-block;width:110px}
.bar{display:inline-block;height:20px;background:#3070d0;vertical-align:middle}
input{font-size:16px;padding:6px;width:180px}
</style></head><body>
<h1>Capacity meters</h1>
<p>Press Measure. Five meters are drawn. Report the name of the one whose bar
is the longest.</p>
<button id="go1">Measure</button>
<div id="bars" role="list"></div>
<p><label>Longest: <input id="ans"></label><button id="go">Submit</button></p>
<div id="out"></div>
<script>
var data=[['north',90],['south',140],['east',60],['west',320],['central',180]];
document.getElementById('go1').onclick=function(){
  var c=document.getElementById('bars'); c.innerHTML='';
  data.forEach(function(d){
    var row=document.createElement('div'); row.className='row';
    row.setAttribute('role','listitem'); row.setAttribute('aria-label',d[0]);
    var l=document.createElement('span'); l.className='lbl'; l.textContent=d[0];
    var b=document.createElement('span'); b.className='bar';
    b.style.width=d[1]+'px';
    row.appendChild(l); row.appendChild(b); c.appendChild(row);
  });
};
document.getElementById('go').onclick=function(){
  document.getElementById('out').textContent='LONGEST '+
    document.getElementById('ans').value.trim().toLowerCase();
};
</script></body></html>"""


def t_bars_setup(seed):
    ws.reset()
    d = _serve_dir()
    with open(os.path.join(d, "bars.html"), "w") as f:
        f.write(BARS_HTML)
    ws.launch_browser("file://" + os.path.join(d, "bars.html"))


def t_bars_verify():
    val, err = _cdp_eval("document.getElementById('out').textContent")
    if val is None:
        return False, err or "could not read page"
    if not val.startswith("LONGEST"):
        return False, "nothing submitted"
    if "west" not in val:
        return False, f"wrong region: {val!r} (longest bar is west)"
    return True, "ok"


SUITE.append(Task(
    "vdelta_rows",
    "Press the Load button. Six jobs will appear; exactly one of them is "
    "shown with a red background, which means it failed. Type the name of "
    "that failed job into the box and submit it.",
    t_rows_setup, t_rows_verify, max_steps=14,
    tags=("browser", "visual", "vdelta"), apps=("chromium",)))

SUITE.append(Task(
    "vdelta_bars",
    "Press the Measure button. Five capacity meters will be drawn, each a "
    "labelled horizontal bar. Work out which one has the longest bar, type "
    "that name into the box and submit it.",
    t_bars_setup, t_bars_verify, max_steps=14,
    tags=("browser", "visual", "vdelta"), apps=("chromium",)))

BY_ID = {t.id: t for t in SUITE}


# ==================================================================== long
# Tasks long enough to exercise compaction and crop ageing. The first round
# of this experiment ran 7-10 steps, so neither mechanism ever fired and the
# tool arms were measured without the one thing that bounds their context.
# These are 25-40 step tasks with several natural boundaries (file dialogs
# opening and closing, applications changing) so compaction has somewhere
# sensible to happen.

def t_long_notes_setup(seed):
    ws.reset()
    ws.launch_editor()


def t_long_notes_verify():
    want = {"notes/n1.txt": "alpha", "notes/n2.txt": "bravo",
            "notes/n3.txt": "charlie"}
    missing = []
    for rel, content in want.items():
        c = _read(rel)
        if c is None:
            missing.append(f"{rel} missing")
        elif content not in _norm(c):
            missing.append(f"{rel} has {c[:30]!r}")
    if missing:
        return False, "; ".join(missing)
    return True, "ok"


def t_long_edits_setup(seed):
    ws.reset({"notes/ledger.txt":
              "ITEM ONE: 100\nITEM TWO: 200\nITEM THREE: 300\n"
              "ITEM FOUR: 400\nITEM FIVE: 500\n"})
    ws.launch_editor(os.path.join(WORK, "notes/ledger.txt"))


def t_long_edits_verify():
    c = _read("notes/ledger.txt")
    if c is None:
        return False, "file missing"
    checks = [("111", "ITEM ONE not changed to 111"),
              ("222", "ITEM TWO not changed to 222"),
              ("333", "ITEM THREE not changed to 333"),
              ("444", "ITEM FOUR not changed to 444")]
    for token, why in checks:
        if token not in c:
            return False, f"{why} (got {c[:90]!r})"
    if "500" not in c:
        return False, "ITEM FIVE should have been left alone"
    return True, "ok"


LONGFORM_HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>Onboarding form</title><style>
body{font-family:sans-serif;margin:30px;max-width:700px}
label{display:block;margin:10px 0 3px}
input,select{font-size:15px;padding:5px;width:300px}
button{margin-top:16px;font-size:16px;padding:8px 18px}
#done{margin-top:14px;font-weight:bold;color:#0a0}</style></head><body>
<h1>Supplier onboarding</h1>
<form id="f">
<label for="company">Company</label><input id="company">
<label for="vat">VAT number</label><input id="vat">
<label for="contact">Contact name</label><input id="contact">
<label for="email">Email</label><input id="email">
<label for="phone">Phone</label><input id="phone">
<label for="city">City</label><input id="city">
<label for="postcode">Postcode</label><input id="postcode">
<label for="country">Country</label>
<select id="country"><option value="">-- choose --</option>
<option value="pt">Portugal</option><option value="es">Spain</option>
<option value="fr">France</option></select>
<button type="submit" id="submit">Submit</button>
</form><div id="done"></div>
<script>
document.getElementById('f').addEventListener('submit',function(e){
 e.preventDefault();
 var d={company:company.value,vat:vat.value,contact:contact.value,
        email:email.value,phone:phone.value,city:city.value,
        postcode:postcode.value,country:country.value};
 document.getElementById('done').textContent='SUBMITTED '+JSON.stringify(d);
});
</script></body></html>"""


def t_long_form_setup(seed):
    ws.reset()
    d = _serve_dir()
    with open(os.path.join(d, "longform.html"), "w") as f:
        f.write(LONGFORM_HTML)
    ws.launch_browser("file://" + os.path.join(d, "longform.html"))


def t_long_form_verify():
    val, err = _cdp_eval("document.getElementById('done').textContent")
    if val is None:
        return False, err or "could not read page"
    if not val.startswith("SUBMITTED"):
        return False, "form not submitted"
    flat = val.replace(" ", "").lower()
    need = [("northwind", "company"), ("es123456", "vat"),
            ("rosaklein", "contact"), ("rosa@northwind.example", "email"),
            ("600111222", "phone"), ("valencia", "city"),
            ("46001", "postcode"), ('"country":"es"', "country")]
    for token, field in need:
        if token.replace(" ", "") not in flat:
            return False, f"{field} wrong or missing in {val[:150]}"
    return True, "ok"


def t_long_transfer_setup(seed):
    ws.reset({"inbox/figures.txt":
              "REGION REPORT\nnorth: 41\nsouth: 52\neast: 63\nwest: 74\n"})
    ws.launch_editor(os.path.join(WORK, "inbox/figures.txt"))


def t_long_transfer_verify():
    c = _read("archive/regions.txt")
    if c is None:
        return False, "archive/regions.txt does not exist"
    got = _norm(c)
    for n in ("41", "52", "63", "74"):
        if n not in got:
            return False, f"value {n} not copied (got {c[:90]!r})"
    return True, "ok"


SUITE.append(Task(
    "long_three_notes",
    "Using the text editor, create three separate files and save each one: "
    f"{WORK}/notes/n1.txt containing the word alpha, "
    f"{WORK}/notes/n2.txt containing the word bravo, and "
    f"{WORK}/notes/n3.txt containing the word charlie. "
    "Each file must contain only its own word.",
    t_long_notes_setup, t_long_notes_verify, max_steps=40,
    tags=("files", "long"), apps=("mousepad",)))

SUITE.append(Task(
    "long_ledger_edits",
    "The open document lists five items with values. Change ITEM ONE to 111, "
    "ITEM TWO to 222, ITEM THREE to 333 and ITEM FOUR to 444. Leave ITEM FIVE "
    "at 500. Then save the file.",
    t_long_edits_setup, t_long_edits_verify, max_steps=40,
    tags=("text", "long"), apps=("mousepad",)))

SUITE.append(Task(
    "long_onboarding_form",
    "Fill in every field of the supplier onboarding form and submit it. "
    "Company: Northwind. VAT number: ES123456. Contact name: Rosa Klein. "
    "Email: rosa@northwind.example. Phone: 600111222. City: Valencia. "
    "Postcode: 46001. Country: Spain.",
    t_long_form_setup, t_long_form_verify, max_steps=40,
    tags=("browser", "form", "long"), apps=("chromium",)))

SUITE.append(Task(
    "long_region_transfer",
    "The open document lists four regions with a number each. Create a new "
    f"file at {WORK}/archive/regions.txt that contains all four numbers "
    "(41, 52, 63 and 74), one per line, and save it. Leave the original "
    "document unchanged.",
    t_long_transfer_setup, t_long_transfer_verify, max_steps=40,
    tags=("files", "cross-app", "long"), apps=("mousepad",)))

BY_ID = {t.id: t for t in SUITE}


# ============================================== round 2: menus and dialogs
#
# These four tasks were designed to probe the defect round 1 measured: on menu
# and dialog work the tool arms spend up to 2.5x the steps of the screenshot
# baseline (REPORT.md §2.7, PREDICTIONS.md Fact 1). They are menu- and
# dialog-heavy by construction and they were registered in PREDICTIONS.md §2
# before anything was run. A reader is entitled to discount them for exactly
# that reason; the control group exists so the discount has somewhere to land.
#
# Every one of them is verified from the filesystem, never from the screen.

MENU_REPLACE_SRC = (
    "PROJECT LOG\n"
    "draft: opening notes\n"
    "second line mentions draft twice: draft\n"
    "closing line\n"
)


def t_menu_replace_setup(seed):
    ws.reset(extra_files={"notes/log.txt": MENU_REPLACE_SRC})
    ws.launch_editor(os.path.join(WORK, "notes/log.txt"))


def t_menu_replace_verify():
    c = _read("notes/log.txt")
    if c is None:
        return False, "notes/log.txt is gone"
    if "draft" in c:
        return False, f"'draft' still present: {c[:120]!r}"
    if c.count("final") != 3:
        return False, f"expected 3 occurrences of 'final', got {c.count('final')}"
    if "PROJECT LOG" not in c or "closing line" not in c:
        return False, f"surrounding text was damaged: {c[:120]!r}"
    return True, "ok"


def t_menu_save_as_setup(seed):
    ws.reset()
    ws.launch_editor(os.path.join(WORK, "notes/beta.txt"))


def t_menu_save_as_verify():
    c = _read("archive/minutes.txt")
    if c is None:
        return False, "archive/minutes.txt does not exist"
    if "beta line" not in c:
        return False, f"contents not carried over: {c[:80]!r}"
    orig = _read("notes/beta.txt")
    if orig is None:
        return False, "the original notes/beta.txt was removed"
    if "beta line" not in orig:
        return False, f"the original was modified: {orig[:80]!r}"
    return True, "ok"


def t_menu_insert_col_setup(seed):
    ws.reset()
    ws.launch_calc(os.path.join(WORK, "data/values.csv"))


def t_menu_insert_col_verify():
    c = _read("data/values-tagged.csv")
    if c is None:
        return False, "data/values-tagged.csv does not exist"
    lines = [l for l in c.splitlines() if l.strip()]
    if len(lines) < 4:
        return False, f"expected 4 rows, got {len(lines)}: {c[:80]!r}"
    head = [h.strip().strip('"').lower() for h in lines[0].split(",")]
    if not head or head[0] != "code":
        return False, f"first column is not 'code': {lines[0]!r}"
    if head[1:4] != ["item", "qty", "price"]:
        return False, f"original columns not preserved: {lines[0]!r}"
    return True, "ok"


def t_menu_new_folder_setup(seed):
    ws.reset()
    ws.launch_files(os.path.join(WORK, "inbox"))


def t_menu_new_folder_verify():
    if not _exists("inbox/2026-Q1"):
        return False, "inbox/2026-Q1 was not created"
    if not os.path.isdir(os.path.join(WORK, "inbox/2026-Q1")):
        return False, "inbox/2026-Q1 exists but is not a folder"
    c = _read("inbox/2026-Q1/report-draft.txt")
    if c is None:
        return False, "report-draft.txt is not inside inbox/2026-Q1"
    if "QUARTERLY REPORT" not in c:
        return False, f"the moved file is not the right one: {c[:60]!r}"
    if _exists("inbox/report-draft.txt"):
        return False, "the file was copied, not moved — it is still in inbox/"
    return True, "ok"


# ================================== round 2: long tasks with explicit constraints
#
# Experiment 4 needs to tell "failed the task" apart from "forgot a constraint",
# which needs constraints that are explicit in the statement and separately
# checkable. Each of these declares both: the text the persistent task object
# repeats, and a decomposition the verifier reports one clause at a time.

LEDGER_CSV = (
    "date,region,amount\n"
    "2026-02-11,north,120\n"
    "2026-03-02,north,340\n"
    "2026-03-08,south,215\n"
    "2026-04-01,south,190\n"
    "2026-03-19,east,455\n"
    "2026-02-27,east,80\n"
)


def t_march_setup(seed):
    ws.reset(extra_files={"data/ledger.csv": LEDGER_CSV})
    ws.launch_calc(os.path.join(WORK, "data/ledger.csv"))


def _march_checks():
    out = _read("data/march.csv")
    checks = {
        "c4_output_at_named_path": out is not None,
        "c1_output_is_csv": False,
        "c2_only_march_rows": False,
        "c3_original_untouched": _read("data/ledger.csv") == LEDGER_CSV,
    }
    if out is not None:
        rows = [l for l in out.splitlines() if l.strip()]
        checks["c1_output_is_csv"] = bool(rows) and all("," in r for r in rows)
        body = [r for r in rows if not r.lower().startswith("date,")]
        has_all_march = all(any(d in r for r in body)
                            for d in ("2026-03-02", "2026-03-08", "2026-03-19"))
        no_others = not any(d in out for d in
                            ("2026-02-11", "2026-04-01", "2026-02-27"))
        checks["c2_only_march_rows"] = bool(body) and has_all_march and no_others
    return checks


def t_march_verify():
    c = _march_checks()
    bad = [k for k, v in c.items() if not v]
    if bad:
        return False, "failed: " + ", ".join(bad)
    return True, "ok"


def t_notes_digest_setup(seed):
    ws.reset()
    ws.launch_editor(os.path.join(WORK, "notes/alpha.txt"))


_DIGEST_EXPECT = {"alpha": "alpha one", "beta": "beta line",
                  "gamma": "gamma line"}


def _digest_checks():
    out = _read("notes/digest.txt")
    checks = {
        "c1_one_line_per_note": False,
        "c2_name_colon_firstline": False,
        "c3_sorted_by_name": False,
        "c4_originals_intact": all(
            _read(f"notes/{n}.txt") is not None and
            _DIGEST_EXPECT[n] in (_read(f"notes/{n}.txt") or "")
            for n in _DIGEST_EXPECT),
    }
    if out is None:
        return checks
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    checks["c1_one_line_per_note"] = len(lines) == 3
    names = []
    good = True
    for l in lines:
        if ":" not in l:
            good = False
            continue
        n, _, rest = l.partition(":")
        n = n.strip().lower()
        names.append(n)
        if n not in _DIGEST_EXPECT or _DIGEST_EXPECT[n] not in rest:
            good = False
    checks["c2_name_colon_firstline"] = good and len(names) == 3
    checks["c3_sorted_by_name"] = names == sorted(names) and len(names) == 3
    return checks


def t_notes_digest_verify():
    c = _digest_checks()
    bad = [k for k, v in c.items() if not v]
    if bad:
        return False, "failed: " + ", ".join(bad)
    return True, "ok"


SUITE.append(Task(
    "menu_replace_all",
    "In the open text editor, use the Search menu's Find and Replace dialog to "
    "replace every occurrence of the word draft with the word final, then save "
    "the file. Leave the rest of the text alone.",
    t_menu_replace_setup, t_menu_replace_verify, max_steps=16,
    tags=("text", "menu"), apps=("mousepad",)))

SUITE.append(Task(
    "menu_save_as_subdir",
    "In the open text editor, use the File menu's Save As dialog to save the "
    f"document into the archive folder as minutes.txt (that is "
    f"{WORK}/archive/minutes.txt). Leave the original file where it is.",
    t_menu_save_as_setup, t_menu_save_as_verify, max_steps=16,
    tags=("files", "menu"), apps=("mousepad",)))

SUITE.append(Task(
    "menu_calc_insert_column",
    "In the open spreadsheet, use the Sheet menu to insert a new column before "
    "column A, put the header code in its first cell, and then save the result "
    f"as {WORK}/data/values-tagged.csv in Text CSV format, keeping the existing "
    "columns as they are.",
    t_menu_insert_col_setup, t_menu_insert_col_verify, max_steps=20,
    tags=("spreadsheet", "menu"), apps=("soffice",)))

SUITE.append(Task(
    "menu_files_new_folder",
    "In the open file manager, use the menus to create a folder called 2026-Q1 "
    "inside the current folder, and then move report-draft.txt into it. Move "
    "it, do not copy it.",
    t_menu_new_folder_setup, t_menu_new_folder_verify, max_steps=20,
    tags=("files", "menu"), apps=("pcmanfm",)))

SUITE.append(Task(
    "long_march_export",
    "The open spreadsheet is a ledger. Export only the rows dated in March 2026 "
    f"to {WORK}/data/march.csv, in CSV format, without modifying the original "
    "ledger file.",
    t_march_setup, t_march_verify, max_steps=40,
    tags=("spreadsheet", "long", "constraints"), apps=("soffice",),
    constraints=(
        "the output must be written to data/march.csv",
        "the output must be in CSV format (comma-separated, one row per line)",
        "the output must contain the March 2026 rows and no others",
        "the original data/ledger.csv must not be modified",
    ),
    verify_constraints=_march_checks))

SUITE.append(Task(
    "long_notes_digest",
    f"The folder {WORK}/notes contains alpha.txt, beta.txt and gamma.txt. "
    f"Write {WORK}/notes/digest.txt with one line per note, each of the form "
    "name: first line of that note (for example  alpha: ...), sorted "
    "alphabetically by name. Do not delete or change the original notes.",
    t_notes_digest_setup, t_notes_digest_verify, max_steps=40,
    tags=("files", "text", "long", "constraints"), apps=("mousepad",),
    constraints=(
        "digest.txt must contain exactly one line per note, three in total",
        "each line must read  name: first line of that note",
        "the lines must be sorted alphabetically by name",
        "alpha.txt, beta.txt and gamma.txt must be left unchanged",
    ),
    verify_constraints=_digest_checks))

BY_ID = {t.id: t for t in SUITE}
