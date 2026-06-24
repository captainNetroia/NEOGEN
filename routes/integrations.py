from __future__ import annotations
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


@router.post("/integrations/verifier")
async def integrations_verifier(body: IntegVerifBody):
    import httpx
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
        if body.name == "openlegi":
            try:
                async with httpx.AsyncClient(timeout=12) as client:
                    r = await client.post(
                        f"https://mcp.openlegi.fr/legifrance/mcp?token={val}",
                        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                        headers={"Content-Type": "application/json",
                                 "Accept": "application/json, text/event-stream"},
                    )
                if r.status_code in (401, 403):
                    return {"ok": False, "erreur": "Token refuse (401/403)."}
                if r.status_code < 500:
                    return {"ok": True}
                return {"ok": False, "erreur": f"Service en erreur (HTTP {r.status_code})."}
            except Exception as e:
                return {"ok": False, "erreur": nettoyer(f"Injoignable : {e}")}
        return {"ok": False, "manuel": True, "erreur": "Pas de test automatique pour cette cle."}

    return {"ok": False, "erreur": "Type d'integration inconnu."}


@router.post("/openlegi/conformite")
async def openlegi_conformite(data: dict):
    import httpx
    query = (data.get("query") or "").strip()
    if not query:
        raise HTTPException(400, "query requis")
    token = _load_cred("openlegi.env", "OPENLEGI_TOKEN")
    if not token:
        raise HTTPException(503, "OpenLegi non configure (OPENLEGI_TOKEN manquant)")
    mcp_url = f"https://mcp.openlegi.fr/legifrance/mcp?token={token}"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                mcp_url,
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                      "params": {"name": "rechercher_code",
                                 "arguments": {"query": query, "nombreResultats": 5}}},
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            result = r.json()
    except Exception as e:
        raise HTTPException(502, f"OpenLegi inaccessible : {e}")
    return {"resultats": result.get("result", result), "query": query}
