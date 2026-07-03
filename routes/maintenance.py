"""
NEOGEN - Maintenance protegee par secret (correction de donnees sans SSH).

Contexte : le VPS public est deploye a la main (pas de Docker Manager Hostinger, pas de SSH
depuis Claude Code). Pour diagnostiquer/corriger les donnees en prod (ex: soldes GEN), on
expose un endpoint protege par un SECRET partage (pas par un compte : un email owner/admin
serait squattable a l'inscription publique). Comparaison a temps constant (hmac.compare_digest).

Fail-closed : si NEOGEN_MAINTENANCE_SECRET n'est pas defini, tout est refuse (503).
Action ciblee et non parametrable : uniquement diagnostic + correction des soldes gratuits.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-07-03.
"""
from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/maintenance", tags=["maintenance"])

_QUOTA_GRATUIT = 200  # credit mensuel du palier gratuit


def _gate_secret(secret_recu: str | None) -> None:
    """Refuse si le secret est absent/mauvais. Fail-closed si non configure."""
    attendu = os.environ.get("NEOGEN_MAINTENANCE_SECRET", "").strip()
    if not attendu:
        raise HTTPException(status_code=503, detail="Maintenance non configuree (secret absent).")
    recu = (secret_recu or "").strip()
    if not recu or not hmac.compare_digest(recu, attendu):
        raise HTTPException(status_code=403, detail="Secret de maintenance invalide.")


def _comptes_gratuits_anormaux() -> list[dict]:
    """Comptes du palier gratuit dont le solde depasse le quota mensuel (symptome du double-credit)."""
    import credits
    from routes.deps import _rjsonl, _USERS
    soldes = credits._lire_soldes()
    anormaux = []
    for u in _rjsonl(_USERS):
        if (u.get("palier") or "gratuit") != "gratuit":
            continue
        uid = u.get("id")
        s = soldes.get(uid, 0)
        if uid and s > _QUOTA_GRATUIT:
            anormaux.append({"id": uid, "email": u.get("email", "?"), "solde": s,
                             "surplus": s - _QUOTA_GRATUIT})
    return anormaux


@router.get("/credits-gratuit/diagnostic")
def diagnostic(x_maintenance_secret: str | None = Header(default=None)):
    """Etat des soldes gratuits : combien de comptes depassent le quota, et de combien.
    Lecture seule. Sert a valider AVANT de corriger."""
    _gate_secret(x_maintenance_secret)
    import credits_gratuit as cg
    from routes.deps import _rjsonl, _USERS
    gratuits = [u for u in _rjsonl(_USERS) if (u.get("palier") or "gratuit") == "gratuit"]
    suivi = cg._lire()
    mois = cg._mois_actuel()
    anormaux = _comptes_gratuits_anormaux()
    orphelins_suivi = [u.get("id") for u in gratuits if suivi.get(u.get("id")) != mois]
    return {
        "mois_courant": mois,
        "comptes_gratuits": len(gratuits),
        "sans_entree_suivi": len(orphelins_suivi),  # exposes au recredit erroné du cron
        "au_dessus_du_quota": len(anormaux),
        "detail": anormaux,
    }


@router.post("/credits-gratuit/corriger")
def corriger(x_maintenance_secret: str | None = Header(default=None)):
    """Corrige durablement : (1) backfill du suivi (stoppe les futurs recredits errones),
    (2) ramene chaque compte gratuit au-dessus du quota a 200 GEN (debit tracé 'gift').
    Idempotent : relancer ne re-corrige rien si tout est deja sain."""
    _gate_secret(x_maintenance_secret)
    import credits
    import credits_gratuit as cg

    adoptes = cg.backfill_suivi()  # empeche que ca revienne
    anormaux = _comptes_gratuits_anormaux()
    corriges = []
    for c in anormaux:
        surplus = c["surplus"]
        if surplus > 0:
            # debit tracé (montant negatif) : ramene le solde au quota gratuit
            nouveau = credits.crediter(
                c["id"], -surplus, "gift",
                f"Correction double-credit : retour au quota gratuit ({_QUOTA_GRATUIT} GEN)")
            corriges.append({"email": c["email"], "avant": c["solde"], "apres": nouveau})
    return {"ok": True, "comptes_adoptes_suivi": adoptes,
            "comptes_corriges": len(corriges), "detail": corriges}
