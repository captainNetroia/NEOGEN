"""
NEOGEN - Sante des providers LLM : qui est REELLEMENT operationnel maintenant.

Avant : gateway.py routait vers un provider choisi par l'utilisateur (ou "anthropic" par
defaut) sans jamais savoir si ce provider avait encore du credit ou une cle valide. Un
agent tombait sur "Your credit balance is too low" en pleine boucle, sans alternative.

Ici : un registre par provider (etat + type d'erreur + derniere verification), persistant
(data/providers_sante.json, meme patron que routeur_bandit.py/data/bandit.json), avec :
  - une sonde ACTIVE (ping reel minimal) en cache TTL -> ne spamme pas l'API a chaque appel
  - un typage de l'echec (credit_epuise / cle_invalide / transitoire / inconnu) au lieu
    du seul bucket "transitoire" du CircuitBreaker de generator.py (qui reste utilise tel
    quel pour les retries fins ; ce module-ci repond a une question differente : "sur quel
    provider dois-je meme ESSAYER ?", pas "combien de fois retenter sur celui choisi").

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-07-10.
"""
from __future__ import annotations

import json
import os
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SANTE_FILE = os.path.join(BASE_DIR, "data", "providers_sante.json")

_LOCK = threading.Lock()

TTL_SANTE = 600.0        # 10 min : au-dela, un statut "operationnel" est re-verifie
TTL_ECHEC_COURT = 120.0  # 2 min : un echec recent est retente plus vite (guerison possible)

# Providers systeme (cle geree par NetroIA, cf credentials_loader.PROVIDER_CRED).
# Les providers custom ajoutes par evolution_gouvernee ou les providers BYOK utilisateur
# ne passent pas par ce registre : leur cle est fournie par requete, la sonde n'a pas de
# sens systeme pour eux (chacun sonde sa propre cle a la volee via /llm/verifier existant).
PROVIDERS_SYSTEME = ("anthropic", "openai", "gemini", "deepseek", "mistral", "moonshot", "glm")


