"""
NEOGEN - Securite web : durcissement des frontieres publiques (culture DevSecOps contre le monde).

Protege la version PUBLIQUE contre les pirates et les « ptit malins » : flood/DoS (rate limit),
clickjacking + sniffing + fuite de referer (headers de securite), exfiltration et scripts distants
(Content-Security-Policy). N'entrave JAMAIS l'instance proprietaire (owner_unlimited) ni les
ressources internes (static, health).

POURQUOI C'EST SUR ET NON-INTRUSIF :
  - Rate limit en memoire par IP, fenetre glissante, seuil large par defaut (le flood seul est bloque).
    Desactive sur l'instance perso du proprio (aucune menace) et exempte static/health/favicon.
  - Headers de securite standard (OWASP) : X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy.
  - CSP permissive par defaut (compatible UI actuelle : styles/scripts inline, images data:), mais
    `connect-src 'self'` = aucun appel reseau du navigateur vers un domaine externe (anti-exfiltration).
    Les appels LLM passent par le SERVEUR (gateway), donc la CSP ne les gene pas.
  - Tout est configurable par variables d'environnement ; defauts sains.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-26.
"""
from __future__ import annotations

import os
import time
from collections import deque

import robustesse as rob

# ── Configuration (env, defauts sains) ──────────────────────────────────────────

def _int_env(nom: str, defaut: int) -> int:
    try:
        return int(os.environ.get(nom, "").strip() or defaut)
    except ValueError:
        return defaut


RATE_FENETRE_S = _int_env("NEOGEN_RATE_FENETRE_S", 60)        # taille de la fenetre
RATE_MAX = _int_env("NEOGEN_RATE_MAX", 120)                   # req/fenetre/IP (global, large)
RATE_MAX_LLM = _int_env("NEOGEN_RATE_MAX_LLM", 20)            # req/fenetre/IP sur routes couteuses

# Routes couteuses (LLM / generation) : flood = cout + DoS -> seuil plus strict.
_PREFIXES_COUTEUX = ("/proposer", "/composer", "/conseil", "/fabriquer",
                     "/savoir/fragments/apercu", "/savoir/pensees/cycle",
                     "/savoir/evolution/proposer")
_MARQUEURS_COUTEUX = ("/chat", "/stream")  # endpoints d'agents (sous-chemins)

# Chemins jamais limites (ressources internes, sondes).
_EXEMPTS = ("/static/", "/health", "/favicon", "/info")


def _rate_actif() -> bool:
    """Rate limit actif SAUF instance perso du proprio (owner_unlimited) ou desactive explicitement."""
    if os.environ.get("NEOGEN_RATE_LIMIT", "").strip().lower() in ("0", "false", "off", "no"):
        return False
    try:
        import quotas
        if quotas._owner_unlimited():
            return False
    except Exception:
        pass
    return True


# ── Rate limiting en memoire (fenetre glissante par IP) ──────────────────────────

_seen: dict[str, deque] = {}
_seen_llm: dict[str, deque] = {}


def _trop_de_requetes(ip: str, chemin: str) -> bool:
    """True si l'IP depasse son quota pour ce chemin (fenetre glissante). Idempotent, ne leve jamais."""
    now = time.time()
    est_couteux = chemin.startswith(_PREFIXES_COUTEUX) or any(m in chemin for m in _MARQUEURS_COUTEUX)
    table = _seen_llm if est_couteux else _seen
    limite = RATE_MAX_LLM if est_couteux else RATE_MAX
    dq = table.setdefault(ip, deque())
    seuil = now - RATE_FENETRE_S
    while dq and dq[0] < seuil:
        dq.popleft()
    if len(dq) >= limite:
        return True
    dq.append(now)
    # garde-fou memoire : purge occasionnelle des IP inactives
    if len(table) > 4096:
        for k in [k for k, v in list(table.items()) if not v or v[-1] < seuil]:
            table.pop(k, None)
    return False


