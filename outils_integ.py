"""
NEOGEN — Outil dispatch pour toutes les intégrations actives.

Un seul point d'entrée : outil_integration(service, action, params).
L'agent connaît les actions disponibles via le bloc_pour_prompt() de integ_hub.
"""
from __future__ import annotations
import json
import httpx
import integ_hub


def _key(service: str) -> str | None:
    return integ_hub.get_key(service)


def _p(params_str: str) -> dict:
    if not params_str:
        return {}
    try:
        return json.loads(params_str)
    except Exception:
        return {}


# ── Notion ─────────────────────────────────────────────────────────────────

def _notion(action: str, p: dict) -> str:
    key = _key("notion")
    if not key:
        return "Notion non active. Active-la dans Integrations."
    h = {"Authorization": f"Bearer {key}", "Notion-Version": "2022-06-28",
         "Content-Type": "application/json"}
    with httpx.Client(timeout=15) as c:
        if action == "chercher":
            r = c.post("https://api.notion.com/v1/search",
                       headers=h, json={"query": p.get("query", "")})
            data = r.json()
            results = data.get("results", [])[:5]
            return json.dumps([{"id": x.get("id"), "title": _notion_title(x)}
                                for x in results], ensure_ascii=False)
        if action == "lire_page":
            page_id = p.get("page_id", "")
            r = c.get(f"https://api.notion.com/v1/pages/{page_id}", headers=h)
            data = r.json()
            return json.dumps({"id": data.get("id"), "title": _notion_title(data),
                                "url": data.get("url")}, ensure_ascii=False)
        if action == "creer_page":
            body = {
                "parent": {"page_id": p.get("parent_id", "")},
                "properties": {"title": {"title": [{"text": {"content": p.get("title", "")}}]}},
            }
            if p.get("content"):
                body["children"] = [{"object": "block", "type": "paragraph",
                                      "paragraph": {"rich_text": [{"text": {"content": p["content"]}}]}}]
            r = c.post("https://api.notion.com/v1/pages", headers=h, json=body)
            data = r.json()
            return json.dumps({"id": data.get("id"), "url": data.get("url")}, ensure_ascii=False)
    return f"Action Notion inconnue : {action}"


def _notion_title(obj: dict) -> str:
    try:
        props = obj.get("properties", {})
        for val in props.values():
            t = val.get("title", [])
            if t:
                return t[0].get("plain_text", "")
    except Exception:
        pass
    return obj.get("id", "")


# ── Slack ───────────────────────────────────────────────────────────────────

def _slack(action: str, p: dict) -> str:
    key = _key("slack")
    if not key:
        return "Slack non actif. Active-le dans Integrations."
    h = {"Authorization": f"Bearer {key}"}
    with httpx.Client(timeout=15) as c:
        if action == "envoyer_message":
            r = c.post("https://slack.com/api/chat.postMessage", headers=h,
                       json={"channel": p.get("channel", ""), "text": p.get("texte", "")})
            data = r.json()
            if data.get("ok"):
                return f"Message envoye dans #{p.get('channel')} (ts={data.get('ts')})"
            return f"Erreur Slack : {data.get('error', 'inconnu')}"
        if action == "lire_canal":
            r = c.get("https://slack.com/api/conversations.history", headers=h,
                      params={"channel": p.get("channel", ""), "limit": p.get("limit", 10)})
            data = r.json()
            msgs = data.get("messages", [])[:10]
            return json.dumps([{"user": m.get("user"), "texte": m.get("text", "")[:200]}
                                for m in msgs], ensure_ascii=False)
    return f"Action Slack inconnue : {action}"


# ── Telegram ────────────────────────────────────────────────────────────────

def _telegram(action: str, p: dict) -> str:
    key = _key("telegram")
    if not key:
        return "Telegram non actif. Active-le dans Integrations."
    with httpx.Client(timeout=15) as c:
        if action == "envoyer_message":
            chat_id = p.get("chat_id", "")
            texte = p.get("texte", "")
            r = c.post(f"https://api.telegram.org/bot{key}/sendMessage",
                       json={"chat_id": chat_id, "text": texte, "parse_mode": "Markdown"})
            data = r.json()
            if data.get("ok"):
                return f"Message Telegram envoye (message_id={data['result']['message_id']})"
            return f"Erreur Telegram : {data.get('description', 'inconnu')}"
    return f"Action Telegram inconnue : {action}"


