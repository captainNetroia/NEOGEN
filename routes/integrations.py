from __future__ import annotations
import asyncio
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .deps import _load_cred

router = APIRouter()


class IntegVerifBody(BaseModel):
    type: str
    name: str = ""
    value: str = ""


@router.get("/integrations/status")
def integrations_status():
    return {
        "openlegi": bool(_load_cred("openlegi.env", "OPENLEGI_TOKEN")),
        "stripe": bool(_load_cred("stripe.env", "STRIPE_SECRET_KEY")),
    }


# ── Verifiers par integration ──────────────────────────────────────────────

async def _verif_openlegi(val: str, c: httpx.AsyncClient) -> dict:
    r = await c.post(
        f"https://mcp.openlegi.fr/legifrance/mcp?token={val}",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
        timeout=12,
    )
    if r.status_code in (401, 403):
        return {"ok": False, "erreur": "Token refuse (401/403)."}
    if r.status_code < 500:
        return {"ok": True}
    return {"ok": False, "erreur": f"Service en erreur (HTTP {r.status_code})."}


async def _verif_notion(val: str, c: httpx.AsyncClient) -> dict:
    r = await c.get(
        "https://api.notion.com/v1/users/me",
        headers={"Authorization": f"Bearer {val}", "Notion-Version": "2022-06-28"},
        timeout=10,
    )
    if r.status_code == 200:
        return {"ok": True}
    if r.status_code in (401, 403):
        return {"ok": False, "erreur": "Token Notion invalide."}
    return {"ok": False, "erreur": f"Notion en erreur (HTTP {r.status_code})."}


async def _verif_slack(val: str, c: httpx.AsyncClient) -> dict:
    r = await c.get(
        "https://slack.com/api/auth.test",
        headers={"Authorization": f"Bearer {val}"},
        timeout=10,
    )
    if r.status_code == 200:
        data = r.json()
        if data.get("ok"):
            return {"ok": True}
        return {"ok": False, "erreur": data.get("error", "token_invalid")}
    return {"ok": False, "erreur": f"Slack inaccessible (HTTP {r.status_code})."}


async def _verif_telegram(val: str, c: httpx.AsyncClient) -> dict:
    r = await c.get(f"https://api.telegram.org/bot{val}/getMe", timeout=10)
    if r.status_code == 200:
        data = r.json()
        if data.get("ok"):
            return {"ok": True}
        return {"ok": False, "erreur": data.get("description", "Token invalide.")}
    return {"ok": False, "erreur": "Token Telegram invalide."}


async def _verif_discord(val: str, c: httpx.AsyncClient) -> dict:
    r = await c.get(
        "https://discord.com/api/v10/users/@me",
        headers={"Authorization": f"Bot {val}"},
        timeout=10,
    )
    if r.status_code == 200:
        return {"ok": True}
    if r.status_code in (401, 403):
        return {"ok": False, "erreur": "Token Discord invalide."}
    return {"ok": False, "erreur": f"Discord en erreur (HTTP {r.status_code})."}


async def _verif_hubspot(val: str, c: httpx.AsyncClient) -> dict:
    r = await c.get(
        "https://api.hubapi.com/account-info/v3/details",
        headers={"Authorization": f"Bearer {val}"},
        timeout=10,
    )
    if r.status_code == 200:
        return {"ok": True}
    if r.status_code in (401, 403):
        return {"ok": False, "erreur": "Token HubSpot invalide."}
    return {"ok": False, "erreur": f"HubSpot en erreur (HTTP {r.status_code})."}


async def _verif_brevo(val: str, c: httpx.AsyncClient) -> dict:
    r = await c.get(
        "https://api.brevo.com/v3/account",
        headers={"api-key": val},
        timeout=10,
    )
    if r.status_code == 200:
        return {"ok": True}
    if r.status_code in (401, 403):
        return {"ok": False, "erreur": "Cle API Brevo invalide."}
    return {"ok": False, "erreur": f"Brevo en erreur (HTTP {r.status_code})."}


async def _verif_airtable(val: str, c: httpx.AsyncClient) -> dict:
    r = await c.get(
        "https://api.airtable.com/v0/meta/whoami",
        headers={"Authorization": f"Bearer {val}"},
        timeout=10,
    )
    if r.status_code == 200:
        return {"ok": True}
    if r.status_code in (401, 403):
        return {"ok": False, "erreur": "Token Airtable invalide."}
    return {"ok": False, "erreur": f"Airtable en erreur (HTTP {r.status_code})."}