def _ip_client(request) -> str:
    """IP reelle du client (respecte X-Forwarded-For derriere un reverse proxy)."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return getattr(getattr(request, "client", None), "host", "") or "?"


# ── Headers de securite (OWASP) + CSP ────────────────────────────────────────────

def _csp() -> str:
    """Content-Security-Policy. Defaut compatible UI actuelle (inline style/script, data: img),
    mais connect-src verrouille a 'self' (anti-exfiltration : pas de fetch externe du navigateur).
    Surchargeable via NEOGEN_CSP."""
    perso = os.environ.get("NEOGEN_CSP", "").strip()
    if perso:
        return perso
    return ("default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'")


_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=()",
    "Content-Security-Policy": _csp(),
}


def headers_securite() -> dict:
    """Headers de securite a poser sur chaque reponse."""
    return dict(_HEADERS)


# ── Branchement FastAPI (middleware mince) ───────────────────────────────────────

def installer(app) -> None:
    """Branche le rate limit + les headers de securite sur l'app FastAPI. Ne leve jamais."""
    from starlette.responses import JSONResponse

    @app.middleware("http")
    async def _securite(request, call_next):
        chemin = request.url.path
        # Rate limit (sauf exempts / instance perso).
        if _rate_actif() and not chemin.startswith(_EXEMPTS):
            ip = _ip_client(request)
            try:
                if _trop_de_requetes(ip, chemin):
                    rob.journaliser(f"rate limit : IP {ip} sur {chemin}", "alerte", source="securite_web")
                    return JSONResponse(
                        status_code=429,
                        content={"detail": "Trop de requetes. Reessaie dans une minute."},
                        headers={"Retry-After": str(RATE_FENETRE_S), **headers_securite()})
            except Exception:
                pass  # le rate limit ne doit jamais casser une requete legitime
        reponse = await call_next(request)
        for k, v in _HEADERS.items():
            reponse.headers.setdefault(k, v)
        return reponse

    rob.journaliser(
        f"securite web installee (rate {'on' if _rate_actif() else 'off'}, "
        f"max {RATE_MAX}/{RATE_FENETRE_S}s, llm {RATE_MAX_LLM})", "info", source="securite_web")


# ── Audit des routes (lecture seule, pour /health ou diagnostic) ─────────────────

def auditer_routes(app) -> dict:
    """Recense les routes et leur niveau de protection (owner-gated vs public). Lecture seule.
    Heuristique : owner-gated = la fonction de route appelle _gate_owner."""
    import inspect
    publiques, owner, autres = [], [], []
    for r in getattr(app, "routes", []):
        chemin = getattr(r, "path", "")
        ep = getattr(r, "endpoint", None)
        if not chemin or ep is None:
            continue
        try:
            src = inspect.getsource(ep)
        except Exception:
            src = ""
        methodes = sorted(getattr(r, "methods", []) or [])
        entree = {"chemin": chemin, "methodes": methodes}
        if "_gate_owner" in src:
            owner.append(entree)
        elif "_auth" in src or "Authorization" in src or "authorization" in src:
            autres.append(entree)
        else:
            publiques.append(entree)
    return {"owner_gated": owner, "auth_requise": autres, "publiques": publiques,
            "totaux": {"owner": len(owner), "auth": len(autres), "publiques": len(publiques)}}


# ── Auto-verification offline ────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 64)
    print("NEOGEN - SECURITE WEB : auto-verification (offline)")
    print("=" * 64)

    os.environ["NEOGEN_OWNER_UNLIMITED"] = ""   # simuler instance publique
    os.environ["NEOGEN_RATE_LIMIT"] = "1"
    globals()["RATE_MAX"] = 3
    globals()["RATE_MAX_LLM"] = 2

    # 1. Sous le seuil -> autorise.
    assert not _trop_de_requetes("1.2.3.4", "/produits")
    assert not _trop_de_requetes("1.2.3.4", "/produits")
    assert not _trop_de_requetes("1.2.3.4", "/produits")
    # 4e -> bloque.
    assert _trop_de_requetes("1.2.3.4", "/produits"), "le 4e doit etre bloque"
    print("  rate limit global : 3 OK puis blocage -> OK")

    # 2. Routes couteuses : seuil plus strict (2).
    assert not _trop_de_requetes("9.9.9.9", "/savoir/fragments/apercu")
    assert not _trop_de_requetes("9.9.9.9", "/savoir/fragments/apercu")
    assert _trop_de_requetes("9.9.9.9", "/savoir/fragments/apercu"), "le 3e LLM doit etre bloque"
    print("  rate limit LLM : 2 OK puis blocage -> OK")

    # 3. IP differente -> compteur independant.
    assert not _trop_de_requetes("5.6.7.8", "/produits")
    print("  isolation par IP -> OK")

    # 4. Headers de securite presents.
    h = headers_securite()
    assert h["X-Frame-Options"] == "DENY" and "connect-src 'self'" in h["Content-Security-Policy"]
    print("  headers securite + CSP connect-src self -> OK")

    # 5. Instance proprio -> rate limit desactive.
    os.environ["NEOGEN_OWNER_UNLIMITED"] = "1"
    assert not _rate_actif(), "le proprio ne doit jamais etre limite"
    os.environ["NEOGEN_OWNER_UNLIMITED"] = ""
    print("  instance proprio -> rate limit off -> OK")

    print("=" * 64)
    print("  TOUT VERT : frontieres publiques durcies, proprio jamais entrave.")
    print("=" * 64)
