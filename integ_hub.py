"""
NEOGEN — Hub des intégrations actives.

Stocke les clés d'intégration côté serveur (data/integrations_actives.json).
Seules les intégrations avec type='key' ou type='url' sont stockées ici.
Les oauth (Google Drive, Gmail, etc.) sont marquées actives sans clé côté serveur.

Sécurité : stockage local uniquement (docker bind mount ./data/).
Pour un déploiement multi-utilisateur, remplacer par secrets vault.
"""
from __future__ import annotations
import json
import pathlib

_DATA_DIR = pathlib.Path(__file__).parent / "data"
_FILE = _DATA_DIR / "integrations_actives.json"

# Actions disponibles par service — injectées dans le prompt système
ACTIONS_PAR_SERVICE: dict[str, str] = {
    "notion":      "chercher(query), lire_page(page_id), creer_page(parent_id, title, content)",
    "slack":       "envoyer_message(channel, texte), lire_canal(channel, limit=10)",
    "telegram":    "envoyer_message(chat_id, texte)",
    "discord":     "envoyer_message(channel_id, texte)",
    "github":      "lire_issues(repo), creer_issue(repo, titre, corps), lire_repo(repo)",
    "linear":      "lire_issues(), creer_issue(titre, description, team_id?)",
    "airtable":    "lire_records(base_id, table), creer_record(base_id, table, champs_json)",
    "todoist":     "lire_taches(), creer_tache(contenu, due_date?)",
    "hubspot":     "lire_contacts(limit?), creer_contact(email, prenom?, nom?)",
    "brevo":       "envoyer_email(to, sujet, html), lire_contacts(limit?)",
    "calendly":    "evenements_a_venir(count?)",
    "figma":       "lire_fichier(file_key), lire_composants(file_key)",
    "vercel":      "lister_deployments(limit?), lire_projet(project_id)",
    "perplexity":  "rechercher(query)",
    "tavily":      "rechercher(query, max_results?)",
    "elevenlabs":  "lister_voix(), synthetiser(texte, voice_id)",
    "pinterest":   "lire_profil(), lire_epingles(ad_account_id?)",
    "deerflow":    "rechercher(query)",
    "brevo":       "envoyer_email(to, sujet, html), lire_contacts(limit?)",
}


def _charger() -> dict:
    try:
        if _FILE.exists():
            return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _sauver(data: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def activer(name: str, key: str, type_: str = "key") -> None:
    data = _charger()
    data[name] = {"key": key, "type": type_}
    _sauver(data)


def desactiver(name: str) -> None:
    data = _charger()
    data.pop(name, None)
    _sauver(data)


def get_key(name: str) -> str | None:
    return (_charger().get(name) or {}).get("key") or None


def is_active(name: str) -> bool:
    return name in _charger()


def liste_actives() -> list[str]:
    return list(_charger().keys())


def bloc_pour_prompt() -> str:
    """Injecte les intégrations actives dans le prompt système des agents.
    Vide si aucune intégration active."""
    actives = _charger()
    if not actives:
        return ""
    lignes = ["\n\nINTEGRATIONS ACTIVES (services connectes par l'utilisateur) :"]
    for name in actives:
        actions = ACTIONS_PAR_SERVICE.get(name, "appeler(params_json)")
        lignes.append(f'  - {name} : {actions}')
    lignes.append(
        "\nPour appeler une integration : outil=\"integration\", "
        'arguments={"service":"<nom>","action":"<action>","params":"{...json...}"}. '
        "Pour les actions modifiant des données : confirme avec l'utilisateur d'abord."
    )
    return "\n".join(lignes)
