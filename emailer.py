"""
NEOGEN - Envoi d'emails transactionnels via Brevo (ex-Sendinblue).

Source unique d'envoi. Ne leve JAMAIS (robustesse : erreur capturee -> loguee -> {ok:False}).
Best-effort : un echec d'email ne doit jamais casser le flux appelant (inscription, rappel...).

Credentials attendus dans credentials/brevo.env (ou variables d'env) :
  BREVO_API_KEY      = xkeysib-...
  BREVO_SENDER_EMAIL = no-reply@netroia.com   (adresse expeditrice verifiee cote Brevo)
  BREVO_SENDER_NAME  = NEOGEN

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-07-01.
"""
from __future__ import annotations

import os

_API_URL = "https://api.brevo.com/v3/smtp/email"


def _cred(cle: str, defaut: str = "") -> str:
    try:
        from credentials_loader import lire_cred
        v = lire_cred("brevo.env", cle)
        return v or defaut
    except Exception:
        return os.environ.get(cle, defaut)


def _base_url() -> str:
    return (os.environ.get("NEOGEN_PUBLIC_URL")
            or os.environ.get("NEOGEN_BASE_URL")
            or "https://neogen.netroia.tech").rstrip("/")


def envoyer_email(to: str, sujet: str, html: str, *, to_name: str = "") -> dict:
    """Envoie un email HTML via Brevo. Ne leve jamais. Retourne {ok, ...}."""
    to = (to or "").strip()
    if not to or "@" not in to:
        return {"ok": False, "raison": "destinataire invalide"}
    api_key = _cred("BREVO_API_KEY")
    if not api_key:
        _log("email non configure (BREVO_API_KEY absent)", "warn", to=to)
        return {"ok": False, "raison": "BREVO_API_KEY absent"}
    sender_email = _cred("BREVO_SENDER_EMAIL", "no-reply@netroia.com")
    sender_name = _cred("BREVO_SENDER_NAME", "NEOGEN")
    payload = {
        "sender": {"email": sender_email, "name": sender_name},
        "to": [{"email": to, "name": to_name or to}],
        "subject": sujet,
        "htmlContent": html,
    }
    try:
        import httpx
        r = httpx.post(_API_URL, json=payload, timeout=15,
                       headers={"api-key": api_key, "Content-Type": "application/json",
                                "Accept": "application/json"})
        if r.status_code in (200, 201, 202):
            _log("email envoye", "info", to=to, sujet=sujet)
            return {"ok": True, "status": r.status_code}
        _log("echec envoi email", "warn", to=to, status=r.status_code, corps=r.text[:200])
        return {"ok": False, "raison": f"HTTP {r.status_code}", "corps": r.text[:200]}
    except Exception as e:
        _log("exception envoi email", "erreur", to=to, err=str(e)[:200])
        return {"ok": False, "raison": str(e)[:200]}


def _log(evt: str, niveau: str = "info", **details) -> None:
    try:
        import robustesse as _rob
        _rob.journaliser(evt, niveau, source="emailer", **details)
    except Exception:
        pass


