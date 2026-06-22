"""
NEOGEN - Planificateur : tâches autonomes récurrentes (cron léger).

L'agent agit TOUT SEUL à intervalles réguliers : veille, rapport quotidien,
rejouer une routine, vérifier quelque chose. Une tâche = {agent, message,
intervalle}. Un thread de fond vérifie chaque minute les tâches dues et les
exécute via l'agent.

SÉCURITÉ BYOK : les tâches autonomes tournent sur le MODELE LOCAL (Ollama, gratuit,
aucune clé) — on ne persiste JAMAIS la clé d'un utilisateur pour l'exécuter en
arrière-plan. L'autonomie ne brûle donc aucun crédit payant.

Persistance : data/taches.jsonl. Conception : Jordan VINCENT (NetroIA) + Claude. 2026-06-22.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TACHES_FILE = os.path.join(BASE_DIR, "data", "taches.jsonl")

_LOCK = threading.Lock()
_THREAD = None
INTERVALLE_MIN_MINUTES = 5     # garde-fou : pas plus fréquent que toutes les 5 min
MAX_LOG = 5                    # on garde les N derniers résultats par tâche


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


def creer(nom: str, agent: str, message: str, intervalle_minutes: int) -> dict:
    intervalle = max(INTERVALLE_MIN_MINUTES, int(intervalle_minutes or 60))
    tache = {
        "id": str(uuid.uuid4())[:8],
        "nom": (nom or "tache").strip()[:80],
        "agent": agent if agent in ("cerveau", "createur", "genealogiste", "secretaire") else "cerveau",
        "message": (message or "").strip()[:500],
        "intervalle_minutes": intervalle,
        "actif": True,
        "derniere_exec": 0.0,
        "logs": [],
    }
    with _LOCK:
        taches = _lire()
        taches.append(tache)
        _ecrire(taches)
    return tache


def basculer(tache_id: str, actif: bool) -> bool:
    with _LOCK:
        taches = _lire()
        trouve = False
        for t in taches:
            if t.get("id") == tache_id:
                t["actif"] = bool(actif)
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


def _journaliser(tache_id: str, resultat: str) -> None:
    with _LOCK:
        taches = _lire()
        for t in taches:
            if t.get("id") == tache_id:
                t["derniere_exec"] = time.time()
                t.setdefault("logs", []).append({
                    "t": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "resultat": (resultat or "")[:300],
                })
                t["logs"] = t["logs"][-MAX_LOG:]
        _ecrire(taches)


def _executer(tache: dict) -> None:
    """Exécute une tâche via l'agent, sur le modèle LOCAL (gratuit, sans clé)."""
    try:
        from agent_core import dialoguer
        from gateway import LLMContext
        # Contexte local : aucune clé persistée, aucun crédit payant consommé.
        ctx = LLMContext(provider="local")
        rep = dialoguer(tache["agent"], tache["message"], ctx=ctx, eco=True)
        _journaliser(tache["id"], rep)
    except Exception as e:
        _journaliser(tache["id"], f"[erreur] {e}")


def _boucle() -> None:
    """Thread de fond : toutes les ~60s, exécute les tâches dues."""
    while True:
        try:
            now = time.time()
            for t in _lire():
                if not t.get("actif"):
                    continue
                interval_s = t.get("intervalle_minutes", 60) * 60
                if now - t.get("derniere_exec", 0) >= interval_s:
                    # On marque AVANT d'exécuter pour éviter les doubles déclenchements.
                    _journaliser(t["id"], "[demarrage]")
                    threading.Thread(target=_executer, args=(t,), daemon=True).start()
        except Exception:
            pass
        time.sleep(60)


def demarrer() -> None:
    """Démarre le thread de planification (idempotent)."""
    global _THREAD
    if _THREAD is None or not _THREAD.is_alive():
        _THREAD = threading.Thread(target=_boucle, daemon=True)
        _THREAD.start()


if __name__ == "__main__":
    print("=" * 60)
    print("NEOGEN - PLANIFICATEUR : auto-vérification")
    print("=" * 60)
    for t in lister():
        if t.get("nom", "").startswith("__test__"):
            supprimer(t["id"])
    t = creer("__test__ veille", "cerveau", "resume l'etat de mes creations", 10)
    assert t["intervalle_minutes"] == 10
    assert t["agent"] == "cerveau"
    # garde-fou intervalle minimum
    t2 = creer("__test__ trop frequent", "secretaire", "ping", 1)
    assert t2["intervalle_minutes"] == INTERVALLE_MIN_MINUTES, t2["intervalle_minutes"]
    assert basculer(t["id"], False)
    assert any(x["id"] == t["id"] and not x["actif"] for x in lister())
    assert supprimer(t["id"]) and supprimer(t2["id"])
    print("  creer / garde-fou intervalle / basculer / supprimer : OK")
    print("=" * 60)
