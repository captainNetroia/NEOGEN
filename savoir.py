"""
NEOGEN - Hub du savoir : unification des 5 silos en un moteur de connaissance extensible.

Architecture extensible : chaque silo = 1 adaptateur (domaine + lire_fn).
Un nouveau silo = register_silo(domaine, lire_fn). Le Hub ne change jamais.

Grain = unité atomique de savoir (texte + métadonnées + score).
Index  : data/savoir/index.json   (dict id -> grain, rechargé/rescorés à rafraichir)
Props  : data/savoir/propositions.jsonl  (log append-only, immuable)

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-25.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Callable

import vecteurs

BASE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(BASE, "data")
_SAVOIR_DIR = os.path.join(_DATA, "savoir")
_INDEX_PATH = os.path.join(_SAVOIR_DIR, "index.json")
_PROPS_PATH = os.path.join(_SAVOIR_DIR, "propositions.jsonl")

# ── Grain ──────────────────────────────────────────────────────────────────────

@dataclass
class Grain:
    id: str
    domaine: str    # "skill" | "memoire" | "erreur" | "amelioration" | "ledger" | "telemetrie"
    type: str       # "competence" | "lecon" | "fait" | "pattern" | "decision"
    contenu: str    # texte principal (indexé pour recherche sémantique)
    score: float    # 0.0–1.0 (calculé par evaluateur)
    ts: float       # timestamp de création/ingestion
    usages: int     # nb de fois retrouvé par chercher()
    meta: dict      # données source brutes (traçabilité)


def _grain_id(domaine: str, contenu: str) -> str:
    return hashlib.sha256(f"{domaine}:{contenu[:200]}".encode()).hexdigest()[:16]


def _to_ts(valeur) -> float:
    """Normalise un timestamp hétérogène en epoch float.
    Gère : float/int epoch, ISO ('2026-06-17T13:44:33[.micro]'),
    format espace ('2026-06-24 10:56:05'). Fallback : maintenant."""
    if valeur is None:
        return time.time()
    if isinstance(valeur, (int, float)):
        return float(valeur)
    s = str(valeur).strip()
    if not s:
        return time.time()
    # epoch en string ?
    try:
        return float(s)
    except ValueError:
        pass
    # formats date
    s = s.replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return time.mktime(time.strptime(s, fmt))
        except (ValueError, OverflowError):
            continue
    return time.time()


# ── Stockage ───────────────────────────────────────────────────────────────────

def _lire_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    try:
        with open(path, encoding="utf-8") as f:
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


def charger_index() -> dict[str, dict]:
    if not os.path.exists(_INDEX_PATH):
        return {}
    try:
        with open(_INDEX_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _sauver_index(index: dict[str, dict]):
    os.makedirs(_SAVOIR_DIR, exist_ok=True)
    with open(_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def charger_propositions(statut: str | None = None) -> list[dict]:
    props = _lire_jsonl(_PROPS_PATH)
    if statut:
        props = [p for p in props if p.get("statut") == statut]
    return sorted(props, key=lambda p: p.get("ts", 0), reverse=True)


def _maj_proposition(prop_id: str, champs: dict):
    """Met à jour les champs d'une proposition dans le fichier (rewrite)."""
    props = _lire_jsonl(_PROPS_PATH)
    for p in props:
        if p.get("id") == prop_id:
            p.update(champs)
    os.makedirs(_SAVOIR_DIR, exist_ok=True)
    with open(_PROPS_PATH, "w", encoding="utf-8") as f:
        for p in props:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")


def _persister_proposition(prop: dict):
    os.makedirs(_SAVOIR_DIR, exist_ok=True)
    with open(_PROPS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(prop, ensure_ascii=False) + "\n")


# ── Registre d'adaptateurs ─────────────────────────────────────────────────────

_SILOS: dict[str, Callable[[], list[Grain]]] = {}


def register_silo(domaine: str, lire_fn: Callable[[], list[Grain]]):
    """Enregistre un adaptateur. lire_fn() -> list[Grain]. Extension en 2 lignes."""
    _SILOS[domaine] = lire_fn


# ── Adaptateurs des 5 silos ────────────────────────────────────────────────────

def _silo_skills() -> list[Grain]:
    try:
        import competences
        grains = []
        for skill in competences.lister():
            contenu = " ".join(filter(None, [
                skill.get("titre", ""),
                skill.get("description", ""),
                skill.get("instructions", "")[:200],
            ]))
            grains.append(Grain(
                id=_grain_id("skill", skill["nom"]),
                domaine="skill",
                type="competence",
                contenu=contenu.strip()[:600],
                score=0.0,
                ts=_to_ts(skill.get("cree_le")),
                usages=int(skill.get("usages", 0)),
                meta={"nom": skill["nom"], "titre": skill.get("titre", ""),
                      "auto": skill.get("auto", False), "socle": skill.get("socle", False)},
            ))
        return grains
    except Exception:
        return []


def _silo_memoire() -> list[Grain]:
    grains = []
    for entry in _lire_jsonl(os.path.join(_DATA, "memoire.jsonl")):
        contenu = entry.get("contenu", "") or entry.get("fait", "") or ""
        if not contenu.strip():
            continue
        grains.append(Grain(
            id=_grain_id("memoire", contenu),
            domaine="memoire",
            type="fait",
            contenu=contenu[:500],
            score=0.0,
            ts=_to_ts(entry.get("cree_le") or entry.get("ts")),
            usages=0,
            meta={"type": entry.get("type", ""), "id": entry.get("id", "")},
        ))
    return grains


