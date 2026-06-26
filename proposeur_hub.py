"""
NEOGEN - Proposeur Hub : génère des propositions d'évolution depuis les grains scorés.

Proposition = action suggérée par le système, Jordan approuve ou refuse.
Types :
  lecon_recurrente  -> erreur vue ≥2 fois -> cristalliser un skill
  pattern_critique  -> signal d'amélioration fort -> intégrer au pipeline
  skill_inutilise   -> skill jamais utilisé -> proposer mise à jour ou archivage
  evolution_skill   -> version améliorée suggérée depuis les leçons accumulées

Jordan approuve : action exécutée (skill créé / mis à jour).
Jordan refuse   : statut=refuse, jamais reproposé.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-25.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

import re

import evaluateur
from savoir import charger_index, charger_propositions, _persister_proposition, _maj_proposition, _lire_jsonl, _DATA

BASE = os.path.dirname(os.path.abspath(__file__))


def _type_erreur(txt: str) -> str:
    """Extrait le type d'exception ('ZeroDivisionError: ...' -> 'ZeroDivisionError')."""
    m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*Error|[A-Za-z_][A-Za-z0-9_]*Exception)", txt or "")
    return m.group(1) if m else ((txt or "").split(":")[0].strip()[:40] or "erreur")


def _prop_id(type_: str, cle: str) -> str:
    return hashlib.sha256(f"{type_}:{cle}".encode()).hexdigest()[:12]


def _prop_existe(prop_id: str) -> bool:
    return any(p.get("id") == prop_id for p in charger_propositions())


# ── Génération heuristique (sans LLM — règles métier) ─────────────────────────

def generer() -> list[dict]:
    """Analyse l'index et génère les propositions manquantes. Idempotent."""
    index = charger_index()
    tous = list(index.values())
    nouvelles: list[dict] = []

    # 1. Leçons récurrentes : erreurs du MÊME TYPE vues ≥2 fois -> nouveau skill.
    #    On compte sur le journal BRUT (les grains identiques sont dédupliqués par hash,
    #    donc compter les grains sous-estimerait la récurrence).
    erreurs_brutes = _lire_jsonl(os.path.join(_DATA, "journal_erreurs.jsonl"))
    par_type: dict[str, list[dict]] = {}
    for e in erreurs_brutes:
        par_type.setdefault(_type_erreur(e.get("erreur", "")), []).append(e)

    for typ, lst in par_type.items():
        if len(lst) < 2:
            continue
        pid = _prop_id("lecon_recurrente", typ)
        if _prop_existe(pid):
            continue
        # La meilleure entrée = celle qui a un diagnostic complet (leçon + correction)
        avec_diag = [e for e in lst if isinstance(e.get("diagnostic"), dict) and e["diagnostic"].get("lecon")]
        meilleur = avec_diag[-1] if avec_diag else lst[-1]
        diag = meilleur.get("diagnostic", {}) if isinstance(meilleur.get("diagnostic"), dict) else {}
        lecon = diag.get("lecon", "") or meilleur.get("erreur", "")
        correction = diag.get("correction", "") or lecon
        prop = {
            "id": pid,
            "type": "lecon_recurrente",
            "titre": f"Cristalliser la leçon : {typ}",
            "justification": (
                f"L'erreur '{typ}' a été observée {len(lst)} fois dans journal_erreurs.jsonl. "
                f"Cristalliser une compétence éviterait sa récurrence automatiquement."
            ),
            "grain_ids": [],
            "impact_estime": f"Prévient ~{len(lst)} erreurs futures similaires",
            "ts": time.time(),
            "statut": "en_attente",
            "skill_actuel": None,
            "skill_propose": {
                "nom": "eviter_" + typ[:24].lower().replace(" ", "_").replace(".", "_"),
                "titre": f"Éviter : {typ}",
                "description": lecon[:200],
                "instructions": correction[:400],
                "outils": [],
            },
        }
        _persister_proposition(prop)
        nouvelles.append(prop)

    # 2. Patterns d'amélioration à score élevé -> intégrer
    ameliorations = [
        g for g in tous
        if g.get("domaine") == "amelioration"
        and float(g.get("score", 0)) >= evaluateur.SEUIL_INTEGRATION
    ]
    for g in ameliorations[:3]:
        pid = _prop_id("pattern_critique", g["id"])
        if _prop_existe(pid):
            continue
        prop = {
            "id": pid,
            "type": "pattern_critique",
            "titre": f"Pattern critique : {g.get('contenu', '')[:60]}",
            "justification": (
                f"Score {g.get('score', 0):.2f} — au-dessus du seuil d'intégration. "
                f"Ce pattern récurrent mérite d'être intégré au pipeline de production."
            ),
            "grain_ids": [g["id"]],
            "impact_estime": "Améliore la robustesse du pipeline",
            "ts": time.time(),
            "statut": "en_attente",
            "skill_actuel": None,
            "skill_propose": None,
        }
        _persister_proposition(prop)
        nouvelles.append(prop)

    # 3. Skills jamais utilisés (usages=0, non-socle, créés il y a >7j) -> archivage ?
    skills_inutilises = [
        g for g in tous
        if g.get("domaine") == "skill"
        and int(g.get("usages", 0)) == 0
        and not g.get("meta", {}).get("socle", False)
        and (time.time() - float(g.get("ts", time.time()))) > 7 * 86400
    ]
    for g in skills_inutilises[:2]:
        nom = g.get("meta", {}).get("nom", g["id"])
        pid = _prop_id("skill_inutilise", nom)
        if _prop_existe(pid):
            continue
        prop = {
            "id": pid,
            "type": "skill_inutilise",
            "titre": f"Skill jamais utilisé : {nom}",
            "justification": (
                f"Ce skill existe depuis plus de 7 jours et n'a jamais été invoqué. "
                f"Envisager une mise à jour de sa description ou un archivage."
            ),
            "grain_ids": [g["id"]],
            "impact_estime": "Réduit le bruit dans la bibliothèque de compétences",
            "ts": time.time(),
            "statut": "en_attente",
            "skill_actuel": {"nom": nom, "titre": g.get("meta", {}).get("titre", nom)},
            "skill_propose": None,
        }
        _persister_proposition(prop)
        nouvelles.append(prop)

    return nouvelles