def template_bienvenue(prenom: str = "") -> tuple[str, str]:
    """Retourne (sujet, html) de l'email de bienvenue NEOGEN."""
    p = (prenom or "").strip()
    salut = f"Bonjour {p}," if p else "Bonjour,"
    url = _base_url()
    sujet = "Bienvenue sur NEOGEN — ton intelligence collective autonome"
    packs = [
        ("Essential", "14,99&euro;/mois",
         "1 500 GEN/mois &middot; 4 providers IA + local &middot; multi-agents, RPA, vision, crons &middot; 5 « Donner vie »/mois, 15 applis, 10 Mode Juge/mois."),
        ("Pro", "29,99&euro;/mois",
         "4 500 GEN/mois &middot; 6 providers &middot; crons illimités &middot; 15 « Donner vie », 50 applis &middot; Webhook &amp; API &middot; Mode ÉCLAIR (-30 à -50% tokens)."),
        ("Power", "49,99&euro;/mois",
         "12 000 GEN/mois &middot; tous les providers &middot; 50 « Donner vie », 200 applis, 100 déploiements gérés &middot; Webhook &amp; API &middot; Mode ÉCLAIR."),
    ]
    packs_html = "".join(
        f'<tr><td style="padding:10px 14px;border:1px solid #1f2933;border-radius:8px">'
        f'<span style="color:#00ff41;font-weight:700">{n}</span> '
        f'<span style="color:#9aa5b1;font-size:13px">&mdash; {prix}</span><br>'
        f'<span style="color:#cbd2d9;font-size:13px;line-height:1.5">{desc}</span></td></tr>'
        f'<tr><td style="height:8px"></td></tr>'
        for n, prix, desc in packs
    )
    html = f"""<!DOCTYPE html><html><body style="margin:0;background:#04080c;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#04080c;padding:28px 0">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:#080c12;border:1px solid rgba(0,255,65,.15);border-radius:16px;padding:34px 30px">
<tr><td>
<div style="font-size:30px;font-weight:900;letter-spacing:4px;color:#00ff41;text-align:center;margin-bottom:6px">NEOGEN</div>
<div style="font-size:11px;color:rgba(0,255,65,.5);letter-spacing:3px;text-transform:uppercase;text-align:center;margin-bottom:26px">Intelligence collective autonome</div>
<p style="color:#e4e7eb;font-size:15px;line-height:1.65">{salut}</p>
<p style="color:#cbd2d9;font-size:14px;line-height:1.7">
Bienvenue sur NEOGEN. C'est un syst&egrave;me multi-agents qui <b style="color:#e4e7eb">pense, cr&eacute;e et &eacute;volue</b> avec toi :
scan d'intention, forge d'applications, mode jug&eacute;, agents autonomes, RPA, veille et conformit&eacute; juridique.
</p>
<div style="background:rgba(0,255,65,.06);border:1px solid rgba(0,255,65,.25);border-radius:10px;padding:14px 16px;margin:18px 0">
<span style="color:#00ff41;font-weight:700;font-size:14px">7 jours d'essai gratuits</span>
<span style="color:#9aa5b1;font-size:13px"> &middot; annulable &agrave; tout moment &middot; rappel par mail 2 jours avant le 1er d&eacute;bit.</span>
</div>
<p style="color:#cbd2d9;font-size:13px;margin-bottom:8px"><b style="color:#e4e7eb">Les offres :</b></p>
<table width="100%" cellpadding="0" cellspacing="0">{packs_html}</table>
<p style="color:#9aa5b1;font-size:12.5px;line-height:1.6;margin-top:6px">
Tu peux aussi rester en <b style="color:#cbd2d9">Freemium</b> (acc&egrave;s limit&eacute;, sans carte) pour d&eacute;couvrir &agrave; ton rythme.
</p>
<div style="text-align:center;margin:26px 0 8px">
<a href="{url}" style="display:inline-block;background:#00ff41;color:#000;font-weight:800;font-size:15px;text-decoration:none;padding:14px 38px;border-radius:11px;letter-spacing:1px">Ouvrir NEOGEN &rarr;</a>
</div>
<p style="color:#6b7280;font-size:11px;text-align:center;line-height:1.6;margin-top:22px">
Tu re&ccedil;ois cet email car un compte NEOGEN a &eacute;t&eacute; cr&eacute;&eacute; avec cette adresse.<br>NetroIA &middot; {url}
</p>
</td></tr></table>
</td></tr></table></body></html>"""
    return sujet, html


def envoyer_bienvenue(to: str, prenom: str = "") -> dict:
    """Compose + envoie l'email de bienvenue. Best-effort, ne leve jamais."""
    try:
        sujet, html = template_bienvenue(prenom)
        return envoyer_email(to, sujet, html, to_name=prenom)
    except Exception as e:
        _log("exception bienvenue", "erreur", err=str(e)[:200])
        return {"ok": False, "raison": str(e)[:200]}


if __name__ == "__main__":
    print("=" * 56)
    print("NEOGEN - EMAILER : auto-verification (offline)")
    print("=" * 56)
    # 1. Template rendu, non vide, contient les elements cles
    sujet, html = template_bienvenue("Alex")
    assert "NEOGEN" in html and "Bonjour Alex" in html
    assert "7 jours" in html and "Essential" in html and "Freemium" in html
    assert sujet and "Bienvenue" in sujet
    print("  template_bienvenue : OK")
    # 2. Destinataire invalide -> refus propre, jamais d'exception
    assert envoyer_email("", "x", "<b>x</b>")["ok"] is False
    assert envoyer_email("pasunemail", "x", "<b>x</b>")["ok"] is False
    print("  garde destinataire invalide : OK")
    # 3. Envoi monkeypatche (0 reseau) : verifie le contrat sans BREVO_API_KEY reel
    import emailer as _self
    _orig = _self.envoyer_email
    calls = {}
    def _fake(to, sujet, html, *, to_name=""):
        calls.update(to=to, sujet=sujet, has_html=bool(html)); return {"ok": True}
    _self.envoyer_email = _fake
    r = _self.envoyer_bienvenue("test@example.com", "Sam")
    assert r["ok"] and calls["to"] == "test@example.com" and calls["has_html"]
    _self.envoyer_email = _orig
    print("  envoyer_bienvenue (monkeypatch, 0 reseau) : OK")
    print("=" * 56)
    print("  Tous les tests emailer OK")
    print("=" * 56)
