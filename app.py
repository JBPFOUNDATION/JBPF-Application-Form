"""
Application Form Download Server
Stamps each downloaded PDF with a unique serial number: JBPF/YYYY/MON/XXXX
Serial counter persists in counter.json
"""

from flask import Flask, send_file, render_template, jsonify, request, redirect
from flask_cors import CORS
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
import io
import json
import os
import threading
import urllib.request
from datetime import datetime

app = Flask(__name__)
CORS(app, origins=os.environ.get("FRONTEND_URL", "*"))

# ── Config ────────────────────────────────────────────────────────────────────
PDF_PATH      = os.path.join(os.path.dirname(__file__), "Application_Form.pdf")
COUNTER_FILE  = os.path.join(os.path.dirname(__file__), "counter.json")
PREFIX        = "JBPF"          # Change to your trust initials if needed
FORM_URL      = "https://forms.gle/MUELu1tA9cfKKr8s6"
DOWNLOAD_KEY  = os.environ.get("DOWNLOAD_KEY", "jbpf2026secure")
SHEETS_URL    = os.environ.get("SHEETS_WEBHOOK_URL", "")
MONTH_ABBR    = ["JAN","FEB","MAR","APR","MAY","JUN",
                 "JUL","AUG","SEP","OCT","NOV","DEC"]

# Thread lock so concurrent downloads don't get the same number
_lock = threading.Lock()

# ── Counter helpers ───────────────────────────────────────────────────────────
def _load_counter():
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE) as f:
            return json.load(f)
    return {"year": datetime.now().year, "month": datetime.now().month, "seq": 0}

def _save_counter(data):
    with open(COUNTER_FILE, "w") as f:
        json.dump(data, f)

def next_serial():
    """Return next serial string and save incremented counter."""
    with _lock:
        now   = datetime.now()
        data  = _load_counter()

        # Reset sequence if year or month changed
        if data["year"] != now.year or data["month"] != now.month:
            data["year"]  = now.year
            data["month"] = now.month
            data["seq"]   = 0

        data["seq"] += 1
        _save_counter(data)

        serial = f"{PREFIX}/{data['year']}/{MONTH_ABBR[data['month']-1]}/{data['seq']:04d}"
        return serial

# ── PDF stamping ──────────────────────────────────────────────────────────────
def stamp_pdf(serial: str) -> bytes:
    """Overlay serial number on page 1 of the form and return PDF bytes."""
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(612, 1008))
    c.setFont("Helvetica-Bold", 11)
    c.setFillColorRGB(0.08, 0.14, 0.49)
    c.drawCentredString(306, 960, f"Application No: {serial}")
    c.save()
    packet.seek(0)

    overlay = PdfReader(packet)
    reader  = PdfReader(PDF_PATH)
    writer  = PdfWriter()

    for i, page in enumerate(reader.pages):
        if i == 0:
            page.merge_page(overlay.pages[0])
        writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()


def fill_pdf(serial: str, data: dict) -> bytes:
    """Fill the form with user data and stamp the serial number."""
    W, H = 612, 1008
    FONT, SZ = "Helvetica", 11

    def trunc(key, n):
        return str(data.get(key) or "")[:n]

    def overlay_page(draw_fn):
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=(W, H))
        c.setFont(FONT, SZ)
        c.setFillColorRGB(0, 0, 0)
        draw_fn(c)
        c.save()
        buf.seek(0)
        return buf

    # ── Page 1 overlay ────────────────────────────────────────────────────────
    def draw_p1(c):
        # Serial (dark blue, bold)
        c.setFont("Helvetica-Bold", 11)
        c.setFillColorRGB(0.08, 0.14, 0.49)
        c.drawCentredString(306, 960, f"Application No: {serial}")
        c.setFont(FONT, SZ)
        c.setFillColorRGB(0, 0, 0)

        # Full Name — 3 pts above each underline (underlines at y≈859, 833)
        name = str(data.get("full_name") or "")
        c.drawString(72, 862, name[:65])
        if len(name) > 65:
            c.drawString(72, 836, name[65:130])

        # Age — 3 pts above underline at y≈808
        c.drawString(112, 811, trunc("age", 15))

        # Residential Address — 3 pts above underlines at y≈757, 731
        addr = str(data.get("address") or "")
        c.drawString(72, 760, addr[:65])
        if len(addr) > 65:
            c.drawString(72, 734, addr[65:130])

        # Telephone / Mobile — 3 pts above underline at y≈705
        c.drawString(250, 708, trunc("phone", 45))

        # Income sources — 3 pts above underlines at y≈655, 619
        c.drawString(157, 658, trunc("pension",  22))
        c.drawString(413, 658, trunc("salary",   22))
        c.drawString(162, 622, trunc("business", 22))
        c.drawString(413, 622, trunc("others",   22))

        # Donation table (3 rows; row height ≈30 pts, top border at y≈488)
        for i, y in enumerate([468, 440, 412]):
            pfx = f"don_{i+1}_"
            c.drawString(78,  y, str(i + 1))
            c.drawString(122, y, trunc(pfx + "name", 34))
            c.drawString(395, y, trunc(pfx + "date", 12))
            c.drawString(487, y, trunc(pfx + "amount", 8))

        # Expenditure table (4 rows × 2 columns, estimated y from PDF layout)
        for i, y in enumerate([263, 228, 193, 158]):
            pfx = f"exp_{i+1}_"
            c.drawString(83,  y, trunc(pfx + "desc1", 20))
            c.drawString(255, y, trunc(pfx + "amt1",  10))
            c.drawString(365, y, trunc(pfx + "desc2", 16))
            c.drawString(498, y, trunc(pfx + "amt2",  8))

        # Total monthly expenditure
        c.drawString(415, 143, trunc("exp_total", 22))

        # Previous aid — underline YES or NO in the form's "YES/NO" label
        # "YES/NO" starts at x≈269; YES≈x269-292, NO≈x296-314
        prev = (data.get("previous_aid") or "NO").upper()
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(1.5)
        if prev == "YES":
            c.line(269, 84, 292, 84)
        else:
            c.line(296, 84, 314, 84)
        c.setLineWidth(1)
        if prev == "YES":
            c.drawString(355, 55, trunc("previous_aid_details", 33))

    # ── Page 2 overlay ────────────────────────────────────────────────────────
    def draw_p2(c):
        # Nature of requirement — up to 4 lines of ~70 chars
        req = str(data.get("requirement") or "")
        for line, y in zip(
            [req[i:i+70] for i in range(0, min(len(req), 280), 70)],
            [921, 890, 860, 829],
        ):
            c.drawString(72, y, line)

        # Date
        date_val = data.get("date") or datetime.now().strftime("%d/%m/%Y")
        c.drawString(155, 676, str(date_val)[:20])

    p1_buf = overlay_page(draw_p1)
    p2_buf = overlay_page(draw_p2)

    overlay1 = PdfReader(p1_buf)
    overlay2 = PdfReader(p2_buf)
    reader   = PdfReader(PDF_PATH)
    writer   = PdfWriter()

    for i, page in enumerate(reader.pages):
        if i == 0:
            page.merge_page(overlay1.pages[0])
        elif i == 1:
            page.merge_page(overlay2.pages[0])
        writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()

