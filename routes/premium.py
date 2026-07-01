from __future__ import annotations
import os as _os

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from .deps import (
    _auth, _load_cred,
    _set_premium, _marquer_essai_utilise, _lier_stripe_customer,
    _revoquer_premium_par_customer,
)

router = APIRouter()

_PALIERS_VALIDES = ("essential", "pro", "power", "enterprise")

_PRICE_KEY_MAP = {
    ("essential", "mensuel"): "STRIPE_PRICE_ESSENTIAL_MENSUEL",
    ("essential", "annuel"):  "STRIPE_PRICE_ESSENTIAL_ANNUEL",
    ("pro",       "mensuel"): "STRIPE_PRICE_PRO_MENSUEL",
    ("pro",       "annuel"):  "STRIPE_PRICE_PRO_ANNUEL",
    ("power",     "mensuel"): "STRIPE_PRICE_POWER_MENSUEL",
    ("power",     "annuel"):  "STRIPE_PRICE_POWER_ANNUEL",
    ("enterprise","mensuel"): "STRIPE_PRICE_ENTERPRISE_MENSUEL",
    ("enterprise","annuel"):  "STRIPE_PRICE_ENTERPRISE_ANNUEL",
}

_PACKS_GEN = {
    "starter":  {"gen": 100,   "eur": 200},
    "pro":      {"gen": 500,   "eur": 800},
    "power":    {"gen": 1500,  "eur": 2000},
    "ultimate": {"gen": 5000,  "eur": 5000},
}


class PremiumCheckoutBody(BaseModel):
    plan: str = "mensuel"
    palier: str = "essential"


class DonBody(BaseModel):
    montant: int


class CreditsDepenseBody(BaseModel):
    fonction: str
    montant: int | None = None


class CreditsRechargerBody(BaseModel):
    pack: str


class BoostActiverBody(BaseModel):
    type_boost: str


# ── Premium ────────────────────────────────────────────────────────────────────

