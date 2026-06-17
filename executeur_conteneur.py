"""
VIVARIUM - Executeur conteneur : isolation de niveau industriel (Docker)

Remplace l'isolation processus de usine.py par un VRAI conteneur durci.
Le code genere tourne dans un conteneur Docker ephemere :
  - --network none        : aucun acces reseau
  - --read-only + tmpfs   : systeme de fichiers en lecture seule, scratch jetable
  - --memory / --cpus / --pids-limit : limites de ressources
  - --cap-drop ALL + no-new-privileges + --user : zero privilege, non-root
  - --rm + timeout        : ephemere, borne dans le temps

SECURITE : a faire tourner en LOCAL (Docker Desktop), JAMAIS sur le VPS de
production (netroia.tech + n8n). Pour du code genere par IA, on ne touche pas
a la prod.

Prerequis (une fois) : Docker Desktop lance + `docker pull python:3.12-slim`.
Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
import subprocess

IMAGE = "python:3.12-slim"


def docker_disponible() -> tuple[bool, str]:
    """Le client ET le demon Docker sont-ils joignables ?"""
    try:
        r = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            return True, r.stdout.strip()
        return False, (r.stderr.strip() or "demon Docker injoignable (Docker Desktop lance ?)")
    except FileNotFoundError:
        return False, "client docker introuvable (Docker non installe)"
    except subprocess.TimeoutExpired:
        return False, "docker info a expire"


def image_presente() -> bool:
    try:
        r = subprocess.run(["docker", "image", "inspect", IMAGE],
                           capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def executer_en_conteneur(code: str, timeout: int = 25):
    """
    Execute le code dans un conteneur Docker durci.
    Renvoie (code_retour, stdout, stderr, chemin) comme executer_isole de usine.py.

    Le code est passe par STDIN (`python -`), PAS par un bind-mount : un bind-mount
    est resolu par le demon HOTE, donc un chemin interne au conteneur appelant
    (cas du service API) serait invisible cote hote. Stdin marche dans les deux cas
    (hote ou conteneur) et evite tout montage du systeme de fichiers.
    """
    cmd = [
        "docker", "run", "--rm", "-i",             # -i : stdin branche
        "--network", "none",                       # aucun reseau
        "--read-only",                             # fs racine en lecture seule
        "--tmpfs", "/tmp:rw,size=32m",             # scratch jetable
        "--memory", "256m", "--cpus", "0.5",       # limites ressources
        "--pids-limit", "64",
        "--cap-drop", "ALL",                       # zero capability
        "--security-opt", "no-new-privileges",
        "--user", "65534:65534",                   # nobody : non-root
        "-e", "PYTHONIOENCODING=utf-8",
        IMAGE,
        "python", "-",                             # lit le programme sur stdin
    ]
    try:
        r = subprocess.run(cmd, input=code, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr, "<stdin>"
    except subprocess.TimeoutExpired:
        # le --rm nettoie le conteneur ; on signale le depassement
        return -1, "", f"TIMEOUT conteneur apres {timeout}s", "<stdin>"


if __name__ == "__main__":
    print("=" * 70)
    print("VIVARIUM - EXECUTEUR CONTENEUR (test d'isolation industrielle)")
    print("=" * 70)

    ok, info = docker_disponible()
    print(f"\nDocker demon : {'OK (' + info + ')' if ok else 'INDISPONIBLE -> ' + info}")
    if not ok:
        print("\nPour activer : lance Docker Desktop, puis relance ce script.")
        raise SystemExit(0)

    if not image_presente():
        print(f"\nImage {IMAGE} absente. Telechargement (une fois, necessite reseau)...")
        subprocess.run(["docker", "pull", IMAGE])

    # Test 1 : un code sain doit tourner et renvoyer 0
    code_sain = (
        "print('Bonjour depuis le conteneur durci')\n"
        "print('2 + 2 =', 2 + 2)\n"
        "assert 2 + 2 == 4\n"
        "print('[OK] test passe a l interieur du conteneur')\n"
    )
    print("\n--- Test 1 : code sain ---")
    rc, out, err, _ = executer_en_conteneur(code_sain)
    print(f"  code retour : {rc}")
    for l in out.strip().splitlines():
        print("    " + l)
    if err.strip():
        print("    [stderr]", err.strip()[:200])

    # Test 2 : une tentative d'acces reseau doit ECHOUER (--network none)
    code_reseau = (
        "import urllib.request\n"
        "urllib.request.urlopen('http://example.com', timeout=5)\n"
        "print('reseau OK (NE DEVRAIT PAS arriver)')\n"
    )
    print("\n--- Test 2 : tentative d'acces reseau (doit echouer) ---")
    rc2, out2, err2, _ = executer_en_conteneur(code_reseau)
    print(f"  code retour : {rc2}")
    derniere = err2.strip().splitlines()[-1] if err2.strip() else "(pas d'erreur ?!)"
    print(f"  -> {'BLOQUE comme prevu : ' + derniere if rc2 != 0 else 'ALERTE : le reseau a marche !'}")

    print("\n" + "=" * 70)
    print("Isolation industrielle prete : conteneur ephemere, sans reseau, sans privilege,")
    print("ressources bornees. A utiliser en LOCAL, jamais sur le VPS de production.")
    print("=" * 70)