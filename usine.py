"""
VIVARIUM - L'Usine : une intention -> du code complet qui TOURNE

Le Compositeur produisait un plan avec organes esquisses. L'Usine va plus loin :
elle genere le CODE COMPLET du produit et l'EXECUTE pour de vrai.

Trois couches de securite avant la moindre execution (philosophie VIVARIUM) :
  1. MEMBRANE      : les effets declares respectent les murs forges.
  2. SCAN STATIQUE : on inspecte le vrai code pour des appels dangereux
                     (reseau, suppression de fichiers, exec...) avant de lancer.
  3. ISOLATION     : execution dans un processus separe, dossier temporaire, timeout.

HONNETETE : pour la fiabilite, on genere UN module coherent d'un coup, pas des
organes separes recolles (le collage de morceaux d'IA est un probleme plus dur).
L'isolation est de niveau processus + timeout, pas un jail durci.

Vrais appels Claude. Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
import os
import re
import sys
import subprocess
import tempfile

import anthropic
from pydantic import BaseModel

from generator import _load_api_key, MODEL
from compositeur import forger_adn, membrane, EffetsDeclares


# ---------------------------------------------------------------------------
# Sortie : un module complet, runnable, qui s'auto-teste
# ---------------------------------------------------------------------------
class ModuleGenere(BaseModel):
    code: str
    explication: str
    effets: EffetsDeclares


def generer_module(adn, client) -> ModuleGenere:
    murs = "\n".join(f"  - {m.id} : {m.label}" for m in adn.murs)
    organes = "\n".join(f"  - {o.nom} : {o.besoin}" for o in adn.organes)
    systeme = (
        f"Tu generes un PRODUIT complet en Python. Objectif : {adn.objectif}\n\n"
        f"MURS ABSOLUS a respecter :\n{murs}\n\n"
        f"ORGANES a implementer :\n{organes}\n\n"
        "Contraintes STRICTES :\n"
        "- Python pur, BIBLIOTHEQUE STANDARD UNIQUEMENT. Aucune dependance externe.\n"
        "- AUCUN acces reseau (pas de socket, urllib, requests).\n"
        "- N'ecris/supprime AUCUN fichier sur le disque.\n"
        "- Un seul module autonome.\n"
        "- Termine par un bloc `if __name__ == \"__main__\":` qui fait une DEMO + des "
        "assert qui prouvent que ca marche, et imprime un message de succes clair.\n"
        "Declare honnetement tes effets."
    )
    resp = client.messages.parse(
        model=MODEL, max_tokens=16000, thinking={"type": "adaptive"},
        system=systeme,
        messages=[{"role": "user", "content": "Genere le module complet, runnable et auto-teste."}],
        output_format=ModuleGenere,
    )
    if resp.parsed_output is None:
        raise RuntimeError("Generation du module echouee")
    return resp.parsed_output


# ---------------------------------------------------------------------------
# Couche 2 : scan statique du vrai code (defense en profondeur)
# ---------------------------------------------------------------------------
# Toujours interdits : vecteurs d'execution arbitraire (RCE), independamment des capacites.
INTERDITS_TOUJOURS = {
    r"\bos\.system": "execution shell",
    r"\bsubprocess\b": "lancement de processus",
    r"\beval\s*\(": "eval",
    r"\bexec\s*\(": "exec",
    r"__import__": "import dynamique",
}
# Interdits SAUF si la capacite RESEAU est accordee au produit.
INTERDITS_RESEAU = {
    r"\bsocket\b": "reseau brut",
    r"\burllib\b|\brequests\b|\bhttp\.client\b": "acces reseau",
}
# Interdits SAUF si la capacite PERSISTANCE est accordee au produit.
INTERDITS_FICHIER = {
    r"\bshutil\.rmtree|\bos\.remove|\bos\.unlink": "suppression de fichiers",
    r"open\s*\([^)]*['\"][wax]": "ecriture de fichier",
}
# Union (compat) : comportement strict par defaut quand aucune capacite n'est accordee.
INTERDITS = {**INTERDITS_TOUJOURS, **INTERDITS_RESEAU, **INTERDITS_FICHIER}


def scan_statique(code: str, cap=None) -> list[str]:
    """Scan statique conscient des capacites : ce qui est accorde n'est plus 'dangereux'."""
    motifs = dict(INTERDITS_TOUJOURS)
    if not (cap is not None and getattr(cap, "reseau", False)):
        motifs.update(INTERDITS_RESEAU)
    if not (cap is not None and getattr(cap, "persistance", False)):
        motifs.update(INTERDITS_FICHIER)
    return [raison for motif, raison in motifs.items() if re.search(motif, code)]


