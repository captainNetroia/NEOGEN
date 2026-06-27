"""
NEOGEN - Graphe associatif : la memoire ou le reve circule (style BisoNet, pur stdlib).

Base du subconscient. Inspire des BisoNets (Koestler / Creative-AI) : un graphe k-partite ou
les noeuds sont des concepts TYPES (pensee, savoir, cellule, erreur) et les aretes des liens
ponderes (co-occurrence). La creativite par bisociation = relier deux concepts de partitions
distantes via un « noeud-pont » (l'exemple classique magnesium<->migraine via bloqueur de calcium).

Construit en continu depuis les traces reelles de NEOGEN (pensees, savoir, cellules, erreurs).
Operations utilisees par le reve : marche aleatoire biaisee, noeuds-ponts, distance (nouveaute),
renforcement/elagage hebbien (consolidation du sommeil).

Pur Python stdlib (aucune dependance). Ne leve jamais. Conception : Jordan VINCENT + Claude. 2026-06-28.
"""
from __future__ import annotations

import json
import os
import random
import re
import time

import robustesse as rob

BASE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(BASE, "data")
_GRAPHE = os.path.join(_DATA, "graphe_associatif.json")

_STOP = {"avec", "pour", "dans", "les", "des", "une", "un", "le", "la", "de", "du", "et", "en",
         "sur", "que", "qui", "est", "par", "au", "aux", "ce", "se", "sa", "son", "ses", "plus",
         "the", "and", "for", "with", "this", "that", "neogen", "pensee", "idee"}


def _mots_cles(texte: str, n: int = 6) -> list[str]:
    """Extrait les mots significatifs d'un texte (concepts candidats). Deterministe."""
    mots = re.findall(r"[a-zA-Zàâéèêëïîôûùç]{4,}", (texte or "").lower())
    vus, out = set(), []
    for m in mots:
        if m in _STOP or m in vus:
            continue
        vus.add(m)
        out.append(m)
    return out[:n]


# ── I/O ───────────────────────────────────────────────────────────────────────────

def _vide() -> dict:
    return {"noeuds": {}, "aretes": {}, "maj": 0}


def charger() -> dict:
    try:
        if os.path.exists(_GRAPHE):
            with open(_GRAPHE, encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, dict) and "noeuds" in d:
                    d.setdefault("aretes", {})
                    return d
    except Exception:
        pass
    return _vide()


