#!/usr/bin/env python3
"""Outil pour alléger une TV LG webOS depuis un ordinateur du même Wi-Fi.

Aucune dépendance : Python 3.8+ suffit. Les commandes qui installent l'écran
d'accueil utilisent en plus les outils officiels LG (`npm i -g @webos-tools/cli`).

    python lgtv.py trouver            # cherche la TV sur le réseau
    python lgtv.py appairer           # accepter la demande sur la TV
    python lgtv.py sauvegarder        # sauvegarde complète + capture
    python lgtv.py capture [nom]      # capture d'écran de la TV
    python lgtv.py applis             # liste des applis installées
    python lgtv.py alleger            # réglages guidés, un par un, avec captures
    python lgtv.py dock               # prépare le dock de l'écran d'accueil
    python lgtv.py fonds [nombre]     # télécharge des fonds d'écran nature
    python lgtv.py installer          # installe l'écran d'accueil sur la TV
    python lgtv.py lancer <id>        # lance une appli

Pour tout remettre comme avant : python restaurer.py
"""

import base64
import datetime
import json
import os
import re
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import threading
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "tv.json")
BACKUPS = os.path.join(HERE, "sauvegardes")
CAPTURES = os.path.join(HERE, "captures")
LAUNCHER = os.path.join(HERE, "launcher")
LAUNCHER_ID = "fr.accueil.zen"
ARES_DEVICE = "tv"

# Applis à mettre dans le dock, dans l'ordre. Chaque entrée : titre affiché,
# mots-clés cherchés dans le nom des applis de la TV, couleur de secours.
FAVORITES = [
    ("4K Player", ["4k player", "4k video player", "player 4k"], "#1f6feb"),
    ("Smart IPTV", ["smart iptv", "siptv"], "#7b3fe4"),
    ("YouTube", ["youtube"], "#e5302a"),
    ("Netflix", ["netflix"], "#b20710"),
    ("Rakuten TV", ["rakuten"], "#bf0000"),
]
# Ajouté à la fin du dock, toujours présent sur webOS.
SETTINGS_TILE = {"id": "com.palm.app.settings", "title": "Réglages", "icon": "", "color": "#636366"}

# Permissions demandées à l'appairage (affichées par la TV).
PERMISSIONS = [
    "LAUNCH", "LAUNCH_WEBAPP", "APP_TO_APP", "CLOSE", "CONTROL_AUDIO",
    "CONTROL_DISPLAY", "CONTROL_INPUT_TEXT", "CONTROL_POWER", "READ_APP_STATUS",
    "READ_CURRENT_CHANNEL", "READ_INPUT_DEVICE_LIST", "READ_NETWORK_STATE",
    "READ_RUNNING_APPS", "READ_TV_CHANNEL_LIST", "READ_INSTALLED_APPS",
    "READ_POWER_STATE", "READ_COUNTRY_INFO", "READ_SETTINGS", "WRITE_NOTIFICATION_TOAST",
    "WRITE_NOTIFICATION_ALERT", "CONTROL_TV_SCREEN", "CAPTURE_TV",
]


def die(msg):
    print("✗ " + msg, file=sys.stderr)
    sys.exit(1)


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def stamp():
    return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


# --------------------------------------------------------------------------
# Client WebSocket minimal (RFC 6455), suffisant pour l'API LG Connect.
# --------------------------------------------------------------------------

