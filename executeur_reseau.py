"""
VIVARIUM - Executeur reseau : egress par liste blanche via proxy

Quand un produit recoit la capacite RESEAU avec une liste blanche de domaines, on
ne lui ouvre PAS Internet en grand. On monte une topologie a 2 reseaux :

  [produit non fiable] --(reseau --internal, AUCUNE route vers Internet)--> [proxy]
  [proxy de confiance] --(reseau egress, acces Internet)--> Internet (liste blanche)

Le produit n'a aucune route directe : sa SEULE sortie est le proxy (via HTTP_PROXY).
Le proxy (NOTRE code, de confiance) n'autorise que les domaines de la liste blanche
(CONNECT pour HTTPS, requete absolue pour HTTP), tout le reste -> 403.

Ainsi : "accorder le reseau" = acces a 2-3 domaines precis, jamais Internet entier.
A utiliser en LOCAL / machine dediee, jamais sur le VPS de production.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-18.
"""

from __future__ import annotations
import base64
import subprocess
import secrets as _secrets

from capacites import FLAGS_INVARIANTS

IMAGE = "python:3.12-slim"

# Proxy d'egress allowlistant (stdlib pure). Lit la liste blanche dans ALLOW.
_PROXY_SRC = r'''
import os, socket, threading, select
from urllib.parse import urlparse

ALLOW = [h.strip().lower() for h in os.environ.get("ALLOW", "").split(",") if h.strip()]

def autorise(host):
    host = (host or "").lower().split(":")[0]
    return any(host == d or host.endswith("." + d) for d in ALLOW)

def tunnel(a, b):
    socks = [a, b]
    try:
        while True:
            r, _, _ = select.select(socks, [], [], 30)
            if not r:
                break
            for s in r:
                data = s.recv(65536)
                if not data:
                    return
                (b if s is a else a).sendall(data)
    finally:
        for s in socks:
            try: s.close()
            except Exception: pass

def handle(client):
    try:
        req = client.recv(65536)
        if not req:
            return client.close()
        line = req.split(b"\r\n", 1)[0].decode("latin1")
        parts = line.split(" ")
        if len(parts) < 2:
            return client.close()
        method, target = parts[0], parts[1]
        if method == "CONNECT":
            host, _, port = target.partition(":")
            port = int(port or 443)
            if not autorise(host):
                client.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\nbloque par la liste blanche")
                return client.close()
            up = socket.create_connection((host, port), timeout=10)
            client.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            tunnel(client, up)
        else:
            u = urlparse(target)
            host, port = u.hostname, (u.port or 80)
            if not autorise(host):
                client.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\nbloque par la liste blanche")
                return client.close()
            up = socket.create_connection((host, port), timeout=10)
            up.sendall(req)
            tunnel(client, up)
    except Exception:
        try: client.close()
        except Exception: pass

srv = socket.socket()
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("0.0.0.0", 8888))
srv.listen(64)
print("PROXY_READY", flush=True)
while True:
    c, _ = srv.accept()
    threading.Thread(target=handle, args=(c,), daemon=True).start()
'''


def _run(args, timeout=30):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def _proxy_pret(nom_proxy: str, essais: int = 15) -> bool:
    """Le proxy ecoute-t-il ? On verifie via les logs (PROXY_READY)."""
    for _ in range(essais):
        r = _run(["docker", "logs", nom_proxy], timeout=10)
        if "PROXY_READY" in (r.stdout + r.stderr):
            return True
    return False


def executer_avec_reseau(code: str, domaines: list[str], timeout: int = 25,
                         cap=None, volume_nom: str | None = None, env_extra: dict | None = None):
    """Execute le code avec egress restreint a `domaines`, via proxy. Nettoie tout a la fin."""
    if not domaines:
        return (-2, "", "RESEAU accorde sans liste blanche : refuse (rien d'autorise).", "<reseau>")

    sid = _secrets.token_hex(4)
    net_int = f"viv_int_{sid}"     # produit : aucune route externe
    net_eg = f"viv_eg_{sid}"       # proxy : acces Internet
    proxy = f"viv_proxy_{sid}"
    b64 = base64.b64encode(_PROXY_SRC.encode()).decode()
    cmd_proxy_py = f"import base64;exec(base64.b64decode('{b64}').decode())"

    cree = []
    try:
        _run(["docker", "network", "create", "--internal", net_int]); cree.append(("net", net_int))
        _run(["docker", "network", "create", net_eg]); cree.append(("net", net_eg))

        # proxy : demarre sur le reseau interne, durci au minimum (notre code de confiance)
        r = _run([
            "docker", "run", "-d", "--name", proxy, "--network", net_int,
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "-e", f"ALLOW={','.join(domaines)}",
            IMAGE, "python", "-c", cmd_proxy_py,
        ])
        if r.returncode != 0:
            return (-2, "", f"proxy non demarre : {r.stderr.strip()[:200]}", "<reseau>")
        cree.append(("ctr", proxy))
        # on donne au proxy l'acces Internet (2e reseau)
        _run(["docker", "network", "connect", net_eg, proxy])

        if not _proxy_pret(proxy):
            return (-2, "", "proxy d'egress jamais pret (timeout).", "<reseau>")

        # produit : durci, sur le reseau interne uniquement, sortie forcee via le proxy
        cmd = ["docker", "run", "-i"] + FLAGS_INVARIANTS + ["--network", net_int]
        if cap is not None and getattr(cap, "persistance", False) and volume_nom:
            from executeur_conteneur import _preparer_volume
            point = getattr(cap, "chemin_persistance", "/data")
            _preparer_volume(volume_nom, point)
            cmd += ["-v", f"{volume_nom}:{point}:rw"]
        proxy_url = f"http://{proxy}:8888"
        cmd += [
            "-e", "PYTHONIOENCODING=utf-8",
            "-e", f"HTTP_PROXY={proxy_url}", "-e", f"HTTPS_PROXY={proxy_url}",
            "-e", f"http_proxy={proxy_url}", "-e", f"https_proxy={proxy_url}",
        ]
        for k, v in (env_extra or {}).items():
            cmd += ["-e", f"{k}={v}"]
        cmd += [IMAGE, "python", "-"]
        try:
            res = subprocess.run(cmd, input=code, capture_output=True, text=True, timeout=timeout)
            return res.returncode, res.stdout, res.stderr, f"<reseau:{','.join(domaines)}>"
        except subprocess.TimeoutExpired:
            return -1, "", f"TIMEOUT conteneur apres {timeout}s", "<reseau>"
    finally:
        # nettoyage : conteneur proxy puis reseaux
        for kind, nom in reversed(cree):
            if kind == "ctr":
                _run(["docker", "rm", "-f", nom], timeout=20)
        for kind, nom in reversed(cree):
            if kind == "net":
                _run(["docker", "network", "rm", nom], timeout=20)