def sauver(g: dict) -> None:
    try:
        os.makedirs(_DATA, exist_ok=True)
        g["maj"] = time.time()
        with open(_GRAPHE, "w", encoding="utf-8") as f:
            json.dump(g, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ── Primitives de graphe ───────────────────────────────────────────────────────────

def ajouter_noeud(g: dict, label: str, type_: str = "concept") -> str:
    nid = re.sub(r"[^a-z0-9]+", "_", (label or "").lower()).strip("_")[:40]
    if not nid:
        return ""
    n = g["noeuds"].get(nid)
    if n:
        n["poids"] = n.get("poids", 1) + 1
    else:
        g["noeuds"][nid] = {"label": label[:60], "type": type_, "poids": 1}
        g["aretes"].setdefault(nid, {})
    return nid


def lier(g: dict, a: str, b: str, delta: float = 1.0) -> None:
    """Renforce le lien a<->b (symetrique). Cree les entrees au besoin."""
    if not a or not b or a == b:
        return
    for x, y in ((a, b), (b, a)):
        ar = g["aretes"].setdefault(x, {})
        ar[y] = round(ar.get(y, 0.0) + delta, 3)


def voisins(g: dict, nid: str) -> dict:
    return g["aretes"].get(nid, {})


def marche_aleatoire(g: dict, depart: str, longueur: int = 4) -> list[str]:
    """Marche aleatoire biaisee par le poids des aretes (node2vec simplifie). Deterministe
    si random est seede. Renvoie le chemin de concepts visites."""
    chemin = [depart]
    courant = depart
    for _ in range(max(1, longueur)):
        vs = voisins(g, courant)
        if not vs:
            break
        cibles, poids = zip(*vs.items())
        courant = random.choices(cibles, weights=poids, k=1)[0]
        chemin.append(courant)
    return chemin


def noeuds_ponts(g: dict, top: int = 10) -> list[str]:
    """Noeuds reliant des partitions (types) distinctes = candidats a la bisociation.
    Score = nombre de types differents parmi les voisins (un pont relie des mondes)."""
    scores = []
    for nid in g["noeuds"]:
        types = {g["noeuds"].get(v, {}).get("type") for v in voisins(g, nid)}
        types.discard(None)
        if len(types) >= 2:
            scores.append((nid, len(types), len(voisins(g, nid))))
    scores.sort(key=lambda t: (t[1], t[2]), reverse=True)
    return [nid for nid, _, _ in scores[:top]]


def distance(g: dict, a: str, b: str, max_sauts: int = 6) -> int:
    """Distance en sauts (BFS) entre 2 noeuds. -1 si non connectes (= tres nouveau si associes)."""
    if a == b:
        return 0
    vu = {a}
    front = [a]
    for d in range(1, max_sauts + 1):
        suiv = []
        for x in front:
            for v in voisins(g, x):
                if v == b:
                    return d
                if v not in vu:
                    vu.add(v)
                    suiv.append(v)
        if not suiv:
            break
        front = suiv
    return -1


def deux_noeuds_distants(g: dict) -> tuple[str, str]:
    """Choisit deux concepts ELOIGNES (distance grande ou non connectes) et de types varies :
    le terreau d'une bisociation feconde. Renvoie ('','') si le graphe est trop petit."""
    noeuds = list(g["noeuds"].keys())
    if len(noeuds) < 2:
        return ("", "")
    meilleur = ("", "", -2)
    for _ in range(min(40, len(noeuds) * 3)):   # echantillonnage borne
        a, b = random.sample(noeuds, 2)
        d = distance(g, a, b)
        # non connectes (-1) = le plus nouveau ; sinon plus c'est loin, mieux c'est.
        score = 99 if d == -1 else d
        if g["noeuds"][a].get("type") != g["noeuds"][b].get("type"):
            score += 1
        if score > meilleur[2]:
            meilleur = (a, b, score)
    return (meilleur[0], meilleur[1])


# ── Construction depuis les traces reelles de NEOGEN ───────────────────────────────

def construire() -> dict:
    """(Re)construit le graphe depuis pensees + savoir + cellules + erreurs : chaque source
    devient des concepts (mots-cles) lies entre eux (co-occurrence = Hebbien). Ne leve jamais."""
    with rob.garde("graphe.construire", source="graphe_associatif"):
        g = charger()

        def _ingerer(texte: str, type_: str):
            cles = _mots_cles(texte)
            ids = [ajouter_noeud(g, c, type_) for c in cles]
            ids = [i for i in ids if i]
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    lier(g, ids[i], ids[j], 1.0)   # co-occurrence -> lien renforce

        # 1. Pensees (le terreau onirique principal).
        try:
            import pensee
            for p in pensee._lire()[-200:]:
                _ingerer(f"{p.get('titre','')} {p.get('synthese','')}", "pensee")
        except Exception:
            pass
        # 2. Savoir (grains des silos).
        try:
            import savoir
            for gr in list(savoir.charger_index().values())[:200]:
                _ingerer(gr.get("contenu") or "", "savoir")
        except Exception:
            pass
        # 3. Cellules forgees (capacites).
        try:
            import capacites_forgees as _cf
            for c in _cf.lister():
                _ingerer(f"{c.get('nom','')} {c.get('resume','')}", "cellule")
        except Exception:
            pass
        # 4. Erreurs (le systeme reve aussi de ses ratages).
        try:
            jp = os.path.join(_DATA, "journal_erreurs.jsonl")
            if os.path.exists(jp):
                with open(jp, encoding="utf-8") as f:
                    for ligne in list(f)[-100:]:
                        ligne = ligne.strip()
                        if ligne:
                            try:
                                e = json.loads(ligne)
                                _ingerer(str(e.get("message") or e.get("operation") or ""), "erreur")
                            except Exception:
                                continue
        except Exception:
            pass

        sauver(g)
        rob.journaliser(f"graphe associatif : {len(g['noeuds'])} concepts, "
                        f"{sum(len(v) for v in g['aretes'].values())//2} liens",
                        "info", source="graphe_associatif")
        return g
    return _vide()


def consolider(decay: float = 0.9, seuil_elagage: float = 0.4) -> dict:
    """Consolidation du sommeil (SRC hebbien) : affaiblit doucement tous les liens (oubli) et
    elague les liens trop faibles. La reconstruction depuis les pensees recentes renforce ce qui
    compte -> le graphe garde les associations vivaces, perd le bruit. Ne leve jamais."""
    with rob.garde("graphe.consolider", source="graphe_associatif"):
        g = charger()
        for x, vs in list(g["aretes"].items()):
            for y in list(vs.keys()):
                vs[y] = round(vs[y] * decay, 3)
                if vs[y] < seuil_elagage:
                    del vs[y]
        # Noeuds devenus orphelins ET faibles -> retires (oubli profond).
        orphelins = [n for n in list(g["noeuds"])
                     if not g["aretes"].get(n) and g["noeuds"][n].get("poids", 1) <= 1]
        for n in orphelins:
            g["noeuds"].pop(n, None)
            g["aretes"].pop(n, None)
        sauver(g)
        return {"ok": True, "concepts": len(g["noeuds"]),
                "liens": sum(len(v) for v in g["aretes"].values()) // 2,
                "elagues": len(orphelins)}
    return {"ok": False}


def etat() -> dict:
    g = charger()
    return {"concepts": len(g["noeuds"]),
            "liens": sum(len(v) for v in g["aretes"].values()) // 2,
            "ponts": len(noeuds_ponts(g)), "maj": g.get("maj", 0)}


def label(g: dict, nid: str) -> str:
    return g["noeuds"].get(nid, {}).get("label", nid)


# ── Auto-verification offline ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile

    print("=" * 64)
    print("NEOGEN - GRAPHE ASSOCIATIF : auto-verification (offline)")
    print("=" * 64)
    _DATA = tempfile.mkdtemp()
    _GRAPHE = os.path.join(_DATA, "graphe_associatif.json")
    random.seed(42)

    g = _vide()
    # Deux mondes (partitions) relies par un pont.
    a = ajouter_noeud(g, "migraine", "savoir")
    b = ajouter_noeud(g, "calcium", "savoir")
    c = ajouter_noeud(g, "magnesium", "cellule")
    d = ajouter_noeud(g, "interface", "pensee")
    lier(g, a, b, 3); lier(g, b, c, 2)   # migraine-calcium-magnesium
    assert voisins(g, b), "b doit avoir des voisins"
    assert distance(g, a, c) == 2, distance(g, a, c)
    assert distance(g, a, d) == -1, "d isole -> non connecte"
    print("  noeuds + liens + distance (BFS) OK")

    # Pont : 'calcium' relie savoir(migraine) et cellule(magnesium) -> 2 types.
    g["noeuds"]["calcium"]  # exists
    lier(g, b, c, 1)
    ponts = noeuds_ponts(g)
    assert "calcium" in ponts, ponts
    print(f"  noeuds-ponts (bisociation) : {ponts} OK")

    # Marche aleatoire bornee + deux noeuds distants.
    chemin = marche_aleatoire(g, a, 3)
    assert chemin[0] == a and len(chemin) >= 1
    x, y = deux_noeuds_distants(g)
    assert x and y and x != y, (x, y)
    print(f"  marche aleatoire {chemin} + paire distante ({x},{y}) OK")

    # Consolidation : decay + elagage.
    _DATA2 = _DATA
    sauver(g)
    before = sum(len(v) for v in charger()["aretes"].values())
    consolider(decay=0.3, seuil_elagage=0.5)   # decay agressif -> elague
    after = sum(len(v) for v in charger()["aretes"].values())
    assert after <= before, (before, after)
    print(f"  consolidation hebbienne : {before} -> {after} liens (elagage) OK")

    print("=" * 64)
    print("  TOUT VERT : graphe associatif (BisoNet) pret pour le reve.")
    print("=" * 64)
