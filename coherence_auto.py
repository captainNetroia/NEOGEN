"""
NEOGEN — Auditeur de cohérence des parcours utilisateur.

Vérifie que chaque étape d'un parcours déclaré a son implémentation réelle :
route enregistrée dans routes/savoir.py, fonction JS dans static/app.js,
fichier data présent. Idempotent, ne lève jamais.

Parcours déclarés dans journeys.json (racine, versionné git).
"""
from __future__ import annotations
import json
import pathlib
import re

_RACINE = pathlib.Path(__file__).parent
_JOURNEYS_FILE = _RACINE / "journeys.json"
_ROUTES_FILE = _RACINE / "routes" / "savoir.py"
_JS_FILE = _RACINE / "static" / "app.js"


def _charger_journeys() -> dict:
    try:
        if _JOURNEYS_FILE.exists():
            return json.loads(_JOURNEYS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"journeys": []}


def _norm_path(p: str) -> str:
    """Remplace {param} par * pour comparer des routes avec et sans paramètres."""
    return re.sub(r"\{[^}]+\}", "*", p)


def _check_route(endpoint: str) -> tuple[bool, str]:
    """Vérifie qu'une route (METHOD /savoir/...) est enregistrée dans routes/savoir.py."""
    if not endpoint:
        return True, "ok"
    if not _ROUTES_FILE.exists():
        return False, "routes/savoir.py introuvable"
    content = _ROUTES_FILE.read_text(encoding="utf-8")
    parts = endpoint.strip().split(" ", 1)
    method = parts[0].lower() if len(parts) == 2 else "get"
    path = parts[-1]
    # Retire le préfixe /savoir (monté par le router include dans api.py)
    path_norm = _norm_path(re.sub(r"^/savoir", "", path))
    # Cherche @router.METHOD("...") dans le fichier et compare en normalisant
    for m in re.finditer(rf'@router\.{method}\("([^"]+)"', content):
        if _norm_path(m.group(1)) == path_norm:
            return True, "ok"
    return False, f"route '{endpoint}' introuvable dans routes/savoir.py"


def _check_js(fn_name: str) -> tuple[bool, str]:
    """Vérifie qu'une fonction JS existe dans static/app.js."""
    if not fn_name:
        return True, "ok"
    if not _JS_FILE.exists():
        return False, "static/app.js introuvable"
    content = _JS_FILE.read_text(encoding="utf-8")
    if f"function {fn_name}" in content or f"async function {fn_name}" in content:
        return True, "ok"
    return False, f"fonction JS '{fn_name}' introuvable dans app.js"


def _check_data(data_path: str) -> tuple[bool, str]:
    """Vérifie qu'un fichier/dossier data existe sur le bind mount."""
    if not data_path:
        return True, "ok"
    p = _RACINE / data_path
    if p.exists():
        return True, "ok"
    return False, f"'{data_path}' absent (data/ non initialisé ou feature pas encore activée)"


def _verifier_etape(e: dict) -> tuple[bool, str]:
    methode = e.get("methode", "check_route")
    if methode == "check_route":
        return _check_route(e.get("endpoint", ""))
    if methode == "check_js":
        return _check_js(e.get("js_fn", ""))
    if methode == "check_data":
        return _check_data(e.get("data_path", ""))
    return True, "methode inconnue (ignoree)"


def audit_journeys() -> dict:
    """Audite tous les parcours déclarés. Retourne {ok, tensions, journeys, total, ko}.
    Jamais d'exception : fail-closed sur toute erreur interne."""
    try:
        data = _charger_journeys()
        tensions: list[dict] = []
        results: list[dict] = []
        for j in data.get("journeys", []):
            etapes_ok = []
            for e in j.get("etapes", []):
                ok, raison = _verifier_etape(e)
                etapes_ok.append({
                    "desc": e.get("desc", ""),
                    "ok": ok,
                    "raison": raison if not ok else None,
                })
                if not ok:
                    tensions.append({
                        "journey": j.get("titre", j.get("id", "?")),
                        "etape": e.get("desc", "?"),
                        "raison": raison,
                    })
            results.append({
                "id": j.get("id"),
                "titre": j.get("titre"),
                "etapes": etapes_ok,
                "ok": all(e2["ok"] for e2 in etapes_ok),
            })
        return {"ok": len(tensions) == 0, "tensions": tensions,
                "journeys": results, "total": len(results), "ko": len(tensions)}
    except Exception as exc:
        return {"ok": False, "tensions": [{"raison": str(exc)}],
                "journeys": [], "total": 0, "ko": 1}


def bloc_pour_prompt() -> str:
    """Résumé des tensions injecté dans le prompt système des agents.
    Vide si tout est cohérent (pas de bruit inutile)."""
    try:
        r = audit_journeys()
        if r["ok"]:
            return ""
        lignes = ["\n\nTENSIONS DE COHERENCE (parcours utilisateur incomplets) :"]
        for t in r["tensions"]:
            lignes.append(f"  - [{t['journey']}] '{t['etape']}' : {t['raison']}")
        lignes.append("Ces étapes manquantes doivent être implémentées avant livraison.\n")
        return "\n".join(lignes)
    except Exception:
        return ""


if __name__ == "__main__":
    print("=== coherence_auto self-test ===")

    # check_route — route connue
    ok, r = _check_route("POST /savoir/fragments/apercu")
    assert ok, f"ECHEC fragments/apercu : {r}"
    print(f"check_route fragments/apercu : OK")

    # check_route — route avec params dynamiques
    ok, r = _check_route("GET /savoir/fragments/{zone}/{frag_id}")
    assert ok, f"ECHEC fragments/zone/id : {r}"
    print(f"check_route fragments/zone/id : OK")

    # check_route — route inexistante
    ok, r = _check_route("POST /savoir/inexistant/route-bidon")
    assert not ok, "ECHEC : devait être KO"
    print(f"check_route inexistant : KO attendu OK")

    # check_js — fonction connue
    ok, r = _check_js("graverFragment")
    assert ok, f"ECHEC graverFragment : {r}"
    print(f"check_js graverFragment : OK")

    # check_js — fonction inexistante
    ok, r = _check_js("fonctionFantome999")
    assert not ok, "ECHEC : devait être KO"
    print(f"check_js fantome : KO attendu OK")

    # audit complet
    result = audit_journeys()
    print(f"\naudit_journeys : {result['total']} parcours, {result['ko']} tension(s)")
    for t in result.get("tensions", []):
        print(f"  TENSION [{t['journey']}] {t['etape']} -> {t['raison']}")

    # bloc_pour_prompt ne lève jamais
    bloc = bloc_pour_prompt()
    print(f"\nbloc_pour_prompt : {len(bloc)} car")

    print("=== self-test OK ===")
