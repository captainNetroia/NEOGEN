"""
NEOGEN - Agent local RPA & Apprentissage par imitation (côté hôte)

Ce script s'exécute directement sur votre machine hôte Windows.
Il fait le pont entre le serveur NEOGEN (dans Docker) et vos périphériques physiques.

Prerequis :
  pip install pyautogui pynput requests

Usage :
  python rpa_agent.py
"""

from __future__ import annotations
import sys
import time
import threading
import logging
import ctypes
import platform
import json as _json
from pathlib import Path

_SETTINGS_PATH = Path(__file__).parent / "data" / "rpa_settings.json"


def _lire_settings() -> dict:
    """Lit les settings RPA depuis le fichier partagé (ecrit par l'API Docker)."""
    try:
        if _SETTINGS_PATH.exists():
            return _json.loads(_SETTINGS_PATH.read_text())
    except Exception:
        pass
    return {"consent_level": "sequence", "sequence_duration": 120}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("NEOGEN-Agent")

# Vérification et installation des dépendances guidée
try:
    import requests
    import pyautogui
    from pynput import mouse, keyboard
except ImportError as e:
    print("\n" + "=" * 68)
    print(f"ERREUR : Dépendance manquante : {e.name}")
    print("Veuillez installer les packages requis pour exécuter l'agent local :")
    print("  pip install pyautogui pynput requests")
    print("=" * 68 + "\n")
    sys.exit(1)

# Configuration de base
SERVER_URL = "http://localhost:8000"
PING_INTERVAL = 2.0  # secondes
POLL_INTERVAL = 1.0  # secondes

# Désactiver la pause par défaut trop longue de PyAutoGUI pour plus de réactivité,
# mais conserver le FAILSAFE.
pyautogui.FAILSAFE = True  # Déplacer la souris au coin haut-gauche = Arrêt d'urgence
pyautogui.PAUSE = 0.05

# État de l'agent
running = True
recording_active = False
mouse_listener = None
keyboard_listener = None

# Consentement par SÉQUENCE (pas par action) : quand l'utilisateur autorise une
# action, on ouvre une fenêtre d'auto-approbation. Les actions suivantes qui
# arrivent dans cette fenêtre s'exécutent sans redemander -> on voit l'agent
# enchaîner les actions au lieu de cliquer "Oui" 53 fois.
_auto_approve_until = 0.0
AUTO_APPROVE_WINDOW = 120.0  # secondes

# Consentement : MessageBox natif Windows (ctypes) ou invite console (autres OS).
# On n'utilise PAS tkinter : il n'est pas thread-safe et la popup est appelee depuis
# poll_loop (thread secondaire), ce qui la fait echouer/bloquer sur Windows.


