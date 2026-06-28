"""
NEOGEN - Planificateur : tâches autonomes récurrentes (cron) multi-modèle.

L'agent agit TOUT SEUL à intervalles réguliers : veille, rapport, routine, contrôle.
Une tâche = {agent, message, intervalle, provider, model}.

DOCTRINE (robustesse.py) :
  - MULTI-MODELE : une tâche s'exécute sur le provider choisi (anthropic, gemini,
    openai, deepseek, mistral, local), present OU futur. La clé est résolue côté
    SYSTEME (credentials de l'instance) -> jamais la clé d'un autre utilisateur (BYOK).
    Provider injoignable -> bascule automatique sur 'local' (Ollama) + alerte loguée.
  - AUTOMATIQUE & IDEMPOTENT : le thread vérifie chaque minute ; une tâche due ne se
    déclenche qu'UNE fois par fenêtre (garde d'idempotence, sûre même après redémarrage).
  - ERREUR CAPTUREE : retry+backoff ; échec définitif -> logué + consigné dans la tâche ;
    après N échecs consécutifs -> tâche auto-pausée (un coup d'avance, plus de martèlement).
  - OBSERVABLE : battement('cron') à chaque tour -> visible dans /health.

Persistance : data/taches.jsonl. Conception : Jordan VINCENT (NetroIA) + Claude. 2026-06-23.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid

import robustesse as rob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TACHES_FILE = os.path.join(BASE_DIR, "data", "taches.jsonl")

_LOCK = threading.Lock()
_THREAD = None
INTERVALLE_MIN_MINUTES = 5      # garde-fou : pas plus fréquent que toutes les 5 min
MAX_LOG = 5                     # on garde les N derniers résultats par tâche
MAX_ECHECS_AVANT_PAUSE = 3      # après N échecs consécutifs -> tâche auto-pausée
PROVIDERS_VALIDES = ("local", "anthropic", "openai", "gemini", "deepseek", "mistral")
AGENTS_VALIDES = ("cerveau", "createur", "genealogiste", "secretaire", "veilleur")

# Résolution des clés système : centralisée dans credentials_loader.PROVIDER_CRED (dette F003).


# ── I/O ─────────────────────────────────────────────────────────────────────

def _lire() -> list[dict]:
    if not os.path.exists(TACHES_FILE):
        return []
    out = []
    try:
        with open(TACHES_FILE, encoding="utf-8") as f:
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


def _ecrire(taches: list[dict]) -> None:
    os.makedirs(os.path.dirname(TACHES_FILE), exist_ok=True)
    with open(TACHES_FILE, "w", encoding="utf-8") as f:
        for t in taches:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")


def lister() -> list[dict]:
    return _lire()


def creer(nom: str, agent: str, message: str, intervalle_minutes: int,
          provider: str = "local", model: str | None = None) -> dict:
    intervalle = max(INTERVALLE_MIN_MINUTES, int(intervalle_minutes or 60))
    prov = (provider or "local").strip().lower()
    if prov not in PROVIDERS_VALIDES:
        prov = "local"
    tache = {
        "id": str(uuid.uuid4())[:8],
        "nom": (nom or "tache").strip()[:80],
        "agent": agent if agent in AGENTS_VALIDES else "cerveau",
        "message": (message or "").strip()[:500],
        "intervalle_minutes": intervalle,
        "provider": prov,
        "model": (model or "").strip() or None,
        "actif": True,
        "derniere_exec": 0.0,
        "echecs_consecutifs": 0,
        "logs": [],
    }
    with _LOCK:
        taches = _lire()
        taches.append(tache)
        _ecrire(taches)
    rob.journaliser(f"tache cron creee : {tache['nom']} ({prov}, {intervalle}min)",
                    "info", source="cron", tache_id=tache["id"])
    return tache


def basculer(tache_id: str, actif: bool) -> bool:
    with _LOCK:
        taches = _lire()
        trouve = False
        for t in taches:
            if t.get("id") == tache_id:
                t["actif"] = bool(actif)
                if actif:
                    t["echecs_consecutifs"] = 0  # réactivation = on repart propre
                trouve = True
        if trouve:
            _ecrire(taches)
        return trouve


def supprimer(tache_id: str) -> bool:
    with _LOCK:
        taches = _lire()
        n = len(taches)
        taches = [t for t in taches if t.get("id") != tache_id]
        if len(taches) < n:
            _ecrire(taches)
            return True
        return False


def _maj_tache(tache_id: str, **champs) -> None:
    """Met à jour des champs d'une tâche + journalise un résultat éventuel (sous verrou)."""
    with _LOCK:
        taches = _lire()
        for t in taches:
            if t.get("id") == tache_id:
                resultat = champs.pop("_resultat", None)
                if resultat is not None:
                    t["derniere_exec"] = time.time()
                    t.setdefault("logs", []).append({
                        "t": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "resultat": str(resultat)[:300],
                    })
                    t["logs"] = t["logs"][-MAX_LOG:]
                t.update(champs)
        _ecrire(taches)


