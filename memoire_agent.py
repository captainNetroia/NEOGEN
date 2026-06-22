"""
NEOGEN - Mémoire cross-session de l'agent.

L'agent se SOUVIENT d'une session à l'autre : qui est l'utilisateur, ses
préférences, ses projets, les faits importants. Chaque souvenir est une ligne
JSON persistée dans data/memoire.jsonl. Un résumé compact des souvenirs est
injecté dans le prompt système (l'agent se souvient automatiquement), et l'agent
peut en ajouter via l'outil 'memoriser' ou en rappeler via 'rappeler'.

Distinct de memoire_generationnelle.py (lignée des PRODUITS). Ici = mémoire de
l'AGENT sur l'utilisateur et le contexte.

Gouvernance : tout est sanitizé (jamais de secret en mémoire). Types : user,
preference, projet, fait.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-22.
"""

from __future__ import annotations

import json
import os
import time
import uuid

from sanitizer import nettoyer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEM_FILE = os.path.join(BASE_DIR, "data", "memoire.jsonl")

TYPES = ("user", "preference", "projet", "fait")
MAX_MEMOIRES = 200  # garde-fou : on ne garde que les N plus récentes


def _lire() -> list[dict]:
    if not os.path.exists(MEM_FILE):
        return []
    out = []
    try:
        with open(MEM_FILE, encoding="utf-8") as f:
            for ligne in f:
                ligne = ligne.strip()
                if ligne:
                    try:
                        out.append(json.loads(ligne))
                    except Exception:
                        continue
    except Exception:
        return []
    return out


def _ecrire(memoires: list[dict]) -> None:
    os.makedirs(os.path.dirname(MEM_FILE), exist_ok=True)
    memoires = memoires[-MAX_MEMOIRES:]
    with open(MEM_FILE, "w", encoding="utf-8") as f:
        for m in memoires:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")


def memoriser(contenu: str, type_: str = "fait") -> dict:
    """Enregistre un souvenir. Dédoublonne sur le contenu (évite les répétitions)."""
    contenu = nettoyer((contenu or "").strip())[:500]
    if not contenu:
        return {}
    type_ = type_ if type_ in TYPES else "fait"
    memoires = _lire()
    # Dédoublonnage simple : même contenu (insensible à la casse) -> on ne ré-ajoute pas.
    for m in memoires:
        if m.get("contenu", "").strip().lower() == contenu.lower():
            return m
    souvenir = {
        "id": str(uuid.uuid4())[:8],
        "contenu": contenu,
        "type": type_,
        "cree_le": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    memoires.append(souvenir)
    _ecrire(memoires)
    return souvenir


def rappeler(requete: str = "", limite: int = 8) -> list[dict]:
    """Rappelle les souvenirs pertinents. Sans requête : les plus récents.
    Avec requête : ceux qui partagent le plus de mots avec la requête."""
    memoires = _lire()
    if not requete.strip():
        return memoires[-limite:][::-1]
    mots = {w for w in requete.lower().split() if len(w) > 2}
    def score(m):
        txt = m.get("contenu", "").lower()
        return sum(1 for w in mots if w in txt)
    classes = sorted(memoires, key=score, reverse=True)
    return [m for m in classes if score(m) > 0][:limite]


def lister() -> list[dict]:
    return _lire()[::-1]


def supprimer(mem_id: str) -> bool:
    memoires = _lire()
    n = len(memoires)
    memoires = [m for m in memoires if m.get("id") != mem_id]
    if len(memoires) < n:
        _ecrire(memoires)
        return True
    return False


def resume_pour_prompt(limite: int = 10) -> str:
    """Résumé compact des souvenirs pour injection dans le prompt système."""
    memoires = _lire()
    if not memoires:
        return ""
    # Priorité : user + preference d'abord (qui est l'utilisateur), puis le reste récent.
    prioritaires = [m for m in memoires if m.get("type") in ("user", "preference")]
    autres = [m for m in memoires if m.get("type") not in ("user", "preference")][-limite:]
    choisis = (prioritaires + autres)[-limite:]
    lignes = [f"  - [{m.get('type','fait')}] {m.get('contenu','')}" for m in choisis]
    return ("\nCE QUE TU SAIS DEJA (memoire des sessions precedentes) :\n"
            + "\n".join(lignes)
            + "\nUtilise ces souvenirs pour personnaliser tes reponses. "
              "Memorise tout fait durable nouveau via l'outil 'memoriser'.")


if __name__ == "__main__":
    print("=" * 60)
    print("NEOGEN - MEMOIRE AGENT : auto-vérification")
    print("=" * 60)
    # Nettoyage d'un éventuel résidu de test
    for m in lister():
        if m.get("contenu", "").startswith("__test__"):
            supprimer(m["id"])
    s = memoriser("__test__ Jordan préfère le français et pas de tirets cadratins", "preference")
    assert s["type"] == "preference"
    assert memoriser("__test__ Jordan préfère le français et pas de tirets cadratins", "preference")["id"] == s["id"], "dédoublonnage KO"
    assert any("__test__" in m["contenu"] for m in lister())
    assert rappeler("français préférence"), "rappel par mots KO"
    assert "__test__" in resume_pour_prompt()
    assert supprimer(s["id"])
    print("  memoriser / dedoublonnage / rappeler / resume / supprimer : OK")
    print("=" * 60)