def demander_consentement(action: dict) -> str:
    """
    Demande la validation de l'utilisateur AVANT toute action physique.
    Thread-safe (appele depuis poll_loop) et toujours au premier plan.
    Windows : MessageBox natif (ctypes). Autres OS : invite console.

    Niveau de consentement (lu depuis data/rpa_settings.json) :
      "auto"     -> jamais de popup, toujours approuve
      "sequence" -> fenetre AUTO_APPROVE_WINDOW (comportement par defaut)
      "always"   -> toujours demander, ignore la fenetre

    Retourne 'approved', 'rejected' ou 'cancelled' (arret d'urgence).
    """
    global _auto_approve_until

    s = _lire_settings()
    level = s.get("consent_level", "sequence")
    window = float(s.get("sequence_duration", 120))

    # Mode auto : aucune popup, toujours approuve.
    if level == "auto":
        logger.info("  [consent:auto] Action approuvee sans popup.")
        return "approved"

    # Mode sequence (defaut) : fenetre d'auto-approbation.
    if level == "sequence" and time.time() < _auto_approve_until:
        return "approved"

    # Mode always : toujours redemander (ignore _auto_approve_until).

    desc = f"Action : {action.get('action')}\n"
    if action.get("x") is not None and action.get("y") is not None:
        desc += f"Position : ({action.get('x')}, {action.get('y')})\n"
    if action.get("text"):
        desc += f"Texte : \"{action.get('text')}\"\n"
    if action.get("key"):
        desc += f"Touche : {action.get('key')}\n"
    if action.get("keys"):
        desc += f"Touches : {' + '.join(action.get('keys'))}\n"
    if action.get("url"):
        desc += f"Ouvrir : {action.get('url')}\n"

    message = (
        "NEOGEN demande l'autorisation de contrôler votre souris/clavier.\n\n"
        f"Première action :\n{desc}\n"
        f"Oui = Autoriser la séquence ({int(window)}s, sans redemander)\n"
        "Non = Ignorer cette action\n"
        "Annuler = ARRÊT D'URGENCE (vide la file)\n\n"
        "Arrêt d'urgence à tout moment : poussez la souris dans le coin HAUT-GAUCHE de l'écran."
    )

    if platform.system() == "Windows":
        # MessageBox natif : thread-safe + premier plan (MB_SYSTEMMODAL | MB_SETFOREGROUND)
        MB_YESNOCANCEL = 0x3
        MB_ICONWARNING = 0x30
        MB_SYSTEMMODAL = 0x1000
        MB_SETFOREGROUND = 0x10000
        flags = MB_YESNOCANCEL | MB_ICONWARNING | MB_SYSTEMMODAL | MB_SETFOREGROUND
        res = ctypes.windll.user32.MessageBoxW(
            0, message, "NEOGEN - Consentement requis", flags
        )
        if res == 6:      # IDYES
            _auto_approve_until = time.time() + window
            logger.info(f"  Séquence autorisée pour {int(window)}s. Exécution visible...")
            return "approved"
        elif res == 7:    # IDNO
            return "rejected"
        return "cancelled"  # IDCANCEL (2) ou fermeture

    # Fallback console (Linux / Mac) : repond dans le terminal de l'agent
    print("\n" + "=" * 60)
    print(message)
    print("=" * 60)
    try:
        rep = input("Autoriser ? [o = oui / n = non / a = arret d'urgence] : ").strip().lower()
    except EOFError:
        return "rejected"
    if rep in ("o", "oui", "y", "yes"):
        _auto_approve_until = time.time() + AUTO_APPROVE_WINDOW
        return "approved"
    if rep in ("a", "arret", "stop"):
        return "cancelled"
    return "rejected"


def _titre_fenetre_active() -> str:
    """Titre de la fenêtre au premier plan (Windows). Vide ailleurs / si erreur."""
    if platform.system() != "Windows":
        return ""
    try:
        u32 = ctypes.windll.user32
        h = u32.GetForegroundWindow()
        n = u32.GetWindowTextLengthW(h)
        buf = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(h, buf, n + 1)
        return buf.value or ""
    except Exception:
        return ""


def _fenetre_active_est_neogen() -> bool:
    """Vrai si la fenêtre active semble être NEOGEN (pour ne pas la fermer)."""
    t = _titre_fenetre_active().lower()
    return ("neogen" in t) or ("localhost:8000" in t) or ("127.0.0.1:8000" in t)


# Indices de titre de fenêtre des navigateurs courants (suffixes usuels).
_NAVIGATEURS = ("google chrome", "microsoft​ edge", "microsoft edge", "mozilla firefox",
                "brave", "opera", "vivaldi", "chromium", "edge")


def _fenetre_active_est_navigateur() -> bool:
    """Vrai si la fenêtre au premier plan est un navigateur (titre reconnu)."""
    t = _titre_fenetre_active().lower()
    return any(n in t for n in _NAVIGATEURS)