# ---------------------------------------------------------------------------
# Couche 3 : execution isolee
#   - de preference : conteneur Docker durci (isolation industrielle, sans reseau)
#   - sinon (Docker eteint) : repli sur processus separe + dossier temp + timeout
# ---------------------------------------------------------------------------
def executer_isole(code: str, timeout: int = 20, cap=None, volume_nom=None):
    # Tentative d'isolation industrielle via conteneur Docker (avec capacites graduees)
    try:
        from executeur_conteneur import docker_disponible, image_presente, executer_en_conteneur
        ok, _ = docker_disponible()
        if ok and image_presente():
            return executer_en_conteneur(code, timeout=max(timeout, 25), cap=cap, volume_nom=volume_nom)
    except Exception:
        pass
    # Repli : isolation processus (Docker indisponible). Garde-fou DevSecOps : on refuse
    # d'executer un produit reclamant des capacites (persistance/reseau) hors conteneur.
    if cap is not None and (getattr(cap, "persistance", False) or getattr(cap, "reseau", False)):
        return (-3, "", "Capacites demandees mais Docker indisponible : execution hors conteneur refusee.", "<repli>")
    d = tempfile.mkdtemp(prefix="vivarium_usine_")
    chemin = os.path.join(d, "produit.py")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(code)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        r = subprocess.run([sys.executable, chemin], capture_output=True, text=True,
                           timeout=timeout, cwd=d, env=env)
        return r.returncode, r.stdout, r.stderr, chemin
    except subprocess.TimeoutExpired:
        return -1, "", f"TIMEOUT apres {timeout}s", chemin


# ---------------------------------------------------------------------------
# L'Usine complete
# ---------------------------------------------------------------------------
def fabriquer(intention: str):
    client = anthropic.Anthropic(api_key=_load_api_key())

    print("=" * 72)
    print(f"VIVARIUM - L'USINE : '{intention}' -> du code qui tourne")
    print("=" * 72)

    print("\n[1] Claude forge l'ADN du produit...")
    adn = forger_adn(intention, client)
    print(f"  OBJECTIF : {adn.objectif}")
    print("  MURS :", ", ".join(m.id + "(" + m.regle + ")" for m in adn.murs))

    print("\n[2] Claude genere le code COMPLET du produit...")
    module = generer_module(adn, client)
    print(f"  {len(module.code.splitlines())} lignes generees. {module.explication[:120]}...")

    print("\n[3] MEMBRANE : effets declares vs murs forges...")
    verdict, raison = membrane(module, adn.murs)
    print(f"  -> {verdict} : {raison}")
    if verdict == "REJETE":
        print("\nLa membrane a rejete le produit. Aucune execution. (gouvernance)")
        return

    print("\n[4] SCAN STATIQUE du vrai code avant execution...")
    dangers = scan_statique(module.code)
    if dangers:
        print(f"  -> BLOQUE : appels dangereux detectes : {dangers}. AUCUNE execution.")
        print("     (la membrane d'inspection du code a fait son travail)")
        return
    print("  -> propre : aucun appel dangereux. Execution autorisee.")

    print("\n[5] EXECUTION ISOLEE (processus separe, dossier temp, timeout)...")
    code_retour, sortie, erreur, chemin = executer_isole(module.code)
    print(f"  fichier : {chemin}")
    print(f"  code retour : {code_retour}")
    if sortie.strip():
        print("  --- SORTIE DU PRODUIT GENERE ---")
        for ligne in sortie.strip().splitlines():
            print("    " + ligne)
    if erreur.strip():
        print("  --- ERREURS ---")
        for ligne in erreur.strip().splitlines()[:15]:
            print("    " + ligne)

    print("\n" + "=" * 72)
    if code_retour == 0:
        print("Une intention est devenue du CODE QUI TOURNE, gouverne et execute en securite.")
        print("Tu as parle. Le systeme a concu, ecrit, verifie, et fait tourner. Pour de vrai.")
    else:
        print("Le code a ete genere et verifie, mais l'execution a echoue (cf. erreurs).")
        print("Honnete : la generation ne donne pas toujours du premier coup du code parfait.")
    print("=" * 72)


if __name__ == "__main__":
    intention = " ".join(sys.argv[1:]) or "un generateur de mots de passe securise"
    fabriquer(intention)
