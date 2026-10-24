#!/usr/bin/env python3
"""Teste lgtv.py et restaurer.py contre une fausse TV webOS (aucune vraie TV nécessaire).

    python tests/test_kit.py

La fausse TV écoute en WebSocket sur 127.0.0.1:3000 (comme une vraie TV sans TLS)
et sert les captures/icônes en HTTP sur 127.0.0.1:3080.
"""

import base64
import hashlib
import http.server
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTTP = "http://127.0.0.1:3080"

APPS = [
    {"id": "com.webos.app.browser", "title": "Navigateur Web", "systemApp": True},
    {"id": "youtube.leanback.v4", "title": "YouTube"},
    {"id": "netflix", "title": "Netflix"},
    {"id": "ui30", "title": "Rakuten TV"},
    {"id": "com.fourk.player", "title": "4K Player"},
    {"id": "com.1827622.109556", "title": "Smart IPTV"},
    {"id": "lgchannels", "title": "LG Channels", "systemApp": True},
]
LAUNCHED = []


def ws_read(sock):
    b1, b2 = sock.recv(2, socket.MSG_WAITALL)
    n = b2 & 0x7F
    if n == 126:
        n = struct.unpack("!H", sock.recv(2, socket.MSG_WAITALL))[0]
    elif n == 127:
        n = struct.unpack("!Q", sock.recv(8, socket.MSG_WAITALL))[0]
    mask = sock.recv(4, socket.MSG_WAITALL)
    data = sock.recv(n, socket.MSG_WAITALL) if n else b""
    assert b2 & 0x80, "le client doit masquer ses trames"
    return b1 & 0x0F, bytes(b ^ mask[i % 4] for i, b in enumerate(data))


def ws_send(sock, text):
    data = text.encode()
    n = len(data)
    head = bytes([0x81]) + (bytes([n]) if n < 126 else bytes([126]) + struct.pack("!H", n) if n < 65536 else bytes([127]) + struct.pack("!Q", n))
    sock.sendall(head + data)


def handle(msg):
    uri = msg.get("uri", "")
    if uri.endswith("listApps"):
        return {"apps": APPS}
    if uri.endswith("listLaunchPoints"):
        return {"launchPoints": [{"id": a["id"], "title": a["title"], "icon": f"{HTTP}/icon.png"} for a in APPS]}
    if uri.endswith("executeOneShot"):
        return {"imageUri": f"{HTTP}/capture.jpg"}
    if uri.endswith("getCurrentSWInformation"):
        return {"product_name": "webOSTV 23", "model_name": "OLED55C3"}
    if uri.endswith("system.launcher/launch"):
        LAUNCHED.append(msg["payload"]["id"])
        return {"returnValue": True}
    if uri.endswith("getExternalInputList"):
        return {"__error": "401 insufficient permissions"}
    return {"returnValue": True}


def client(conn):
    head = b""
    while b"\r\n\r\n" not in head:
        head += conn.recv(1024)
    key = [l.split(b": ")[1] for l in head.split(b"\r\n") if l.lower().startswith(b"sec-websocket-key")][0]
    accept = base64.b64encode(hashlib.sha1(key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest())
    conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                 b"Sec-WebSocket-Accept: " + accept + b"\r\n\r\n")
    try:
        while True:
            op, data = ws_read(conn)
            if op == 8:
                return
            msg = json.loads(data)
            if msg["type"] == "register":
                if not msg["payload"].get("client-key"):
                    ws_send(conn, json.dumps({"type": "response", "id": msg["id"], "payload": {"pairingType": "PROMPT"}}))
                ws_send(conn, json.dumps({"type": "registered", "id": msg["id"], "payload": {"client-key": "cle-test"}}))
                continue
            payload = handle(msg)
            if "__error" in payload:
                ws_send(conn, json.dumps({"type": "error", "id": msg["id"], "error": payload["__error"]}))
            else:
                ws_send(conn, json.dumps({"type": "response", "id": msg["id"], "payload": payload}))
    except (ValueError, OSError):
        pass


