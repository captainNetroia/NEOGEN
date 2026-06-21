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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("NEOGEN-Agent")

# Vérification et installation des dépendances guidée
try:
    import requests
    import pyautogui
    from pynput import mouse, keyboard
    import tkinter as tk
    from tkinter import messagebox
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

# Initialisation de Tkinter
root = tk.Tk()
root.withdraw()  # Cacher la fenêtre principale, on utilise uniquement les popups


def demander_consentement(action: dict) -> str:
    """
    Affiche une boîte de dialogue à l'utilisateur sur l'hôte pour valider l'action.
    Retourne 'approved' (Yes), 'rejected' (No) ou 'cancelled' (Cancel).
    """
    desc = f"Action : {action.get('action')}\n"
    if action.get("x") is not None and action.get("y") is not None:
        desc += f"Position : ({action.get('x')}, {action.get('y')})\n"
    if action.get("text"):
        desc += f"Texte : \"{action.get('text')}\"\n"
    if action.get("key"):
        desc += f"Touche : {action.get('key')}\n"
    if action.get("keys"):
        desc += f"Touches : {' + '.join(action.get('keys'))}\n"

    message = (
        "NEOGEN demande l'autorisation d'interagir avec votre machine :\n\n"
        f"{desc}\n"
        "Voulez-vous autoriser cette action ?\n\n"
        "- Oui : Exécuter\n"
        "- Non : Ignorer cette action\n"
        "- Annuler : Déclencher l'ARRÊT D'URGENCE"
    )
    
    # Exécuter dans le thread principal ou forcer l'affichage au premier plan
    root.update()
    root.deiconify()
    root.withdraw()
    
    ans = messagebox.askyesnocancel(
        title="NEOGEN - Consentement requis",
        message=message,
        default=messagebox.NO
    )
    
    if ans is True:
        return "approved"
    elif ans is False:
        return "rejected"
    else:
        return "cancelled"


def executer_physique(action: dict) -> tuple[bool, str | None]:
    """Exécute l'action via pyautogui sur l'hôte."""
    act_type = action.get("action")
    x = action.get("x")
    y = action.get("y")
    text = action.get("text", "")
    key = action.get("key", "")
    keys = action.get("keys", [])
    amount = action.get("amount", 3)
    interval = action.get("interval", 0.05)

    try:
        if act_type == "move":
            pyautogui.moveTo(int(x), int(y))
        elif act_type == "click":
            pyautogui.click(int(x), int(y))
        elif act_type == "double_click":
            pyautogui.doubleClick(int(x), int(y))
        elif act_type == "right_click":
            pyautogui.rightClick(int(x), int(y))
        elif act_type == "scroll":
            pyautogui.scroll(int(amount), x=int(x) if x else None, y=int(y) if y else None)
        elif act_type == "type":
            pyautogui.typewrite(text, interval=interval)
        elif act_type == "press":
            pyautogui.press(key)
        elif act_type == "hotkey":
            pyautogui.hotkey(*keys)
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


if __name__ == "__main__":
    print("=" * 68)
    print("           NEOGEN - AGENT LOCAL AUTOMATISATION & IMITATION           ")
    print("=" * 68)
    print("   L'agent est actif et écoute sur : " + SERVER_URL)
    print("   Arrêt d'urgence hôte (failsafe) : déplacez le curseur tout en haut à gauche")
    print("   Fermer l'agent : Ctrl+C dans cette console")
    print("=" * 68 + "\n")

    t1 = threading.Thread(target=ping_loop, daemon=True)
    t2 = threading.Thread(target=poll_loop, daemon=True)
    t1.start()
    t2.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nArrêt de l'agent local.")
        running = False
        toggle_listeners(False)
        sys.exit(0)
