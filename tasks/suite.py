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


def t_calc_cell_verify():
    def chk(rows, raw):
        flat = _norm(raw)
        if "48.5" not in flat.replace(",", "."):
            return False, f"total 48.5 not found in {raw[:120]!r}"
        return True, "ok"
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
