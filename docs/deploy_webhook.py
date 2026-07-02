#!/usr/bin/env python3
"""
NEOGEN - Webhook de deploiement : declenche 'git pull + rebuild' sans SSH.

Contexte : Claude Code n'a pas d'acces SSH direct au VPS (restriction sandbox). Ce petit
service tourne EN PERMANENCE sur le VPS (systemd), separement du conteneur NEOGEN qu'il
redemarre - sinon il se couperait lui-meme en plein redeploiement. Ecoute en local
uniquement (127.0.0.1), expose au monde via le reverse proxy nginx existant (reutilise
le certificat SSL deja en place pour neogen.netroia.tech, aucun nouveau port ouvert).

Securite :
- Action fixe et non parametrable : UNIQUEMENT 'git pull' + 'docker compose up -d --build'
  sur le repo NEOGEN. Aucune commande arbitraire n'est jamais construite depuis la requete.
- Authentification par secret partage (header X-Deploy-Secret), comparaison a temps
  constant (hmac.compare_digest) pour eviter une attaque par timing.
- Chaque appel est journalise (succes/echec, horodatage) dans deploy_webhook.log.
- Aucune dependance externe : stdlib uniquement (http.server), rien a installer sur le VPS.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-07-02.
"""
from __future__ import annotations

import hmac
import http.server
import json
import os
import subprocess
import time

PORT = 9001
REPO_DIR = "/root/NEOGEN"
COMPOSE_FILE = "docker-compose.prod.yml"
SECRET = os.environ.get("DEPLOY_WEBHOOK_SECRET", "")
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deploy_webhook.log")


def _log(ligne: str) -> None:
    horodatage = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{horodatage}] {ligne}\n")
    except Exception:
        pass


def _deployer() -> dict:
    """Sequence fixe : pull puis rebuild. Ne prend aucun parametre de la requete."""
    etapes = []
    try:
        r1 = subprocess.run(
            ["git", "-C", REPO_DIR, "pull", "origin", "main"],
            capture_output=True, text=True, timeout=60,
        )
        etapes.append({"etape": "git pull", "code": r1.returncode,
                       "sortie": (r1.stdout + r1.stderr)[-2000:]})
        if r1.returncode != 0:
            return {"ok": False, "etapes": etapes}

        r2 = subprocess.run(
            ["docker", "compose", "-f", COMPOSE_FILE, "up", "-d", "--build"],
            capture_output=True, text=True, timeout=600, cwd=REPO_DIR,
        )
        etapes.append({"etape": "docker compose up -d --build", "code": r2.returncode,
                       "sortie": (r2.stdout + r2.stderr)[-2000:]})
        return {"ok": r2.returncode == 0, "etapes": etapes}
    except Exception as e:
        etapes.append({"etape": "exception", "erreur": str(e)})
        return {"ok": False, "etapes": etapes}


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/deploy":
            self.send_response(404)
            self.end_headers()
            return

        recu = self.headers.get("X-Deploy-Secret", "")
        if not SECRET or not hmac.compare_digest(recu, SECRET):
            _log("REFUS : secret invalide ou absent")
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b'{"ok": false, "raison": "secret invalide"}')
            return

        _log("DEBUT deploiement")
        resultat = _deployer()
        _log(f"FIN deploiement : ok={resultat['ok']}")

        self.send_response(200 if resultat["ok"] else 500)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resultat, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        pass  # silence le log stdout par defaut de BaseHTTPRequestHandler ; on a notre propre _log


def main() -> None:
    if not SECRET:
        print("ERREUR : DEPLOY_WEBHOOK_SECRET non defini. Arret.")
        raise SystemExit(1)
    serveur = http.server.HTTPServer(("127.0.0.1", PORT), _Handler)
    _log(f"demarrage webhook sur 127.0.0.1:{PORT}")
    serveur.serve_forever()


if __name__ == "__main__":
    main()
