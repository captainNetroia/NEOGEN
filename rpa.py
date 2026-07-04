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
CONTINU_STATE_FILE = os.path.join(DATA_DIR, "rpa_continuous.json")  # etat persiste du mode continu

# Etat RPA scope par utilisateur : chaque user_id a sa propre file, ses propres
# resultats, son propre contexte navigateur, sa propre derniere capture d'ecran
# et son propre horodatage de ping. Cloisonnement : la file/l'ecran/le contexte
# d'un utilisateur ne sont jamais visibles ni modifiables par un autre.
def _etat_defaut() -> dict:
    return {
        "queue": [],
        "results": {},
        "browser_ctx": {"url": "", "titre": "", "ts": 0.0},
        "last_screenshot": {"b64": None, "ts": 0.0},
        "last_ping_time": 0.0,
    }


_ETATS: dict[str, dict] = {}


def _etat(user_id: str) -> dict:
    return _ETATS.setdefault(user_id, _etat_defaut())


# Session d'enregistrement d'imitation active (mono-utilisateur : un seul
# enregistrement manuel a la fois dans tout le systeme, comme avant le scoping ;
# c'est un mode explicite start/stop, pas un flux permanent comme la queue RPA).
_ACTIVE_RECORDING: list[dict] = []
_IS_RECORDING: bool = False

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


def store_screenshot(user_id: str, b64: str) -> None:
    """Stocke la dernière capture d'écran envoyée par l'agent local de cet utilisateur."""
    e = _etat(user_id)
    e["last_screenshot"]["b64"] = b64
    e["last_screenshot"]["ts"] = time.time()


def get_screenshot(user_id: str, apres: float = 0.0) -> str | None:
    """Renvoie la dernière capture de cet utilisateur si plus récente que 'apres'."""
    shot = _etat(user_id)["last_screenshot"]
    if shot["b64"] and shot["ts"] > apres:
        return shot["b64"]
    return None


def request_screenshot(user_id: str) -> float:
    """Demande une capture d'écran à l'agent local de cet utilisateur. Renvoie
    l'instant de la demande (sert à savoir si la capture reçue est postérieure)."""
    t = time.time()
    RpaQueue.push(user_id, {"action": "screenshot", "guard": "screenshot"})
    return t