class WebSocket:
    def __init__(self, host, port, secure, timeout=10):
        raw = socket.create_connection((host, port), timeout=timeout)
        if secure:
            # La TV utilise un certificat auto-signé sur le réseau local.
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            raw = ctx.wrap_socket(raw, server_hostname=host)
        self.sock = raw
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET / HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(1024)
            if not chunk:
                raise ConnectionError("la TV a fermé la connexion")
            head += chunk
        head, self.buffer = head.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise ConnectionError("réponse inattendue : " + head.split(b"\r\n", 1)[0].decode(errors="replace"))

    def settimeout(self, seconds):
        self.sock.settimeout(seconds)

    def _read(self, n):
        while len(self.buffer) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("connexion fermée")
            self.buffer += chunk
        data, self.buffer = self.buffer[:n], self.buffer[n:]
        return data

    def _send_frame(self, opcode, payload):
        header = bytes([0x80 | opcode])
        n = len(payload)
        if n < 126:
            header += bytes([0x80 | n])
        elif n < 65536:
            header += bytes([0x80 | 126]) + struct.pack("!H", n)
        else:
            header += bytes([0x80 | 127]) + struct.pack("!Q", n)
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        self.sock.sendall(header + mask + masked)

    def send(self, text):
        self._send_frame(0x1, text.encode())

    def recv(self):
        message = b""
        while True:
            b1, b2 = self._read(2)
            opcode, n = b1 & 0x0F, b2 & 0x7F
            if n == 126:
                n = struct.unpack("!H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack("!Q", self._read(8))[0]
            mask = self._read(4) if b2 & 0x80 else None
            payload = self._read(n)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if opcode == 0x8:
                raise ConnectionError("la TV a fermé la connexion")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode in (0x0, 0x1, 0x2):
                message += payload
                if b1 & 0x80:
                    return message.decode()

    def close(self):
        try:
            self._send_frame(0x8, b"")
            self.sock.close()
        except OSError:
            pass


# --------------------------------------------------------------------------
# Découverte et API LG Connect (ssap://)
# --------------------------------------------------------------------------

def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))  # aucune donnée envoyée
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def ssdp_discover(timeout=4):
    msg = (
        "M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\n"
        "MX: 2\r\nST: urn:lge-com:service:webos-second-screen:1\r\n\r\n"
    ).encode()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.settimeout(timeout)
    found = {}
    try:
        for _ in range(2):
            sock.sendto(msg, ("239.255.255.250", 1900))
        while True:
            data, (ip, _) = sock.recvfrom(4096)
            text = data.decode(errors="replace")
            name = re.search(r"(?im)^DLNADeviceName\.lge\.com:\s*(.+)$", text)
            found[ip] = urllib.parse.unquote(name.group(1).strip()) if name else "TV LG webOS"
    except (socket.timeout, OSError):
        pass
    finally:
        sock.close()
    return found


