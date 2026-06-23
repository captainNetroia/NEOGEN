"""
NEOGEN - Compétences (skills) : socle inné + cristallisation automatique.

Inspiré de skill-creator (Anthropic), mais au standard NEOGEN :

  - SOCLE TOUJOURS ACTIF : des compétences fondamentales (savoir-faire inné) sont
    TOUJOURS injectées dans le prompt de chaque agent, dès le 1er message, sans
    attendre qu'elles soient "apprises". Elles enseignent les bons réflexes à TOUS
    les modèles (utile surtout aux petits modèles locaux).
  - CRISTALLISATION AUTOMATIQUE PAR CONTEXTE : quand l'agent accomplit une tâche
    utile et reproductible (une trajectoire d'outils qui a réussi), la compétence
    se fige TOUTE SEULE — selon le CONTEXTE réel (ce qui s'est passé), pas une
    simple heuristique de complexité. Idempotent : même trajectoire = pas de doublon.
  - USAGE TRACÉ : chaque invocation incrémente un compteur -> pertinence + signal
    pour l'auto-amélioration (un skill jamais utilisé / souvent utile se voit).

Une compétence = des DONNÉES (pas du code exécuté) : nom, description, instructions,
outils mobilisés. Tout est sanitizé ; seuls des outils existants sont référençables.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-23.
"""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata

from sanitizer import nettoyer

try:
    import robustesse as rob
except Exception:
    rob = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(BASE_DIR, "data", "skills")

_SLUG = re.compile(r"[^a-z0-9_]+")


# ── SOCLE : compétences innées, toujours injectées ─────────────────────────────
# Ce sont les bons réflexes de NEOGEN. Toujours présentes, jamais supprimables via l'UI.
SOCLE: list[dict] = [
    {
        "nom": "discernement_avant_creation",
        "titre": "Discerner avant de créer",
        "description": "Toujours cadrer une intention (valeur/faisabilité/clarté) avant de fabriquer.",
        "instructions": ("Avant de lancer creer_application, utilise 'discerner' pour évaluer valeur, "
                         "faisabilité et clarté. Si l'intention est floue, reformule-la avec l'utilisateur "
                         "avant de produire. Ne fabrique jamais à l'aveugle."),
        "outils": ["discerner", "creer_application"],
    },
    {
        "nom": "voir_avant_agir",
        "titre": "Regarder l'écran avant d'agir",
        "description": "Avant tout clic ou saisie, regarder réellement l'écran pour connaître les coordonnées.",
        "instructions": ("Avant de cliquer ou de remplir un champ via controler_ecran, appelle d'abord "
                         "'regarder_ecran' avec un objectif clair : tu obtiens la position réelle des "
                         "éléments au lieu de deviner. N'invente jamais une coordonnée ni une URL."),
        "outils": ["regarder_ecran", "controler_ecran", "ouvrir_url"],
    },
    {
        "nom": "memoire_continue",
        "titre": "Se souvenir d'une session à l'autre",
        "description": "Mémoriser les faits durables sur l'utilisateur ; rappeler avant de répondre.",
        "instructions": ("Quand l'utilisateur révèle un fait durable (préférence, projet, identité), "
                         "appelle 'memoriser'. Avant une réponse qui dépend de son contexte, appelle "
                         "'rappeler' pour réutiliser ce que tu sais déjà. La continuité fait la qualité."),
        "outils": ["memoriser", "rappeler"],
    },
    {
        "nom": "reutiliser_avant_refaire",
        "titre": "Réutiliser une compétence avant de tout refaire",
        "description": "Vérifier les compétences existantes avant d'improviser une procédure.",
        "instructions": ("Avant d'accomplir une tâche qui pourrait déjà être connue, appelle "
                         "'lister_skills' ; si une compétence correspond, applique-la via 'utiliser_skill'. "
                         "On ne réinvente pas ce qu'on sait déjà faire."),
        "outils": ["lister_skills", "utiliser_skill"],
    },
]
_SOCLE_NOMS = {s["nom"] for s in SOCLE}


