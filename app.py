import os
import re
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "lances.db"))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
INITIAL_BID = float(os.environ.get("INITIAL_BID", 300.00))
PORT = int(os.environ.get("PORT", 5002))

app = Flask(__name__, static_folder=".", template_folder=".")

def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bids (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                whatsapp TEXT NOT NULL,
                amount REAL NOT NULL,
                created_at TEXT NOT NULL,
                ip TEXT
            )
        ''')
        conn.commit()

init_db()

def obfuscate_bidder(bid_id, name):
    clean = re.sub(r'\s+', ' ', name.strip())
    parts = clean.split(' ')
    if len(parts) >= 2:
        return f"{parts[0][0]}*** {parts[-1][0]}***"
    elif len(clean) > 2:
        return f"{clean[0]}***{clean[-1]}"
    return f"Proponente #{bid_id:03d}"

# --- Rotas Frontend ---

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")

@app.route("/admin")
@app.route("/admin.html")
def admin_page():
    return send_from_directory(BASE_DIR, "admin.html")

@app.route("/style.css")
def css():
    return send_from_directory(BASE_DIR, "style.css")

@app.route("/script.js")
def js():
    return send_from_directory(BASE_DIR, "script.js")

# --- Rotas da API de Lances ---

@app.route("/api/bids/stats", methods=["GET"])
def get_bids_stats():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(amount), COUNT(*) FROM bids")
        max_bid, count = cursor.fetchone()

        highest_bid = max_bid if (max_bid is not None and max_bid >= INITIAL_BID) else INITIAL_BID
        min_next_bid = highest_bid + 20.0 if count > 0 else INITIAL_BID

        cursor.execute("SELECT id, name, amount, created_at FROM bids ORDER BY id DESC LIMIT 5")
        recent = []
        for row in cursor.fetchall():
            bid_id, raw_name, amount, created_at = row
            recent.append({
                "bidder": obfuscate_bidder(bid_id, raw_name),
                "amount": amount,
                "created_at": created_at
            })

    return jsonify({
        "initialBid": INITIAL_BID,
        "currentHighest": highest_bid,
        "minNextBid": min_next_bid,
        "totalBids": count,
        "recentBids": recent
    })

@app.route("/api/bids", methods=["POST"])
def post_bid():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip()
    whatsapp = str(data.get("whatsapp", "")).strip()
    domain = str(data.get("domain", "")).strip()

    try:
        amount = float(data.get("amount", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Valor de lance inválido."}), 400

    if not name or len(name) < 2:
        return jsonify({"error": "Informe seu nome."}), 400

    if not email or "@" not in email:
        return jsonify({"error": "Informe um e-mail válido."}), 400

    if not whatsapp or len(re.sub(r'\D', '', whatsapp)) < 8:
        return jsonify({"error": "Informe um telefone/WhatsApp com DDD."}), 400

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(amount), COUNT(*) FROM bids")
        max_bid, count = cursor.fetchone()

        highest_bid = max_bid if (max_bid is not None and max_bid >= INITIAL_BID) else INITIAL_BID
        min_required = highest_bid + 20.0 if count > 0 else INITIAL_BID

        if amount < min_required:
            formatted_min = f"R$ {min_required:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            return jsonify({"error": f"O lance mínimo permitido é de {formatted_min}"}), 400

        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        cursor.execute('''
            INSERT INTO bids (domain, name, email, whatsapp, amount, created_at, ip)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (domain, name, email, whatsapp, amount, created_at, client_ip))
        conn.commit()

    return jsonify({
        "success": True,
        "message": "Lance registrado com sucesso.",
        "amount": amount
    }), 201

@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")
    if password == ADMIN_PASSWORD:
        return jsonify({"success": True})
    return jsonify({"error": "Senha incorreta."}), 401

@app.route("/api/admin/bids", methods=["GET"])
def admin_list_bids():
    auth_header = request.headers.get("X-Admin-Password")
    if auth_header != ADMIN_PASSWORD:
        return jsonify({"error": "Não autorizado."}), 401

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, domain, name, email, whatsapp, amount, created_at, ip
            FROM bids
            ORDER BY amount DESC, id DESC
        ''')
        rows = cursor.fetchall()

        bids = []
        for r in rows:
            bids.append({
                "id": r[0],
                "domain": r[1],
                "name": r[2],
                "email": r[3],
                "whatsapp": r[4],
                "amount": r[5],
                "created_at": r[6],
                "ip": r[7]
            })

    return jsonify({"bids": bids})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
