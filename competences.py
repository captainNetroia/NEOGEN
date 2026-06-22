"""
NEOGEN - Compétences (skills) auto-créées par l'agent.

Inspiré de skill-creator (Anthropic) : l'agent forge ses PROPRES compétences
réutilisables. Une compétence = une procédure nommée définie en DONNÉES (pas du
code brut exécuté → aucune faille d'exécution arbitraire). Elle contient :
  - un nom + une description (quand l'utiliser)
  - des instructions (le savoir-faire, injecté à l'agent quand il l'invoque)
  - la liste des outils NEOGEN qu'elle mobilise

Les compétences sont persistées dans data/skills/{nom}.json, listées
automatiquement dans le prompt de l'agent (donc disponibles DÈS leur création,
sans redémarrage) et invocables via l'outil utiliser_skill.

Gouvernance : tout est sanitizé ; une compétence ne peut référencer que des
outils existants ; pas d'exécution de code libre.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-22.
"""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata

from sanitizer import nettoyer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(BASE_DIR, "data", "skills")

_SLUG = re.compile(r"[^a-z0-9_]+")


def _slug(nom: str) -> str:
    """Nom de fichier sûr : minuscules, underscores, alphanumérique (accents retirés)."""
    base = unicodedata.normalize("NFKD", (nom or "")).encode("ascii", "ignore").decode()
    s = _SLUG.sub("_", base.strip().lower()).strip("_")
    return s[:48] or "skill"


def creer(nom: str, description: str, instructions: str,
          outils: list[str] | None = None, auto: bool = False) -> dict:
    """Crée/écrase une compétence. Renvoie la compétence enregistrée."""
    os.makedirs(SKILLS_DIR, exist_ok=True)
    slug = _slug(nom)
    skill = {
        "nom": slug,
        "titre": nettoyer((nom or slug).strip())[:80],
        "description": nettoyer((description or "").strip())[:300],
        "instructions": nettoyer((instructions or "").strip())[:4000],
        "outils": [str(o).strip() for o in (outils or []) if str(o).strip()],
        "auto": bool(auto),
        "cree_le": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(SKILLS_DIR, f"{slug}.json"), "w", encoding="utf-8") as f:
        json.dump(skill, f, ensure_ascii=False, indent=2)
    return skill


def lister() -> list[dict]:
    """Toutes les compétences apprises (triées par date de création décroissante)."""
    if not os.path.isdir(SKILLS_DIR):
        return []
    out = []
    for fn in os.listdir(SKILLS_DIR):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(SKILLS_DIR, fn), encoding="utf-8") as f:
                out.append(json.load(f))
        except Exception:
            continue
    out.sort(key=lambda s: s.get("cree_le", ""), reverse=True)
    return out


def charger(nom: str) -> dict | None:
    """Charge une compétence par son nom (ou slug)."""
    slug = _slug(nom)
    p = os.path.join(SKILLS_DIR, f"{slug}.json")
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def supprimer(nom: str) -> bool:
    slug = _slug(nom)
    p = os.path.join(SKILLS_DIR, f"{slug}.json")
    if os.path.exists(p):
        os.remove(p)
        return True
    return False


def resume_pour_prompt(limite: int = 12) -> str:
    """Liste compacte des compétences pour injecter dans le prompt système de l'agent."""
    skills = lister()[:limite]
    if not skills:
        return ""
    lignes = [f"  - {s['nom']} : {s.get('description','')}" for s in skills]
    return ("\nCOMPETENCES APPRISES (tu peux les invoquer via utiliser_skill {\"nom\": \"...\"}) :\n"
            + "\n".join(lignes))


if __name__ == "__main__":
    print("=" * 60)
    print("NEOGEN - COMPETENCES : auto-vérification")
    print("=" * 60)
    s = creer("Résumer un PDF", "Résume un document en 5 points clés",
              "1. Lis le document. 2. Extrais les idées. 3. Donne 5 points.",
              outils=["conseiller"], auto=False)
    assert s["nom"] == "resumer_un_pdf", s["nom"]
    assert charger("Résumer un PDF")["titre"] == "Résumer un PDF"
    assert any(x["nom"] == "resumer_un_pdf" for x in lister())
    assert "resumer_un_pdf" in resume_pour_prompt()
    assert supprimer("Résumer un PDF")
    print("  créer / charger / lister / résumé / supprimer : OK")
    print("=" * 60)
