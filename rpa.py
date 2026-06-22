"""
NEOGEN - Module RPA & Apprentissage par imitation (côté serveur)

Ce module gère :
  1. La file d'attente globale d'actions RPA (RpaQueue) envoyées par les conteneurs
     ou rejouées depuis les imitations.
  2. L'historique et la journalisation des actions RPA sous la gouvernance NEOGEN.
  3. L'apprentissage par imitation : enregistrement, stockage (JSON local),
     révision et relecture de séquences d'actions utilisateur.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-21.
"""

from __future__ import annotations
import os
import json
import uuid
import time
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
IMITATIONS_DIR = os.path.join(DATA_DIR, "imitations")
RPA_LOG_FILE = os.path.join(DATA_DIR, "rpa_logs.jsonl")

# File d'attente en mémoire pour l'agent RPA
_QUEUE: list[dict] = []
# Session d'enregistrement d'imitation active
_ACTIVE_RECORDING: list[dict] = []
_IS_RECORDING: bool = False
_LAST_PING_TIME: float = 0.0

# ── Apprentissage continu (non-draconien) ─────────────────────────────────────
# Au lieu d'un enregistrement manuel start/stop, l'agent observe en continu (si
# active par l'utilisateur), segmente le flux par pauses, et quand une MEME
# sequence revient -> il l'apprend automatiquement comme routine reutilisable.
_CONTINUOUS: bool = False
_SEGMENT: list[dict] = []           # segment d'actions en cours de construction
_LAST_ACTION_TIME: float = 0.0      # pour couper les segments aux pauses
_SEEN_SIGNATURES: dict[str, int] = {}  # signature de sequence -> nb d'occurrences
_AUTO_LEARNED: list[dict] = []      # routines apprises automatiquement (resume)
IDLE_GAP = 4.0                      # secondes d'inactivite -> fin de segment
MIN_SEGMENT = 3                     # actions minimum pour qu'un segment compte
REPEAT_THRESHOLD = 2               # nb d'occurrences avant apprentissage auto

def ping_agent():
    global _LAST_PING_TIME
    _LAST_PING_TIME = time.time()

def is_agent_connected() -> bool:
    return (time.time() - _LAST_PING_TIME) < 5.0


class RpaQueue:
    @staticmethod
    def push(action: dict) -> str:
        """Ajoute une action à la file d'attente avec un statut 'pending'."""
        action_id = action.get("id") or str(uuid.uuid4())
        item = {
            "id": action_id,
            "action": action.get("action", "click"),
            "x": action.get("x"),
            "y": action.get("y"),
            "amount": action.get("amount", 3),
            "text": action.get("text", ""),
            "keys": action.get("keys", []),
            "key": action.get("key", ""),
            "url": action.get("url", ""),
            "guard": action.get("guard", ""),
            "interval": action.get("interval", 0.05),
            "status": "pending",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "error": None
        }
        _QUEUE.append(item)
        logger.info(f"[RPA QUEUE] Action push: {item['action']} ({action_id})")
        return action_id

    @staticmethod
    def push_multiple(actions: list[dict]) -> list[str]:
        """Ajoute une liste d'actions d'un coup."""
        ids = []
        for act in actions:
            ids.append(RpaQueue.push(act))
        return ids

    @staticmethod
    def get_pending() -> dict | None:
        """Renvoie la première action en attente ('pending') et la passe en 'executing'."""
        for item in _QUEUE:
            if item["status"] == "pending":
                item["status"] = "executing"
                return item
        return None

    @staticmethod
    def set_result(action_id: str, status: str, error: str | None = None) -> bool:
        """Met à jour le statut d'une action et écrit dans le journal persistant."""
        for item in _QUEUE:
            if item["id"] == action_id:
                item["status"] = status
                item["error"] = error
                item["finished_at"] = datetime.now().isoformat(timespec="seconds")
                
                # Journalisation persistante sous NEOGEN
                RpaQueue._log_action(item)
                
                # Nettoyage si exécuté ou échoué
                if status in ("executed", "failed", "rejected"):
                    try:
                        _QUEUE.remove(item)
                    except ValueError:
                        pass
                return True
        return False

    @staticmethod
    def clear() -> int:
        """Arrêt d'urgence : vide toute la file d'attente RPA."""
        count = len(_QUEUE)
        # Log de l'arrêt d'urgence
        for item in _QUEUE:
            item["status"] = "cancelled"
            item["error"] = "Emergency Stop triggered"
            RpaQueue._log_action(item)
        _QUEUE.clear()
        logger.warning(f"[RPA QUEUE] Emergency stop: {count} actions cancelled.")
        return count

    @staticmethod
    def list_queue() -> list[dict]:
        """Renvoie l'état actuel de la file."""
        return list(_QUEUE)

    @staticmethod
    def _log_action(item: dict):
        """Écrit l'action dans le journal d'actions NEOGEN."""
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(RPA_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Apprentissage par imitation (Imitation Learning)
# ---------------------------------------------------------------------------

def start_recording() -> bool:
    """Démarre une session d'enregistrement d'imitation."""
    global _ACTIVE_RECORDING, _IS_RECORDING
    _ACTIVE_RECORDING = []
    _IS_RECORDING = True
    logger.info("[IMITATION] Enregistrement démarré.")
    return True

def is_recording() -> bool:
    return _IS_RECORDING

def _normaliser_action(action: dict) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "action": action.get("action", "click"),
        "x": action.get("x"),
        "y": action.get("y"),
        "amount": action.get("amount", 3),
        "text": action.get("text", ""),
        "keys": action.get("keys", []),
        "key": action.get("key", ""),
        "interval": action.get("interval", 0.05),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }


