#!/usr/bin/env python3
"""Remet la TV dans l'état de la sauvegarde.

    python restaurer.py                 # utilise la dernière sauvegarde
    python restaurer.py sauvegardes/2026-10-24_20-15-00

1. Désinstalle l'écran d'accueil « Accueil Zen » (seule chose installée par le kit).
2. Relit le journal des changements et te guide pour annuler chacun d'eux,
   avec une capture de vérification.
3. Compare la liste des applis avec celle de la sauvegarde (rien ne doit manquer).
"""

import json
import os
import shutil
import subprocess
import sys

import lgtv


def uninstall_launcher():
    exe = shutil.which("ares-install")
    if not exe:
        print("  (outils LG absents : si « Accueil Zen » est installé, retire-le depuis le ruban d'accueil,\n"
              "   c'est la seule appli que le kit a ajoutée)")
        return
    listed = subprocess.run([exe, "--device", lgtv.ARES_DEVICE, "--list"], capture_output=True, text=True)
    if lgtv.LAUNCHER_ID not in listed.stdout:
        print("  ✓ Accueil Zen n'est pas installé")
        return
    subprocess.run([exe, "--device", lgtv.ARES_DEVICE, "--remove", lgtv.LAUNCHER_ID], check=False)
    print("  ✓ Accueil Zen désinstallé")


def main():
    folder = os.path.join(lgtv.HERE, sys.argv[1]) if len(sys.argv) > 1 else lgtv.latest_backup()
    log_path = os.path.join(folder, "modifications.json")
    if not os.path.exists(log_path):
        lgtv.die(f"pas de journal dans {folder}")
    log = json.load(open(log_path, encoding="utf-8"))
    print(f"Restauration depuis {os.path.relpath(folder, lgtv.HERE)}\n")

    print("1/3 Écran d'accueil")
    uninstall_launcher()

    tv = lgtv.connected_tv()
    shots = os.path.join(folder, "captures-restauration")
    done = [(k, v) for k, v in log["reglages"].items() if v.get("fait")]
    print(f"\n2/3 Réglages à annuler : {len(done)}")
    for key, entry in reversed(done):
        print(f"── {key}\n   {entry['pour_annuler']}")
        if entry.get("capture_avant"):
            print(f"   État d'origine : {entry['capture_avant']}")
        answer = input("   Annulé ? (O/n) ").strip().lower()
        if answer in ("n", "non"):
            continue
        lgtv.take_capture(tv, key + "-restaure", shots)
        entry["fait"] = False
        entry["restaure"] = True
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2, ensure_ascii=False)

    print("\n3/3 Vérification des applis")
    before = json.load(open(os.path.join(folder, "applis.json"), encoding="utf-8")).get("apps", [])
    now = {a["id"] for a in lgtv.list_apps(tv)}
    missing = [a.get("title", a["id"]) for a in before if a["id"] not in now]
    print("  ✓ Toutes les applis d'origine sont là" if not missing else "  ⚠ Absentes : " + ", ".join(missing))
    print(f"  Ordre d'origine du ruban : {os.path.relpath(os.path.join(folder, 'ruban_accueil.txt'), lgtv.HERE)}")
    lgtv.take_capture(tv, "accueil-restaure", shots)
    tv.toast("Restauration terminée ✓")
    tv.close()
    print("\n✓ Terminé. Pour un retour total aux réglages d'usine (efface tout, y compris tes comptes) :\n"
          "  Réglages > Général > Système > Réinitialiser les paramètres d'origine — normalement inutile.")


if __name__ == "__main__":
    main()
