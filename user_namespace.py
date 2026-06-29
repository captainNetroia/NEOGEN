"""
Routage des chemins de données par utilisateur — le « sac » de chaque joueur.

Principe (validé Jordan 2026-06-29, « monde commun ») :
  - Le PROPRIÉTAIRE (instance locale NEOGEN_OWNER_UNLIMITED, ou email = NEOGEN_OWNER_EMAIL
    sur le web) travaille dans data/ — l'application MAÎTRE, inchangée, zéro régression.
  - Chaque utilisateur WEB possède son sac : data/users/{user_id}/ où vivent SES artefacts
    (cellules forgées, agents, règles, CSS, produits). Il agit sur l'appli de façon
    individuelle sans jamais toucher data/ (le monde primordial partagé : Pensée,
    conscience, réseau de savoir, noyau).

Ce module ne fait QUE router des chemins. Il ne lit/écrit jamais de données métier.
Jamais d'exception levée vers l'appelant : en cas de doute, on retombe sur data/ (base).
"""
from __future__ import annotations
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(BASE, "data")
_USERS_ROOT = os.path.join(_DATA, "users")

# Caractères autorisés dans un id de sac sur disque (anti-traversal).
_ID_SAFE = re.compile(r"[^a-zA-Z0-9_-]")


def _owner_unlimited() -> bool:
    """Instance privée du propriétaire : tout passe par data/ (miroir de quotas)."""
    return os.environ.get("NEOGEN_OWNER_UNLIMITED", "").strip().lower() in ("1", "true", "yes", "on")


def est_owner(user: dict | None) -> bool:
    """True si l'appelant est le propriétaire (instance locale OU email maître).
    Le propriétaire travaille toujours dans data/ (l'appli maître = la vérité)."""
    if _owner_unlimited():
        return True
    owner = os.environ.get("NEOGEN_OWNER_EMAIL", "").strip().lower()
    if owner and user and (user.get("email", "").strip().lower() == owner):
        return True
    return False


def _sac_id(user: dict | None) -> str | None:
    """Identifiant de sac sûr pour le disque, ou None si pas de sac (= base data/)."""
    if not user:
        return None
    if est_owner(user):
        return None  # le maître n'a pas de sac : il EST data/
    uid = str(user.get("id") or "").strip()
    if not uid:
        return None
    uid = _ID_SAFE.sub("", uid)[:64]
    return uid or None


def data_dir(user: dict | None) -> str:
    """Répertoire de données effectif pour cet utilisateur.
    Propriétaire / inconnu → data/ (base). Utilisateur web → data/users/{id}/."""
    sac = _sac_id(user)
    if sac is None:
        return _DATA
    chemin = os.path.join(_USERS_ROOT, sac)
    try:
        os.makedirs(chemin, exist_ok=True)
    except Exception:
        return _DATA  # garde absolu : jamais bloquer, retomber sur la base
    return chemin


def data_path(user: dict | None, *parties: str) -> str:
    """Chemin complet vers un fichier du sac de l'utilisateur (ou de la base)."""
    return os.path.join(data_dir(user), *parties)


def a_un_sac(user: dict | None) -> bool:
    """True si cet utilisateur a un sac séparé (= utilisateur web non-propriétaire)."""
    return _sac_id(user) is not None


def sac_id(user: dict | None) -> str | None:
    """Identifiant public du sac (pour le marquage scope user:{id}), ou None pour le maître."""
    return _sac_id(user)


if __name__ == "__main__":
    # Self-test offline (aucune dépendance réseau / autre module).
    os.environ["NEOGEN_OWNER_UNLIMITED"] = "0"
    os.environ["NEOGEN_OWNER_EMAIL"] = "admin@example.com"

    # Maître par email → data/ (pas de sac)
    maitre = {"id": "u_owner", "email": "admin@example.com"}
    assert not a_un_sac(maitre), "le maître ne doit pas avoir de sac"
    assert data_dir(maitre) == _DATA, "le maître doit pointer sur data/"

    # Utilisateur web → sac séparé
    alice = {"id": "u_alice123", "email": "alice@example.com"}
    assert a_un_sac(alice), "un user web doit avoir un sac"
    d = data_dir(alice)
    assert d.endswith(os.path.join("users", "u_alice123")), f"sac inattendu : {d}"
    assert data_path(alice, "cellules_forgees.json").endswith("cellules_forgees.json")

    # Anti-traversal : id malicieux nettoyé
    pirate = {"id": "../../etc/passwd", "email": "x@x.com"}
    d2 = data_dir(pirate)
    assert ".." not in os.path.relpath(d2, _USERS_ROOT), f"traversal non bloqué : {d2}"

    # Anonyme → base data/
    assert data_dir(None) == _DATA, "anonyme doit retomber sur data/"

    # Instance owner-unlimited → tout sur data/
    os.environ["NEOGEN_OWNER_UNLIMITED"] = "1"
    assert data_dir(alice) == _DATA, "owner-unlimited : tout sur data/ (local Jordan)"

    print("user_namespace : self-test OK")
