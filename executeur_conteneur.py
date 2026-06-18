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
import json
import subprocess

from capacites import FLAGS_INVARIANTS, Capacites

IMAGE = "python:3.12-slim"

# Runner injecte apres le code d'un produit promu : lit l'entree JSON (env), appelle
# executer(donnees), et imprime le resultat apres un marqueur (pour le retrouver dans la sortie).
_MARQUEUR_OK = "___VIVARIUM_RESULT___"
_MARQUEUR_ERR = "___VIVARIUM_ERROR___"
_RUNNER = (
    "\n\n# --- runner VIVARIUM (promotion : execute sur donnees reelles) ---\n"
    "import os as _o, json as _j\n"
    "try:\n"
    "    _d = _j.loads(_o.environ.get('VIVARIUM_INPUT', 'null'))\n"
    "    _r = executer(_d)\n"
    "    print('" + _MARQUEUR_OK + "' + _j.dumps(_r, ensure_ascii=False, default=str))\n"
    "except Exception as _e:\n"
    "    print('" + _MARQUEUR_ERR + "' + repr(_e))\n"
)


def _extraire_resultat(rc, out, err) -> dict:
    for ligne in (out or "").splitlines():
        if ligne.startswith(_MARQUEUR_OK):
            try:
                return {"ok": True, "resultat": json.loads(ligne[len(_MARQUEUR_OK):])}
            except Exception as e:
                return {"ok": False, "erreur": f"resultat non JSON : {e}"}
        if ligne.startswith(_MARQUEUR_ERR):
            return {"ok": False, "erreur": ligne[len(_MARQUEUR_ERR):]}
    return {"ok": False, "erreur": (err.strip().splitlines()[-1] if err.strip() else "aucun resultat produit")}


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

    # RESEAU : invariant DevSecOps -> aucune sortie brute. La sortie passe par un proxy
    # d'egress qui n'autorise que la liste blanche de domaines (cf. executeur_reseau).
    if cap.reseau:
        from executeur_reseau import executer_avec_reseau
        return executer_avec_reseau(code, cap.domaines_autorises, timeout=timeout,
                                    cap=cap, volume_nom=volume_nom)

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


def executer_avec_entree(code: str, donnees: dict, timeout: int = 25,
                         cap: Capacites | None = None, volume_nom: str | None = None) -> dict:
    """
    Execute un PRODUIT PROMU sur de VRAIES donnees : injecte `donnees` (JSON via env),
    appelle executer(donnees) dans le bac a sable (memes invariants/capacites), et renvoie
    {"ok": bool, "resultat"|"erreur": ...}. Le code du produit n'est pas modifie : on lui
    ajoute un runner qui lit l'entree et imprime le resultat apres un marqueur.
    """
    cap = cap or Capacites()
    wrapped = code + _RUNNER
    entree_json = json.dumps(donnees, ensure_ascii=False)

    if cap.reseau:
        from executeur_reseau import executer_avec_reseau
        rc, out, err, _ = executer_avec_reseau(wrapped, cap.domaines_autorises, timeout=timeout,
                                               cap=cap, volume_nom=volume_nom,
                                               env_extra={"VIVARIUM_INPUT": entree_json})
        return _extraire_resultat(rc, out, err)

    cmd = ["docker", "run", "-i"] + FLAGS_INVARIANTS + ["--network", "none"]
    if cap.persistance:
        if not volume_nom:
            return {"ok": False, "erreur": "persistance accordee mais aucun volume fourni"}
        _preparer_volume(volume_nom, cap.chemin_persistance)
        cmd += ["-v", f"{volume_nom}:{cap.chemin_persistance}:rw"]
    cmd += ["-e", "PYTHONIOENCODING=utf-8", "-e", f"VIVARIUM_INPUT={entree_json}", IMAGE, "python", "-"]
    try:
        r = subprocess.run(cmd, input=wrapped, capture_output=True, text=True, timeout=timeout)
        return _extraire_resultat(r.returncode, r.stdout, r.stderr)
    except subprocess.TimeoutExpired:
        return {"ok": False, "erreur": f"TIMEOUT apres {timeout}s"}


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