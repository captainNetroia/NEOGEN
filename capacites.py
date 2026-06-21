"""
NEOGEN - Capacites : le modele a DEUX niveaux de murs

Idee de Jordan (2026-06-17) : un createur ne doit pas etre bloque par des murs
qui l'empechent de produire de vrais besoins. Les murs d'un PRODUIT partent de
zero, sont PROPOSES par l'organisme, DISCUTES/choisis par l'humain, et forgent un
ADN tout neuf. Mais le CREATEUR garde ses propres murs, juges necessaires pour la
securite (culture DevSecOps), qui le protegent sans l'empecher de creer.

  NIVEAU 1 - INVARIANTS DU CREATEUR (quasi immuables, securite/DevSecOps) :
     isolation obligatoire, non-root, ressources bornees, ephemere, zero reseau
     par defaut, l'humain accorde les capacites et garde le dernier mot.
     -> ne dependent PAS du produit. Ils protegent l'hote, la prod, le genome.

  NIVEAU 2 - CAPACITES ACCORDEES AU PRODUIT (partent de zero, co-construites) :
     PERSISTANCE : un espace disque isole, jetable, jamais le disque de l'hote.
     RESEAU      : sortie restreinte a une liste blanche de domaines.
     -> proposees par l'organisme selon la nature du produit, validees par l'humain.

La securite ne disparait pas quand on accorde une capacite : elle devient GRADUEE.
Le bac a sable se configure pour matcher EXACTEMENT ce qui a ete accorde, rien de plus.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# NIVEAU 1 - Invariants du createur (juges necessaires, toujours actifs)
# ---------------------------------------------------------------------------
INVARIANTS_CREATEUR = [
    ("isolation_obligatoire", "Tout code genere s'execute en conteneur isole, jamais sur l'hote ni la prod."),
    ("non_root", "Le code tourne en utilisateur non privilegie (nobody), sans capabilities, no-new-privileges."),
    ("ressources_bornees", "Memoire, CPU, PIDs limites ; conteneur ephemere (--rm)."),
    ("reseau_zero_par_defaut", "Aucun acces reseau par defaut ; toute sortie passe par une liste blanche accordee."),
    ("humain_dernier_mot", "Les capacites sont accordees par l'humain, qui garde toujours le dernier mot."),
]

# Flags Docker toujours presents : la traduction technique des invariants.
# Ils ne dependent jamais du produit.
FLAGS_INVARIANTS = [
    "--rm",
    "--read-only",                       # racine en lecture seule (la persistance se fait sur un volume dedie)
    "--tmpfs", "/tmp:rw,size=32m",        # scratch jetable
    "--memory", "256m", "--cpus", "0.5",  # ressources bornees
    "--pids-limit", "64",
    "--cap-drop", "ALL",                  # zero capability
    "--security-opt", "no-new-privileges",
    "--user", "65534:65534",              # nobody : non-root
]

# ---------------------------------------------------------------------------
# NIVEAU 2 - Capacites accordables a un produit
# ---------------------------------------------------------------------------
PERSISTANCE = "persistance"
RESEAU = "reseau"
BUREAU = "bureau"  # RPA / computer-use

CATALOGUE_CAPACITES = {
    PERSISTANCE: "Lire/ecrire dans un espace disque ISOLE et jetable (monte sur /data). Jamais le disque de l'hote.",
    RESEAU: "Sortie reseau limitee a une LISTE BLANCHE de domaines. Aucun autre acces.",
    BUREAU: "Piloter le clavier et la souris de l'hote via l'agent local (RPA / computer-use).",
}


@dataclass
class Capacites:
    """Ce que l'humain a accorde a CE produit. Vide = produit pur (calcul en memoire)."""
    persistance: bool = False
    reseau: bool = False
    bureau: bool = False
    domaines_autorises: list[str] = field(default_factory=list)  # liste blanche si reseau accorde
    chemin_persistance: str = "/data"                            # point de montage cote conteneur

    def accordees(self) -> list[str]:
        out = []
        if self.persistance:
            out.append(PERSISTANCE)
        if self.reseau:
            out.append(RESEAU)
        if self.bureau:
            out.append(BUREAU)
        return out

    def resume(self) -> str:
        if not self.accordees():
            return "aucune (produit pur, calcul en memoire)"
        parts = []
        if self.persistance:
            parts.append(f"persistance ({self.chemin_persistance})")
        if self.reseau:
            dom = ", ".join(self.domaines_autorises) or "AUCUN domaine (a preciser)"
            parts.append(f"reseau -> liste blanche : {dom}")
        if self.bureau:
            parts.append("bureau (RPA / computer-use)")
        return " | ".join(parts)


def contraintes_generation(cap: Capacites) -> str:
    """
    Le texte injecte dans le prompt de generation. Au lieu d'INTERDIRE le disque et
    le reseau a tous les produits, on dit au produit ce qui lui est ACCORDE.
    Un produit n'utilise QUE ce qui lui est accorde : c'est sa frontiere, pas une castration.
    """
    lignes = ["Python pur, bibliotheque standard uniquement."]
    if cap.persistance:
        lignes.append(f"Tu PEUX lire/ecrire des fichiers, UNIQUEMENT sous {cap.chemin_persistance} "
                      f"(espace isole et persistant accorde a ce produit).")
    else:
        lignes.append("N'ecris/supprime AUCUN fichier (aucune persistance accordee).")
    if cap.reseau:
        dom = ", ".join(cap.domaines_autorises) or "(liste blanche a respecter)"
        lignes.append(f"Tu PEUX faire des requetes reseau SORTANTES, UNIQUEMENT vers : {dom}.")
    else:
        lignes.append("AUCUN acces reseau (aucune capacite reseau accordee).")
    if cap.bureau:
        lignes.append("Tu PEUX piloter le bureau (clavier, souris) de l'hote en imprimant des actions au format "
                      "exact 'RPA_ACTION:{\"action\": \"click\", \"x\": X, \"y\": Y}' (ou d'autres actions comme "
                      "move, double_click, right_click, scroll, type, press, hotkey) sur stdout. Exemple: "
                      "print('RPA_ACTION:{\"action\": \"click\", \"x\": 500, \"y\": 300}') ou "
                      "print('RPA_ACTION:{\"action\": \"type\", \"text\": \"hello\"}'). Tout se fait via stdout.")
    else:
        lignes.append("Aucun pilotage clavier ou souris (aucune capacite bureau accordee).")
    return "\n".join(f"- {l}" for l in lignes)

