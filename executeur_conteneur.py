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

from capacites import FLAGS_INVARIANTS, Capacites

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


def _preparer_volume(nom: str, point: str = "/data") -> None:
    """
    Cree le volume nomme (idempotent) et donne sa propriete a l'utilisateur non-root
    du produit (65534). Le chown est un SETUP CREATEUR : root, jetable, sur un volume
    isole uniquement, jamais sur l'hote. Sans lui, le produit non-root ne peut ecrire.
    """
    subprocess.run(["docker", "volume", "create", nom], capture_output=True, text=True, timeout=15)
    subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--user", "0:0",
         "-v", f"{nom}:{point}", IMAGE, "chown", "-R", "65534:65534", point],
        capture_output=True, text=True, timeout=40,
    )


def executer_en_conteneur(code: str, timeout: int = 25,
                          cap: Capacites | None = None, volume_nom: str | None = None):
    """
    Execute le code dans un conteneur Docker, avec une isolation GRADUEE selon les
    capacites accordees au produit (cf. capacites.py). Les invariants du createur
    (FLAGS_INVARIANTS) sont TOUJOURS appliques : non-root, zero capability, ressources
    bornees, ephemere, racine en lecture seule.

    Renvoie (code_retour, stdout, stderr, chemin), comme executer_isole de usine.py.

    Le code passe par STDIN (`python -`), jamais par un bind-mount (un bind-mount est
    resolu par le demon HOTE, donc invisible depuis le conteneur API). La PERSISTANCE
    accordee utilise un VOLUME NOMME (gere par le demon -> marche aussi en sibling).

    NIVEAU 1 (createur) : toujours actif. NIVEAU 2 (produit) : seulement si accorde.
    """
    cap = cap or Capacites()

    # RESEAU : invariant DevSecOps -> aucune sortie brute. Tant que la liste blanche
    # n'est pas appliquee par un proxy d'egress, on REFUSE d'ouvrir le reseau (on ne
    # viole pas l'invariant en silence). La capacite reste declarable ; son execution
    # reelle arrive a l'etape suivante (proxy d'egress + reseau interne).
    if cap.reseau:
        return (-2, "",
                "RESEAU accorde mais enforcement liste blanche pas encore actif "
                "(proxy d'egress = prochaine etape). Execution reseau refusee par securite.",
                "<reseau>")

    cmd = ["docker", "run", "-i"] + FLAGS_INVARIANTS + ["--network", "none"]

    # PERSISTANCE : volume nomme isole monte sur le point d'ancrage accorde.
    if cap.persistance:
        if not volume_nom:
            return (-2, "", "PERSISTANCE accordee mais aucun volume nomme fourni.", "<persistance>")
        _preparer_volume(volume_nom, cap.chemin_persistance)
        cmd += ["-v", f"{volume_nom}:{cap.chemin_persistance}:rw"]

    cmd += ["-e", "PYTHONIOENCODING=utf-8", IMAGE, "python", "-"]

    try:
        r = subprocess.run(cmd, input=code, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr, ("<volume:" + volume_nom + ">" if cap.persistance else "<stdin>")
    except subprocess.TimeoutExpired:
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