def wait_result(user_id: str, action_id: str, timeout: float = 30.0) -> dict:
    """Attend le résultat d'une action RPA de cet utilisateur (bloquant).
    Retourne {status, error}. status : 'executed' | 'failed' | 'rejected' | 'timeout'."""
    results = _etat(user_id)["results"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        if action_id in results:
            return results.pop(action_id)
        time.sleep(0.2)
    return {"status": "timeout", "error": f"aucun résultat après {timeout}s"}


def store_browser_context(user_id: str, ctx: dict) -> None:
    """Reçoit et stocke le contexte navigateur envoyé par l'agent hôte de cet utilisateur."""
    b = _etat(user_id)["browser_ctx"]
    b["url"] = ctx.get("url", "")
    b["titre"] = ctx.get("titre", "")
    b["ts"] = time.time()


def get_browser_context(user_id: str) -> dict:
    """Retourne le dernier contexte navigateur connu de cet utilisateur (url, titre, ts)."""
    return dict(_etat(user_id)["browser_ctx"])


def request_browser_context(user_id: str) -> float:
    """Demande à l'agent hôte de cet utilisateur de lire le contexte navigateur actif.
    Retourne le timestamp de la demande."""
    t = time.time()
    RpaQueue.push(user_id, {"action": "get_browser_context"})
    return t


def ping_agent(user_id: str):
    _etat(user_id)["last_ping_time"] = time.time()

def is_agent_connected(user_id: str) -> bool:
    return (time.time() - _etat(user_id)["last_ping_time"]) < 5.0


# ── Liste noire d'actions dangereuses ───────────────────────────────────────
# Garde-fou fail-closed avant toute mise en file : une action qui matche est
# rejetee ici, jamais transmise a l'agent local. Vise les 2 familles d'abus
# les plus dangereuses pour un RPA public : ouvrir un handler non-http (acces
# fichier local / execution JS hors navigateur) et invoquer un shell systeme
# (via la combinaison Win+R puis frappe d'une commande, la voie la plus directe
# pour un agent RPA d'obtenir une execution de code arbitraire sur l'hote).
_SCHEMES_URL_INTERDITS = ("file:", "javascript:", "data:", "vbscript:")
_COMMANDES_SHELL_INTERDITES = (
    "cmd", "powershell", "pwsh", "regedit", "certutil", "mshta",
    "wscript", "cscript", "bitsadmin", "rundll32",
)


class ActionRpaRefusee(Exception):
    """Levee quand une action RPA matche la liste noire. Message propre, jamais
    d'exception qui fuite au client."""


def _valider_action_liste_noire(action: dict) -> None:
    """Fail-closed : lève ActionRpaRefusee si l'action est dans la liste noire.
    Ne bloque jamais autre chose que les motifs explicitement identifiés."""
    act_type = (action.get("action") or "").strip().lower()

    if act_type == "open_url":
        url = (action.get("url") or "").strip().lower()
        if any(url.startswith(s) for s in _SCHEMES_URL_INTERDITS):
            raise ActionRpaRefusee(f"Schema d'URL non autorise : {url[:30]}")

    if act_type == "type":
        texte = (action.get("text") or "").strip().lower()
        if any(cmd in texte for cmd in _COMMANDES_SHELL_INTERDITES):
            raise ActionRpaRefusee("Texte contenant une commande systeme interdite.")

    if act_type == "hotkey":
        keys = [str(k).strip().lower() for k in (action.get("keys") or [])]
        # Win+R (execution de commande) : le combo lui-meme est inoffensif, mais
        # on le bloque par prudence car il ouvre la porte a n'importe quelle saisie
        # ensuite (la frappe suivante n'est pas forcement liee dans la meme requete).
        if set(keys) == {"win", "r"} or ("win" in keys and "r" in keys and len(keys) == 2):
            raise ActionRpaRefusee("Combinaison Win+R non autorisee (ouverture Executer Windows).")


class RpaQueue:
    @staticmethod
    def push(user_id: str, action: dict) -> str:
        """Ajoute une action à la file d'attente de cet utilisateur, statut 'pending'.
        Leve ActionRpaRefusee si l'action matche la liste noire (fail-closed)."""
        _valider_action_liste_noire(action)
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
        _etat(user_id)["queue"].append(item)
        logger.info(f"[RPA QUEUE] Action push: {item['action']} ({action_id}) user={user_id}")
        return action_id

    @staticmethod
    def push_multiple(user_id: str, actions: list[dict]) -> list[str]:
        """Ajoute une liste d'actions d'un coup pour cet utilisateur.
        Atomique : si une seule action de la liste matche la liste noire, AUCUNE
        n'est poussee (evite qu'une sequence partiellement malveillante s'execute
        en partie avant le refus)."""
        for act in actions:
            _valider_action_liste_noire(act)
        ids = []
        for act in actions:
            ids.append(RpaQueue.push(user_id, act))
        return ids

    @staticmethod
    def get_pending(user_id: str) -> dict | None:
        """Renvoie la première action en attente de cet utilisateur et la passe en 'executing'."""
        for item in _etat(user_id)["queue"]:
            if item["status"] == "pending":
                item["status"] = "executing"
                return item
        return None

    @staticmethod
    def set_result(user_id: str, action_id: str, status: str, error: str | None = None) -> bool:
        """Met à jour le statut d'une action de cet utilisateur et journalise."""
        queue = _etat(user_id)["queue"]
        for item in queue:
            if item["id"] == action_id:
                item["status"] = status
                item["error"] = error
                item["finished_at"] = datetime.now().isoformat(timespec="seconds")

                # Journalisation persistante sous NEOGEN
                RpaQueue._log_action(user_id, item)

                # Stocker le résultat AVANT de retirer (pour wait_result)
                if status in ("executed", "failed", "rejected"):
                    _etat(user_id)["results"][action_id] = {"status": status, "error": error}
                    try:
                        queue.remove(item)
                    except ValueError:
                        pass
                return True
        return False

    @staticmethod
    def clear(user_id: str) -> int:
        """Arrêt d'urgence : vide la file d'attente RPA de cet utilisateur."""
        queue = _etat(user_id)["queue"]
        count = len(queue)
        for item in queue:
            item["status"] = "cancelled"
            item["error"] = "Emergency Stop triggered"
            RpaQueue._log_action(user_id, item)
        queue.clear()
        logger.warning(f"[RPA QUEUE] Emergency stop: {count} actions cancelled. user={user_id}")
        return count

    @staticmethod
    def list_queue(user_id: str) -> list[dict]:
        """Renvoie l'état actuel de la file de cet utilisateur."""
        return list(_etat(user_id)["queue"])

    @staticmethod
    def _log_action(user_id: str, item: dict):
        """Écrit l'action dans le journal d'actions NEOGEN, avec l'utilisateur proprietaire."""
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(RPA_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({**item, "user_id": user_id}, ensure_ascii=False) + "\n")


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

def _continu_charger_etat() -> bool:
    """Restaure l'etat du mode continu depuis le disque (survit aux redemarrages)."""
    try:
        if os.path.exists(CONTINU_STATE_FILE):
            with open(CONTINU_STATE_FILE, encoding="utf-8") as f:
                return bool(json.load(f).get("enabled", False))
    except Exception:
        pass
    return False


def _continu_sauver_etat(enabled: bool) -> None:
    """Persiste l'etat du mode continu. Tolerant : un echec disque ne casse rien."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CONTINU_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"enabled": bool(enabled)}, f)
    except Exception as e:
        logger.warning(f"[APPRENTISSAGE] etat continu non persiste : {e}")


def set_continuous(enabled: bool) -> bool:
    """Active/désactive l'apprentissage continu. À l'arrêt, finalise le segment.
    L'etat est persiste : il survit aux redemarrages du conteneur (ne se coupe plus seul)."""
    global _CONTINUOUS, _SEGMENT
    if enabled:
        _CONTINUOUS = True
        logger.info("[APPRENTISSAGE] Mode continu activé.")
    else:
        _continu_finaliser_segment()
        _CONTINUOUS = False
        logger.info("[APPRENTISSAGE] Mode continu désactivé.")
    _continu_sauver_etat(_CONTINUOUS)
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


# Restaure l'etat persiste au chargement du module : si l'utilisateur avait active
# l'apprentissage continu, il le reste apres un redemarrage du conteneur.
_CONTINUOUS = _continu_charger_etat()
if _CONTINUOUS:
    logger.info("[APPRENTISSAGE] Mode continu restaure depuis l'etat persiste.")

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

def replay_recording(user_id: str, rec_id: str) -> list[str] | None:
    """Charge l'imitation et pousse toutes ses actions dans la file d'attente de cet utilisateur."""
    rec = get_recording(rec_id)
    if not rec:
        return None
    actions = rec.get("actions", [])
    logger.info(f"[RPA QUEUE] Replay de l'imitation '{rec_id}' ({len(actions)} actions) user={user_id}")
    return RpaQueue.push_multiple(user_id, actions)


# ---------------------------------------------------------------------------
# Reglages de consentement — UN SEUL fichier partage (pas par utilisateur) :
# l'agent local (rpa_agent.py) lit ce fichier directement sur disque via le
# bind-mount Docker, sans connaitre d'user_id. Limite assumee : le niveau de
# consentement est un reglage de la MACHINE sur laquelle l'agent est installe,
# pas du compte NEOGEN connecte. Cloisonner ce reglage par utilisateur demanderait
# de faire transiter l'user_id jusqu'a la lecture locale de rpa_agent.py, hors
# perimetre de cette session (cf. plan : protocole minimal, pas le packaging complet).
# ---------------------------------------------------------------------------
_SETTINGS_FILE = os.path.join(DATA_DIR, "rpa_settings.json")
_SETTINGS_DEFAULT = {"consent_level": "sequence", "sequence_duration": 120}


def get_settings() -> dict:
    """Lit les paramètres RPA depuis data/rpa_settings.json."""
    try:
        if os.path.exists(_SETTINGS_FILE):
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return {**_SETTINGS_DEFAULT, **json.load(f)}
    except Exception:
        pass
    return dict(_SETTINGS_DEFAULT)


def save_settings(data: dict) -> dict:
    """Persiste les paramètres RPA dans data/rpa_settings.json."""
    os.makedirs(DATA_DIR, exist_ok=True)
    current = get_settings()
    current.update({k: v for k, v in data.items() if k in _SETTINGS_DEFAULT})
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return current


def intercepter_sorties_rpa(user_id: str, stdout: str) -> list[dict]:
    """
    Parcourt le stdout d'un conteneur pour y chercher les commandes RPA
    au format RPA_ACTION:{...}. Pousse chaque action valide dans la file de cet utilisateur.
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
        RpaQueue.push_multiple(user_id, actions_trouvees)
        logger.info(f"[RPA DETECT] {len(actions_trouvees)} actions interceptées et empilées. user={user_id}")
    return actions_trouvees


if __name__ == "__main__":
    print("=" * 60)
    print("NEOGEN - RPA : auto-verification (scoping + liste noire)")
    print("=" * 60)

    # ── Cloisonnement par utilisateur ────────────────────────────────────────
    uid_a, uid_b = "__test_rpa_a__", "__test_rpa_b__"
    _ETATS.pop(uid_a, None)
    _ETATS.pop(uid_b, None)

    id_a = RpaQueue.push(uid_a, {"action": "click", "x": 10, "y": 20})
    assert len(RpaQueue.list_queue(uid_a)) == 1
    assert len(RpaQueue.list_queue(uid_b)) == 0, "la file de B ne doit jamais voir les actions de A"

    store_screenshot(uid_a, "b64_a")
    assert get_screenshot(uid_a) == "b64_a"
    assert get_screenshot(uid_b) is None, "screenshot de A ne doit pas fuiter vers B"

    store_browser_context(uid_a, {"url": "https://a.example", "titre": "A"})
    assert get_browser_context(uid_a)["url"] == "https://a.example"
    assert get_browser_context(uid_b)["url"] == "", "contexte navigateur de A ne doit pas fuiter vers B"

    ping_agent(uid_a)
    assert is_agent_connected(uid_a)
    assert not is_agent_connected(uid_b), "ping de A ne doit pas connecter B"

    RpaQueue.set_result(uid_a, id_a, "executed")
    r = wait_result(uid_a, id_a, timeout=0.5)
    assert r["status"] == "executed"
    assert len(RpaQueue.list_queue(uid_a)) == 0, "action terminee retiree de la file"

    cleared = RpaQueue.clear(uid_a)
    assert cleared == 0, "file de A deja vide apres set_result"

    _ETATS.pop(uid_a, None)
    _ETATS.pop(uid_b, None)

    # ── Liste noire d'actions dangereuses ────────────────────────────────────
    uid_c = "__test_rpa_blacklist__"
    _ETATS.pop(uid_c, None)

    # Action normale : acceptee.
    RpaQueue.push(uid_c, {"action": "click", "x": 1, "y": 1})

    # open_url avec schema interdit : refusee, rien ajoute.
    try:
        RpaQueue.push(uid_c, {"action": "open_url", "url": "file:///etc/passwd"})
        assert False, "file:// aurait du etre refuse"
    except ActionRpaRefusee:
        pass

    # open_url http normal : acceptee.
    RpaQueue.push(uid_c, {"action": "open_url", "url": "https://example.com"})

    # type() contenant une commande shell : refusee.
    try:
        RpaQueue.push(uid_c, {"action": "type", "text": "powershell -c whoami"})
        assert False, "commande powershell aurait du etre refusee"
    except ActionRpaRefusee:
        pass

    # hotkey Win+R : refusee.
    try:
        RpaQueue.push(uid_c, {"action": "hotkey", "keys": ["win", "r"]})
        assert False, "Win+R aurait du etre refuse"
    except ActionRpaRefusee:
        pass

    # push_multiple atomique : une action refusee bloque tout le lot.
    avant = len(RpaQueue.list_queue(uid_c))
    try:
        RpaQueue.push_multiple(uid_c, [
            {"action": "click", "x": 5, "y": 5},
            {"action": "open_url", "url": "javascript:alert(1)"},
        ])
        assert False, "lot avec une action interdite aurait du etre refuse en bloc"
    except ActionRpaRefusee:
        pass
    assert len(RpaQueue.list_queue(uid_c)) == avant, "push_multiple doit etre atomique"

    _ETATS.pop(uid_c, None)

    print("  Tous les tests RPA OK (cloisonnement utilisateur + liste noire)")
    print("=" * 60)