# ── Pensee (intelligence collective) -> proposition ─────────────────────────────

def proposer_depuis_pensee(pensee: dict) -> dict:
    """Une pensee a haut score devient une proposition d'evolution (flux existant).
    C'est la retro-action « la boucle nourrit le systeme » : la pensee remonte dans
    le meme onglet ou Jordan approuve/refuse. Idempotente via _prop_id('pensee', id)."""
    pid_src = pensee.get("id") or _prop_id("pensee_src", pensee.get("titre", ""))
    pid = _prop_id("pensee", pid_src)
    if _prop_existe(pid):
        return {"ok": True, "id": pid, "deja": True}
    titre = (pensee.get("titre") or "Pensee").strip()[:80]
    synthese = (pensee.get("synthese") or "").strip()
    score = float(pensee.get("score", 0.0))
    prop = {
        "id": pid,
        "type": "pensee_creative",
        "titre": f"Pensee a explorer : {titre}",
        "justification": (
            f"Pensee autonome (ambiance {pensee.get('ambiance', '?')}, "
            f"type {pensee.get('type', '?')}) de score {score:.2f}. {synthese}"
        ),
        "grain_ids": [],
        "impact_estime": "Piste creative issue de l'intelligence collective de NEOGEN.",
        "ts": time.time(),
        "statut": "en_attente",
        "skill_actuel": None,
        "skill_propose": None,
        "pensee_id": pensee.get("id", ""),
        "pensee_synthese": synthese[:400],
    }
    _persister_proposition(prop)
    return {"ok": True, "id": pid, "deja": False}


# ── Evolution gouvernee -> proposition (le levier que la Pensee actionne) ────────

