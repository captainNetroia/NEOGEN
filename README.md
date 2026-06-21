# NEOGEN

Un organisme logiciel : tu decris une intention, NEOGEN forge une application fonctionnelle.
Code genere, valide en membrane, execute en conteneur durci, persistant au registre.

Concu par Jordan VINCENT (NetroIA). Protection IP : eSoleau DSO2026022686 (INPI, 2026-06-19).

---

## Ce que NEOGEN fait

1. Tu decris ce que tu veux construire (en francais ou anglais)
2. NEOGEN scanne l'intention, propose un ADN (objectif, regles, capacites)
3. Tu valides ou ajustes l'ADN
4. La forge tourne en direct (SSE) : generation, membrane, conteneur durci, execution
5. Le produit est enregistre, testable, telechargeable, evolvable

Chaque produit est versionne en generations. Tu peux le faire evoluer, revenir en arriere,
le telecharger en ZIP.

---

## Installation locale (5 minutes)

**Prerequis :** Docker Desktop installe et lance.

```bash
# 1. Cloner
git clone <repo-url> neogen && cd neogen

# 2. Lancer (remplacer sk-ant-... par ta cle Anthropic)
ANTHROPIC_API_KEY=sk-ant-... docker compose up --build

# 3. Ouvrir
http://localhost:8000
```

C'est tout. Aucune autre dependance.

### Ce qui est inclus gratuitement

- Generation de code par IA (Claude)
- Membrane de gouvernance (validation automatique)
- Execution en conteneur Docker durci
- Registre persistant des produits fabriques
- Studio de creation interactif (stepper A-Z)
- Analyse conformite indicative
- Telechargement ZIP du code genere
- Interface multi-modele (gateway configurable)

### Integrations optionnelles

| Integration | Fichier credentials | Usage |
|-------------|---------------------|-------|
| OpenLegi (Legifrance) | `credentials/openlegi.env` | Analyse juridique dans le scan |
| Stripe | `credentials/stripe.env` | Bouton de don dans l'interface |

Ces integrations sont **facultatives**. NEOGEN fonctionne entierement sans elles.

---

## Deploiement sur serveur

```bash
# Sur ta machine distante (Linux + Docker)
git clone <repo-url> neogen && cd neogen

# Variables d'environnement
export ANTHROPIC_API_KEY=sk-ant-...
export NEOGEN_BASE_URL=https://ton-domaine.com   # pour les redirections Stripe

docker compose up -d --build
```

Puis configurer un reverse proxy (Nginx, Caddy) vers le port 8000.

### Exemple Nginx minimal

```nginx
server {
    listen 443 ssl;
    server_name ton-domaine.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_buffering off;              # requis pour les flux SSE
        proxy_read_timeout 300s;
    }
}
```

---

## Structure des credentials (optionnel)

```
credentials/          <- dossier frere de neogen/, monte en lecture seule
├── openlegi.env      <- OPENLEGI_TOKEN=xxx
└── stripe.env        <- STRIPE_SECRET_KEY=sk_live_...
```

Ces fichiers ne sont jamais copies dans l'image Docker.

---

## Architecture technique

```
api.py              <- FastAPI : tous les endpoints (generation, registre, don, integrations)
ui.py               <- Interface web (HTML/CSS/JS, servie par FastAPI)
pipeline.py         <- Pipeline de fabrication (forge + membrane + conteneur)
generator.py        <- Generation de code via LLM (gateway multi-modele)
gateway.py          <- Abstraction provider : Anthropic, OpenAI, Gemini, DeepSeek...
membrane.py         <- Validation gouvernance (murs, regles, capacites)
registre.py         <- Persistance des produits fabriques
promoteur.py        <- Promotion produit -> application web deployable
orchestrateur.py    <- Decomposition en organes + delegation agentique
evolution.py        <- Evolution 2 vitesses (jumeau + etalon anti-Goodhart)
docker-compose.yml  <- Orchestration du service
```

---

## Notes de securite

- Le socket Docker est monte pour executer le code genere en conteneur durci.
  **Lancer uniquement sur une machine dediee, jamais sur un VPS de production partage.**
- Les credentials sont montes en lecture seule, jamais copiees dans l'image.
- Chaque produit execute dans un conteneur isole avec capacites graduees (reseau, persistance).

---

*NEOGEN v13 -- Jordan VINCENT / NetroIA -- 2026*