async def _verif_todoist(val: str, c: httpx.AsyncClient) -> dict:
    r = await c.get(
        "https://api.todoist.com/rest/v2/projects",
        headers={"Authorization": f"Bearer {val}"},
        timeout=10,
    )
    if r.status_code == 200:
        return {"ok": True}
    if r.status_code in (401, 403):
        return {"ok": False, "erreur": "Token Todoist invalide."}
    return {"ok": False, "erreur": f"Todoist en erreur (HTTP {r.status_code})."}


async def _verif_calendly(val: str, c: httpx.AsyncClient) -> dict:
    r = await c.get(
        "https://api.calendly.com/users/me",
        headers={"Authorization": f"Bearer {val}"},
        timeout=10,
    )
    if r.status_code == 200:
        return {"ok": True}
    if r.status_code in (401, 403):
        return {"ok": False, "erreur": "Token Calendly invalide."}
    return {"ok": False, "erreur": f"Calendly en erreur (HTTP {r.status_code})."}


async def _verif_github(val: str, c: httpx.AsyncClient) -> dict:
    r = await c.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {val}", "Accept": "application/vnd.github+json"},
        timeout=10,
    )
    if r.status_code == 200:
        return {"ok": True}
    if r.status_code in (401, 403):
        return {"ok": False, "erreur": "Token GitHub invalide ou expire."}
    return {"ok": False, "erreur": f"GitHub en erreur (HTTP {r.status_code})."}


async def _verif_linear(val: str, c: httpx.AsyncClient) -> dict:
    r = await c.post(
        "https://api.linear.app/graphql",
        headers={"Authorization": val, "Content-Type": "application/json"},
        json={"query": "{ viewer { id name } }"},
        timeout=10,
    )
    if r.status_code == 200:
        data = r.json()
        if "errors" in data:
            return {"ok": False, "erreur": data["errors"][0].get("message", "Token invalide.")}
        return {"ok": True}
    if r.status_code in (401, 403):
        return {"ok": False, "erreur": "Token Linear invalide."}
    return {"ok": False, "erreur": f"Linear en erreur (HTTP {r.status_code})."}


async def _verif_figma(val: str, c: httpx.AsyncClient) -> dict:
    r = await c.get(
        "https://api.figma.com/v1/me",
        headers={"X-Figma-Token": val},
        timeout=10,
    )
    if r.status_code == 200:
        return {"ok": True}
    if r.status_code in (401, 403):
        return {"ok": False, "erreur": "Token Figma invalide."}
    return {"ok": False, "erreur": f"Figma en erreur (HTTP {r.status_code})."}


async def _verif_vercel(val: str, c: httpx.AsyncClient) -> dict:
    r = await c.get(
        "https://api.vercel.com/v2/user",
        headers={"Authorization": f"Bearer {val}"},
        timeout=10,
    )
    if r.status_code == 200:
        return {"ok": True}
    if r.status_code in (401, 403):
        return {"ok": False, "erreur": "Token Vercel invalide."}
    return {"ok": False, "erreur": f"Vercel en erreur (HTTP {r.status_code})."}


async def _verif_elevenlabs(val: str, c: httpx.AsyncClient) -> dict:
    r = await c.get(
        "https://api.elevenlabs.io/v1/user",
        headers={"xi-api-key": val},
        timeout=10,
    )
    if r.status_code == 200:
        return {"ok": True}
    if r.status_code in (401, 403):
        return {"ok": False, "erreur": "Cle API ElevenLabs invalide."}
    return {"ok": False, "erreur": f"ElevenLabs en erreur (HTTP {r.status_code})."}


async def _verif_pinterest(val: str, c: httpx.AsyncClient) -> dict:
    r = await c.get(
        "https://api.pinterest.com/v5/user_account",
        headers={"Authorization": f"Bearer {val}"},
        timeout=10,
    )
    if r.status_code == 200:
        return {"ok": True}
    if r.status_code in (401, 403):
        return {"ok": False, "erreur": "Token Pinterest invalide."}
    return {"ok": False, "erreur": f"Pinterest en erreur (HTTP {r.status_code})."}


