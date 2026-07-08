# CLAUDE.md — VIVARIUM (produit : NEOGEN)

> Projet-spécifique. Complète `C:\Netroia\CLAUDE.md` (règles globales).
> Ne pas dupliquer les règles globales ici.
> Créé : 2026-07-08 avec la rule `claude-md-creator`
> Note d'alias : le dossier s'appelle VIVARIUM, le produit livré s'appelle NEOGEN — les deux noms désignent le même projet.

## Domaine & Stack

- **Domaine** : IA / agents cognitifs / API FastAPI + Docker
- **Stack** : Python 3.12, FastAPI + uvicorn, anthropic SDK, Pydantic 2, Stripe, httpx — voir `requirements.txt`
- **Racine** : `C:\Netroia\VIVARIUM\`

## GOD Files du Domaine

> Lire en priorité au démarrage de session :

- `C:\Netroia\Production-NetroIA\architecture-GOD\GOD-ai.md` (contient la section "Ollama depuis un conteneur Docker" spécifique à ce projet)
- `C:\Netroia\Production-NetroIA\architecture-GOD\GOD-orchestrateur.md` (si travail cross-agents)

## Credentials Requis

| Service | Fichier credentials | Note |
|---------|---------------------|------|
| Anthropic (fallback vision système + génération) | `C:\Netroia\credentials\anthropic-api.env` | Peut être à sec (crédit épuisé) — vérifier avant de compter dessus |
| Gemini (fallback vision système) | `C:\Netroia\credentials\gemini-api.env` | Peut être à sec (crédit épuisé) — vérifier avant de compter dessus |
| DeepSeek | `C:\Netroia\credentials\deepseek-api.env` | Pas de vision sur l'API publique (seulement sur chat.deepseek.com) |
| Stripe | `C:\Netroia\credentials\stripe.env` | Paiement packs GEN + abonnements, webhook signé |
| SSH VPS NEOGEN | `C:\Netroia\credentials\vps-neogen.env` / `ssh-vps.env` | Déploiement VPS |
| Webhook déploiement | `C:\Netroia\credentials\neogen-deploy-webhook.env` | Redéploiement auto sur push |
| Maintenance | `C:\Netroia\credentials\neogen-maintenance.env` | Endpoint de maintenance, vide = désactivé (fail-closed) |
| Tout le dossier credentials | monté en lecture seule dans le conteneur via `../credentials:/app/credentials:ro` | Ne JAMAIS copier dans l'image Docker |

## Chemins Clés

| Rôle | Chemin absolu |
|------|--------------|
| Sources | `C:\Netroia\VIVARIUM\` |
| Data persistante | `C:\Netroia\VIVARIUM\data\` (monté dans le conteneur, survit aux rebuild) |
| Interface propriétaire (forge UI) | `C:\Netroia\VIVARIUM\ui_custom.py` (monté, écrit par le conteneur, versionnable) |
| Docs déploiement | `C:\Netroia\VIVARIUM\docs\DEPLOY-WEBHOOK-SETUP.md` |

## Commandes Essentielles

```powershell
# Lancer (local)
C:\Netroia\VIVARIUM\Lancer-NEOGEN.bat

# Build + kill + restart (SEQUENCE OBLIGATOIRE après tout changement de code)
cd C:\Netroia\VIVARIUM
docker compose build neogen-api
docker compose stop neogen-api
docker compose up -d neogen-api

# Test santé
curl http://localhost:8000/health
```

## État Actuel

- **VPS** : NEOGEN déployé sur `76.13.53.162` (srv1792379, Ubuntu 24.04, 2 vCPU, 7.8 Go RAM), HTTPS actif. SSH confirmé fonctionnel avec `C:\Users\adrie\.ssh\id_ed25519`.
- **Remotes git** : `origin` = `https://github.com/captainNetroia/VIVARIUM.git`, `public` = `https://github.com/captainNetroia/NEOGEN.git` (le VPS clone `public`) — **toujours pousser sur les deux**.
- **Ollama** : local (Docker Desktop) via `host.docker.internal:11434/v1` ; VPS via `NEOGEN_OLLAMA_BASE=http://172.20.0.1:11434/v1` mais seulement 2 vCPU — `/api/tags` répond vite, une vraie génération peut timeout. Garder tel quel + avertissement UI, pas d'upgrade VPS prévu.
- **Vision (analyse d'image)** : fallback en cascade Anthropic système → Gemini système, activé via `NEOGEN_VISION_FALLBACK=1` (docker-compose.yml). Les deux clés système peuvent être à sec de crédit — dans ce cas, le message d'erreur combine les deux échecs pour que l'utilisateur sache que c'est un problème de crédit, pas de code.
- **Outil `lire_page_web`** : fetch HTTP + extraction texte d'une URL, accordé au Cerveau et au Secrétaire (pas de navigateur, pas de consentement RPA requis).
- **Étapes validées** : paiement Stripe idempotent (`credits.crediter_idempotent()`, dédup atomique sous le même verrou, webhook signé + re-vérification directe côté Stripe avant tout crédit), pas de double prélèvement possible.
- **Prochaine priorité** : voir `Documentation-Projets/NEOGEN/logs.md` pour le dernier état de session.

## Conventions Spécifiques au Projet

- Deux remotes git à synchroniser à chaque push (`origin` VIVARIUM + `public` NEOGEN).
- Jamais de push automatique — attendre le mot déclencheur explicite "Netroiapush".
- `outils.py` : format `OUTILS["nom"] = (fonction, "description")`, et TOUJOURS ajouter le nom d'outil aux profils d'agents concernés dans `agent_core.py` (`PROFILS[...]["outils"]` et/ou `_OUTILS_PAR_SECTION`) — sinon l'outil est invisible pour tous les agents malgré son enregistrement. Le moteur de cohérence interne (`/health` → `coherence.tensions`) détecte cet oubli automatiquement.
- `outils.py` et `agent_core.py` ne sont PAS bind-montés dans Docker → rebuild obligatoire après modification (contrairement à `ui_custom.py` et `data/`).

## Anti-Patterns Découverts sur CE Projet

> Pièges spécifiques à ce projet (anti-patterns globaux → voir AGENT-ANTI-PATTERNS.md)

- **Fallback vision qui masque la vraie cause** : si le fallback système échoue aussi, remonter les DEUX erreurs (provider actif + fallback), jamais une seule — sinon le diagnostic pointe vers le mauvais provider.
- **Ne jamais deviner un modèle vision pour un nouveau provider** : vérifier par appel API réel qu'un modèle supporte bien `image_url`/vision avant de l'ajouter à `VISION_MODELS` dans `gateway.py` — un blog tiers ou une doc marketing peut annoncer une capacité absente de l'API publique réelle (cas vécu avec DeepSeek : vision existe sur chat.deepseek.com, pas sur l'API).
- **`localStorage.neogen_active_provider`/`neogen_active_model`** : valeurs GLOBALES uniques partagées par TOUS les agents, pas par agent individuel — source de confusion si on pense avoir activé un modèle pour un agent spécifique.