def _slug(nom: str) -> str:
    """Nom de fichier sûr : minuscules, underscores, alphanumérique (accents retirés)."""
    base = unicodedata.normalize("NFKD", (nom or "")).encode("ascii", "ignore").decode()
    s = _SLUG.sub("_", base.strip().lower()).strip("_")
    return s[:48] or "skill"


def creer(nom: str, description: str, instructions: str,
          outils: list[str] | None = None, auto: bool = False,
          socle: bool = False, signature: str = "") -> dict:
    """Crée/écrase une compétence. Renvoie la compétence enregistrée."""
    os.makedirs(SKILLS_DIR, exist_ok=True)
    slug = _slug(nom)
    existant = charger(slug) or {}
    skill = {
        "nom": slug,
        "titre": nettoyer((nom or slug).strip())[:80],
        "description": nettoyer((description or "").strip())[:300],
        "instructions": nettoyer((instructions or "").strip())[:4000],
        "outils": [str(o).strip() for o in (outils or []) if str(o).strip()],
        "auto": bool(auto),
        "socle": bool(socle),
        "signature": signature[:120],
        "usages": int(existant.get("usages", 0)),
        "cree_le": existant.get("cree_le") or time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(SKILLS_DIR, f"{slug}.json"), "w", encoding="utf-8") as f:
        json.dump(skill, f, ensure_ascii=False, indent=2)
    return skill