def proposer_depuis_evolution(changement: dict) -> dict:
    """Un changement autorise par le noyau devient une proposition d'evolution SYSTEME.
    L'approbation = le consentement humain qui declenche l'application reelle. Idempotent."""
    cle = hashlib.sha256(json.dumps(changement, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    pid = _prop_id("evolution", cle)
    if _prop_existe(pid):
        return {"ok": True, "id": pid, "deja": True}
    type_ = changement.get("type", "?")
    portee = changement.get("portee", "?")
    titre = (changement.get("titre") or f"Evolution {type_}").strip()[:80]
    prop = {
        "id": pid,
        "type": "evolution_systeme",
        "titre": f"Evolution [{type_}] : {titre}",
        "justification": (
            f"{changement.get('raison', '') or 'Changement propose par le systeme.'} "
            f"(portee {portee}). Applique uniquement apres ton consentement ; "
            f"le noyau (ADN + murs) reste intouche."
        ),
        "grain_ids": [],
        "impact_estime": f"Modifie l'application ({type_}) de facon gouvernee et reversible.",
        "ts": time.time(),
        "statut": "en_attente",
        "skill_actuel": None,
        "skill_propose": None,
        "changement": changement,
        "portee_evo": portee,
    }
    _persister_proposition(prop)
    return {"ok": True, "id": pid, "deja": False}


# ── Actions d'approbation ──────────────────────────────────────────────────────

def approuver(prop_id: str) -> dict:
    """Jordan approuve -> exécuter l'action, marquer approuve."""
    props = charger_propositions()
    prop = next((p for p in props if p.get("id") == prop_id), None)
    if not prop:
        return {"ok": False, "erreur": "proposition introuvable"}
    if prop.get("statut") != "en_attente":
        return {"ok": False, "erreur": f"statut={prop.get('statut')}, pas en_attente"}

    resultat = _executer(prop)
    _maj_proposition(prop_id, {"statut": "approuve", "approuve_le": time.time(), "resultat": resultat})

    # Si la proposition vient d'un "Donner vie" -> marquer la pensee source comme vie_donnee.
    pensee_id = prop.get("changement", {}).get("payload", {}).get("_pensee_id") or \
                prop.get("pensee_id", "")
    if pensee_id:
        try:
            import pensee as _pensee_mod
            _pensee_mod.marquer_vie_donnee(pensee_id)
        except Exception:
            pass

    return {"ok": True, "prop_id": prop_id, "resultat": resultat,
            "pensee_id": pensee_id or None}


def refuser(prop_id: str) -> dict:
    """Jordan refuse -> marquer refuse, ne plus reproposer."""
    props = charger_propositions()
    prop = next((p for p in props if p.get("id") == prop_id), None)
    if not prop:
        return {"ok": False, "erreur": "proposition introuvable"}
    _maj_proposition(prop_id, {"statut": "refuse", "refuse_le": time.time()})
    return {"ok": True, "prop_id": prop_id}


def _executer(prop: dict) -> str:
    """Exécute l'action associée à une proposition approuvée."""
    type_ = prop.get("type")

    if type_ in ("lecon_recurrente", "pattern_critique") and prop.get("skill_propose"):
        try:
            import competences
            sk = prop["skill_propose"]
            competences.creer(
                nom=sk.get("nom", "skill_hub"),
                description=sk.get("description", ""),
                instructions=sk.get("instructions", ""),
                outils=sk.get("outils", []),
                auto=True,
            )
            return f"Skill '{sk.get('nom')}' cristallisé."
        except Exception as e:
            return f"Erreur création skill : {e}"

    if type_ == "skill_inutilise":
        # Pour l'instant : loguer — une suppression ne se fait jamais automatiquement
        return "Archivage manuel recommandé (suppression non automatique par sécurité)."

    if type_ == "evolution_systeme":
        # Consentement donne -> on actionne le levier d'auto-evolution (data-driven, garde
        # par le noyau a l'application). Reformat l'app sans jamais toucher au noyau.
        try:
            import evolution_gouvernee
            ch = prop.get("changement") or {}
            r = evolution_gouvernee.appliquer(ch, user=None)
            if r.get("ok"):
                return f"Evolution appliquee [{ch.get('type')}] : {r.get('detail', '')} (gen {r.get('generation')})."
            return f"Evolution refusee : {r.get('raison', 'inconnue')}."
        except Exception as e:
            return f"Evolution echouee : {e}"

    if type_ == "pensee_creative":
        # Approuver une pensée = la mémoriser -> elle redevient un grain du silo
        # mémoire -> re-nourrit le Hub du savoir (la boucle se referme).
        try:
            import memoire_agent
            txt = prop.get("pensee_synthese", "") or prop.get("titre", "")
            m = memoire_agent.memoriser(f"[Pensée retenue] {txt}", "fait")
            return f"Pensée mémorisée (souvenir {m.get('id', '?')}) — nourrit le savoir."
        except Exception as e:
            return f"Pensée notée (mémorisation échouée : {e})."

    return "Action notée, aucune opération automatique pour ce type."