_KEY_VERIFIERS = {
    "openlegi":   _verif_openlegi,
    "notion":     _verif_notion,
    "slack":      _verif_slack,
    "telegram":   _verif_telegram,
    "discord":    _verif_discord,
    "hubspot":    _verif_hubspot,
    "brevo":      _verif_brevo,
    "airtable":   _verif_airtable,
    "todoist":    _verif_todoist,
    "calendly":   _verif_calendly,
    "github":     _verif_github,
    "linear":     _verif_linear,
    "figma":      _verif_figma,
    "vercel":     _verif_vercel,
    "elevenlabs": _verif_elevenlabs,
    "pinterest":  _verif_pinterest,
}

# ── Routes ─────────────────────────────────────────────────────────────────

@router.post("/integrations/activer")
def integrations_activer(body: dict):
    """Stocke la clé d'une intégration côté serveur pour que les agents y accèdent."""
    import integ_hub
    name = (body.get("name") or "").strip()
    key = (body.get("key") or "").strip()
    type_ = (body.get("type") or "key").strip()
    if not name:
        return {"ok": False, "erreur": "name requis"}
    integ_hub.activer(name, key, type_)
    return {"ok": True, "name": name}


@router.delete("/integrations/activer/{name}")
def integrations_desactiver(name: str):
    """Supprime une intégration du stockage serveur."""
    import integ_hub
    integ_hub.desactiver(name)
    return {"ok": True}


@router.get("/integrations/actives")
def integrations_actives():
    """Liste les intégrations actives (sans les clés)."""
    import integ_hub
    return {"actives": integ_hub.liste_actives()}


@router.post("/integrations/verifier")
async def integrations_verifier(body: IntegVerifBody):
    from sanitizer import nettoyer
    t = (body.type or "").strip()
    val = (body.value or "").strip()

    if t == "oauth":
        return {"ok": False, "manuel": True,
                "erreur": "Verification automatique impossible (connexion via le navigateur)."}

    if t == "url":
        if not val:
            return {"ok": False, "erreur": "URL vide."}
        if not val.startswith(("http://", "https://")):
            val = "https://" + val
        try:
            async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
                r = await client.get(val)
            if r.status_code < 500:
                return {"ok": True}
            return {"ok": False, "erreur": f"Le service repond en erreur (HTTP {r.status_code})."}
        except Exception as e:
            return {"ok": False, "erreur": nettoyer(f"Injoignable : {e}")}

    if t == "key":
        if not val:
            return {"ok": False, "erreur": "Token vide."}
        verifier = _KEY_VERIFIERS.get(body.name)
        if verifier:
            try:
                async with httpx.AsyncClient(timeout=12) as client:
                    result = await verifier(val, client)
                if result.get("erreur") is None:
                    result.pop("erreur", None)
                return result
            except Exception as e:
                return {"ok": False, "erreur": nettoyer(f"Injoignable : {e}")}
        return {"ok": False, "manuel": True,
                "erreur": "Pas de test automatique pour cette cle — active manuellement."}

    return {"ok": False, "erreur": "Type d'integration inconnu."}


def _parse_mcp_resp(r) -> dict:
    """Parse MCP response: JSON ou SSE (data: {...} lines)."""
    import json as _json
    ct = r.headers.get("content-type", "")
    text = r.text.strip()
    if not text:
        return {}
    if "event-stream" in ct or text.startswith("data:"):
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload and payload != "[DONE]":
                    try:
                        return _json.loads(payload)
                    except Exception:
                        continue
        return {}
    try:
        return r.json()
    except Exception:
        return {}


def _extraire_termes_legaux_sync(intention: str) -> str:
    """Extrait 2-3 mots-clés juridiques depuis une intention utilisateur (appel sync LLM)."""
    try:
        from generator import _load_api_key, MODEL_SCAN
        import anthropic
        key = _load_api_key()
        if not key:
            return intention[:60]
        c = anthropic.Anthropic(api_key=key)
        msg = c.messages.create(
            model=MODEL_SCAN, max_tokens=40,
            messages=[{"role": "user", "content": (
                f"Extrais 2-3 mots-cles juridiques francais pour rechercher dans Legifrance "
                f"(ex: 'donnees personnelles RGPD', 'e-commerce droit consommation'). "
                f"Intention : '{intention}'. "
                f"Reponds uniquement avec les mots-cles, sans ponctuation ni explication."
            )}],
        )
        return (msg.content[0].text or "").strip() or intention[:60]
    except Exception:
        return intention[:60]


