"""
NEOGEN - Environnement : source de verite unique du CONTEXTE de deploiement.

"Tout doit fonctionner en fonction de l'environnement." Une instance NEOGEN
tourne soit en LOCAL (machine d'un utilisateur), soit en SERVEUR (VPS/web public).
Le comportement reseau (contribution au reseau d'intelligence, telemetrie) doit
s'adapter : en local, securite d'abord (opt-in explicite, anonymisation stricte) ;
en serveur, le noeud participe pleinement mais reste anonymise.

Detection (par ordre de priorite) :
  1. NEOGEN_ENV = "local" | "serveur"            (explicite, gagne toujours)
  2. NEOGEN_BASE_URL pointant vers un domaine public (pas localhost) -> serveur
  3. defaut -> local (le plus sur : rien ne part sans consentement)

Politique par environnement (consommee par reseau_savoir + telemetrie) :
  - local   : contribution = "consent" (jamais sans opt-in), anonymisation stricte
  - serveur : contribution = "auto"    (le noeud partage), anonymisation standard
  Opt-out global, tout environnement : NEOGEN_CONTRIBUTION = "off".

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-25.
"""
from __future__ import annotations

import os

_LOCAL = "local"
_SERVEUR = "serveur"


def _url_publique(url: str) -> bool:
    """Vrai si l'URL designe un hote public (pas localhost / 127.* / .local)."""
    u = (url or "").strip().lower()
    if not u:
        return False
    for marqueur in ("localhost", "127.0.0.1", "0.0.0.0", "::1", ".local", "host.docker.internal"):
        if marqueur in u:
            return False
    return u.startswith("http://") or u.startswith("https://")


def contexte() -> str:
    """Renvoie 'local' ou 'serveur'. Detection explicite puis heuristique."""
    explicite = os.environ.get("NEOGEN_ENV", "").strip().lower()
    if explicite in (_LOCAL, _SERVEUR):
        return explicite
    if _url_publique(os.environ.get("NEOGEN_BASE_URL", "")):
        return _SERVEUR
    return _LOCAL


def est_serveur() -> bool:
    return contexte() == _SERVEUR


def est_local() -> bool:
    return contexte() == _LOCAL


def politique() -> dict:
    """Politique reseau effective pour cet environnement.

    contribution : "auto" | "consent" | "off"
      - auto    : l'instance partage ses skills a haute valeur (anonymises).
      - consent : ne partage QUE si l'utilisateur a opte pour le niveau "tout".
      - off     : aucune contribution montante (opt-out global).
    anonymisation : "stricte" | "standard"
    consentement_requis : un consentement est TOUJOURS requis cote telemetrie ;
      ce drapeau dit si, en plus, la politique d'env exige l'opt-in explicite.
    """
    ctx = contexte()
    opt_out = os.environ.get("NEOGEN_CONTRIBUTION", "").strip().lower() == "off"

    if ctx == _SERVEUR:
        contribution = "off" if opt_out else "auto"
        return {
            "contexte": _SERVEUR,
            "contribution": contribution,
            "anonymisation": "standard",
            "consentement_requis": True,
        }
    # local : securite d'abord
    contribution = "off" if opt_out else "consent"
    return {
        "contexte": _LOCAL,
        "contribution": contribution,
        "anonymisation": "stricte",
        "consentement_requis": True,
    }


def resume() -> dict:
    """Vue lisible pour /health, le dashboard ou le debug."""
    p = politique()
    return {
        "contexte": p["contexte"],
        "contribution": p["contribution"],
        "anonymisation": p["anonymisation"],
        "base_url": os.environ.get("NEOGEN_BASE_URL", "") or "(non defini)",
    }


if __name__ == "__main__":
    print("=" * 64)
    print("NEOGEN - ENVIRONNEMENT : auto-verification")
    print("=" * 64)

    # defaut = local, securite d'abord
    for k in ("NEOGEN_ENV", "NEOGEN_BASE_URL", "NEOGEN_CONTRIBUTION"):
        os.environ.pop(k, None)
    assert contexte() == _LOCAL, contexte()
    assert politique()["contribution"] == "consent"

    # URL publique -> serveur auto
    os.environ["NEOGEN_BASE_URL"] = "https://neogen.netroia.tech"
    assert contexte() == _SERVEUR, contexte()
    assert politique()["contribution"] == "auto"

    # localhost -> reste local
    os.environ["NEOGEN_BASE_URL"] = "http://localhost:8000"
    assert contexte() == _LOCAL, contexte()

    # explicite gagne
    os.environ["NEOGEN_ENV"] = "serveur"
    assert contexte() == _SERVEUR

    # opt-out global coupe tout
    os.environ["NEOGEN_CONTRIBUTION"] = "off"
    assert politique()["contribution"] == "off"

    for k in ("NEOGEN_ENV", "NEOGEN_BASE_URL", "NEOGEN_CONTRIBUTION"):
        os.environ.pop(k, None)
    print("  detection local/serveur + politique + opt-out : OK")
    print("=" * 64)
    print("  TOUT VERT.")
    print("=" * 64)