def assurer_socle() -> int:
    """Matérialise les compétences du socle si absentes/obsolètes. Idempotent.
    Renvoie le nombre de compétences socle (re)posées. Le slug = le 'nom' canonique."""
    os.makedirs(SKILLS_DIR, exist_ok=True)
    n = 0
    for s in SOCLE:
        existant = charger(s["nom"])
        instructions_attendues = nettoyer(s["instructions"].strip())[:4000]
        if existant and existant.get("socle") and existant.get("instructions") == instructions_attendues:
            continue  # déjà à jour
        skill = {
            "nom": s["nom"],
            "titre": nettoyer(s["titre"])[:80],
            "description": nettoyer(s["description"])[:300],
            "instructions": instructions_attendues,
            "outils": list(s["outils"]),
            "auto": False, "socle": True, "signature": s["nom"],
            "usages": int((existant or {}).get("usages", 0)),
            "cree_le": (existant or {}).get("cree_le") or time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(os.path.join(SKILLS_DIR, f"{s['nom']}.json"), "w", encoding="utf-8") as f:
            json.dump(skill, f, ensure_ascii=False, indent=2)
        n += 1
    return n


def lister(inclure_socle: bool = True) -> list[dict]:
    """Compétences (socle d'abord, puis apprises par usage/récence décroissante)."""
    assurer_socle()
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
    if not inclure_socle:
        out = [s for s in out if not s.get("socle")]
    # Tri : socle d'abord, puis par usages puis récence.
    out.sort(key=lambda s: (not s.get("socle"), -int(s.get("usages", 0)), s.get("cree_le", "")),
             reverse=False)
    return out


def charger(nom: str) -> dict | None:
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
    """Supprime une compétence APPRISE. Le socle est protégé (non supprimable)."""
    slug = _slug(nom)
    if slug in _SOCLE_NOMS:
        return False
    p = os.path.join(SKILLS_DIR, f"{slug}.json")
    if os.path.exists(p):
        os.remove(p)
        return True
    return False


def enregistrer_usage(nom: str) -> None:
    """Incrémente le compteur d'usage d'une compétence (pertinence + auto-amélioration)."""
    s = charger(nom)
    if not s:
        return
    s["usages"] = int(s.get("usages", 0)) + 1
    s["dernier_usage"] = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(os.path.join(SKILLS_DIR, f"{_slug(nom)}.json"), "w", encoding="utf-8") as f:
            json.dump(s, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def cristalliser_auto(nom: str, description: str, instructions: str,
                      outils: list[str] | None = None, signature: str = "") -> dict | None:
    """Cristallise une compétence AUTOMATIQUEMENT, de façon IDEMPOTENTE.
    Si une compétence de même signature (ou même slug) existe déjà -> ne recrée pas.
    Renvoie la compétence créée, ou None si déjà connue (pas de doublon)."""
    sig = (signature or _slug(nom))[:120]
    # Idempotence : déjà cristallisé pour cette signature ?
    for s in lister(inclure_socle=False):
        if s.get("signature") == sig or s.get("nom") == _slug(nom):
            return None
    if rob is not None:
        cle = f"skill_auto:{sig}"
        if rob.deja_fait(cle):
            return None
        rob.marquer_fait(cle)
    s = creer(nom, description, instructions, outils, auto=True, signature=sig)
    if rob is not None:
        rob.journaliser(f"competence cristallisee automatiquement : {s['nom']}", "succes",
                        source="competences")
    return s


def resume_pour_prompt(limite: int = 12) -> str:
    """Liste compacte pour le prompt système. Socle TOUJOURS inclus + meilleures apprises."""
    skills = lister()
    if not skills:
        return ""
    socle = [s for s in skills if s.get("socle")]
    apprises = [s for s in skills if not s.get("socle")][: max(0, limite - len(socle))]
    lignes = []
    if socle:
        lignes.append("  [socle - réflexes toujours actifs]")
        lignes += [f"    - {s['nom']} : {s.get('description','')}" for s in socle]
    if apprises:
        lignes.append("  [apprises]")
        lignes += [f"    - {s['nom']} : {s.get('description','')}" for s in apprises]
    return ("\nCOMPETENCES (invoque-les via utiliser_skill {\"nom\": \"...\"}) :\n"
            + "\n".join(lignes))


if __name__ == "__main__":
    import tempfile
    print("=" * 60)
    print("NEOGEN - COMPETENCES (socle + cristallisation auto) : auto-vérification")
    print("=" * 60)
    # Isolation : dossier skills temporaire + idempotence robustesse temporaire
    # (le test ne doit JAMAIS polluer les vraies données — doctrine).
    SKILLS_DIR = os.path.join(tempfile.mkdtemp(), "skills")
    if rob is not None:
        rob._DATA = tempfile.mkdtemp()
        rob.IDEMPOTENCE = os.path.join(rob._DATA, "i.json")
        rob.JOURNAL = os.path.join(rob._DATA, "j.jsonl")
    # Socle : posé et toujours présent
    n = assurer_socle()
    skills = lister()
    assert all(any(s["nom"] == b["nom"] for s in skills) for b in SOCLE), "socle manquant"
    assert "discernement_avant_creation" in resume_pour_prompt()
    # Socle non supprimable
    assert supprimer("discernement_avant_creation") is False, "le socle ne doit pas être supprimable"
    print(f"  socle : {len(SOCLE)} competences toujours actives + protegees OK")

    # Création + usage
    s = creer("Résumer un PDF", "Résume un document en 5 points clés",
              "1. Lis. 2. Extrais. 3. Donne 5 points.", outils=["conseiller"])
    assert s["nom"] == "resumer_un_pdf"
    enregistrer_usage("resumer_un_pdf")
    assert charger("resumer_un_pdf")["usages"] == 1
    print("  creer / usage incremente OK")

    # Cristallisation auto idempotente
    a1 = cristalliser_auto("creer convertisseur", "Refaire un convertisseur",
                           "utilise creer_application", ["creer_application"], signature="sig_test_conv")
    a2 = cristalliser_auto("creer convertisseur", "Refaire un convertisseur",
                           "utilise creer_application", ["creer_application"], signature="sig_test_conv")
    assert a1 is not None and a2 is None, "doublon non bloqué"
    print("  cristallisation auto idempotente (pas de doublon) OK")

    # Nettoyage des skills de test
    supprimer("resumer_un_pdf")
    supprimer("creer_convertisseur")
    print("=" * 60)
    print("  TOUT VERT.")
    print("=" * 60)