def _lire() -> dict:
    if not os.path.exists(SANTE_FILE):
        return {}
    try:
        with open(SANTE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _ecrire(d: dict) -> None:
    try:
        os.makedirs(os.path.dirname(SANTE_FILE), exist_ok=True)
        with open(SANTE_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _typer_erreur(e: Exception) -> str:
    """Classe une exception d'appel LLM pour distinguer 'jamais la peine de retenter
    maintenant' (credit/cle) de 'transitoire' (reseau/surcharge, guerison probable vite)."""
    txt = str(e).lower()
    if "credit balance is too low" in txt or "insufficient_quota" in txt or "billing" in txt:
        return "credit_epuise"
    if any(k in txt for k in ("invalid_api_key", "incorrect api key", "unauthorized", "401", "authentication")):
        return "cle_invalide"
    if any(k in txt for k in ("timeout", "connection", "econnreset", "503", "502", "529",
                              "rate limit", "429", "overloaded")):
        return "transitoire"
    return "inconnu"


def _enregistrer(provider: str, ok: bool, *, raison: str = "") -> None:
    with _LOCK:
        d = _lire()
        d[provider] = {"ok": ok, "raison": raison if not ok else "operationnel",
                       "derniere_verif": time.time()}
        _ecrire(d)


def marquer_echec(provider: str, e: Exception) -> str:
    """A appeler par le code appelant quand un appel a 'provider' echoue reellement
    (pas juste une sonde) : met a jour le registre avec le type d'erreur. Renvoie le type."""
    provider = (provider or "").lower()
    typ = _typer_erreur(e)
    # Un echec transitoire n'invalide pas longtemps le provider (TTL court, on retentera vite).
    _enregistrer(provider, ok=False, raison=typ)
    return typ


def marquer_succes(provider: str) -> None:
    _enregistrer((provider or "").lower(), ok=True)


def _sonder(provider: str) -> dict:
    """Ping reel minimal (1 tour, max_tokens bas) pour verifier qu'un provider systeme
    repond. Reutilise credentials_loader (cle systeme) + gateway (adaptateur unifie).
    Ne leve jamais : renvoie toujours un statut, meme en cas d'exception de sonde."""
    try:
        import credentials_loader as _cl
        cle = _cl.cle_provider(provider)
        if not cle and provider != "local":
            return {"ok": False, "raison": "cle_absente", "derniere_verif": time.time()}
        import gateway as _gw
        ctx = _gw.LLMContext(provider=provider, api_key=cle or None)
        client = _gw.client(ctx, tier="leger")
        client.messages.create(max_tokens=8, messages=[{"role": "user", "content": "ping"}])
        return {"ok": True, "raison": "operationnel", "derniere_verif": time.time()}
    except Exception as e:
        return {"ok": False, "raison": _typer_erreur(e), "derniere_verif": time.time()}


def statut(provider: str, *, sonder_si_expire: bool = True) -> dict:
    """Statut courant d'un provider SYSTEME (cache TTL). Si perime (ou jamais teste) et
    sonder_si_expire=True, effectue une sonde active et met a jour le cache.
    Renvoie {ok, raison, derniere_verif}. 'raison' in : operationnel, credit_epuise,
    cle_invalide, cle_absente, transitoire, inconnu, jamais_teste."""
    provider = (provider or "").lower()
    with _LOCK:
        d = _lire()
        entree = d.get(provider)
    if entree is None:
        if not sonder_si_expire:
            return {"ok": False, "raison": "jamais_teste", "derniere_verif": 0.0}
        res = _sonder(provider)
        _enregistrer(provider, res["ok"], raison=res["raison"])
        return res
    age = time.time() - entree.get("derniere_verif", 0.0)
    ttl = TTL_ECHEC_COURT if not entree.get("ok") else TTL_SANTE
    if age <= ttl or not sonder_si_expire:
        return entree
    res = _sonder(provider)
    _enregistrer(provider, res["ok"], raison=res["raison"])
    return res


def providers_operationnels(candidats: list[str] | None = None, *, sonder: bool = True) -> list[str]:
    """Sous-liste de 'candidats' (defaut : tous les providers systeme) actuellement
    operationnels, dans l'ordre d'entree (l'appelant fournit deja l'ordre de preference)."""
    candidats = candidats or list(PROVIDERS_SYSTEME)
    return [p for p in candidats if statut(p, sonder_si_expire=sonder).get("ok")]


def etat() -> dict:
    """Etat lisible de tous les providers connus (pour /health ou debug)."""
    return dict(_lire())


if __name__ == "__main__":
    import tempfile
    print("=" * 60)
    print("NEOGEN - PROVIDER_SANTE : auto-verification")
    print("=" * 60)
    SANTE_FILE = os.path.join(tempfile.mkdtemp(), "providers_sante.json")

    assert _typer_erreur(Exception("Your credit balance is too low to access")) == "credit_epuise"
    assert _typer_erreur(Exception("401 Unauthorized invalid_api_key")) == "cle_invalide"
    assert _typer_erreur(Exception("Connection timeout")) == "transitoire"
    assert _typer_erreur(Exception("something weird")) == "inconnu"
    print("  typage erreur (credit/cle/transitoire/inconnu) : OK")

    marquer_echec("anthropic", Exception("Your credit balance is too low"))
    st = statut("anthropic", sonder_si_expire=False)
    assert st["ok"] is False and st["raison"] == "credit_epuise", st
    print("  marquer_echec + cache (pas de re-sonde immediate) : OK")

    marquer_succes("deepseek")
    st2 = statut("deepseek", sonder_si_expire=False)
    assert st2["ok"] is True
    print("  marquer_succes : OK")

    ops = providers_operationnels(["anthropic", "deepseek"], sonder=False)
    assert ops == ["deepseek"], ops
    print("  providers_operationnels filtre correctement : OK")
    print("=" * 60)