def add_recorded_action(action: dict) -> None:
    """Ajoute une action interceptée. Va vers l'enregistrement manuel (si actif)
    ET/OU vers l'apprentissage continu (si actif)."""
    item = _normaliser_action(action)
    if _IS_RECORDING:
        _ACTIVE_RECORDING.append(item)
        logger.info(f"[IMITATION] Action enregistrée : {item['action']}")
    if _CONTINUOUS:
        _continu_observer(item)


# ── Apprentissage continu : observation + détection de routines récurrentes ────

def set_continuous(enabled: bool) -> bool:
    """Active/désactive l'apprentissage continu. À l'arrêt, finalise le segment."""
    global _CONTINUOUS, _SEGMENT
    if enabled:
        _CONTINUOUS = True
        logger.info("[APPRENTISSAGE] Mode continu activé.")
    else:
        _continu_finaliser_segment()
        _CONTINUOUS = False
        logger.info("[APPRENTISSAGE] Mode continu désactivé.")
    return _CONTINUOUS


def is_continuous() -> bool:
    return _CONTINUOUS


def _signature_segment(seg: list[dict]) -> str:
    """Signature stable d'une séquence : la suite des types d'actions."""
    return ">".join(a.get("action", "?") for a in seg)


def _continu_observer(item: dict) -> None:
    """Ajoute l'action au segment courant ; coupe le segment après une pause."""
    global _SEGMENT, _LAST_ACTION_TIME
    now = time.time()
    if _SEGMENT and (now - _LAST_ACTION_TIME) > IDLE_GAP:
        _continu_finaliser_segment()
    _SEGMENT.append(item)
    _LAST_ACTION_TIME = now


def _continu_finaliser_segment() -> None:
    """Clôt le segment en cours : si une même séquence revient, l'apprend en routine."""
    global _SEGMENT, _SEEN_SIGNATURES
    seg, _SEGMENT = _SEGMENT, []
    if len(seg) < MIN_SEGMENT:
        return
    sig = _signature_segment(seg)
    _SEEN_SIGNATURES[sig] = _SEEN_SIGNATURES.get(sig, 0) + 1
    occ = _SEEN_SIGNATURES[sig]
    logger.info(f"[APPRENTISSAGE] Segment {sig} vu {occ} fois.")
    if occ == REPEAT_THRESHOLD:
        # Séquence récurrente -> on l'apprend automatiquement.
        nom = f"Routine apprise ({len(seg)} etapes)"
        rec = _sauver_routine(nom, seg, auto=True)
        if rec:
            _AUTO_LEARNED.append({"id": rec["id"], "name": nom,
                                  "steps": len(seg), "signature": sig})
            logger.info(f"[APPRENTISSAGE] Routine récurrente apprise : {rec['id']}")


