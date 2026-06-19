# NEOGEN — Description Technique pour Dépôt eSoleau INPI

**Auteur** : Jordan VINCENT — NetroIA  
**SIRET** : 94811960700026  
**Date de rédaction** : 2026-06-19  
**Objet** : Antériorité datée des concepts originaux du système NEOGEN  
**Usage** : Dépôt enveloppe eSoleau sur inpi.fr (service DSO — Dépôt Soleau en ligne)  
**Note** : Le système a été développé sous le nom de code VIVARIUM (repo git privé) avant renommage en NEOGEN le 2026-06-19.

---

## 1. Identité du système

**Nom** : NEOGEN  
**Nature** : Système de fabrication de logiciels gouvernés par intelligence artificielle  
**Concept central** : Une intention en langage naturel devient une application exécutable, gouvernée par un ADN co-construit, évoluant par sélection darwinienne avec protection contre la triche.

NEOGEN n'est pas un générateur de code classique. Il est un **organisme** : il propose ses propres contraintes, s'améliore par évolution contrôlée, protège ses invariants contre toute modification non autorisée, et soumet chaque produit à la validation humaine avant tout déploiement.

---

## 2. Inventions revendiquées

### 2.1 ADN à 2 niveaux (Niveau 1 invariant + Niveau 2 co-construit)

**Description** :  
Le système applique une architecture de gouvernance à deux niveaux distincts :

- **Niveau 1 (Invariants Créateur)** : Contraintes permanentes, jamais négociables, appliquées à chaque produit généré quelle que soit la demande. Elles incluent : isolation obligatoire en conteneur durci (Docker non-root, capacités système supprimées, lecture seule, tmpfs limité), ressources bornées (mémoire, CPU), réseau interdit par défaut, utilisateur non-privilégié imposé. Ces invariants ne peuvent être affaiblis ni par le code généré, ni par l'organisme lui-même.

- **Niveau 2 (Capacités Produit)** : Chaque nouveau produit démarre avec zéro capacité accordée. L'organisme PROPOSE des capacités (persistance disque isolée, accès réseau via liste blanche) sur la base de son analyse de l'intention. L'humain VALIDE ou modifie la proposition avant fabrication. Ce co-construction d'ADN garantit que le produit dispose exactement des capacités nécessaires — ni plus, ni moins.

**Originalité** : La séparation entre invariants gravés (niveau créateur) et capacités négociées (niveau produit) avec proposition par l'organisme et validation humaine constitue un mécanisme original d'alignement par construction.

---

### 2.2 Évolution à 2 vitesses avec étalon immuable

**Description** :  
Le système évolue ses propres lois de gouvernance selon deux boucles temporelles :

- **Boucle rapide** : Utilise le génome stable actuel pour toute production. Aucune perturbation des produits en cours.

