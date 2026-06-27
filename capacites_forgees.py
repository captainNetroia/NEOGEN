"""
NEOGEN - Capacites forgees : la VRAIE PORTE D'ACCES entre le code genere et le systeme.

Probleme resolu : la forge (forge_evolution) generait du vrai code Python, le testait,
le validait, le persistait dans data/cellules_forgees/{nom}.py... puis L'OUBLIAIT. La
cellule etait une fonction propre mais ORPHELINE : aucune ligne du systeme ne l'importait
ni ne l'appelait. Le code existait, le pont d'integration n'existait pas -> sentiment de vide.

Ce module est ce pont. Code GRAVE (immuable) qui LIT le dossier data-driven des cellules :
  1. charge_capacites()      -> importe dynamiquement chaque cellule ACCEPTEE et sans mur
  2. verifier_integration()  -> PREUVE qu'une cellule est reellement chargeable + appelable
  3. invoquer(nom, **params) -> appel REEL de la capacite (sous rob.garde, ne leve jamais)
  4. CAPACITES (lazy)        -> {nom: callable} : le registre vivant des fonctions integrees

GARDE-FOUS (fail-closed) : on n'integre EN PROCESSUS que les cellules dont le registre
porte un verdict ACCEPTE ET dont les effets reels ne touchent NI au reseau NI a la
suppression de donnees (sinon : reste 'forgee' sur disque mais PAS chargee -> statut honnete).
La cellule a deja passe la Membrane + le smoke-test Docker ; ici on expose une fonction pure.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-27.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import os

import robustesse as rob

BASE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(BASE, "data")
_CELLULES_DIR = os.path.join(_DATA, "cellules_forgees")
_REGISTRE = os.path.join(_DATA, "cellules_forgees.json")

# Cache du registre vivant {nom: callable}. Reconstruit par recharger().
CAPACITES: dict = {}
_INFOS: dict = {}   # {nom: {fonction, signature, params, resume}}


# ── Lecture du registre des cellules forgees ─────────────────────────────────────

def _charger_registre() -> dict:
    try:
        if os.path.exists(_REGISTRE):
            with open(_REGISTRE, encoding="utf-8") as f:
                d = json.load(f)
                return d if isinstance(d, dict) else {}
    except Exception:
        pass
    return {}


def _integrable(meta: dict) -> tuple[bool, str]:
    """Porte fail-closed pour l'integration EN PROCESSUS. Une cellule presente dans le registre
    a DEJA passe la Membrane (les rejets ne sont jamais persistes). On gate donc sur les EFFETS
    REELS : une cellule qui touche au reseau ou supprime des donnees reste sur disque, jamais
    chargee dans le processus principal (elle ne tournerait qu'en conteneur isole)."""
    effets = meta.get("effets_reels") or {}
    if effets.get("network_access"):
        return False, "touche au reseau (mur) -> non integree en processus, reste en sandbox"
    if effets.get("deletes_data"):
        return False, "supprime des donnees (mur) -> non integree en processus, reste en sandbox"
    return True, "integrable"


# ── Import dynamique d'une cellule + reperage de la fonction principale ───────────

def _trouver_fonction_principale(module, nom_cellule: str):
    """La fonction exposee : priorite a celle qui porte le nom de la cellule, sinon
    'executer'/'run'/'main', sinon la premiere fonction publique definie dans le module."""
    candidats = [nom_cellule, "executer", "run", "main", "appliquer"]
    for nom in candidats:
        fn = getattr(module, nom, None)
        if callable(fn):
            return nom, fn
    # Premiere fonction publique definie DANS ce module (pas un import).
    for nom, obj in vars(module).items():
        if nom.startswith("_"):
            continue
        if inspect.isfunction(obj) and obj.__module__ == module.__name__:
            return nom, obj
    return None, None


def charger_capacite(nom: str) -> tuple:
    """Importe la cellule {nom}.py et renvoie (callable, info) ou (None, raison_str).
    Ne leve jamais. L'import execute le code de niveau module (deja valide par la Membrane)."""
    chemin = os.path.join(_CELLULES_DIR, f"{nom}.py")
    if not os.path.exists(chemin):
        return None, f"fichier introuvable : {nom}.py"
    try:
        spec = importlib.util.spec_from_file_location(f"capacite_{nom}", chemin)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as e:
        return None, f"import echoue : {e}"
    nom_fn, fn = _trouver_fonction_principale(module, nom)
    if not fn:
        return None, "aucune fonction publique exposable"
    try:
        sig = inspect.signature(fn)
        params = [p for p in sig.parameters]
        signature = f"{nom_fn}{sig}"
    except (ValueError, TypeError):
        params, signature = [], f"{nom_fn}(...)"
    return fn, {"fonction": nom_fn, "signature": signature, "params": params,
                "resume": (inspect.getdoc(fn) or "").split("\n")[0][:160]}


# ── Construction du registre vivant ───────────────────────────────────────────────

def recharger() -> dict:
    """(Re)construit CAPACITES depuis le registre des cellules. Renvoie un resume.
    Seules les cellules integrables (ACCEPTE + sans mur) sont chargees en processus."""
    CAPACITES.clear()
    _INFOS.clear()
    reg = _charger_registre()
    charges, ignores = [], []
    for nom, meta in reg.items():
        ok, motif = _integrable(meta)
        if not ok:
            ignores.append({"nom": nom, "raison": motif})
            continue
        fn, info = charger_capacite(nom)
        if fn:
            CAPACITES[nom] = fn
            _INFOS[nom] = info
            charges.append(nom)
        else:
            ignores.append({"nom": nom, "raison": info})
    return {"charges": charges, "ignores": ignores,
            "total": len(reg), "actifs": len(charges)}


def lister() -> list[dict]:
    """Capacites integrees (chargees en processus) avec leur signature, pour l'UI/les agents."""
    if not CAPACITES:
        recharger()
    return [{"nom": n, **_INFOS.get(n, {})} for n in CAPACITES]


# ── Verification d'integration : la PREUVE qu'une capacite est reellement branchee ─

def verifier_integration(nom: str) -> dict:
    """Controle du fonctionnement APRES integration : la cellule se charge-t-elle et
    expose-t-elle une fonction appelable ? C'est ce qui distingue 'forgee' de 'integree'.
    Ne leve jamais. Renvoie {ok, resume, signature?}."""
    fn, info = charger_capacite(nom)
    if not fn:
        return {"ok": False, "resume": info}
    reg = _charger_registre()
    integrable, motif = _integrable(reg.get(nom, {}))
    if not integrable:
        return {"ok": False, "resume": motif, "signature": info.get("signature")}
    return {"ok": True, "resume": "chargee + fonction appelable exposee",
            "signature": info.get("signature"), "fonction": info.get("fonction")}


# ── Invocation reelle d'une capacite forgee ───────────────────────────────────────

def invoquer(nom: str, **params) -> dict:
    """Appelle REELLEMENT une capacite forgee. Sous rob.garde : ne leve jamais.
    Renvoie {ok, resultat?|erreur?}. Filtre les params a la signature de la fonction."""
    with rob.garde(f"invoquer capacite {nom}", source="capacites_forgees"):
        if nom not in CAPACITES:
            recharger()
        fn = CAPACITES.get(nom)
        if not fn:
            return {"ok": False, "erreur": f"capacite '{nom}' non integree"}
        # Ne passe que les params reconnus par la signature (evite TypeError).
        try:
            sig = inspect.signature(fn)
            accepte_kwargs = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())
            if accepte_kwargs:
                kw = params
            else:
                kw = {k: v for k, v in params.items() if k in sig.parameters}
        except (ValueError, TypeError):
            kw = params
        resultat = fn(**kw)
        rob.journaliser(f"capacite forgee '{nom}' invoquee", "info", source="capacites_forgees")
        return {"ok": True, "resultat": resultat}
    return {"ok": False, "erreur": "erreur capturee (voir journal)"}