def ws_server():
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 3000))
    srv.listen()
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=client, args=(conn,), daemon=True).start()


class Files(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"\xff\xd8fake-jpeg" if self.path.endswith(".jpg") else b"\x89PNGfake")

    def log_message(self, *args):
        pass


def run(workdir, *args, stdin=""):
    res = subprocess.run([sys.executable, *args], cwd=workdir, input=stdin, capture_output=True, text=True, timeout=60,
                         env={**os.environ, "PATH": os.path.dirname(sys.executable)})  # sans ares-* : chemin « outils absents »
    print(f"$ python {' '.join(args)}\n{res.stdout}{res.stderr}")
    assert res.returncode == 0, f"échec : {args}"
    return res.stdout


def main():
    threading.Thread(target=ws_server, daemon=True).start()
    threading.Thread(target=http.server.ThreadingHTTPServer(("127.0.0.1", 3080), Files).serve_forever, daemon=True).start()
    work = tempfile.mkdtemp()
    kit = os.path.join(work, "lg-tv")
    shutil.copytree(KIT, kit, ignore=shutil.ignore_patterns("tests", "tv.json", "sauvegardes", "captures", "dist", "__pycache__"))

    run(kit, "lgtv.py", "trouver", "127.0.0.1", stdin="1\n")
    out = run(kit, "lgtv.py", "appairer")
    assert "OLED55C3" in out
    assert json.load(open(os.path.join(kit, "tv.json")))["client_key"] == "cle-test"

    out = run(kit, "lgtv.py", "sauvegarder")
    backup = os.path.join(kit, json.load(open(os.path.join(kit, "tv.json")))["derniere_sauvegarde"])
    for f in ("applis.json", "lanceur.json", "ruban_accueil.txt", "modifications.json"):
        assert os.path.exists(os.path.join(backup, f)), f
    assert "⚠ entrees" in out  # une requête refusée n'interrompt pas la sauvegarde
    assert any(f.endswith("accueil-avant.jpg") for f in os.listdir(backup))

    out = run(kit, "lgtv.py", "applis")
    assert "Smart IPTV" in out and "système" in out

    run(kit, "lgtv.py", "dock")
    dock = json.load(open(os.path.join(kit, "launcher", "config.json")))["dock"]
    assert [d["id"] for d in dock] == ["com.fourk.player", "com.1827622.109556", "youtube.leanback.v4", "netflix", "ui30", "com.palm.app.settings"], dock
    assert all(d["icon"].startswith("icons/") for d in dock[:-1])

    run(kit, "lgtv.py", "lancer", "netflix")
    assert LAUNCHED == ["netflix"]

    # Allègement guidé : oui à la question Live Plus (on garde), fait pour les 4 premiers, puis on quitte.
    from importlib import util
    spec = util.spec_from_file_location("reglages", os.path.join(kit, "reglages.py"))
    reglages = util.module_from_spec(spec)
    spec.loader.exec_module(reglages)
    answers = "\n\n" * 4 + "o\n" + "q\n"
    run(kit, "lgtv.py", "alleger", stdin=answers)
    log = json.load(open(os.path.join(backup, "modifications.json")))["reglages"]
    assert [k for k, v in log.items() if v["fait"]] == [r["id"] for r in reglages.REGLAGES[:4]], log
    assert log["live_plus"] == {"fait": False, "raison": "utilisé"}
    assert log["promotion_accueil"]["capture_avant"] and log["promotion_accueil"]["capture_apres"]

    out = run(kit, "restaurer.py", stdin="\n" * 4)
    log = json.load(open(os.path.join(backup, "modifications.json")))["reglages"]
    assert not any(v["fait"] for v in log.values())
    assert "Toutes les applis d'origine sont là" in out

    shutil.rmtree(work)
    print("✓ tous les tests passent")


if __name__ == "__main__":
    main()