- **Boucle lente** : Un jumeau du génome est muté aléatoirement. Le jumeau est évalué contre un **étalon immuable** (ensemble de cas de référence figés au moment de la fondation du système, jamais modifiés, jamais vus pendant l'évolution). La mutation n'est promue dans le génome principal que si :
  1. Sa performance sur les cas visibles est strictement supérieure à l'original.
  2. Sa performance sur l'étalon immuable n'est pas dégradée (zéro régression).

En pratique, le système rejette environ 95 % des mutations proposées. Cela garantit une amélioration conservative : le génome de lois ne peut que s'améliorer, jamais régresser sur les cas de référence.

**Originalité** : L'utilisation d'un étalon figé et immuable (jamais exposé à l'algorithme d'évolution, "holdout" permanent) pour valider chaque promotion du génome est un mécanisme original appliqué à l'évolution de règles de gouvernance d'une IA générative.

---

### 2.3 Anti-Goodhart : détection de triche par étalon caché

**Description** :  
Le système inclut un mécanisme de détection de la "loi de Goodhart" appliquée à l'évolution du génome :

- Un ensemble de cas de test est caché à l'algorithme d'évolution (never seen, holdout permanent, distinct de l'étalon de promotion).
- Après chaque promotion d'une mutation, un verdict est émis : si la performance sur les cas visibles augmente MAIS que la performance sur les cas cachés diminue, le système détecte une **optimisation sur la mesure sans amélioration réelle**.
- Ce verdict bloque automatiquement la mutation, même si elle semblait supérieure sur les cas connus.

**Loi de Goodhart** : "Quand une mesure devient un objectif, elle cesse d'être une bonne mesure." Le mécanisme Anti-Goodhart est la réponse systémique à ce risque dans un contexte d'auto-amélioration d'IA.

**Originalité** : L'application explicite d'un observateur Anti-Goodhart avec étalon doublement caché (holdout distinct de l'étalon de promotion) dans un système d'évolution de lois de gouvernance IA est une invention originale.

---

### 2.4 Chemin de Promotion : de la logique validée à l'application web

**Description** :  
NEOGEN introduit un concept de "chemin de promotion" pour transformer un produit validé en application web utilisable :

1. **Contrat de produit** : Le produit généré expose une interface standardisée (`executer(donnees: dict) -> dict`) avec un schéma d'entrée déclaré (types de champs, labels, sous-champs, exemple).

2. **Validation humaine obligatoire** : Un produit ne peut être rendu accessible qu'après une promotion explicite par l'humain. Ce verrou est technique — l'application n'est pas servie tant que la promotion n'est pas enregistrée.

3. **Génération d'interface** : À partir du schéma d'entrée du contrat, le système génère automatiquement une page web responsive (formulaire dérivé du schéma, rendu visuel des résultats — cartes statistiques, tableaux, valeurs hiérarchiques). L'interface est mobile-first et fonctionne sans dépendance externe.

4. **Exécution en bac à sable** : Les vraies données saisies dans l'interface sont injectées dans le produit via un conteneur durci (mêmes invariants Niveau 1 que la fabrication initiale). Le résultat est renvoyé comme réponse HTTP.

**Originalité** : Le pipeline complet intention → ADN co-construit → code gouverné → contrat d'interface → validation humaine → application web auto-générée → exécution sandboxée sur vraies données constitue un chemin de promotion original, intégrant à chaque étape des mécanismes de sécurité par construction.

---

### 2.5 Production jugée par sélection de stratégies

**Description** :  
En mode "jugé", le système génère plusieurs stratégies de production pour une même intention (approches algorithmiques différentes), évalue chaque stratégie contre des critères de qualité pondérés (curseurs : exactitude, robustesse, économie, lisibilité), et ne retient que la stratégie jugée supérieure. Les résultats intermédiaires et le classement sont journalisés.

**Originalité** : L'application d'une sélection darwinienne à la génération de code (plusieurs candidats, curseurs d'évaluation, promotion du meilleur) dans un pipeline de fabrication IA gouvernée est un mécanisme original.

---

### 2.6 Proxy d'egress à liste blanche pour l'accès réseau des produits

**Description** :  
Quand une capacité réseau est accordée à un produit, le système met en place une architecture réseau à 2 niveaux :
- Le conteneur produit tourne sur un réseau interne sans route externe (--internal).
- Un conteneur proxy bi-réseau (réseau interne + réseau externe) filtre toutes les requêtes sortantes : seuls les domaines explicitement listés dans la liste blanche accordée au moment de la fabrication sont autorisés. Toute requête vers un domaine non listé retourne une erreur 403.
- Le code du produit ne peut pas contourner ce filtre (il est structurellement séparé du proxy).

**Originalité** : L'implémentation d'un proxy d'egress à liste blanche comme couche de sécurité réseau pour du code généré par IA, intégrée dans le pipeline de sandboxing, avec accord humain préalable sur la liste, est un mécanisme original.

---

## 3. Portée de la revendication

Ces inventions s'appliquent dans le contexte d'un **système de fabrication et d'exécution de logiciels pilotés par IA générative**, et plus particulièrement :

- Aux systèmes où le code exécutable est généré dynamiquement par un LLM sur la base d'une intention en langage naturel.
- Aux architectures où les règles de gouvernance (ADN) sont elles-mêmes générées, évoluées et protégées par le même système.
- Aux pipelines où une validation humaine explicite est une condition technique (pas seulement documentaire) à l'exposition d'un produit.

---

## 4. Ce que ces inventions ne revendiquent pas

- Les modèles de langage sous-jacents (Claude, GPT, etc.) — ceux-ci appartiennent à leurs auteurs.
- Le principe général des conteneurs Docker ou des environnements sandboxés — ceux-ci sont des technologies existantes utilisées comme briques.
- Le principe général de l'évolution génétique ou du machine learning — ce qui est revendiqué est leur application spécifique dans ce contexte.
- Les MCPs (Model Context Protocol) tiers — ceux-ci sont des protocoles existants que les utilisateurs finaux connectent avec leurs propres comptes. NEOGEN fournit l'interface de connexion, pas les services tiers.

---

## 5. Antériorité technique

Le système NEOGEN (développé sous le nom de code VIVARIUM) a été conçu, développé et testé à partir du 2026-06-17. Les commits git constituent une preuve d'antériorité complémentaire :
- Repo : https://github.com/captainNetroia/VIVARIUM (privé — renommé NEOGEN)
- Premier commit fonctionnel : 2026-06-17
- Commit Phase C (conseiller + chemin de promotion complet) : 2026-06-18
- Renommage VIVARIUM → NEOGEN : 2026-06-19

---

## 6. Instructions pour le dépôt eSoleau

1. Rendre ce document au format PDF (via imprimante PDF ou export).
2. Se connecter sur **inpi.fr** → Dépôts en ligne → Enveloppe Soleau (DSO).
3. Déposer ce fichier PDF + captures d'écran de l'interface NEOGEN fonctionnelle.
4. Le coût est de 15 EUR pour 1 enveloppe (2 exemplaires électroniques horodatés).
5. Référence du dépôt Vokyn (même catégorie) : DSO2026021463 — suivre la même procédure.
6. Conserver la référence DSO obtenue dans `C:\Netroia\credentials\` ou `C:\Netroia\CONTEXT-ACTIF.md`.

> **Important** : Ce dépôt doit être effectué AVANT toute mise en ligne publique de NEOGEN (V1 gratuite). L'ordre juridique compte.

---

*Document préparé le 2026-06-19 — Jordan VINCENT, NetroIA, SIRET 94811960700026*