def _sauver_routine(name: str, actions: list[dict], auto: bool = False) -> dict | None:
    """Persiste une séquence comme routine réutilisable (même format que stop_recording)."""
    if not actions:
        return None
    os.makedirs(IMITATIONS_DIR, exist_ok=True)
    rec_id = str(uuid.uuid4())[:8]
    record = {
        "id": rec_id,
        "name": name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "auto": auto,
        "actions": actions,
    }
    with open(os.path.join(IMITATIONS_DIR, f"{rec_id}.json"), "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return record


def continuous_status() -> dict:
    """État de l'apprentissage continu (pour l'UI)."""
    return {
        "enabled": _CONTINUOUS,
        "segment_len": len(_SEGMENT),
        "signatures": len(_SEEN_SIGNATURES),
        "learned": _AUTO_LEARNED[-10:],
    }

def stop_recording(name: str) -> dict | None:
    """Arrête l'enregistrement et le persiste dans data/imitations/{name}.json."""
    global _IS_RECORDING, _ACTIVE_RECORDING
    if not _IS_RECORDING:
        return None
    _IS_RECORDING = False
    
    os.makedirs(IMITATIONS_DIR, exist_ok=True)
    slug_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name).lower()
    filepath = os.path.join(IMITATIONS_DIR, f"{slug_name}.json")
    
    record = {
        "name": name,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "actions": _ACTIVE_RECORDING
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
        
    logger.info(f"[IMITATION] Enregistrement '{name}' sauvegardé avec {len(_ACTIVE_RECORDING)} actions.")
    _ACTIVE_RECORDING = []
    return record

def list_recordings() -> list[dict]:
    """Liste tous les enregistrements d'imitation disponibles."""
    if not os.path.exists(IMITATIONS_DIR):
        return []
    out = []
    for filename in os.listdir(IMITATIONS_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(IMITATIONS_DIR, filename)
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)
                    out.append({
                        "id": filename[:-5],
                        "name": data.get("name", filename[:-5]),
                        "created_at": data.get("created_at"),
                        "steps": len(data.get("actions", []))
                    })
            except Exception as e:
                logger.error(f"Erreur de lecture de {filename}: {e}")
    out.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return out

def get_recording(rec_id: str) -> dict | None:
    """Récupère le détail d'une imitation."""
    filepath = os.path.join(IMITATIONS_DIR, f"{rec_id}.json")
    if not os.path.exists(filepath):
        return None
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)

def update_recording(rec_id: str, actions: list[dict]) -> bool:
    """Met à jour les actions d'un enregistrement (édition par l'utilisateur)."""
    filepath = os.path.join(IMITATIONS_DIR, f"{rec_id}.json")
    if not os.path.exists(filepath):
        return False
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    data["actions"] = actions
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True

def delete_recording(rec_id: str) -> bool:
    """Supprime un enregistrement d'imitation."""
    filepath = os.path.join(IMITATIONS_DIR, f"{rec_id}.json")
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False

def replay_recording(rec_id: str) -> list[str] | None:
    """Charge l'imitation et pousse toutes ses actions dans la file d'attente RPA."""
    rec = get_recording(rec_id)
    if not rec:
        return None
    actions = rec.get("actions", [])
    logger.info(f"[RPA QUEUE] Replay de l'imitation '{rec_id}' ({len(actions)} actions)")
    return RpaQueue.push_multiple(actions)


# ---------------------------------------------------------------------------
# Intercepteur de sortie standard des conteneurs
# ---------------------------------------------------------------------------
def intercepter_sorties_rpa(stdout: str) -> list[dict]:
    """
    Parcourt le stdout d'un conteneur pour y chercher les commandes RPA
    au format RPA_ACTION:{...}. Pousse chaque action valide dans la file RPA.
    """
    actions_trouvees = []
    for line in stdout.splitlines():
        if line.startswith("RPA_ACTION:"):
            payload_str = line[len("RPA_ACTION:"):].strip()
            try:
                action = json.loads(payload_str)
                if isinstance(action, dict) and "action" in action:
                    actions_trouvees.append(action)
            except Exception as e:
                logger.error(f"[RPA DETECT] Erreur de parsing de l'action: {payload_str} : {e}")
    if actions_trouvees:
        RpaQueue.push_multiple(actions_trouvees)
        logger.info(f"[RPA DETECT] {len(actions_trouvees)} actions interceptées et empilées.")
    return actions_trouvees