# ── Google Sheets logging ─────────────────────────────────────────────────────
def _log_to_sheets(serial, data):
    """POST submission details to Google Apps Script webhook (fire-and-forget).
    Apps Script returns a 302 redirect — we follow it manually with a second POST."""
    if not SHEETS_URL:
        return
    payload = json.dumps({
        "serial":    serial,
        "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "name":      data.get("full_name", ""),
        "phone":     data.get("phone", ""),
        "email":     data.get("email", ""),
        "reference": data.get("reference", ""),
    }).encode()
    try:
        # First request — expect a 302 from Apps Script
        req = urllib.request.Request(
            SHEETS_URL, data=payload,
            headers={"Content-Type": "application/json"},
        )
        opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
        # Disable auto-redirect so we can re-POST to the redirect URL
        opener.handler_map.clear()
        try:
            opener.open(req, timeout=10)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and "Location" in e.headers:
                redirect_url = e.headers["Location"]
                req2 = urllib.request.Request(
                    redirect_url, data=payload,
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req2, timeout=10)
    except Exception:
        pass  # never block the download if logging fails

def log_to_sheets(serial, data):
    threading.Thread(target=_log_to_sheets, args=(serial, data), daemon=True).start()

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/download")
def download():
    if request.args.get("key") != DOWNLOAD_KEY:
        return redirect(FORM_URL)

    serial   = next_serial()
    pdf_data = stamp_pdf(serial)

    filename = f"Application_Form_{serial.replace('/', '_')}.pdf"
    return send_file(
        io.BytesIO(pdf_data),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )

@app.route("/fill-and-download", methods=["POST"])
def fill_and_download():
    """Accept form data, fill the PDF, stamp a serial, and return it."""
    fd = request.form
    if not fd.get("full_name") or not fd.get("requirement"):
        return jsonify({"error": "full_name and requirement are required"}), 400

    serial   = next_serial()
    data     = fd.to_dict()
    pdf_data = fill_pdf(serial, data)
    log_to_sheets(serial, data)
    filename = f"Application_Form_{serial.replace('/', '_')}.pdf"
    return send_file(
        io.BytesIO(pdf_data),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/generate-serial")
def generate_serial():
    """Called by Google Apps Script on form submit. Returns next serial and increments counter."""
    if request.args.get("key") != DOWNLOAD_KEY:
        return jsonify({"error": "unauthorized"}), 401
    serial = next_serial()
    return jsonify({"serial": serial})

@app.route("/counter")
def counter():
    """Return total downloads (all-time seq for current period)."""
    data = _load_counter()
    return jsonify({"total": data["seq"]})

@app.route("/stats")
def stats():
    """Show current counter stats (admin endpoint)."""
    data = _load_counter()
    now  = datetime.now()
    return jsonify({
        "total_downloads_this_period": data["seq"],
        "current_period": f"{MONTH_ABBR[data['month']-1]} {data['year']}",
        "next_serial": f"{PREFIX}/{now.year}/{MONTH_ABBR[now.month-1]}/{data['seq']+1:04d}",
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"Starting form server on http://localhost:{port}")
    app.run(debug=False, port=port)