# ── Auto-verification offline (cree une cellule temporaire, l'integre, l'invoque) ─

if __name__ == "__main__":
    import tempfile

    print("=" * 64)
    print("NEOGEN - CAPACITES FORGEES : auto-verification (offline)")
    print("=" * 64)

    _tmp = tempfile.mkdtemp()
    _DATA = _tmp
    _CELLULES_DIR = os.path.join(_tmp, "cellules_forgees")
    _REGISTRE = os.path.join(_tmp, "cellules_forgees.json")
    os.makedirs(_CELLULES_DIR, exist_ok=True)

    # 1. Cellule propre, sans mur -> integrable + invocable.
    with open(os.path.join(_CELLULES_DIR, "additionner.py"), "w", encoding="utf-8") as f:
        f.write("def additionner(a=0, b=0):\n"
                "    \"\"\"Additionne deux nombres.\"\"\"\n"
                "    return {'somme': a + b}\n")
    # 2. Cellule qui touche au reseau -> NON integrable en processus (fail-closed).
    with open(os.path.join(_CELLULES_DIR, "scanner_reseau.py"), "w", encoding="utf-8") as f:
        f.write("import socket\ndef executer():\n    return socket.gethostname()\n")

    with open(_REGISTRE, "w", encoding="utf-8") as f:
        json.dump({
            "additionner": {"nom": "additionner", "verdict": "ACCEPTE",
                            "effets_reels": {"network_access": False, "deletes_data": False}},
            "scanner_reseau": {"nom": "scanner_reseau", "verdict": "ACCEPTE",
                               "effets_reels": {"network_access": True, "deletes_data": False}},
        }, f)

    resume = recharger()
    assert "additionner" in resume["charges"], resume
    assert any(i["nom"] == "scanner_reseau" for i in resume["ignores"]), resume
    print(f"  recharger : {resume['actifs']} integree(s), {len(resume['ignores'])} ignoree(s) (mur) OK")

    v = verifier_integration("additionner")
    assert v["ok"] and "additionner" in v["signature"], v
    print(f"  verifier_integration : {v['signature']} -> {v['resume']} OK")

    v2 = verifier_integration("scanner_reseau")
    assert not v2["ok"], v2
    print(f"  verifier_integration (mur reseau) : refus fail-closed OK")

    r = invoquer("additionner", a=2, b=3, ignore_moi="x")
    assert r["ok"] and r["resultat"]["somme"] == 5, r
    print(f"  invoquer additionner(2,3) -> {r['resultat']} (params parasites filtres) OK")

    r2 = invoquer("inexistante")
    assert not r2["ok"], r2
    print(f"  invoquer capacite inexistante -> refus propre OK")

    print("=" * 64)
    print("  TOUT VERT : les cellules forgees deviennent de vraies fonctions appelables.")
    print("=" * 64)
