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
from datetime import datetime

app = Flask(__name__)
CORS(app, origins=os.environ.get("FRONTEND_URL", "*"))

# ── Config ────────────────────────────────────────────────────────────────────
PDF_PATH      = os.path.join(os.path.dirname(__file__), "Application_Form.pdf")
COUNTER_FILE  = os.path.join(os.path.dirname(__file__), "counter.json")
PREFIX        = "JBPF"          # Change to your trust initials if needed
FORM_URL      = "https://forms.gle/MUELu1tA9cfKKr8s6"
DOWNLOAD_KEY  = os.environ.get("DOWNLOAD_KEY", "jbpf2026secure")
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
    # Build a one-page overlay containing only the serial text
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(612, 1008))   # matches your PDF size
    c.setFont("Helvetica-Bold", 11)
    c.setFillColorRGB(0.08, 0.14, 0.49)               # dark-blue ink
    c.drawString(22, 982, f"Application No: {serial}")
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
