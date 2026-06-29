# NEOGEN

**Un agent IA autonome qui tourne sur ta machine.**

NEOGEN pense, crée, forge du code, s'améliore — avec l'IA de ton choix, tes clés, tes données chez toi.

> Conçu par Jordan VINCENT (NetroIA) — Protection IP : eSoleau INPI 2026

---

## Ce que NEOGEN fait

- **Agents conversationnels** avec outils réels (mémoire, navigation web, RPA, création)
- **Forge de code** : une idée → Claude/GPT génère du vrai Python → testé en sandbox Docker → intégré
- **La Pensée** : intelligence collective autonome qui fait émerger idées, tendances, propositions
- **Auto-évolution** : NEOGEN se modifie lui-même via des stores data-driven (jamais le code noyau)
- **Multi-provider** : Claude, GPT, Gemini, DeepSeek, Mistral, ou **Ollama en local et gratuit**

---

## Démarrage en 3 commandes

**Prérequis : Docker Desktop installé et lancé.**

```bash
git clone https://github.com/captainNetroia/NEOGEN.git && cd NEOGEN
cp .env.example .env          # optionnel : ajouter ta clé IA
docker compose up --build
```

Puis ouvrir [http://localhost:8000](http://localhost:8000)

> **Sans aucune clé IA**, NEOGEN fonctionne avec Ollama (100% local et gratuit).
> Intégrations → onglet Local → entrer l'URL Ollama → choisir le modèle.

### Scripts de lancement rapide

| OS | Commande |
|---|---|
| Windows | Double-clic sur `Lancer-NEOGEN.bat` |
| Mac / Linux | `./start.sh` |

---

## Choisir ton IA (BYOK — Bring Your Own Key)

Ta clé reste sur ta machine, n'est jamais stockée côté serveur.

| Provider | Clé |
|---|---|
| Claude (Anthropic) | `sk-ant-...` |
| GPT (OpenAI) | `sk-...` |
| Gemini (Google) | `AIza...` |
| DeepSeek | `sk-...` |
| Mistral | `...` |
| **Ollama (local, gratuit)** | aucune clé |

Configuration : **Intégrations → Modèle IA → onglet du provider → coller la clé → Activer**

---

## Mise à jour

```bash
# Windows
Mettre-a-jour-NEOGEN.bat

# Mac / Linux
./update.sh
```

---

## Déploiement sur serveur (avec forge sécurisée)

Pour héberger NEOGEN avec la forge Docker active tout en protégeant le reste du serveur,
utiliser `docker-compose.prod.yml` — il inclut 3 couches de sécurité :

1. **Socket proxy** (Tecnativa) — filtre les opérations Docker autorisées
2. **Réseaux isolés** — NEOGEN ne peut pas atteindre les autres services
3. **Limites ressources** — CPU/RAM plafonnés, un job forge ne peut pas saturer le serveur

```bash
cp .env.example .env
# Remplir NEOGEN_BASE_URL, NEOGEN_OWNER_EMAIL dans .env
docker compose -f docker-compose.prod.yml up -d --build
```

Puis configurer nginx (exemple inclus dans `docs/nginx.conf.example`).

> `NEOGEN_OWNER_UNLIMITED` et `NEOGEN_ALLOW_DEFAULT_KEY` sont à **0** par défaut
> dans `docker-compose.prod.yml`. Ne jamais les passer à 1 en production publique.

---

## Architecture

```
api.py                  FastAPI — tous les endpoints
ui.py                   Interface web (HTML/CSS/JS)
agent_core.py           Moteur ReAct multi-tours (agents)
gateway.py              Abstraction LLM — 6 providers
forge_evolution.py      Forge idée → code → sandbox → intégration
evolution_gouvernee.py  Auto-évolution data-driven (sans toucher le noyau)
pensee.py               La Pensée — intelligence collective autonome
noyau.py                Murs immuables (gouvernance, sécurité)
user_namespace.py       Isolation multi-tenant (sac per-user)
docker-compose.yml      Lancement local
docker-compose.prod.yml Déploiement prod (socket-proxy + réseaux isolés)
```

---

## Sécurité

- Chaque code forgé tourne dans un conteneur Docker **isolé** (`--network none`, read-only, non-root)
- Les clés API ne sont **jamais** stockées côté serveur (headers par requête)
- `noyau.py` contient les 23 fichiers immuables — aucune évolution ne peut les réécrire
- En déploiement public : rate-limit IP, headers OWASP, CSP anti-exfiltration

---

## Licence

Ce projet est sous **Business Source License 1.1 (BSL 1.1)**.

- Usage **personnel et non-commercial** : libre
- Usage **commercial** (héberger comme service payant, distribuer dans un produit commercial) : contacter [captain@netroia.com](mailto:captain@netroia.com)
- Conversion en licence open source après 4 ans

---

*NEOGEN — NetroIA 2026*