def _verifier_close_tab() -> tuple[bool, str]:
    """Décide si Ctrl+W est sûr et utile. Renvoie (autorise, message diagnostic).
    - refuse si NEOGEN au premier plan (anti-suicide) ;
    - refuse si la fenêtre active n'est pas un navigateur (évite le no-op silencieux) ;
    - autorise sinon. Le message explique TOUJOURS la décision (un coup d'avance)."""
    titre = _titre_fenetre_active() or "(titre inconnu)"
    if _fenetre_active_est_neogen():
        return False, f"Refuse : la fenetre active est NEOGEN ('{titre}'). Mets l'onglet a fermer au premier plan."
    if platform.system() == "Windows" and not _fenetre_active_est_navigateur():
        return False, (f"Refuse : la fenetre active n'est pas un navigateur ('{titre}'). "
                       "Clique d'abord sur la fenetre du navigateur, puis reessaye.")
    return True, f"Fermeture de l'onglet actif du navigateur ('{titre}')."


def _capturer_et_envoyer() -> tuple[bool, str | None]:
    """Capture l'écran, encode en PNG base64, et l'envoie au backend NEOGEN.
    Donne des 'yeux' à l'agent : le modèle vision analysera cette image."""
    try:
        import io, base64
        img = pyautogui.screenshot()
        # Réduit la taille pour rester raisonnable côté modèle vision (largeur max ~1280).
        if img.width > 1280:
            ratio = 1280 / img.width
            img = img.resize((1280, int(img.height * ratio)))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        requests.post(f"{SERVER_URL}/rpa/screenshot", json={"image": b64}, timeout=10)
        return True, None
    except Exception as e:
        return False, f"capture écran échouée : {e}"


def executer_physique(action: dict) -> tuple[bool, str | None]:
    """Exécute l'action via pyautogui sur l'hôte."""
    act_type = action.get("action")
    x = action.get("x")
    y = action.get("y")
    text = action.get("text", "")
    key = action.get("key", "")
    keys = action.get("keys", [])
    url = action.get("url", "")
    amount = action.get("amount", 3)
    interval = action.get("interval", 0.05)
    guard = action.get("guard", "")

    # Garde close_tab : refus diagnostiqué si NEOGEN ou si pas un navigateur (plus de no-op muet).
    if guard == "close_tab":
        ok_close, diag = _verifier_close_tab()
        logger.info("close_tab -> %s", diag)
        if not ok_close:
            return False, diag

    # Déplacement visible : la souris glisse (duration) au lieu de se téléporter,
    # pour que l'utilisateur voie concrètement l'agent agir.
    GLIDE = 0.35
    try:
        if act_type == "move":
            pyautogui.moveTo(int(x), int(y), duration=GLIDE)
        elif act_type == "click":
            pyautogui.moveTo(int(x), int(y), duration=GLIDE)
            pyautogui.click()
        elif act_type == "double_click":
            pyautogui.moveTo(int(x), int(y), duration=GLIDE)
            pyautogui.doubleClick()
        elif act_type == "right_click":
            pyautogui.moveTo(int(x), int(y), duration=GLIDE)
            pyautogui.rightClick()
        elif act_type == "scroll":
            pyautogui.scroll(int(amount), x=int(x) if x else None, y=int(y) if y else None)
        elif act_type == "type":
            pyautogui.typewrite(text, interval=interval)
        elif act_type == "press":
            pyautogui.press(key)
        elif act_type == "hotkey":
            pyautogui.hotkey(*keys)
        elif act_type == "open_url":
            import webbrowser
            if not url:
                return False, "open_url sans url"
            webbrowser.open(url)
        elif act_type == "screenshot":
            return _capturer_et_envoyer()
        else:
            return False, f"Action inconnue : {act_type}"
        return True, None
    except pyautogui.FailSafeException:
        logger.warning("[FAILSAFE] Arrêt d'urgence déclenché par l'utilisateur (coin supérieur gauche) !")
        return False, "Failsafe déclenché"
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Enregistrement (Imitation Learning)
# ---------------------------------------------------------------------------

