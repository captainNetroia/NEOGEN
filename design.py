"""
NEOGEN - Doctrine de design : l'esthetique epuree (style Apple) injectee partout.

Source de verite UNIQUE de la charte visuelle NEOGEN. Toute production destinee
a l'oeil humain (application forgee, page, artefact, rendu d'agent) doit s'y
conformer : clarte, sobriete, hierarchie, respiration, accessibilite.

Pourquoi un module dedie : "toujours reflechir a l'esthetique" est une exigence
transverse (item roadmap E.8). Un seul endroit la definit ; agent_core et la
Forge (generator/orchestrateur) la consomment via bloc_pour_prompt(). Changer la
charte = changer ce fichier, partout a la fois.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-25.
"""
from __future__ import annotations

# ── La charte (principes, pas de jargon) ────────────────────────────────────────
# "Less but better." Retirer jusqu'a l'essentiel, puis soigner le detail.
_PRINCIPES = [
    "Clarte d'abord : une seule idee dominante par ecran, hierarchie visuelle nette "
    "(un titre fort, le reste en retrait).",
    "Respiration : espace blanc genereux, jamais de surcharge. L'espacement suit une "
    "echelle reguliere (multiples de 4 ou 8 px).",
    "Palette restreinte : un fond neutre, un seul accent, contraste maitrise. Pas de "
    "couleurs criardes ni de degrades gratuits.",
    "Typographie systeme : -apple-system, SF Pro, Inter ou Segoe UI ; 2 ou 3 tailles "
    "maximum, interlignage confortable (~1.5).",
    "Profondeur discrete : coins arrondis doux, ombres subtiles, aucune bordure dure "
    "quand une ombre legere suffit.",
    "Mouvement sobre : transitions douces (~150-250ms, ease), jamais d'animation qui "
    "distrait ou ralentit.",
    "Accessibilite : cibles tactiles >= 44px, contraste AA, focus visible au clavier, "
    "etats (survol/actif/desactive) clairs.",
    "Coherence : grille alignee au pixel, memes rayons et espacements partout. Le "
    "detail soigne (alignements parfaits) fait le haut de gamme.",
    "Honnetete : pas de bruit decoratif. Chaque element a une raison d'etre ; si on "
    "peut le retirer sans perte, on le retire.",
]

DOCTRINE = "Charte esthetique NEOGEN (epure, style Apple) :\n" + "\n".join(
    f"  - {p}" for p in _PRINCIPES
)


def bloc_pour_prompt(contexte: str = "agent") -> str:
    """Renvoie le bloc design a injecter dans un prompt systeme.

    contexte = "agent" : rappel court (l'agent garde l'esthetique a l'esprit).
    contexte = "forge" : charte complete (on concoit un produit beau par defaut).
    """
    if contexte == "forge":
        return (
            "\n\nESTHETIQUE (obligatoire des qu'il y a une sortie visible) :\n"
            + DOCTRINE
            + "\n  Si le produit a une interface (HTML/CSS/UI), applique cette charte : "
            "rendu epure, lisible, agreable a l'oeil, du niveau d'une app Apple. "
            "Un produit fonctionnel mais laid est incomplet."
        )
    # contexte agent : volontairement court (economie de tokens)
    return (
        "\n\nESTHETIQUE : des qu'une sortie est destinee a l'oeil (interface, page, "
        "visuel, mise en forme), vise l'epure style Apple : clarte, respiration, "
        "palette sobre, hierarchie nette, detail soigne. Beau ET fonctionnel."
    )


if __name__ == "__main__":
    print("=" * 64)
    print("NEOGEN - DESIGN : auto-verification")
    print("=" * 64)
    assert DOCTRINE and len(_PRINCIPES) >= 8, "charte incomplete"
    bagent = bloc_pour_prompt("agent")
    bforge = bloc_pour_prompt("forge")
    assert "ESTHETIQUE" in bagent and "Apple" in bagent
    assert "ESTHETIQUE" in bforge and len(bforge) > len(bagent), "forge doit etre plus complet"
    print(f"  {len(_PRINCIPES)} principes, bloc agent {len(bagent)}c / forge {len(bforge)}c : OK")
    print("=" * 64)
    print("  TOUT VERT.")
    print("=" * 64)
