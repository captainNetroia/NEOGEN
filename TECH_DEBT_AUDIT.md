# Tech Debt Audit — NEOGEN (VIVARIUM)
Généré : 2026-06-23 · via skill `tech-debt-audit` (ksimback) · périmètre : code actif (hors `_archive/`, `data/`)

## Executive summary (classé par impact)
- **2 god files** concentrent la dette et le churn : `ui.py` (3772 LOC, 34 modifs/90j) et `api.py` (2030 LOC, 28 modifs/90j).
- `ui.py` = HTML + CSS + JS + Python dans **une seule chaîne** → toute évolution UI touche un fichier de 3700 lignes (cause directe du churn).
- **Duplication transverse** : 4 implémentations de « lire une clé dans credentials/ », 5+ modules réinventent les helpers JSONL `_lire/_ecrire`.
- **API dépréciée** : `@app.on_event("startup")` (api.py:66) — supprimé dans les FastAPI récents → bascule `lifespan`.
- **Dette de test** : `boosts/recompenses/anonymizer/telemetrie` ont un auto-test mais ne sont **pas** dans la suite `tests/test_neogen.py`.
- **Exceptions avalées** : ~55 `except Exception:` ; la plupart légitimes (socle robustesse), certaines silencieuses sans log (api.py, generator.py).
- Incohérence d'observabilité : Telegram expose `statut()` mais n'émet pas de `battement()` comme cron/auto-amélioration.
- Pas de `.gitattributes` → warnings LF/CRLF à chaque commit.

## Modèle mental de l'architecture
NEOGEN est un monolithe FastAPI **zéro-build** : `api.py` expose ~80 endpoints, `ui.py` sert une SPA en une page (chaîne `PAGE`). Le cœur métier est un pipeline gouverné (`pipeline.fabriquer` → membrane/scan/conteneur durci) alimenté par un gateway multi-provider (`gateway.py`) et orchestré en délégation parallèle (`orchestrateur.py`). Couche autonome récente bien isolée : `robustesse.py` (socle), `planificateur`, `auto_amelioration`, `competences`. La dette se concentre **non** dans le cœur métier (propre, testé) mais dans les 2 façades god-files qui ont grossi par accrétion.

## Findings