def send_recorded_action(action_data: dict):
    """Envoie une action utilisateur capturée au backend NEOGEN."""
    try:
        requests.post(f"{SERVER_URL}/rpa/record/action", json=action_data, timeout=2)
    except Exception as e:
        logger.error(f"Impossible d'envoyer l'action enregistrée : {e}")


def on_click(x, y, button, pressed):
    if pressed and recording_active:
        action_name = "click"
        if button == mouse.Button.right:
            action_name = "right_click"
        
        send_recorded_action({
            "action": action_name,
            "x": int(x),
            "y": int(y)
        })


def on_press(key):
    if not recording_active:
        return
    try:
        # Touches normales
        char = key.char
        if char:
            send_recorded_action({
                "action": "type",
                "text": char
            })
    except AttributeError:
        # Touches spéciales (Entrée, Espace, etc.)
        kname = key.name
        if kname == "space":
            send_recorded_action({
                "action": "type",
                "text": " "
            })
        elif kname in ("enter", "tab", "backspace", "delete", "esc", "up", "down", "left", "right"):
            send_recorded_action({
                "action": "press",
                "key": kname
            })


def toggle_listeners(enable: bool):
    global recording_active, mouse_listener, keyboard_listener
    if enable and not recording_active:
        recording_active = True
        logger.info("[IMITATION] Démarrage des capteurs de mouvements système...")
        mouse_listener = mouse.Listener(on_click=on_click)
        keyboard_listener = keyboard.Listener(on_press=on_press)
        mouse_listener.start()
        keyboard_listener.start()
    elif not enable and recording_active:
        recording_active = False
        logger.info("[IMITATION] Arrêt des capteurs.")
        if mouse_listener:
            mouse_listener.stop()
        if keyboard_listener:
            keyboard_listener.stop()


# ---------------------------------------------------------------------------
# Boucles principales de communication
# ---------------------------------------------------------------------------

def ping_loop():
    """Signale la présence de l'agent au serveur toutes les 2 secondes."""
    while running:
        try:
            r = requests.post(f"{SERVER_URL}/rpa/agent/ping", timeout=2)
            if r.status_code == 200:
                data = r.json()
                # Activer/Désactiver l'enregistrement selon l'ordre du serveur
                toggle_listeners(data.get("recording", False))
        except Exception:
            # En cas de perte de connexion, désactiver les listeners
            toggle_listeners(False)
        time.sleep(PING_INTERVAL)


def poll_loop():
    """Interroge le serveur pour récupérer des tâches RPA à exécuter."""
    while running:
        try:
            # Récupérer l'action suivante
            r = requests.get(f"{SERVER_URL}/rpa/pending", timeout=3)
            if r.status_code == 200:
                action = r.json()
                if action and "id" in action:
                    action_id = action["id"]
                    logger.info(f"[RPA QUEUE] Action reçue : {action['action']} (ID: {action_id})")

                    # 1. Demander le consentement de l'utilisateur
                    decision = demander_consentement(action)

                    if decision == "approved":
                        logger.info("  Action approuvée. Exécution physique...")
                        ok, err = executer_physique(action)
                        if ok:
                            logger.info("  Action exécutée avec succès.")
                            requests.post(f"{SERVER_URL}/rpa/action/result", json={
                                "id": action_id, "status": "executed"
                            })
                        else:
                            logger.error(f"  Échec de l'exécution : {err}")
                            requests.post(f"{SERVER_URL}/rpa/action/result", json={
                                "id": action_id, "status": "failed", "error": err
                            })
                    elif decision == "rejected":
                        logger.warning("  Action rejetée par l'utilisateur.")
                        requests.post(f"{SERVER_URL}/rpa/action/result", json={
                            "id": action_id, "status": "rejected"
                        })
                    else:
                        logger.warning("  Arrêt d'urgence demandé !")
                        global _auto_approve_until
                        _auto_approve_until = 0.0  # coupe l'auto-approbation en cours
                        # Vider la file côté serveur
                        requests.post(f"{SERVER_URL}/rpa/clear")
                        requests.post(f"{SERVER_URL}/rpa/action/result", json={
                            "id": action_id, "status": "rejected", "error": "Emergency stop"
                        })
            elif r.status_code == 404:
                # Aucune action en attente
                pass
        except requests.ConnectionError:
            logger.warning("Serveur NEOGEN injoignable. Retrying...")
            time.sleep(3)
        except Exception as e:
            logger.error(f"Erreur dans la boucle de polling : {e}")
        
        time.sleep(POLL_INTERVAL)


