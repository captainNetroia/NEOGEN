"""
Garde-fou de compatibilité : détecte les mises à jour du noyau NEOGEN et vérifie
que les cellules forgées par chaque utilisateur restent valides (compile-check).

Principe : hash des fichiers noyau → tampon dans data/version_stamp.txt.
  Si le hash change → scan automatique → les cellules cassées reçoivent a_reverifier=True.
Jamais bloquant : toute exception est avalée (ne jamais empêcher le démarrage).
"""
from __future__ import annotations
import hashlib, json, time
from pathlib import Path

_DATA = Path("data")
_CELLULES_JSON = _DATA / "cellules_forgees.json"
_CELLULES_DIR = _DATA / "cellules_forgees"
_SCAN_JSON = _DATA / "compatibilite_scan.json"
_STAMP = _DATA / "version_stamp.txt"

# Fichiers noyau dont la modification invalide potentiellement les cellules forgées.
_NOYAU = [
    "noyau.py", "pensee.py", "evolution_gouvernee.py",
    "agent_core.py", "capacites_forgees.py", "quotas.py",
    "robustesse.py", "requirements.txt",
]


def _version_actuelle() -> str:
    h = hashlib.sha256()
    for nom in sorted(_NOYAU):
        p = Path(nom)
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


def _lire_registre() -> dict:
    try:
        if _CELLULES_JSON.exists():
            return json.loads(_CELLULES_JSON.read_text("utf-8"))
    except Exception:
        pass
    return {}


def _ecrire_registre(reg: dict) -> None:
    _CELLULES_JSON.write_text(json.dumps(reg, ensure_ascii=False, indent=2), "utf-8")


def _compiler_cellule(nom: str, fichier: str) -> dict:
    chemin = _DATA / fichier
    if not chemin.exists():
        return {"ok": False, "erreur": "fichier introuvable"}
    try:
        code = chemin.read_text("utf-8")
        compile(code, str(chemin), "exec")
        return {"ok": True, "erreur": None}
    except SyntaxError as e:
        return {"ok": False, "erreur": f"SyntaxError ligne {e.lineno}: {e.msg}"}
    except Exception as e:
        return {"ok": False, "erreur": str(e)[:200]}


def scanner(forcer: bool = False) -> dict:
    """Scanne toutes les cellules forgées. Retourne le rapport complet.
    Si forcer=False et scan récent (< 60s), retourne le dernier rapport mis en cache."""
    if not forcer and _SCAN_JSON.exists():
        try:
            ancien = json.loads(_SCAN_JSON.read_text("utf-8"))
            if time.time() - ancien.get("ts", 0) < 60:
                return ancien
        except Exception:
            pass

    registre = _lire_registre()
    resultats: dict[str, dict] = {}
    modifie = False
    nb_ok = nb_ko = 0

    for nom, meta in registre.items():
        fichier = meta.get("fichier", f"cellules_forgees/{nom}.py")
        r = _compiler_cellule(nom, fichier)
        resultats[nom] = {
            "ok": r["ok"],
            "erreur": r["erreur"],
            "score": meta.get("score", 0),
            "a_reverifier": not r["ok"],
        }
        if r["ok"]:
            nb_ok += 1
            # Effacer le flag si la cellule redevient valide
            if meta.get("a_reverifier"):
                registre[nom].pop("a_reverifier", None)
                registre[nom].pop("raison_reverification", None)
                modifie = True
        else:
            nb_ko += 1
            if not meta.get("a_reverifier"):
                registre[nom]["a_reverifier"] = True
                registre[nom]["raison_reverification"] = r["erreur"]
                modifie = True

    if modifie:
        _ecrire_registre(registre)

    rapport = {
        "ts": time.time(),
        "version": _version_actuelle(),
        "total": nb_ok + nb_ko,
        "ok": nb_ok,
        "ko": nb_ko,
        "cellules": resultats,
    }
    try:
        _SCAN_JSON.write_text(json.dumps(rapport, ensure_ascii=False, indent=2), "utf-8")
    except Exception:
        pass
    return rapport


def check_on_startup() -> None:
    """Appelé au démarrage. Lance le scan uniquement si le noyau a changé depuis
    le dernier démarrage. Jamais bloquant."""
    try:
        version = _version_actuelle()
        ancienne = _STAMP.read_text("utf-8").strip() if _STAMP.exists() else ""
        _STAMP.write_text(version, "utf-8")
        if version == ancienne:
            return  # rien n'a changé, pas besoin de scanner
        rapport = scanner(forcer=True)
        if rapport["ko"]:
            try:
                import robustesse as _rob
                _rob.journaliser("version_guard", "alerte",
                    f"Mise à jour noyau détectée : {rapport['ko']} cellule(s) marquée(s) à_reverifier")
            except Exception:
                pass
    except Exception:
        pass  # guard absolu : ne jamais bloquer le démarrage


def dernier_rapport() -> dict | None:
    """Retourne le dernier rapport de scan sans relancer le scan."""
    try:
        if _SCAN_JSON.exists():
            return json.loads(_SCAN_JSON.read_text("utf-8"))
    except Exception:
        pass
    return None