# ── Discord ─────────────────────────────────────────────────────────────────

def _discord(action: str, p: dict) -> str:
    key = _key("discord")
    if not key:
        return "Discord non actif. Active-le dans Integrations."
    h = {"Authorization": f"Bot {key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=15) as c:
        if action == "envoyer_message":
            channel_id = p.get("channel_id", "")
            r = c.post(f"https://discord.com/api/v10/channels/{channel_id}/messages",
                       headers=h, json={"content": p.get("texte", "")})
            if r.status_code in (200, 201):
                data = r.json()
                return f"Message Discord envoye (id={data.get('id')})"
            return f"Erreur Discord (HTTP {r.status_code}) : {r.text[:200]}"
    return f"Action Discord inconnue : {action}"


# ── GitHub ──────────────────────────────────────────────────────────────────

def _github(action: str, p: dict) -> str:
    key = _key("github")
    if not key:
        return "GitHub non actif. Active-le dans Integrations."
    h = {"Authorization": f"Bearer {key}", "Accept": "application/vnd.github+json"}
    with httpx.Client(timeout=15) as c:
        if action == "lire_issues":
            repo = p.get("repo", "")
            r = c.get(f"https://api.github.com/repos/{repo}/issues",
                      headers=h, params={"state": "open", "per_page": 10})
            return json.dumps([{"number": i["number"], "title": i["title"], "state": i["state"]}
                                for i in r.json()[:10]], ensure_ascii=False)
        if action == "creer_issue":
            repo = p.get("repo", "")
            r = c.post(f"https://api.github.com/repos/{repo}/issues", headers=h,
                       json={"title": p.get("titre", ""), "body": p.get("corps", "")})
            data = r.json()
            return json.dumps({"number": data.get("number"), "url": data.get("html_url")},
                               ensure_ascii=False)
        if action == "lire_repo":
            r = c.get(f"https://api.github.com/repos/{p.get('repo','')}", headers=h)
            data = r.json()
            return json.dumps({"name": data.get("name"), "description": data.get("description"),
                                "stars": data.get("stargazers_count"),
                                "language": data.get("language")}, ensure_ascii=False)
    return f"Action GitHub inconnue : {action}"


# ── Linear ──────────────────────────────────────────────────────────────────

def _linear(action: str, p: dict) -> str:
    key = _key("linear")
    if not key:
        return "Linear non actif. Active-le dans Integrations."
    h = {"Authorization": key, "Content-Type": "application/json"}
    with httpx.Client(timeout=15) as c:
        if action == "lire_issues":
            r = c.post("https://api.linear.app/graphql", headers=h,
                       json={"query": "{ viewer { assignedIssues { nodes { id title state { name } priority } } } }"})
            issues = r.json().get("data", {}).get("viewer", {}).get("assignedIssues", {}).get("nodes", [])
            return json.dumps([{"id": i["id"], "title": i["title"],
                                "state": i.get("state", {}).get("name")} for i in issues[:15]],
                               ensure_ascii=False)
        if action == "creer_issue":
            mutation = """
mutation($titre: String!, $desc: String, $team: String) {
  issueCreate(input: {title: $titre, description: $desc, teamId: $team}) {
    issue { id title url } success
  }
}"""
            r = c.post("https://api.linear.app/graphql", headers=h,
                       json={"query": mutation, "variables": {
                           "titre": p.get("titre", ""), "desc": p.get("description", ""),
                           "team": p.get("team_id")}})
            data = r.json().get("data", {}).get("issueCreate", {})
            if data.get("success"):
                return json.dumps(data.get("issue", {}), ensure_ascii=False)
            return f"Erreur Linear : {r.json().get('errors', r.text[:200])}"
    return f"Action Linear inconnue : {action}"


# ── Airtable ────────────────────────────────────────────────────────────────

def _airtable(action: str, p: dict) -> str:
    key = _key("airtable")
    if not key:
        return "Airtable non actif. Active-le dans Integrations."
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    base = p.get("base_id", "")
    table = p.get("table", "")
    with httpx.Client(timeout=15) as c:
        if action == "lire_records":
            r = c.get(f"https://api.airtable.com/v0/{base}/{table}", headers=h,
                      params={"maxRecords": 20})
            records = r.json().get("records", [])
            return json.dumps([{"id": rec["id"], **rec.get("fields", {})}
                                for rec in records], ensure_ascii=False)
        if action == "creer_record":
            champs = json.loads(p.get("champs_json", "{}")) if isinstance(p.get("champs_json"), str) else p.get("champs_json", {})
            r = c.post(f"https://api.airtable.com/v0/{base}/{table}", headers=h,
                       json={"records": [{"fields": champs}]})
            created = r.json().get("records", [{}])[0]
            return json.dumps({"id": created.get("id"), "fields": created.get("fields", {})},
                               ensure_ascii=False)
    return f"Action Airtable inconnue : {action}"


# ── Todoist ─────────────────────────────────────────────────────────────────

def _todoist(action: str, p: dict) -> str:
    key = _key("todoist")
    if not key:
        return "Todoist non actif. Active-le dans Integrations."
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=15) as c:
        if action == "lire_taches":
            r = c.get("https://api.todoist.com/rest/v2/tasks", headers=h)
            tasks = r.json()
            return json.dumps([{"id": t["id"], "content": t["content"],
                                "due": t.get("due", {}).get("string") if t.get("due") else None}
                                for t in tasks[:20]], ensure_ascii=False)
        if action == "creer_tache":
            body = {"content": p.get("contenu", "")}
            if p.get("due_date"):
                body["due_string"] = p["due_date"]
            r = c.post("https://api.todoist.com/rest/v2/tasks", headers=h, json=body)
            data = r.json()
            return json.dumps({"id": data.get("id"), "content": data.get("content"),
                                "url": data.get("url")}, ensure_ascii=False)
    return f"Action Todoist inconnue : {action}"