# ── Icône barre système (tray) ────────────────────────────────────────────────
# Présence visuelle dans la zone de notification Windows (comme Ollama/Docker),
# avec menu Statut / Ouvrir NEOGEN / Quitter. Optionnel : si pystray/Pillow ne
# sont pas installés, on retombe sur le mode console.

def _icone_image(connecte: bool):
    """Dessine un disque (vert = connecté au serveur, gris = en attente)."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    couleur = (22, 163, 74, 255) if connecte else (100, 116, 139, 255)
    d.ellipse([10, 10, 54, 54], fill=couleur)
    d.ellipse([24, 24, 40, 40], fill=(255, 255, 255, 230))
    return img


def _lancer_tray():
    """Lance l'agent avec une icône barre système. Retourne False si indisponible."""
    try:
        import pystray
    except Exception:
        return False

    def _serveur_ok() -> bool:
        try:
            return requests.get(f"{SERVER_URL}/health", timeout=2).status_code == 200
        except Exception:
            return False

    icon = pystray.Icon("neogen-agent", _icone_image(False), "NEOGEN - Agent local")

    def _statut_texte(_=None):
        return "Serveur : connecté" if _serveur_ok() else "Serveur : injoignable"

    def _ouvrir(_=None):
        import webbrowser
        webbrowser.open(SERVER_URL)

    def _quitter(_=None):
        global running
        running = False
        toggle_listeners(False)
        icon.stop()

    icon.menu = pystray.Menu(
        pystray.MenuItem(_statut_texte, None, enabled=False),
        pystray.MenuItem("Ouvrir NEOGEN", _ouvrir),
        pystray.MenuItem("Quitter l'agent", _quitter),
    )

    def _maj_icone():
        """Met à jour la couleur de l'icône selon l'état du serveur."""
        while running:
            try:
                icon.icon = _icone_image(_serveur_ok())
                icon.update_menu()
            except Exception:
                pass
            time.sleep(5)

    threading.Thread(target=ping_loop, daemon=True).start()
    threading.Thread(target=poll_loop, daemon=True).start()
    threading.Thread(target=_maj_icone, daemon=True).start()
    logger.info("Agent lancé avec icône barre système. Clic droit sur l'icône pour le menu.")
    icon.run()  # bloquant jusqu'à Quitter
    sys.exit(0)


def _lancer_console():
    """Mode console classique (fallback si pas de tray)."""
    print("=" * 68)
    print("           NEOGEN - AGENT LOCAL AUTOMATISATION & IMITATION           ")
    print("=" * 68)
    print("   L'agent est actif et écoute sur : " + SERVER_URL)
    print("   Arrêt d'urgence hôte (failsafe) : déplacez le curseur tout en haut à gauche")
    print("   Fermer l'agent : Ctrl+C dans cette console")
    print("=" * 68 + "\n")

    threading.Thread(target=ping_loop, daemon=True).start()
    threading.Thread(target=poll_loop, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nArrêt de l'agent local.")
        global running
        running = False
        toggle_listeners(False)
        sys.exit(0)


if __name__ == "__main__":
    # Préférence : icône barre système. Si pystray/Pillow absents -> console.
    if not _lancer_tray():
        _lancer_console()