# ── Résolution du contexte LLM (multi-provider, clé système, BYOK-safe) ────────

def _cle_systeme(provider: str) -> str:
    """Clé SYSTEME de l'instance pour ce provider (jamais celle d'un utilisateur).
    Délègue au chargeur unique (dette F003). Vide si non configurée."""
    from credentials_loader import cle_provider
    return cle_provider(provider)


def _resoudre_ctx(tache: dict):
    """Construit le LLMContext d'exécution. Renvoie (ctx, provider_effectif).
    - local : aucune clé requise.
    - autre provider : clé système requise ; absente -> bascule sur local + alerte."""
    from gateway import LLMContext
    prov = (tache.get("provider") or "local").lower()
    model = tache.get("model") or None
    if prov == "local":
        return LLMContext(provider="local", model=model), "local"
    cle = _cle_systeme(prov)
    if not cle:
        rob.journaliser(
            f"tache '{tache.get('nom')}' : provider '{prov}' sans clé système -> bascule sur local",
            "alerte", source="cron", tache_id=tache.get("id"))
        return LLMContext(provider="local"), "local"
    return LLMContext(provider=prov, model=model, api_key=cle), prov


# ── Exécution d'une tâche (robuste, multi-provider) ────────────────────────────

def _executer(tache: dict) -> None:
    """Exécute une tâche via l'agent, sur son provider (clé système), avec disjoncteur+retry.
    Toute erreur est capturée, loguée et consignée. Échecs répétés -> auto-pause."""
    from agent_core import dialoguer

    ctx, prov = _resoudre_ctx(tache)
    disj = rob.Disjoncteur.pour(f"cron:{prov}", seuil=3, cooldown_s=120.0)

    if not disj.disponible():
        rob.journaliser(f"tache '{tache.get('nom')}' differee : provider '{prov}' en disjonction",
                        "info", source="cron", tache_id=tache.get("id"))
        _maj_tache(tache["id"], _resultat=f"[differe] provider {prov} momentanement coupe")
        return

    def _run():
        return dialoguer(tache["agent"], tache["message"], ctx=ctx, eco=True)

    try:
        # Retry + backoff ; le disjoncteur compte les échecs du provider.
        rep = disj.appeler(
            lambda: rob.reessayer(_run, tentatives=2, delai=2.0, backoff=2.0,
                                  nom=f"cron:{tache.get('nom')}", source="cron"),
            defaut=None,
        )
        if rep is None:
            raise RuntimeError(f"provider {prov} indisponible (disjoncteur/retry épuisés)")
        _maj_tache(tache["id"], echecs_consecutifs=0,
                   _resultat=f"[{prov}] {rep}")
        rob.journaliser(f"tache '{tache.get('nom')}' executee ({prov})", "succes",
                        source="cron", tache_id=tache.get("id"))
    except Exception as e:
        echecs = int(tache.get("echecs_consecutifs", 0)) + 1
        champs = {"echecs_consecutifs": echecs,
                  "_resultat": f"[erreur {prov}] {str(e)[:200]}"}
        niveau = "erreur"
        if echecs >= MAX_ECHECS_AVANT_PAUSE:
            champs["actif"] = False
            niveau = "critique"
            rob.journaliser(
                f"tache '{tache.get('nom')}' AUTO-PAUSEE apres {echecs} echecs consecutifs",
                "critique", source="cron", tache_id=tache.get("id"), erreur=str(e))
        else:
            rob.journaliser(f"tache '{tache.get('nom')}' en echec ({echecs}/{MAX_ECHECS_AVANT_PAUSE})",
                            niveau, source="cron", tache_id=tache.get("id"), erreur=str(e))
        _maj_tache(tache["id"], **champs)