def _silo_erreurs() -> list[Grain]:
    grains = []
    for entry in _lire_jsonl(os.path.join(_DATA, "journal_erreurs.jsonl")):
        diag = entry.get("diagnostic", {}) if isinstance(entry.get("diagnostic"), dict) else {}
        lecon = diag.get("lecon", "") or entry.get("erreur", "")
        if not lecon.strip():
            continue
        grains.append(Grain(
            id=_grain_id("erreur", lecon),
            domaine="erreur",
            type="lecon",
            contenu=lecon[:500],
            score=0.0,
            ts=_to_ts(entry.get("timestamp") or entry.get("ts")),
            usages=0,
            meta={
                "erreur": (entry.get("erreur", "") or "")[:100],
                "correction": diag.get("correction", "")[:200],
            },
        ))
    return grains


def _silo_amelioration() -> list[Grain]:
    grains = []
    for entry in _lire_jsonl(os.path.join(_DATA, "auto_amelioration.jsonl")):
        contenu = entry.get("action", "") or entry.get("detail", "") or ""
        if not contenu.strip():
            continue
        grains.append(Grain(
            id=_grain_id("amelioration", contenu),
            domaine="amelioration",
            type="pattern",
            contenu=contenu[:500],
            score=0.0,
            ts=_to_ts(entry.get("timestamp") or entry.get("ts")),
            usages=0,
            meta={"type": entry.get("type", ""), "signal": entry.get("signal", "")},
        ))
    return grains


def _silo_ledger() -> list[Grain]:
    grains = []
    for path in [
        os.path.join(_DATA, "ledger.jsonl"),
        os.path.join(_DATA, "ledger_production.jsonl"),
    ]:
        for entry in _lire_jsonl(path):
            contenu = entry.get("reason", "") or entry.get("raison", "") or entry.get("action", "") or ""
            if not contenu.strip():
                continue
            grains.append(Grain(
                id=_grain_id("ledger", contenu),
                domaine="ledger",
                type="decision",
                contenu=contenu[:500],
                score=0.0,
                ts=_to_ts(entry.get("timestamp") or entry.get("ts")),
                usages=0,
                meta={"decision": entry.get("decision", "") or entry.get("verdict", ""),
                      "cell": entry.get("cell", "")},
            ))
    return grains


def _silo_telemetrie() -> list[Grain]:
    grains = []
    for entry in _lire_jsonl(os.path.join(_DATA, "telemetrie_data.jsonl")):
        contenu = entry.get("evenement", "") or entry.get("message", "") or ""
        if not contenu.strip():
            continue
        grains.append(Grain(
            id=_grain_id("telemetrie", contenu),
            domaine="telemetrie",
            type="fait",
            contenu=contenu[:300],
            score=0.0,
            ts=_to_ts(entry.get("timestamp") or entry.get("ts")),
            usages=0,
            meta={"niveau": entry.get("niveau", ""), "source": entry.get("source", "")},
        ))
    return grains


# ── Hub ────────────────────────────────────────────────────────────────────────

class Hub:
    """Moteur de connaissance unifié. Extensible : register_silo() = 1 adaptateur."""

    def __init__(self):
        os.makedirs(_SAVOIR_DIR, exist_ok=True)
        register_silo("skill", _silo_skills)
        register_silo("memoire", _silo_memoire)
        register_silo("erreur", _silo_erreurs)
        register_silo("amelioration", _silo_amelioration)
        register_silo("ledger", _silo_ledger)
        register_silo("telemetrie", _silo_telemetrie)

    def rafraichir(self) -> dict:
        """Re-ingère tous les silos, rescores, met à jour l'index. Idempotent."""
        from evaluateur import scorer_grain
        index = charger_index()
        stats: dict[str, int] = {}
        tous_grains: list[Grain] = []

        # Passe 1 : lire tous les silos
        for domaine, lire_fn in _SILOS.items():
            try:
                grains = lire_fn()
                for g in grains:
                    existant = index.get(g.id, {})
                    g.usages = existant.get("usages", g.usages)
                    tous_grains.append(g)
                stats[domaine] = len(grains)
            except Exception as e:
                stats[domaine] = 0

        # Passe 2 : scorer chaque grain en contexte du corpus complet
        for g in tous_grains:
            g.score = scorer_grain(g, tous_grains)
            index[g.id] = asdict(g)

        _sauver_index(index)
        return stats

    def chercher(self, requete: str, domaine: str | None = None, k: int = 5) -> list[dict]:
        """Recherche sémantique TF-IDF dans l'index. Incrémente les usages."""
        index = charger_index()
        tous = list(index.values())
        if domaine:
            tous = [g for g in tous if g.get("domaine") == domaine]
        if not tous:
            return []
        docs = [g.get("contenu", "") for g in tous]
        resultats = vecteurs.classer(requete, docs, limite=k, seuil=0.05)
        out = []
        for i, score_cos in resultats:
            g = tous[i]
            g["usages"] = int(g.get("usages", 0)) + 1
            index[g["id"]] = g
            out.append({"grain": g, "score_cosinus": round(score_cos, 3)})
        _sauver_index(index)
        return out

    def etat(self) -> dict:
        index = charger_index()
        par_domaine: dict[str, int] = {}
        for g in index.values():
            d = g.get("domaine", "?")
            par_domaine[d] = par_domaine.get(d, 0) + 1
        props = charger_propositions()
        en_attente = sum(1 for p in props if p.get("statut") == "en_attente")
        return {
            "grains": par_domaine,
            "total_grains": len(index),
            "propositions_en_attente": en_attente,
            "propositions_total": len(props),
            "silos": list(_SILOS.keys()),
        }


# Singleton
HUB = Hub()
