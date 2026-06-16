"""
VIVARIUM - Demo : une loi qui manquait, ajoutee une fois, marche partout.

glace + feu donnait INERTE : le monde ne connaissait pas la fonte.
On a ajoute UNE loi generique (loi_fonte). Sans appel API, on rejoue glace+feu
avec les natures que Claude avait deja donnees, puis on prouve que la meme loi
fait fondre n'importe quelle matiere rigide et froide. Jamais codee par paire.
"""

from matiere import Matiere, rencontre, DEFAUT


def scene(titre, a, b):
    print("\n" + "=" * 66 + f"\n{titre}\n" + "=" * 66)
    print("  ", a)
    print("  ", b)
    journal, produits = rencontre(a, b, DEFAUT)
    for l in journal:
        print("  " + l)
    for p in produits:
        print("   -> ne :", p)


# Natures attribuees par Claude lors de l'incarnation (vrai appel precedent)
glace = Matiere("glace", 0.60, 0.10, 0.00, 0.80, -0.20)
feu = Matiere("feu", 0.20, 0.70, 1.00, 0.30, -0.20)

# Deux autres matieres rigides et froides, pour prouver que la loi generalise
acier = Matiere("acier", 0.95, 0.05, 0.20, 0.95, 0.00)
pierre = Matiere("pierre", 0.85, 0.05, 0.25, 0.90, 0.10)

print("Une seule loi ajoutee (loi_fonte). Aucune paire codee a la main.")
scene("1. glace rencontre feu (le raté d'avant, maintenant)", glace, feu)
scene("2. feu rencontre acier (jamais vu, et pourtant ca fond)", feu, acier)
scene("3. feu rencontre pierre (encore une, sans rien coder de plus)", feu, pierre)

print("\n" + "=" * 66)
print("La meme loi de fonte agit sur glace, acier, pierre. On ne l'a ecrite")
print("qu'une fois. C'est ca, l'extensibilite : une loi, une infinite de paires.")