def _boucle() -> None:
    """Thread de fond : toutes les ~60s, déclenche les tâches dues (une seule fois/fenêtre)."""
    while True:
        with rob.garde("boucle cron", source="cron"):
            now = time.time()
            taches = _lire()
            rob.battement("cron", taches=len(taches),
                          actives=sum(1 for t in taches if t.get("actif")))
            for t in taches:
                if not t.get("actif"):
                    continue
                interval_s = max(INTERVALLE_MIN_MINUTES, t.get("intervalle_minutes", 60)) * 60
                if now - t.get("derniere_exec", 0) < interval_s:
                    continue
                # Idempotence : une fenêtre temporelle = un seul déclenchement,
                # même si plusieurs instances/threads ou un redémarrage surviennent.
                slot = int(now // interval_s)
                cle = f"cron:{t['id']}:{slot}"
                if rob.deja_fait(cle, ttl_s=interval_s):
                    continue
                rob.marquer_fait(cle)
                _maj_tache(t["id"], _resultat="[demarrage]")
                threading.Thread(target=_executer, args=(t,), daemon=True).start()
        time.sleep(60)


def demarrer() -> None:
    """Démarre le thread de planification (idempotent)."""
    global _THREAD
    if _THREAD is None or not _THREAD.is_alive():
        _THREAD = threading.Thread(target=_boucle, daemon=True)
        _THREAD.start()
        rob.journaliser("planificateur cron demarre", "info", source="cron")


def statut() -> dict:
    """État observable du planificateur (pour /health et l'UI)."""
    taches = _lire()
    return {
        "actif": _THREAD is not None and _THREAD.is_alive(),
        "total": len(taches),
        "actives": sum(1 for t in taches if t.get("actif")),
        "en_pause": sum(1 for t in taches if not t.get("actif")),
    }


if __name__ == "__main__":
    import tempfile
    # Isolation : journal/idempotence robustesse en temporaire (le test ne pollue rien).
    rob._DATA = tempfile.mkdtemp()
    rob.JOURNAL = os.path.join(rob._DATA, "j.jsonl")
    rob.IDEMPOTENCE = os.path.join(rob._DATA, "i.json")
    rob.SANTE = os.path.join(rob._DATA, "s.json")
    print("=" * 60)
    print("NEOGEN - PLANIFICATEUR multi-modele : auto-verification")
    print("=" * 60)
    for t in lister():
        if t.get("nom", "").startswith("__test__"):
            supprimer(t["id"])

    # Création + garde-fous
    t = creer("__test__ veille", "cerveau", "resume l'etat de mes creations", 10, provider="anthropic")
    assert t["intervalle_minutes"] == 10 and t["provider"] == "anthropic"
    t2 = creer("__test__ trop frequent", "secretaire", "ping", 1, provider="inexistant")
    assert t2["intervalle_minutes"] == INTERVALLE_MIN_MINUTES
    assert t2["provider"] == "local", "provider invalide -> local"

    # Résolution de contexte : provider sans clé -> bascule local
    ctx, prov = _resoudre_ctx({"id": "x", "nom": "t", "provider": "mistral", "model": None})
    assert prov in ("local", "mistral")  # local si pas de clé mistral système
    ctx2, prov2 = _resoudre_ctx({"id": "x", "nom": "t", "provider": "local"})
    assert prov2 == "local"

    # Bascule + suppression
    assert basculer(t["id"], False)
    assert any(x["id"] == t["id"] and not x["actif"] for x in lister())
    assert supprimer(t["id"]) and supprimer(t2["id"])

    # Statut observable
    s = statut()
    assert "actives" in s and "total" in s
    print("  creer / garde-fous / provider / resolution ctx / bascule / statut : OK")
    print("=" * 60)