def port_scan(timeout=0.4):
    """Plan B si le multicast est bloqué : cherche le port 3000/3001 sur le /24."""
    ip = local_ip()
    if not ip:
        return {}
    prefix = ip.rsplit(".", 1)[0]
    found = {}

    def probe(host):
        for port in (3001, 3000):
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    found[host] = f"appareil webOS probable (port {port})"
                    return
            except OSError:
                pass

    threads = [threading.Thread(target=probe, args=(f"{prefix}.{i}",)) for i in range(1, 255)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return found


class TV:
    def __init__(self, host, client_key=None):
        self.host = host
        self.client_key = client_key
        self.ws = None
        self.counter = 0

    def connect(self):
        errors = []
        for port, secure in ((3001, True), (3000, False)):
            try:
                self.ws = WebSocket(self.host, port, secure)
                return self
            except (OSError, ConnectionError, ssl.SSLError) as e:
                errors.append(f"{port}: {e}")
        die(f"impossible de joindre la TV à {self.host} ({'; '.join(errors)}). "
            "Vérifie qu'elle est allumée et que « LG Connect Apps » / « Allumer via Wi-Fi » est activé.")

    def register(self, wait_for_prompt=60):
        payload = {
            "forcePairing": False,
            "pairingType": "PROMPT",
            "manifest": {"manifestVersion": 1, "appVersion": "1.0", "permissions": PERMISSIONS},
        }
        if self.client_key:
            payload["client-key"] = self.client_key
        self.ws.send(json.dumps({"type": "register", "id": "register_0", "payload": payload}))
        self.ws.settimeout(wait_for_prompt)
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("type") == "registered":
                self.client_key = msg["payload"]["client-key"]
                self.ws.settimeout(15)
                return self.client_key
            if msg.get("type") == "error":
                die("appairage refusé : " + str(msg.get("error")))
            if msg.get("payload", {}).get("pairingType") == "PROMPT":
                print("→ Accepte la demande qui s'affiche sur la TV (télécommande : OK)…")

    def request(self, uri, payload=None):
        self.counter += 1
        rid = f"req_{self.counter}"
        msg = {"type": "request", "id": rid, "uri": uri}
        if payload is not None:
            msg["payload"] = payload
        self.ws.send(json.dumps(msg))
        while True:
            reply = json.loads(self.ws.recv())
            if reply.get("id") != rid:
                continue
            if reply.get("type") == "error":
                raise RuntimeError(f"{uri} : {reply.get('error')}")
            return reply.get("payload", {})

    def try_request(self, uri, payload=None):
        try:
            return self.request(uri, payload)
        except (RuntimeError, OSError, ConnectionError) as e:
            return {"erreur": str(e)}

    def toast(self, text):
        self.try_request("ssap://system.notifications/createToast", {"message": text})

    def close(self):
        if self.ws:
            self.ws.close()


def connected_tv():
    state = load_state()
    if not state.get("host"):
        die("TV inconnue. Lance d'abord : python lgtv.py trouver")
    tv = TV(state["host"], state.get("client_key")).connect()
    key = tv.register()
    if key != state.get("client_key"):
        state["client_key"] = key
        save_state(state)
    return tv


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "lgtv-kit/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)
    return dest


def take_capture(tv, label, folder=CAPTURES):
    os.makedirs(folder, exist_ok=True)
    res = tv.try_request("ssap://tv/executeOneShot", {"path": "/tmp/capture.jpg", "method": "DISPLAY", "format": "JPG"})
    uri = res.get("imageUri")
    if not uri:
        print(f"  (capture impossible : {res.get('erreur', 'la TV ne renvoie pas d image')} — "
              "certains modèles la bloquent ; prends une photo avec ton téléphone)")
        return None
    safe = re.sub(r"[^\w-]+", "-", label).strip("-") or "capture"
    dest = os.path.join(folder, f"{stamp()}_{safe}.jpg")
    try:
        fetch(uri, dest)
    except OSError as e:
        print(f"  (téléchargement de la capture impossible : {e})")
        return None
    print(f"  📷 {os.path.relpath(dest, HERE)}")
    return dest


def list_apps(tv):
    apps = tv.request("ssap://com.webos.applicationManager/listApps").get("apps", [])
    return sorted(apps, key=lambda a: str(a.get("title", "")).lower())


# --------------------------------------------------------------------------
# Commandes
# --------------------------------------------------------------------------

def cmd_trouver(args):
    if args:
        found = {args[0]: "TV indiquée à la main"}
    else:
        print("Recherche des TV LG sur le Wi-Fi…")
        found = ssdp_discover() or port_scan()
    if not found:
        die("aucune TV trouvée. Allume-la, vérifie que l'ordinateur est sur le même Wi-Fi, "
            "ou indique l'adresse : python lgtv.py trouver 192.168.1.42")
    items = list(found.items())
    for i, (ip, name) in enumerate(items, 1):
        print(f"  {i}. {name} — {ip}")
    choice = 0
    if len(items) > 1:
        choice = int(input("Numéro de ta TV : ") or 1) - 1
    host = items[choice][0]
    state = load_state()
    if state.get("host") != host:
        state = {"host": host}
    save_state(state)
    print(f"✓ TV enregistrée : {host}. Étape suivante : python lgtv.py appairer")


def cmd_appairer(args):
    tv = connected_tv()
    info = tv.try_request("ssap://com.webos.service.update/getCurrentSWInformation")
    state = load_state()
    state["modele"] = info.get("model_name") or info.get("product_name")
    state["webos"] = info.get("product_name")
    save_state(state)
    tv.toast("Kit d'allègement connecté ✓")
    print(f"✓ Appairé ({state.get('modele') or 'modèle inconnu'}). Étape suivante : python lgtv.py sauvegarder")
    tv.close()


def cmd_sauvegarder(args):
    tv = connected_tv()
    folder = os.path.join(BACKUPS, stamp())
    os.makedirs(folder)
    queries = {
        "infos_systeme": "ssap://system/getSystemInfo",
        "version_logiciel": "ssap://com.webos.service.update/getCurrentSWInformation",
        "applis": "ssap://com.webos.applicationManager/listApps",
        "lanceur": "ssap://com.webos.applicationManager/listLaunchPoints",
        "entrees": "ssap://tv/getExternalInputList",
        "son": "ssap://audio/getVolume",
        "appli_en_cours": "ssap://com.webos.applicationManager/getForegroundAppInfo",
    }
    for name, uri in queries.items():
        data = tv.try_request(uri)
        with open(os.path.join(folder, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  ⚠ {name} ({data['erreur']})" if "erreur" in data else f"  ✓ {name}")
    # Ordre et visibilité du ruban d'accueil = la donnée la plus utile à restaurer.
    points = json.load(open(os.path.join(folder, "lanceur.json"), encoding="utf-8")).get("launchPoints", [])
    with open(os.path.join(folder, "ruban_accueil.txt"), "w", encoding="utf-8") as f:
        for i, p in enumerate(points, 1):
            f.write(f"{i:2}. {p.get('title')}  [{p.get('id')}]\n")
    take_capture(tv, "accueil-avant", folder)
    with open(os.path.join(folder, "modifications.json"), "w", encoding="utf-8") as f:
        json.dump({"cree_le": stamp(), "reglages": {}}, f, indent=2)
    state = load_state()
    state["derniere_sauvegarde"] = os.path.relpath(folder, HERE)
    save_state(state)
    tv.toast("Sauvegarde terminée ✓")
    print(f"✓ Sauvegarde dans {os.path.relpath(folder, HERE)}")
    tv.close()


def cmd_capture(args):
    tv = connected_tv()
    take_capture(tv, args[0] if args else "capture")
    tv.close()


def cmd_applis(args):
    tv = connected_tv()
    for a in list_apps(tv):
        flags = []
        if a.get("systemApp"):
            flags.append("système")
        if not a.get("visible", True):
            flags.append("masquée")
        print(f"  {a.get('title', '?'):<32} {a.get('id'):<42} {', '.join(flags)}")
    tv.close()


def cmd_lancer(args):
    if not args:
        die("indique l'identifiant de l'appli (voir : python lgtv.py applis)")
    tv = connected_tv()
    tv.request("ssap://system.launcher/launch", {"id": args[0]})
    print(f"✓ {args[0]} lancée")
    tv.close()


def latest_backup():
    folder = load_state().get("derniere_sauvegarde")
    if not folder or not os.path.isdir(os.path.join(HERE, folder)):
        die("fais d'abord une sauvegarde : python lgtv.py sauvegarder")
    return os.path.join(HERE, folder)


def cmd_alleger(args):
    from reglages import REGLAGES

    folder = latest_backup()
    log_path = os.path.join(folder, "modifications.json")
    log = json.load(open(log_path, encoding="utf-8"))
    tv = connected_tv()
    shots = os.path.join(folder, "captures")
    print("Je te guide réglage par réglage. Pour chacun : je pose la question si c'est une\n"
          "fonction que tu pourrais utiliser, tu fais le changement avec la télécommande,\n"
          "et je prends une capture avant/après. Entrée = oui, n = non, q = quitter.\n")
    for r in REGLAGES:
        if r["id"] in log["reglages"] and not log["reglages"][r["id"]].get("restaure"):
            continue  # déjà traité lors d'une séance précédente
        print(f"── {r['titre']}")
        print(f"   {r['pourquoi']}")
        if r.get("question"):
            answer = input(f"   ❓ {r['question']} (o/N) ").strip().lower()
            if answer == "q":
                break
            if answer in ("o", "oui", "y"):
                print("   → On garde tel quel.\n")
                log["reglages"][r["id"]] = {"fait": False, "raison": "utilisé"}
                json.dump(log, open(log_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
                continue
        print(f"   Chemin : {r['chemin']}")
        input("   Ouvre cet écran sur la TV puis appuie sur Entrée (capture AVANT)… ")
        before = take_capture(tv, r["id"] + "-avant", shots)
        print(f"   Action : {r['action']}")
        answer = input("   Fait ? (O/n/q) ").strip().lower()
        if answer == "q":
            break
        done = answer not in ("n", "non")
        after = take_capture(tv, r["id"] + "-apres", shots) if done else None
        log["reglages"][r["id"]] = {
            "fait": done, "le": stamp(), "pour_annuler": r["annuler"],
            "capture_avant": before and os.path.relpath(before, HERE),
            "capture_apres": after and os.path.relpath(after, HERE),
        }
        json.dump(log, open(log_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print("   ✓ noté\n" if done else "   → laissé tel quel\n")
    tv.close()
    print("Journal des changements :", os.path.relpath(log_path, HERE))


def match_app(apps, keywords):
    for a in apps:
        title = str(a.get("title", "")).lower()
        if any(k in title for k in keywords):
            return a
    return None


def cmd_dock(args):
    tv = connected_tv()
    apps = list_apps(tv)
    points = {p.get("id"): p for p in tv.try_request("ssap://com.webos.applicationManager/listLaunchPoints").get("launchPoints", [])}
    os.makedirs(os.path.join(LAUNCHER, "icons"), exist_ok=True)
    extras = [(name, [name.lower()], "#3a3a3c") for name in args]
    dock = []
    for title, keywords, color in FAVORITES + extras:
        app = match_app(apps, keywords)
        if not app:
            print(f"  ⚠ {title} introuvable sur la TV — ignorée")
            continue
        entry = {"id": app["id"], "title": title, "icon": "", "color": color}
        icon = points.get(app["id"], {}).get("largeIcon") or points.get(app["id"], {}).get("icon") or ""
        if icon.startswith("http"):
            dest = os.path.join(LAUNCHER, "icons", re.sub(r"[^\w.-]", "_", app["id"]) + ".png")
            try:
                fetch(icon, dest)
                entry["icon"] = "icons/" + os.path.basename(dest)
            except OSError:
                pass
        dock.append(entry)
        print(f"  ✓ {title:<12} {app['id']}" + ("" if entry["icon"] else "  (icône de secours)"))
    dock.append(SETTINGS_TILE)
    config_path = os.path.join(LAUNCHER, "config.json")
    config = json.load(open(config_path, encoding="utf-8"))
    config["dock"] = dock
    json.dump(config, open(config_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"✓ Dock écrit dans launcher/config.json ({len(dock)} tuiles)")
    tv.close()


WIKIMEDIA_CATEGORIES = [
    "Category:Featured pictures of landscapes",
    "Category:Featured pictures of mountains",
    "Category:Featured pictures of forests",
    "Category:Featured pictures of lakes",
    "Category:Featured pictures of waterfalls",
]


def cmd_fonds(args):
    """Télécharge des photos nature libres de droits (Wikimedia Commons, images « remarquables »)."""
    import random

    count = int(args[0]) if args else 12
    folder = os.path.join(LAUNCHER, "wallpapers")
    os.makedirs(folder, exist_ok=True)
    candidates = []
    for cat in WIKIMEDIA_CATEGORIES:
        query = urllib.parse.urlencode({
            "action": "query", "format": "json", "generator": "categorymembers",
            "gcmtitle": cat, "gcmtype": "file", "gcmlimit": "100", "prop": "imageinfo",
            "iiprop": "url|size|extmetadata|mime", "iiurlwidth": "1920",
        })
        req = urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + query,
                                     headers={"User-Agent": "lgtv-kit/1.0 (fonds d'ecran personnels)"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                pages = json.load(r).get("query", {}).get("pages", {}).values()
        except (OSError, ValueError) as e:
            print(f"  ⚠ {cat} : {e}")
            continue
        for p in pages:
            info = (p.get("imageinfo") or [{}])[0]
            if info.get("mime") != "image/jpeg" or info.get("width", 0) < info.get("height", 1) * 1.4:
                continue
            meta = info.get("extmetadata", {})
            artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "inconnu")).strip()
            candidates.append({
                "url": info.get("thumburl") or info["url"], "page": info.get("descriptionurl"),
                "auteur": artist, "licence": meta.get("LicenseShortName", {}).get("value", "?"),
                "titre": p.get("title", "").replace("File:", "").rsplit(".", 1)[0],
            })
    if not candidates:
        die("aucune photo récupérée (connexion ?). Tu peux aussi déposer tes propres .jpg dans launcher/wallpapers/")
    random.shuffle(candidates)
    manifest = []
    for i, c in enumerate(candidates[:count], 1):
        name = f"nature-{i:02}.jpg"
        try:
            fetch(c["url"], os.path.join(folder, name))
        except OSError as e:
            print(f"  ⚠ {c['titre']} : {e}")
            continue
        manifest.append({"file": "wallpapers/" + name, "titre": c["titre"], "credit": f"{c['auteur']} · {c['licence']}", "source": c["page"]})
        print(f"  ✓ {name}  {c['titre'][:50]}")
    sync_wallpapers(manifest)


def sync_wallpapers(manifest=None):
    """Ajoute au manifeste les .jpg déposés à la main dans launcher/wallpapers/."""
    folder = os.path.join(LAUNCHER, "wallpapers")
    path = os.path.join(folder, "wallpapers.json")
    if manifest is None:
        try:
            manifest = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            manifest = []
    known = {m["file"] for m in manifest}
    for name in sorted(os.listdir(folder)):
        if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and "wallpapers/" + name not in known:
            manifest.append({"file": "wallpapers/" + name, "titre": os.path.splitext(name)[0], "credit": ""})
    manifest = [m for m in manifest if os.path.exists(os.path.join(LAUNCHER, m["file"]))]
    json.dump(manifest, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"✓ {len(manifest)} photo(s) dans launcher/wallpapers (+ 6 paysages dessinés intégrés)")


def ares(*cmd, check=True):
    exe = shutil.which(cmd[0])
    if not exe:
        die(f"{cmd[0]} introuvable. Installe les outils LG : npm install -g @webos-tools/cli")
    print("  $ " + " ".join(cmd))
    return subprocess.run([exe, *cmd[1:]], check=check)


def ares_device_ready():
    exe = shutil.which("ares-setup-device")
    if not exe:
        return False
    out = subprocess.run([exe, "--list"], capture_output=True, text=True).stdout
    return any(line.split()[:1] == [ARES_DEVICE] for line in out.splitlines())


def cmd_installer(args):
    state = load_state()
    latest_backup()  # refuse d'installer sans sauvegarde
    if not ares_device_ready():
        print("Première installation : sur la TV, ouvre l'appli « Developer Mode » (LG Content Store),\n"
              "connecte-toi avec un compte développeur LG gratuit, active « Dev Mode Status »\n"
              "puis « Key Server ». La TV redémarre une fois.")
        input("Entrée quand c'est fait… ")
        ares("ares-setup-device", "--add", ARES_DEVICE, "--info", f"host={state['host']}",
             "--info", "port=9922", "--info", "username=prisoner")
        print("Saisis la « Passphrase » affichée dans l'appli Developer Mode :")
        ares("ares-novacom", "--device", ARES_DEVICE, "--getkey")
    sync_wallpapers()
    dist = os.path.join(HERE, "dist")
    os.makedirs(dist, exist_ok=True)
    ares("ares-package", LAUNCHER, "--outdir", dist)
    ipks = sorted(f for f in os.listdir(dist) if f.startswith(LAUNCHER_ID) and f.endswith(".ipk"))
    ares("ares-install", "--device", ARES_DEVICE, os.path.join(dist, ipks[-1]))
    ares("ares-launch", "--device", ARES_DEVICE, LAUNCHER_ID)
    tv = connected_tv()
    import time
    time.sleep(4)
    take_capture(tv, "accueil-zen")
    tv.close()
    print("✓ Écran d'accueil installé. Astuce : place « Accueil Zen » en tête du ruban LG et\n"
          "  appuie longuement sur une touche chiffre de la télécommande pour en faire un raccourci.")


COMMANDS = {
    "trouver": cmd_trouver, "appairer": cmd_appairer, "sauvegarder": cmd_sauvegarder,
    "capture": cmd_capture, "applis": cmd_applis, "lancer": cmd_lancer, "alleger": cmd_alleger,
    "dock": cmd_dock, "fonds": cmd_fonds, "installer": cmd_installer,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(0 if len(sys.argv) < 2 else 1)
    try:
        COMMANDS[sys.argv[1]](sys.argv[2:])
    except KeyboardInterrupt:
        print("\ninterrompu")