# ── HubSpot ─────────────────────────────────────────────────────────────────

def _hubspot(action: str, p: dict) -> str:
    key = _key("hubspot")
    if not key:
        return "HubSpot non actif. Active-le dans Integrations."
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=15) as c:
        if action == "lire_contacts":
            r = c.get("https://api.hubapi.com/crm/v3/objects/contacts", headers=h,
                      params={"limit": p.get("limit", 10)})
            contacts = r.json().get("results", [])
            return json.dumps([{"id": x["id"], **x.get("properties", {})}
                                for x in contacts], ensure_ascii=False)
        if action == "creer_contact":
            r = c.post("https://api.hubapi.com/crm/v3/objects/contacts", headers=h,
                       json={"properties": {"email": p.get("email", ""),
                                            "firstname": p.get("prenom", ""),
                                            "lastname": p.get("nom", "")}})
            data = r.json()
            return json.dumps({"id": data.get("id"), "email": p.get("email")},
                               ensure_ascii=False)
    return f"Action HubSpot inconnue : {action}"


# ── Brevo ───────────────────────────────────────────────────────────────────

def _brevo(action: str, p: dict) -> str:
    key = _key("brevo")
    if not key:
        return "Brevo non actif. Active-le dans Integrations."
    h = {"api-key": key, "Content-Type": "application/json"}
    with httpx.Client(timeout=15) as c:
        if action == "envoyer_email":
            r = c.post("https://api.brevo.com/v3/smtp/email", headers=h,
                       json={"to": [{"email": p.get("to", "")}],
                             "subject": p.get("sujet", ""),
                             "htmlContent": p.get("html", p.get("texte", ""))})
            if r.status_code < 300:
                return f"Email envoye a {p.get('to')} (messageId={r.json().get('messageId')})"
            return f"Erreur Brevo : {r.text[:300]}"
        if action == "lire_contacts":
            r = c.get("https://api.brevo.com/v3/contacts", headers=h,
                      params={"limit": p.get("limit", 10)})
            contacts = r.json().get("contacts", [])
            return json.dumps([{"email": x.get("email"), "id": x.get("id")}
                                for x in contacts], ensure_ascii=False)
    return f"Action Brevo inconnue : {action}"


