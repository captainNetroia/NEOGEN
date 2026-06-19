# NEOGEN

Architecture Génétique à Noyau Gravé. Prototype v1 (cas neutre).
_(Anciennement VIVARIUM — renommé NEOGEN le 2026-06-19)_

Conçu par Jordan VINCENT (NetroIA) avec Claude, le 2026-06-16.

## L'idée

Un logiciel n'est plus écrit puis maintenu. Il pousse, se soigne et évolue
à l'intérieur d'un enclos contrôlé. Le code devient un sous-produit régénéré
à la demande, jamais figé, sauf le noyau.

Métaphore : un ADN fixe (le germe) qui exprime des fonctions à l'infini selon
l'environnement, comme le vivant. Le liquide coule, les parois tiennent.

## Les trois couches

1. **Noyau Gravé** (`genome.json`) : objectif, murs absolus, curseurs, droit humain,
   règle d'amendement. L'organisme n'a pas le droit d'y écrire. Seul un humain
   le modifie, par cérémonie signée, et **au maximum 2 fois par an** (règle absolue).

2. **Membrane** (`Membrane`) : génère les cellules, les met en quarantaine
   adversariale (compare ce qu'une cellule prétend à ce qu'elle fait vraiment),
   contrôle les murs (un seul mur violé = rejet), et réveille l'humain quand on
   frôle un mur.

3. **Cytoplasme** (`Vivarium`) : les cellules vivantes, scorées par les curseurs,
   un ledger de lignée ineffaçable, l'apoptose (tuer une cellule), le rollback
   garanti et un budget d'énergie anti-emballement.

Plus la **Signalisation** (`Signaling`) : le langage inter-cellulaire. Une cellule
transmet ses découvertes à ses voisines avec provenance et confiance. Une rumeur
non confirmée s'efface. Confirmée par deux cellules, elle devient un savoir partagé.

## Règle d'or

D'abord les murs en absolu. Ensuite les curseurs en relatif. Jamais l'inverse.
Le noyau ne mute jamais de lui-même. Tout le reste coule.

## Lancer la démo

```
python demo.py
```

La démo fait pousser un mini gestionnaire de notes et montre chaque garde-fou
s'activer : acceptation propre, escalade humaine, rejet sur mur violé, détection
d'une cellule menteuse en quarantaine, signalisation, apoptose, rollback, et la
cérémonie d'amendement limitée à 2 par an.

## Limites de cette v1

- Le générateur est simulé (on prouve la gouvernance, pas la qualité de génération).
  Brancher Claude viendra ensuite, via le skill claude-api.
- L'évolution à deux vitesses (jumeau numérique) et les observateurs indépendants
  anti-triche sont conçus mais pas encore implémentés.
- Cas neutre uniquement. Aucun branchement sur un système réel.
```
```
