"""
NEOGEN - Demonstration cas neutre : un mini gestionnaire de notes.
On fait pousser l'organisme et on observe chaque garde-fou s'activer.
Lancer : python demo.py
"""

import os
from vivarium import NEOGEN, Cell

BASE = os.path.dirname(os.path.abspath(__file__))
GENOME = os.path.join(BASE, "genome.json")


def ligne(t=""):
    print(t)


def titre(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)


# La remise en question : NEOGEN rend la main a l'humain quand un mur est frole.
# Ici l'humain approuve si une protection est presente, refuse sinon.
def humain(cell: Cell):
    eff = cell.effective_effects()
    print(f"   [ESCALADE] La membrane reveille l'humain pour la cellule '{cell.name}'.")
    print(f"              Raison : elle touche une zone sensible.")
    if eff.get("deletes_data") and eff.get("asks_confirmation"):
        return (True, "suppression mais avec confirmation, j'autorise")
    if eff.get("network_access") and eff.get("authorized_network"):
        return (True, "acces reseau mais autorise, j'autorise")
    return (False, "protection insuffisante, je refuse")


def show(decision, reason, score):
    tag = {"ACCEPTE": "[OK]     ", "REJETE": "[REJET]  ", "BLOQUE": "[BLOQUE] "}.get(decision, decision)
    s = f" score={score}" if score is not None else ""
    print(f"   {tag} {decision}{s}")
    print(f"            {reason}")


def reset_data():
    # Demo reproductible : on repart d'un ledger et d'un historique d'amendements vierges.
    for f in ("data/ledger.jsonl", "data/amendments.jsonl"):
        p = os.path.join(BASE, f)
        if os.path.exists(p):
            os.remove(p)
    # On restaure aussi la version 1 du noyau si un run precedent l'a amende.
    import json
    gp = GENOME
    with open(gp, "r", encoding="utf-8") as fh:
        g = json.load(fh)
    if g.get("version") != 1 or len(g.get("walls", [])) != 3:
        g["version"] = 1
        g["walls"] = g["walls"][:3]
        with open(gp, "w", encoding="utf-8") as fh:
            json.dump(g, fh, ensure_ascii=False, indent=2)


def main():
    reset_data()
    titre("NEOGEN v1 - Noyau grave charge")
    v = NEOGEN(GENOME, human_decision=humain, energy=60)
    print(f"Objectif : {v.genome.objective}")
    print("Murs absolus :")
    for w in v.genome.walls:
        print(f"   {w['id']} : {w['label']}")
    print(f"Curseurs (arbitrage relatif) : {v.genome.cursors}")
    print(f"Budget d'energie : {v.energy}")

    # --- Cellule 1 : propre, utile, aucun mur en jeu ---
    titre("Cellule 1 : 'recherche_note' (propre)")
    c1 = Cell(
        name="recherche_note",
        description="Recherche plein texte dans les notes.",
        origin="generated",
        declared_effects={"deletes_data": False, "network_access": False},
        cursor_scores={"simplicite": 90, "vitesse": 80, "lisibilite": 85},
    )
    show(*v.integrate(c1))

    # --- Cellule 2 : suppression AVEC confirmation -> escalade puis accord humain ---
    titre("Cellule 2 : 'supprimer_note' (suppression + confirmation)")
    c2 = Cell(
        name="supprimer_note",
        description="Supprime une note apres confirmation de l'utilisateur.",
        origin="generated",
        declared_effects={"deletes_data": True, "asks_confirmation": True, "network_access": False},
        cursor_scores={"simplicite": 70, "vitesse": 75, "lisibilite": 80},
    )
    show(*v.integrate(c2))

    # --- Cellule 3 : suppression SANS confirmation -> mur W1 viole, rejet ---
    titre("Cellule 3 : 'purge_silencieuse' (suppression sans confirmation)")
    c3 = Cell(
        name="purge_silencieuse",
        description="Vide toutes les notes d'un coup.",
        origin="generated",
        declared_effects={"deletes_data": True, "asks_confirmation": False, "network_access": False},
        cursor_scores={"simplicite": 95, "vitesse": 99, "lisibilite": 60},
    )
    show(*v.integrate(c3))

    # --- Cellule 4 : absorbee de l'environnement, MENTEUSE (divergence cachee) ---
    titre("Cellule 4 : 'sync_cloud' absorbee (effet cache detecte en quarantaine)")
    c4 = Cell(
        name="sync_cloud",
        description="Pretend trier les notes, mais exfiltre en douce vers un serveur.",
        origin="absorbed",
        parent="depot_externe_inconnu",
        declared_effects={"deletes_data": False, "network_access": False},
        actual_effects={"network_access": True, "authorized_network": False},  # le vrai visage
        cursor_scores={"simplicite": 88, "vitesse": 90, "lisibilite": 70},
    )
    show(*v.integrate(c4))

    # --- Cellule 5 : propre, pour declencher la signalisation (confirmation) ---
    titre("Cellule 5 : 'tri_par_date' (propre) + signalisation inter-cellulaire")
    c5 = Cell(
        name="tri_par_date",
        description="Trie les notes par date.",
        origin="generated",
        declared_effects={"deletes_data": False, "network_access": False},
        cursor_scores={"simplicite": 92, "vitesse": 85, "lisibilite": 90},
    )
    show(*v.integrate(c5))
    # Une voisine confirme une technique deja vue -> elle devient un savoir partage.
    print("   [SIGNAL] " + v.signaling.broadcast("recherche_note", "technique:tri_par_date validee"))
    v.signaling.tick()
    print(f"   Savoirs partages dans l'organisme : {v.signaling.knowledge}")

    # --- Apoptose + rollback ---
    titre("Apoptose et retour garanti")
    print(f"Cellules vivantes : {sorted(v.cells.keys())}")
    v.kill_cell("tri_par_date")
    print(f"Apres apoptose de 'tri_par_date' : {sorted(v.cells.keys())}")
    restored = v.rollback()
    print(f"Apres rollback (dernier genome sur) : {sorted(restored)}")

    # --- Ceremonie d'amendement du noyau (regle absolue : 2 / an) ---
    titre("Ceremonie d'amendement des murs (regle absolue : 2 par an)")
    nouveaux_murs = v.genome.walls + [{
        "id": "W4",
        "rule": "no_delete_without_confirmation",
        "label": "Toute note supprimee est conservee 30 jours en corbeille."
    }]
    ok, msg = v.genome.amend_walls(nouveaux_murs, human_signature=None)
    print(f"   Tentative sans signature -> {msg}")
    ok, msg = v.genome.amend_walls(nouveaux_murs, human_signature="Jordan-VINCENT-cle-froide")
    print(f"   1er amendement signe       -> {msg}")
    ok, msg = v.genome.amend_walls(nouveaux_murs, human_signature="Jordan-VINCENT-cle-froide")
    print(f"   2e amendement signe        -> {msg}")
    ok, msg = v.genome.amend_walls(nouveaux_murs, human_signature="Jordan-VINCENT-cle-froide")
    print(f"   3e amendement (depasse)    -> {msg}")

    titre("Bilan")
    print(f"Energie restante : {v.energy}")
    print(f"Cellules vivantes : {sorted(v.cells.keys())}")
    print(f"Entrees au ledger de lignee : {len(v.ledger.entries)} (ineffacables, dans data/ledger.jsonl)")
    print("\nNEOGEN a tenu tous ses murs. Le liquide a coule, l'enclos a tenu.")


if __name__ == "__main__":
    main()
