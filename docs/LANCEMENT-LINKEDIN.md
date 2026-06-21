# NEOGEN — Plan de lancement LinkedIn (open core)

Modele retenu : **open core**.
- Gratuit : cœur en self-host (l'utilisateur installe avec SA cle IA, ou Ollama gratuit).
- Payant : version cloud hebergee par NetroIA (cle-en-main) + features equipe/entreprise.

Sequence : **1) Video demo + waitlist  ->  2) Repo GitHub pret a cloner  ->  3) Cloud payant.**

---

## PHASE 1 — Video demo + waitlist (capter l'audience)

### Objectif
Creer le desir AVANT de livrer. Filtrer les vrais interesses. Cout : 0 EUR.

### Script video (60 a 90 secondes)

1. **Accroche (0-8s)** : poser le probleme.
   "Les agents IA codent en yolo. Ils peuvent tout casser. Et si un agent
   construisait des applis entieres, mais sous controle total ?"

2. **Le geste magique (8-35s)** : montrer le studio.
   On tape une intention simple ("un convertisseur de devises").
   On lance la forge. La barre SSE defile en direct : ADN, generation,
   membrane (vert = valide), conteneur durci, execution. Une appli nait.

3. **Le differenciateur (35-60s)** : la gouvernance.
   "Chaque ligne passe une membrane de securite. Le code tourne isole.
   L'humain garde le dernier mot. C'est un agent qui cree, mais gouverne."
   Montrer un rejet (mur viole = rouge) + auto-reparation.

4. **Le choix d'IA (60-75s)** : montrer les onglets.
   "Avec ton Claude, GPT, Gemini, DeepSeek, ou Ollama en local et gratuit."

5. **CTA (75-90s)** :
   "NEOGEN arrive. Lien en commentaire pour la beta. Dis-moi en commentaire
   quelle appli tu ferais forger en premier."

Outils video possibles : capture d'ecran reelle (OBS) + montage. Eviter le
sur-produit : la forge en direct EST le wow, le brut credibilise.

### Brouillon post LinkedIn

> J'ai construit un organisme logiciel.
>
> Tu lui decris une intention. Il forge une application complete, sous tes yeux :
> il ecrit le code, le valide dans une membrane de securite, l'execute dans un
> conteneur isole, et l'enregistre. En direct.
>
> La difference avec les agents IA actuels ? Ils codent en yolo. NEOGEN code
> gouverne : chaque ligne passe des murs, l'execution est isolee, et l'humain
> garde le dernier mot. La creation sans la perte de controle.
>
> Il marche avec l'IA de TON choix : Claude, GPT, Gemini, DeepSeek, ou Ollama
> en local (100% gratuit, hors-ligne). Aucune dependance a un fournisseur.
>
> Je cherche des testeurs pour la beta. Si tu veux forger ta premiere appli,
> le lien d'inscription est en commentaire.
>
> Quelle appli tu ferais creer en premier ? Dis-le moi plus bas.
>
> #IA #DevTools #OpenSource #IndieHacker #Agents

(Mettre le lien waitlist en PREMIER commentaire, pas dans le post : LinkedIn
penalise les liens externes dans le corps du post.)

### Waitlist : option la plus simple
- **Tally.so** ou **Google Form** : gratuit, 5 min a creer. Champs : email,
  "quelle appli tu ferais forger", niveau technique (sait lancer Docker ?).
- Le champ "niveau technique" te permet de prioriser les testeurs qui iront
  au bout du `docker compose up`.

---

## PHASE 2 — Repo GitHub pret a cloner

### Checklist avant de rendre public
- [x] README clair (installation 5 min, choix d'IA) — fait
- [x] .dockerignore (image vierge) — fait
- [x] Aucune cle / produit / email perso — fait
- [ ] Fichier LICENSE (decision a prendre, voir ci-dessous)
- [ ] .env.example (montrer les variables : ANTHROPIC_API_KEY, NEOGEN_BASE_URL, NEOGEN_ADMIN_EMAIL)
- [ ] Capture d'ecran ou GIF dans le README (le wow visuel)
- [ ] Verifier un `git clone` propre sur une machine neuve (ou dossier vierge)

### Licence : le point a trancher (open core)
Pour proteger ton offre cloud tout en etant "ouvert" :
- **Business Source License (BSL 1.1)** : usage self-host libre, INTERDIT de
  revendre NEOGEN comme service managé concurrent, bascule en open-source
  apres N annees. Utilisee par Sentry, MariaDB, HashiCorp (avant). Recommandee
  pour l'open core.
- Alternative permissive (Apache 2.0) : adoption max, mais un concurrent peut
  revendre ton cloud. A eviter si le cloud paye est ta monetisation.
- Une licence = un acte juridique : a valider (OpenLegi / juriste) avant
  publication publique.

---

## PHASE 3 — Cloud payant (open core, plus tard)

- Tu heberges NEOGEN sur une machine dediee (jamais le VPS prod netroia.tech).
- Stripe est deja a moitie integre (le don) : reutilisable pour l'abonnement.
- Idees de fonctions payantes (cloud-only, donc non contournables en self-host) :
  delegation multi-agents illimitee, evolution 2 vitesses, productions illimitees,
  espace equipe, historique long, support. Le self-host garde les fonctions de base.

---

## Garde-fous
- Jamais le VPS prod (187.124.36.81 / netroia.tech / n8n) pour heberger NEOGEN.
- Docker socket = machine dediee uniquement.
- Self-host = cle de l'utilisateur, jamais les credits de Jordan.

*Cree : 2026-06-21 — Plan valide par Jordan (open core + video/waitlist puis repo).*
