import http.server
import socketserver
import json
import sqlite3
import os
import re
from datetime import datetime

PORT = int(os.environ.get("PORT", 8080))
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "lances.db"))
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
INITIAL_BID = float(os.environ.get("INITIAL_BID", 300.00))

def init_db():
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
    # Totalmente anônimo/ofuscado: Proponente #102 ou C*** O***
    clean = re.sub(r'\s+', ' ', name.strip())
    parts = clean.split(' ')
    if len(parts) >= 2:
        return f"{parts[0][0]}*** {parts[-1][0]}***"
    elif len(clean) > 2:
        return f"{clean[0]}***{clean[-1]}"
    return f"Proponente #{bid_id:03d}"

class BidHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Admin-Password')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/bids/stats"):
            self.handle_get_stats()
            return

        if self.path.startswith("/api/admin/bids"):
            self.handle_admin_list_bids()
            return

        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/bids":
            self.handle_post_bid()
            return
        elif self.path == "/api/admin/login":
            self.handle_admin_login()
            return
        else:
            self.send_error(404, "Endpoint not found")

    def handle_get_stats(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(amount), COUNT(*) FROM bids")
            max_bid, count = cursor.fetchone()

            highest_bid = max_bid if (max_bid is not None and max_bid >= INITIAL_BID) else INITIAL_BID
            min_next_bid = highest_bid + 20.0 if count > 0 else INITIAL_BID

            # Histórico com nomes totalmente ofuscados
            cursor.execute("SELECT id, name, amount, created_at FROM bids ORDER BY id DESC LIMIT 5")
            recent = []
            for row in cursor.fetchall():
                bid_id, raw_name, amount, created_at = row
                recent.append({
                    "bidder": obfuscate_bidder(bid_id, raw_name),
                    "amount": amount,
                    "created_at": created_at
                })

            response_data = {
                "initialBid": INITIAL_BID,
                "currentHighest": highest_bid,
                "minNextBid": min_next_bid,
                "totalBids": count,
                "recentBids": recent
            }

            self.send_json_response(200, response_data)

    def handle_post_bid(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)

            name = str(data.get("name", "")).strip()
            email = str(data.get("email", "")).strip()
            whatsapp = str(data.get("whatsapp", "")).strip()
            domain = str(data.get("domain", "")).strip()
            try:
                amount = float(data.get("amount", 0))
            except (ValueError, TypeError):
                self.send_json_response(400, {"error": "Valor de lance inválido."})
                return

            if not name or len(name) < 2:
                self.send_json_response(400, {"error": "Informe seu nome."})
                return

            if not email or "@" not in email:
                self.send_json_response(400, {"error": "Informe um e-mail válido."})
                return

            if not whatsapp or len(re.sub(r'\D', '', whatsapp)) < 8:
                self.send_json_response(400, {"error": "Informe um telefone/WhatsApp com DDD."})
                return

            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT MAX(amount), COUNT(*) FROM bids")
                max_bid, count = cursor.fetchone()

                highest_bid = max_bid if (max_bid is not None and max_bid >= INITIAL_BID) else INITIAL_BID
                min_required = highest_bid + 20.0 if count > 0 else INITIAL_BID

                if amount < min_required:
                    self.send_json_response(400, {
                        "error": f"O lance mínimo permitido é de R$ {min_required:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    })
                    return

                created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                client_ip = self.client_address[0]

                cursor.execute('''
                    INSERT INTO bids (domain, name, email, whatsapp, amount, created_at, ip)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (domain, name, email, whatsapp, amount, created_at, client_ip))
                conn.commit()

            self.send_json_response(201, {
                "success": True,
                "message": "Lance registrado com sucesso.",
                "amount": amount
            })

        except Exception as e:
            self.send_json_response(500, {"error": f"Erro interno: {str(e)}"})

    def check_auth(self):
        auth_header = self.headers.get("X-Admin-Password")
        return auth_header == ADMIN_PASSWORD

    def handle_admin_login(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        try:
            data = json.loads(body)
            password = data.get("password", "")
            if password == ADMIN_PASSWORD:
                self.send_json_response(200, {"success": True})
            else:
                self.send_json_response(401, {"error": "Senha incorreta."})
        except Exception:
            self.send_json_response(400, {"error": "Requisição inválida."})

    def handle_admin_list_bids(self):
        if not self.check_auth():
            self.send_json_response(401, {"error": "Não autorizado."})
            return

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

            self.send_json_response(200, {"bids": bids})

    def send_json_response(self, code, data):
        payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

if __name__ == "__main__":
    print(f"Servidor iniciado em http://0.0.0.0:{PORT}")
    with socketserver.TCPServer(("", PORT), BidHandler) as httpd:
        httpd.serve_forever()