@router.post("/premium/checkout")
def premium_checkout(body: PremiumCheckoutBody | None = None,
                     authorization: str | None = Header(default=None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Connecte-toi pour passer premium.")
    import quotas as _qotas
    palier_actuel = _qotas.palier(user)
    plan   = (body.plan   if body else "mensuel") or "mensuel"
    palier = (body.palier if body else "essential") or "essential"
    if palier not in _PALIERS_VALIDES:
        palier = "essential"
    if palier_actuel == palier:
        raise HTTPException(status_code=400, detail=f"Tu es deja au palier '{palier}'.")
    import stripe as _stripe
    secret_key = _load_cred("stripe.env", "STRIPE_SECRET_KEY")
    cle_price = _PRICE_KEY_MAP.get((palier, plan))
    price_id = (_load_cred("stripe.env", cle_price) if cle_price else "") or \
               _load_cred("stripe.env", "STRIPE_PRICE_ID_MENSUEL") or \
               _load_cred("stripe.env", "STRIPE_PRICE_ID")
    if not secret_key or not price_id:
        raise HTTPException(status_code=503, detail="Stripe premium non configure.")
    _stripe.api_key = secret_key
    base_url = _os.environ.get("NEOGEN_BASE_URL", "http://localhost:8000").rstrip("/")
    try:
        prix = _stripe.Price.retrieve(price_id)
        mode = "subscription" if getattr(prix, "recurring", None) else "payment"
        params = dict(
            mode=mode,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            client_reference_id=user["id"],
            customer_email=user.get("email"),
            metadata={"palier": palier},
            success_url=f"{base_url}/#compte?premium_session={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base_url}/#compte",
        )
        if mode == "subscription" and not user.get("essai_utilise"):
            jours = int(_os.environ.get("NEOGEN_TRIAL_DAYS", "7") or 7)
            params["subscription_data"] = {"trial_period_days": jours, "metadata": {"palier": palier}}
            _marquer_essai_utilise(user["id"])
        session = _stripe.checkout.Session.create(**params)
        return {"url": session.url, "palier": palier, "plan": plan}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stripe : {e}")


@router.post("/premium/confirmer")
def premium_confirmer(data: dict, authorization: str | None = Header(default=None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Non authentifie")
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id manquant")
    import stripe as _stripe
    secret_key = _load_cred("stripe.env", "STRIPE_SECRET_KEY")
    if not secret_key:
        raise HTTPException(status_code=503, detail="Stripe non configure")
    _stripe.api_key = secret_key
    try:
        sess = _stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stripe : {e}")
    statut_ok = sess.get("payment_status") in ("paid", "no_payment_required")
    if statut_ok and sess.get("client_reference_id") == user["id"]:
        palier_sess = (sess.get("metadata") or {}).get("palier", "essential")
        _set_premium(user["id"], True, palier_sess)
        _lier_stripe_customer(user["id"], sess.get("customer") or "")
        essai = sess.get("payment_status") == "no_payment_required"
        import credits as _cred
        _cred.recharger_mensuel(user["id"], palier_sess)
        return {"ok": True, "premium": True, "palier": palier_sess, "essai": essai}
    return {"ok": False, "premium": False, "raison": "Paiement non confirme pour ce compte."}


@router.post("/premium/webhook")
async def premium_webhook(request: Request):
    import json as _json
    import stripe as _stripe
    secret_key = _load_cred("stripe.env", "STRIPE_SECRET_KEY")
    wh_secret = _load_cred("stripe.env", "STRIPE_WEBHOOK_SECRET")
    if not secret_key:
        raise HTTPException(status_code=503, detail="Stripe non configure")
    _stripe.api_key = secret_key
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    if not wh_secret:
        raise HTTPException(status_code=503,
                            detail="Webhook Stripe non configuré (STRIPE_WEBHOOK_SECRET absent).")
    try:
        event = _stripe.Webhook.construct_event(payload, sig, wh_secret)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Signature invalide : {e}")
    etype = event.get("type")
    obj = event.get("data", {}).get("object", {})
    if etype == "checkout.session.completed":
        uid = obj.get("client_reference_id")
        if uid and obj.get("payment_status") in ("paid", "no_payment_required"):
            palier_evt = (obj.get("metadata") or {}).get("palier", "essential")
            _set_premium(uid, True, palier_evt)
            _lier_stripe_customer(uid, obj.get("customer") or "")
            import credits as _cred
            _cred.recharger_mensuel(uid, palier_evt)
    elif etype in ("customer.subscription.deleted",):
        _revoquer_premium_par_customer(obj.get("customer") or "")
    elif etype == "invoice.payment_failed":
        _revoquer_premium_par_customer(obj.get("customer") or "")
    return {"received": True}


@router.get("/premium/abonnement")
def premium_abonnement(authorization: str | None = Header(default=None)):
    """Etat de l'abonnement Stripe de l'utilisateur (pour la section Compte)."""
    user = _auth(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Non authentifie")
    import quotas as _q
    p = _q.palier(user)
    base = {"palier": p, "actif": p != "gratuit"}
    cid = user.get("stripe_customer_id")
    if not cid or p == "gratuit":
        return {**base, "abonnement": None}
    secret_key = _load_cred("stripe.env", "STRIPE_SECRET_KEY")
    if not secret_key:
        return {**base, "abonnement": None}
    import stripe as _stripe
    _stripe.api_key = secret_key
    try:
        subs = _stripe.Subscription.list(customer=cid, status="all", limit=3)
        for s in subs.get("data", []):
            if s.get("status") in ("active", "trialing", "past_due"):
                return {**base, "abonnement": {
                    "id": s.get("id"),
                    "statut": s.get("status"),
                    "annulation_prevue": bool(s.get("cancel_at_period_end")),
                    "fin_periode": s.get("current_period_end"),
                }}
    except Exception as e:
        return {**base, "abonnement": None, "erreur": str(e)[:120]}
    return {**base, "abonnement": None}


@router.post("/premium/annuler")
def premium_annuler(authorization: str | None = Header(default=None)):
    """Programme la resiliation a la fin de la periode payee (garde l'acces jusque-la)."""
    user = _auth(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Non authentifie")
    cid = user.get("stripe_customer_id")
    if not cid:
        raise HTTPException(status_code=400, detail="Aucun abonnement Stripe lie a ce compte.")
    secret_key = _load_cred("stripe.env", "STRIPE_SECRET_KEY")
    if not secret_key:
        raise HTTPException(status_code=503, detail="Stripe non configure")
    import stripe as _stripe
    _stripe.api_key = secret_key
    try:
        subs = _stripe.Subscription.list(customer=cid, status="active", limit=3)
        cible = None
        for s in subs.get("data", []):
            if s.get("status") in ("active", "trialing", "past_due"):
                cible = s
                break
        if not cible:
            raise HTTPException(status_code=404, detail="Aucun abonnement actif a resilier.")
        maj = _stripe.Subscription.modify(cible["id"], cancel_at_period_end=True)
        return {"ok": True, "annulation_prevue": True,
                "fin_periode": maj.get("current_period_end"),
                "message": "Resiliation programmee. Tu gardes l'acces jusqu'a la fin de la periode payee."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stripe : {e}")


@router.post("/premium/reactiver")
def premium_reactiver(authorization: str | None = Header(default=None)):
    """Annule une resiliation programmee (reprend l'abonnement)."""
    user = _auth(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Non authentifie")
    cid = user.get("stripe_customer_id")
    if not cid:
        raise HTTPException(status_code=400, detail="Aucun abonnement Stripe lie a ce compte.")
    secret_key = _load_cred("stripe.env", "STRIPE_SECRET_KEY")
    if not secret_key:
        raise HTTPException(status_code=503, detail="Stripe non configure")
    import stripe as _stripe
    _stripe.api_key = secret_key
    try:
        subs = _stripe.Subscription.list(customer=cid, status="all", limit=3)
        for s in subs.get("data", []):
            if s.get("cancel_at_period_end"):
                _stripe.Subscription.modify(s["id"], cancel_at_period_end=False)
                return {"ok": True, "annulation_prevue": False,
                        "message": "Abonnement repris. Aucune resiliation prevue."}
        raise HTTPException(status_code=404, detail="Aucune resiliation programmee a annuler.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stripe : {e}")


# ── Don ────────────────────────────────────────────────────────────────────────

@router.post("/don/checkout")
def don_checkout(body: DonBody):
    if body.montant < 1:
        raise HTTPException(status_code=400, detail="Montant minimum : 1 EUR")
    import stripe as _stripe
    secret_key = _load_cred("stripe.env", "STRIPE_SECRET_KEY")
    if not secret_key:
        raise HTTPException(status_code=503, detail="Stripe non configure")
    _stripe.api_key = secret_key
    try:
        base_url = _os.environ.get("NEOGEN_BASE_URL", "http://localhost:8000").rstrip("/")
        session = _stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price_data": {"currency": "eur", "unit_amount": body.montant * 100,
                                        "product_data": {"name": "Soutenir NEOGEN",
                                                         "description": "Don libre pour financer le calcul et le developpement"}},
                         "quantity": 1}],
            mode="payment",
            success_url=f"{base_url}/#don?merci=1",
            cancel_url=f"{base_url}/#don",
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stripe : {e}")


# ── Crédits (GEN) ───────────────────────────────────────────────────────────────

@router.get("/credits/me")
def credits_me(authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    import credits as _cred
    import quotas as _q
    return {"solde": _cred.solde(user["id"]), "palier": _q.palier(user),
            "historique": _cred.historique(user["id"]),
            "gen_mensuel": _cred.GEN_MENSUEL.get(_q.palier(user), 0)}


@router.post("/credits/depenser")
def credits_depenser(body: CreditsDepenseBody, authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    import credits as _cred
    import quotas as _q
    p = _q.palier(user)
    montant = body.montant if body.montant is not None else (_cred.cout(body.fonction, p) or 0)
    if montant is None:
        raise HTTPException(402, f"'{body.fonction}' non disponible sur le palier {p}.")
    result = _cred.debiter(user["id"], montant, body.fonction)
    if not result["ok"]:
        raise HTTPException(402, f"Solde GEN insuffisant ({result['manque']} GEN manquants).")
    return result


@router.post("/credits/recharger")
def credits_recharger(body: CreditsRechargerBody, authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    pack = _PACKS_GEN.get(body.pack)
    if not pack:
        raise HTTPException(400, f"Pack inconnu : {body.pack}. Valides : {list(_PACKS_GEN)}")
    import stripe as _stripe
    secret_key = _load_cred("stripe.env", "STRIPE_SECRET_KEY")
    if not secret_key:
        raise HTTPException(503, "Stripe non configure")
    _stripe.api_key = secret_key
    base_url = _os.environ.get("NEOGEN_BASE_URL", "http://localhost:8000").rstrip("/")
    try:
        session = _stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price_data": {"currency": "eur", "unit_amount": pack["eur"],
                                        "product_data": {"name": f"Pack GEN {body.pack.capitalize()} — {pack['gen']} Genyte",
                                                         "description": f"{pack['gen']} GEN credites immediatement sur ton compte NEOGEN"}},
                         "quantity": 1}],
            mode="payment",
            client_reference_id=user["id"],
            customer_email=user.get("email"),
            metadata={"type": "credits", "pack": body.pack, "gen": str(pack["gen"])},
            success_url=f"{base_url}/#compte?credits_ok={pack['gen']}",
            cancel_url=f"{base_url}/#compte",
        )
        return {"url": session.url, "pack": body.pack, "gen": pack["gen"]}
    except Exception as e:
        raise HTTPException(502, f"Stripe : {e}")


@router.post("/credits/confirmer-recharge")
def credits_confirmer_recharge(data: dict, authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        raise HTTPException(400, "session_id manquant")
    import stripe as _stripe
    _stripe.api_key = _load_cred("stripe.env", "STRIPE_SECRET_KEY")
    try:
        sess = _stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        raise HTTPException(502, f"Stripe : {e}")
    if (sess.get("payment_status") != "paid" or
            sess.get("client_reference_id") != user["id"] or
            (sess.get("metadata") or {}).get("type") != "credits"):
        return {"ok": False, "raison": "Session invalide ou non payee."}
    gen = int((sess.get("metadata") or {}).get("gen", 0))
    pack = (sess.get("metadata") or {}).get("pack", "")
    import credits as _cred
    nouveau = _cred.crediter(user["id"], gen, "purchase", f"Pack GEN {pack}")
    return {"ok": True, "gen_ajoutes": gen, "nouveau_solde": nouveau}


@router.get("/credits/boosts")
def credits_boosts(authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    import boosts as _boosts
    return {"boosts": _boosts.boosts_actifs(user["id"])}


@router.post("/credits/boosts/activer")
def credits_boosts_activer(body: BoostActiverBody, authorization: str = Header(None)):
    user = _auth(authorization)
    if not user:
        raise HTTPException(401, "Non authentifie")
    import boosts as _boosts
    import quotas as _q
    result = _boosts.activer(user["id"], body.type_boost, _q.palier(user))
    if not result["ok"]:
        raise HTTPException(402, result["raison_refus"])
    return result