# ── Calendly ────────────────────────────────────────────────────────────────

def _calendly(action: str, p: dict) -> str:
    key = _key("calendly")
    if not key:
        return "Calendly non actif. Active-le dans Integrations."
    h = {"Authorization": f"Bearer {key}"}
    with httpx.Client(timeout=15) as c:
        if action == "evenements_a_venir":
            me = c.get("https://api.calendly.com/users/me", headers=h).json()
            user_uri = me.get("resource", {}).get("uri", "")
            r = c.get("https://api.calendly.com/scheduled_events", headers=h,
                      params={"user": user_uri, "status": "active",
                               "count": p.get("count", 5)})
            events = r.json().get("collection", [])
            return json.dumps([{"name": e.get("name"), "start": e.get("start_time"),
                                 "status": e.get("status")} for e in events],
                               ensure_ascii=False)
    return f"Action Calendly inconnue : {action}"


# ── Figma ───────────────────────────────────────────────────────────────────

def _figma(action: str, p: dict) -> str:
    key = _key("figma")
    if not key:
        return "Figma non actif. Active-le dans Integrations."
    h = {"X-Figma-Token": key}
    with httpx.Client(timeout=20) as c:
        if action in ("lire_fichier", "lire_composants"):
            file_key = p.get("file_key", "")
            r = c.get(f"https://api.figma.com/v1/files/{file_key}", headers=h)
            data = r.json()
            return json.dumps({
                "name": data.get("name"),
                "last_modified": data.get("lastModified"),
                "components_count": len(data.get("components", {})),
            }, ensure_ascii=False)
    return f"Action Figma inconnue : {action}"


# ── Vercel ──────────────────────────────────────────────────────────────────

def _vercel(action: str, p: dict) -> str:
    key = _key("vercel")
    if not key:
        return "Vercel non actif. Active-le dans Integrations."
    h = {"Authorization": f"Bearer {key}"}
    with httpx.Client(timeout=15) as c:
        if action == "lister_deployments":
            r = c.get("https://api.vercel.com/v6/deployments", headers=h,
                      params={"limit": p.get("limit", 5)})
            deploys = r.json().get("deployments", [])
            return json.dumps([{"uid": d.get("uid"), "url": d.get("url"),
                                 "state": d.get("state"), "created": d.get("created")}
                                for d in deploys], ensure_ascii=False)
        if action == "lire_projet":
            proj_id = p.get("project_id", "")
            r = c.get(f"https://api.vercel.com/v9/projects/{proj_id}", headers=h)
            data = r.json()
            return json.dumps({"name": data.get("name"), "framework": data.get("framework"),
                                "url": data.get("latestDeployments", [{}])[0].get("url") if data.get("latestDeployments") else None},
                               ensure_ascii=False)
    return f"Action Vercel inconnue : {action}"


# ── Perplexity ──────────────────────────────────────────────────────────────

def _perplexity(action: str, p: dict) -> str:
    key = _key("perplexity")
    if not key:
        return "Perplexity non actif. Active-le dans Integrations."
    if action == "rechercher":
        query = p.get("query", "")
        with httpx.Client(timeout=30) as c:
            r = c.post("https://api.perplexity.ai/chat/completions",
                       headers={"Authorization": f"Bearer {key}",
                                "Content-Type": "application/json"},
                       json={"model": "sonar", "messages": [{"role": "user", "content": query}]})
            if r.status_code == 200:
                choices = r.json().get("choices", [])
                content = choices[0].get("message", {}).get("content", "") if choices else ""
                return content[:1500]
            return f"Erreur Perplexity (HTTP {r.status_code}) : {r.text[:200]}"
    return f"Action Perplexity inconnue : {action}"


# ── Tavily ──────────────────────────────────────────────────────────────────