def _structurer_resultats_legaux_sync(intention: str, raw_text: str) -> dict:
    """Filtre et structure les resultats bruts Legifrance vers un JSON exploitable.
    Ne garde que les articles pertinents pour l'objectif. Ne leve jamais (repli propre)."""
    import json as _json
    fallback = {"articles": [], "synthese": "", "brut": (raw_text or "")[:1200]}
    try:
        from generator import _load_api_key, MODEL_SCAN
        import anthropic
        key = _load_api_key()
        if not key or not (raw_text or "").strip():
            return fallback
        c = anthropic.Anthropic(api_key=key)
        prompt = (
            "Tu es juriste francais. Voici l'objectif d'un utilisateur puis des resultats bruts "
            "de Legifrance (LODA).\n"
            f"OBJECTIF : {intention}\n\n"
            f"RESULTATS BRUTS :\n{raw_text[:9000]}\n\n"
            "Selectionne UNIQUEMENT les textes/articles reellement pertinents pour l'objectif "
            "(ignore tout hors-sujet). Reponds en JSON STRICT, sans texte autour :\n"
            '{"synthese":"2-3 phrases sur ce que ces textes impliquent concretement pour le projet",'
            '"articles":[{"titre":"...","reference":"ex: Article L221-5 Code de la consommation",'
            '"resume":"1 phrase claire","pertinence":"haute|moyenne",'
            '"lien":"url legifrance si presente sinon chaine vide",'
            '"pourquoi":"pourquoi c est pertinent pour cet objectif precis"}]}\n'
            "Si aucun texte n'est pertinent : articles=[] et synthese explique qu'aucun resultat "
            "ne correspond a l'objectif."
        )
        msg = c.messages.create(
            model=MODEL_SCAN, max_tokens=1600,
            messages=[{"role": "user", "content": prompt}],
        )
        txt = (msg.content[0].text or "").strip()
        i, j = txt.find("{"), txt.rfind("}")
        if i >= 0 and j > i:
            data = _json.loads(txt[i:j + 1])
            if isinstance(data, dict) and isinstance(data.get("articles"), list):
                data.setdefault("synthese", "")
                return data
        return fallback
    except Exception:
        return fallback


@router.post("/openlegi/conformite")
async def openlegi_conformite(data: dict):
    query = (data.get("query") or "").strip()
    if not query:
        raise HTTPException(400, "query requis")
    token = _load_cred("openlegi.env", "OPENLEGI_TOKEN")
    if not token:
        raise HTTPException(503, "OpenLegi non configure (OPENLEGI_TOKEN manquant)")

    # Extraction LLM des termes juridiques pertinents (SDK sync -> thread)
    legal_query = await asyncio.to_thread(_extraire_termes_legaux_sync, query)

    mcp_url = f"https://mcp.openlegi.fr/legifrance/mcp?token={token}"
    _hdrs = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            init_r = await client.post(
                mcp_url,
                json={"jsonrpc": "2.0", "id": 0, "method": "initialize",
                      "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                 "clientInfo": {"name": "neogen", "version": "1.0"}}},
                headers=_hdrs,
            )
            session_id = init_r.headers.get("Mcp-Session-Id", "")
            if not session_id:
                init_body = _parse_mcp_resp(init_r)
                session_id = (init_body.get("result") or {}).get("sessionId", "")
            call_hdrs = {**_hdrs, **({"Mcp-Session-Id": session_id} if session_id else {})}
            r = await client.post(
                mcp_url,
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                      "params": {"name": "rechercher_dans_texte_legal",
                                 "arguments": {"search": legal_query, "page_size": 5}}},
                headers=call_hdrs,
            )
            result = _parse_mcp_resp(r)
    except Exception as e:
        raise HTTPException(502, f"OpenLegi inaccessible : {e}")

    # Extraction du texte brut LODA depuis la reponse MCP
    import json as _json
    raw = result.get("result", result)
    raw_text = ""
    if isinstance(raw, dict):
        content = raw.get("content")
        if isinstance(content, list):
            raw_text = "\n".join(str(b.get("text", "")) for b in content if isinstance(b, dict))
        if not raw_text:
            raw_text = _json.dumps(raw, ensure_ascii=False)
    elif isinstance(raw, str):
        raw_text = raw

    # Structuration LLM : filtre sur l'objectif, cartes exploitables (repli propre si echec)
    structured = await asyncio.to_thread(_structurer_resultats_legaux_sync, query, raw_text)
    return {"resultats": structured, "query": legal_query, "termes": legal_query}