| ID | Catégorie | File:Line | Sévérité | Effort | Description | Recommandation |
|----|-----------|-----------|----------|--------|-------------|----------------|
| F001 | Décay archi | ui.py:1-3772 | High | L | God file : HTML/CSS/JS/Python en une chaîne `PAGE`. Tout changement UI = diff sur 3700 lignes | Extraire CSS et JS en fichiers statiques servis (`/static/app.js`, `/static/app.css`) ; garder zéro-build via `StaticFiles` |
| F002 | Décay archi | api.py:1-2030 | High | L | God file : ~80 endpoints (auth, premium, credits, télémétrie, rpa, taches…) dans un module | Découper en routers FastAPI (`routers/premium.py`, `routers/credits.py`, `routers/agents.py`) via `APIRouter` |
| F003 | Consistance | api.py (`_load_cred`), planificateur.py (`_cle_systeme`), generator.py (`_load_api_key`), passerelle_telegram.py | Medium | M | 4 façons de lire une clé dans `credentials/` | Centraliser dans `credentials_loader.py` (un seul `lire_cred(fichier, cle)`) ; les 4 appelants l'importent |
| F004 | Consistance | api.py (`_rjsonl/_ajsonl`), boosts.py, memoire_agent.py, planificateur.py, quotas.py | Medium | M | 5+ implémentations de lire/écrire JSONL | Ajouter `lire_jsonl/ajout_jsonl/ecrire_jsonl` dans `robustesse.py` (ou `stockage.py`) ; remplacer les copies |
| F005 | Dépréciation | api.py:66 | Medium | S | `@app.on_event("startup")` est déprécié (FastAPI ≥0.93, supprimé à terme) | Migrer vers `lifespan=` (contextmanager async) |
| F006 | Dette de test | tests/test_neogen.py | Medium | S | `boosts`, `recompenses`, `anonymizer`, `telemetrie` non couverts par la suite (seuls leurs `__main__` testent) | Ajouter 4 tests important leurs fonctions clés |
| F007 | Gestion erreur | generator.py, api.py (`except Exception: pass` sans log) | Medium | M | Échecs silencieux sans trace → debug difficile en prod | Router via `robustesse.protege/journaliser` (capturé ET logué) |
| F008 | Observabilité | passerelle_telegram.py | Low | S | `statut()` exposé mais pas de `battement()` → invisible dans `/health` quand actif | Émettre `rob.battement("telegram", ...)` dans la boucle de polling |
| F009 | Config/Git | (racine) absence `.gitattributes` | Low | S | Warnings LF↔CRLF à chaque `git add` | Ajouter `.gitattributes` (`* text=auto eol=lf`) |
| F010 | Décay archi | agent_core.py:1-823 | Medium | M | Outils + profils + boucle ReAct + cristallisation dans un module | Extraire `outils.py` (définitions d'outils) du moteur `dialoguer` |
| F011 | Sécurité (hygiène) | gateway.voir fallback (NEOGEN_VISION_FALLBACK) | Low | S | Fallback vision utilise la clé système si env activé : risque de coût non attendu si mal compris | OK car opt-in + off par défaut ; documenter clairement dans l'UI/README |

## Top 5 — si tu ne corriges que ça
1. **F003+F004 (duplication credentials + JSONL)** — vrai multiplicateur de bugs : un fix de sécurité sur la lecture de clé doit aujourd'hui être répété 4×. Centraliser élimine la classe entière. *Diff* : créer `credentials_loader.lire_cred()` + `robustesse.lire_jsonl/ajout_jsonl`, remplacer les appelants.
2. **F005 (startup déprécié)** — cassera à une montée de version FastAPI. Migration `lifespan` = ~15 lignes, sûre.
3. **F006 (tests monétisation)** — `credits/boosts/telemetrie` touchent argent + RGPD : non couverts = risque. 4 petits tests.
4. **F001 (ui.py)** — extraire JS/CSS en statiques : divise par ~3 la surface de churn, sans build. Plus gros effort mais plus gros gain de vélocité.
5. **F007 (exceptions silencieuses)** — router les `except: pass` legacy vers `robustesse.journaliser` pour ne plus debugger à l'aveugle.

## Quick wins (Low effort × Medium+ sévérité) — checklist
- [ ] F005 : migrer `on_event` → `lifespan` (api.py)
- [ ] F009 : ajouter `.gitattributes`
- [ ] F006 : 4 tests (boosts/recompenses/anonymizer/telemetrie)
- [ ] F008 : `battement("telegram")` dans la boucle de polling
- [ ] F003 : `credentials_loader.py` + remplacer les 4 appelants
- [ ] F004 : helpers JSONL dans robustesse + remplacer les copies

## Things that look bad but are actually fine (REQUIS)
- **`robustesse.py` : 8 `except Exception:`** — INTENTIONNEL. Le socle anti-crash ne DOIT jamais propager : c'est sa raison d'être. Chaque catch logue via `journaliser`. Correct par conception, ne pas « corriger ».
- **`ui.py` en une seule chaîne `PAGE`** — c'est un god file (F001) MAIS le choix zéro-build (aucun bundler, servi tel quel) est délibéré et a de la valeur (déploiement trivial). L'extraction en statiques garde ce bénéfice ; ne PAS introduire de build webpack.
- **`vivarium.py` (nom de module conservé malgré le rebrand NEOGEN)** — intentionnel : marqueurs runtime `___VIVARIUM_RESULT___` etc. préservés. Documenté dans logs. Ne pas renommer à l'aveugle.
- **Imports paresseux partout dans agent_core/api** (`import x` dans les fonctions) — semble être une odeur, mais c'est volontaire : évite les cycles d'import et garde le smoke test hors-ligne. Garder.
- **`_archive/physique-du-sens/`** — gros volume de code « mort » apparent, mais c'est de l'archive explicite (préfixe `_archive`), hors périmètre runtime. Ne pas auditer comme dette active.

## Open questions pour le mainteneur
- `executeur_reseau.py` (3 `except`) est-il encore utilisé par un chemin actif, ou résiduel ?
- Les modules `matiere/apprentissage/invention/selection/evolution` (la « physique du sens ») sont-ils sur un chemin de production ou de la R&D conservée ? (Impacte s'ils doivent être testés/maintenus au même standard.)
- `quotas.py` + `credits.py` ont des barèmes de coût en double conceptuel (PREMIUM_ONLY vs COUTS) : source de vérité unique souhaitée ?