def _tavily(action: str, p: dict) -> str:
    key = _key("tavily")
    if not key:
        return "Tavily non actif. Active-le dans Integrations."
    if action == "rechercher":
        with httpx.Client(timeout=20) as c:
            r = c.post("https://api.tavily.com/search",
                       headers={"Content-Type": "application/json"},
                       json={"api_key": key, "query": p.get("query", ""),
                             "max_results": p.get("max_results", 5)})
            if r.status_code == 200:
                results = r.json().get("results", [])[:5]
                return json.dumps([{"title": x.get("title"), "url": x.get("url"),
                                    "snippet": x.get("content", "")[:300]} for x in results],
                                   ensure_ascii=False)
            return f"Erreur Tavily (HTTP {r.status_code}) : {r.text[:200]}"
    return f"Action Tavily inconnue : {action}"


# ── ElevenLabs ──────────────────────────────────────────────────────────────

def _elevenlabs(action: str, p: dict) -> str:
    key = _key("elevenlabs")
    if not key:
        return "ElevenLabs non actif. Active-le dans Integrations."
    h = {"xi-api-key": key}
    with httpx.Client(timeout=30) as c:
        if action == "lister_voix":
            r = c.get("https://api.elevenlabs.io/v1/voices", headers=h)
            voices = r.json().get("voices", [])[:10]
            return json.dumps([{"voice_id": v["voice_id"], "name": v["name"]}
                                for v in voices], ensure_ascii=False)
        if action == "synthetiser":
            voice_id = p.get("voice_id", "21m00Tcm4TlvDq8ikWAM")
            texte = p.get("texte", "")[:2500]
            r = c.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                       headers={**h, "Content-Type": "application/json"},
                       json={"text": texte, "model_id": "eleven_multilingual_v2"})
            if r.status_code == 200:
                import pathlib, time
                out = pathlib.Path(__file__).parent / "data" / "audio"
                out.mkdir(parents=True, exist_ok=True)
                fname = f"tts_{int(time.time())}.mp3"
                (out / fname).write_bytes(r.content)
                return f"Audio genere : data/audio/{fname} ({len(r.content)} bytes)"
            return f"Erreur ElevenLabs (HTTP {r.status_code}) : {r.text[:200]}"
    return f"Action ElevenLabs inconnue : {action}"


# ── Dispatch principal ───────────────────────────────────────────────────────

_DISPATCHERS: dict[str, object] = {
    "notion":      _notion,
    "slack":       _slack,
    "telegram":    _telegram,
    "discord":     _discord,
    "github":      _github,
    "linear":      _linear,
    "airtable":    _airtable,
    "todoist":     _todoist,
    "hubspot":     _hubspot,
    "brevo":       _brevo,
    "calendly":    _calendly,
    "figma":       _figma,
    "vercel":      _vercel,
    "perplexity":  _perplexity,
    "tavily":      _tavily,
    "elevenlabs":  _elevenlabs,
}


def outil_integration(service: str = "", action: str = "", params: str = "", **kw) -> str:
    """Appelle un service integre par l'utilisateur.
    service : notion|slack|telegram|discord|github|linear|airtable|todoist|hubspot|brevo|calendly|figma|vercel|perplexity|tavily|elevenlabs
    action : depend du service (ex: chercher, envoyer_message, creer_issue, lire_taches...)
    params : JSON des parametres de l'action (ex: {"channel":"#general","texte":"bonjour"})"""
    service = (service or "").strip().lower()
    action = (action or "").strip().lower()
    if not service:
        actives = integ_hub.liste_actives()
        return f"Service manquant. Integrations actives : {', '.join(actives) or 'aucune'}"
    if not integ_hub.is_active(service):
        return f"Integration '{service}' non active. Active-la dans la section Integrations."
    dispatcher = _DISPATCHERS.get(service)
    if not dispatcher:
        return f"Service '{service}' non reconnu ou non implemente."
    try:
        return dispatcher(action, _p(params))  # type: ignore[operator]
    except httpx.TimeoutException:
        return f"Timeout : le service '{service}' n'a pas repondu dans les delais."
    except Exception as exc:
        return f"Erreur {service}/{action} : {exc}"
