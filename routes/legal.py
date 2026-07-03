"""
NEOGEN - Pages legales (mentions legales, CGU, politique de confidentialite).

Base pre-lancement pour un service en ligne edite par une entreprise individuelle (AE) France,
qui collecte des comptes (email + mot de passe hache) et traite des donnees personnelles (RGPD).

AVERTISSEMENT : ces documents sont une base serieuse mais NE remplacent PAS un conseil juridique.
Faire relire par un professionnel avant un lancement public a grande echelle est recommande.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-07-03.
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/legal", tags=["legal"])

# ── Identite editeur (source : SIRET AE Jordan VINCENT / NetroIA) ────────────────
_EDITEUR = "Jordan VINCENT"
_MARQUE = "NetroIA"
_STATUT = "Entrepreneur individuel (micro-entreprise)"
_SIRET = "94811960700026"
_CONTACT = "captain@netroia.com"
_HEBERGEUR = "Hostinger International Ltd. — 61 Lordou Vironos Street, 6023 Larnaca, Chypre"
_MAJ = "3 juillet 2026"


def _page(titre: str, corps: str) -> str:
    return (
        "<!doctype html><html lang=fr><head><meta charset=utf-8>"
        "<meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{titre} — NEOGEN</title><style>"
        "body{margin:0;background:#05080a;color:#c8d6cc;font:15px/1.7 -apple-system,Segoe UI,Roboto,sans-serif}"
        ".wrap{max-width:820px;margin:0 auto;padding:48px 22px 80px}"
        "h1{color:#39ff41;font-size:26px;margin:0 0 6px;letter-spacing:.5px}"
        "h2{color:#8affa0;font-size:17px;margin:34px 0 10px;border-top:1px solid rgba(57,255,65,.14);padding-top:22px}"
        ".maj{color:rgba(200,214,204,.4);font-size:12px;margin-bottom:8px}"
        "a{color:#39ff41}p,li{color:#b3c4b8}strong{color:#e6f5ea}"
        ".back{display:inline-block;margin-bottom:26px;color:rgba(200,214,204,.55);text-decoration:none;font-size:13px}"
        ".warn{margin-top:40px;padding:12px 16px;border:1px solid rgba(57,255,65,.2);border-radius:8px;"
        "background:rgba(57,255,65,.04);font-size:12px;color:rgba(200,214,204,.6)}"
        "</style></head><body><div class=wrap>"
        "<a class=back href='/'>&larr; Retour a NEOGEN</a>"
        f"<h1>{titre}</h1><div class=maj>Derniere mise a jour : {_MAJ}</div>"
        f"{corps}"
        "<div class=warn>Ces informations legales sont fournies de bonne foi. Pour toute question "
        f"relative a tes donnees ou au service, contacte <a href='mailto:{_CONTACT}'>{_CONTACT}</a>.</div>"
        "</div></body></html>"
    )


@router.get("/mentions-legales", response_class=HTMLResponse)
def mentions_legales():
    corps = (
        "<h2>Editeur du site</h2>"
        f"<p><strong>{_EDITEUR}</strong> — {_STATUT}, exploitant sous le nom commercial « {_MARQUE} ».<br>"
        f"SIRET : {_SIRET}.<br>Contact : <a href='mailto:{_CONTACT}'>{_CONTACT}</a>.</p>"
        "<h2>Directeur de la publication</h2>"
        f"<p>{_EDITEUR}.</p>"
        "<h2>Hebergement</h2>"
        f"<p>{_HEBERGEUR}</p>"
        "<h2>Propriete intellectuelle</h2>"
        "<p>Le coeur de NEOGEN est distribue sous <a href='https://github.com/captainNetroia/NEOGEN/blob/main/LICENSE' "
        "target=_blank rel=noopener>Business Source License 1.1</a>. La marque, les contenus et l'interface "
        "restent la propriete de l'editeur, sauf mention contraire.</p>"
    )
    return _page("Mentions legales", corps)


@router.get("/confidentialite", response_class=HTMLResponse)
def confidentialite():
    corps = (
        f"<p><strong>Responsable de traitement :</strong> {_EDITEUR} ({_MARQUE}), "
        f"contact <a href='mailto:{_CONTACT}'>{_CONTACT}</a>.</p>"
        "<h2>Donnees collectees</h2><ul>"
        "<li><strong>Compte</strong> : adresse email, mot de passe (jamais stocke en clair — hache par "
        "PBKDF2-HMAC-SHA256), prenom/nom fournis.</li>"
        "<li><strong>Profil</strong> : informations que tu renseignes librement (centres d'interet, projet, "
        "style de travail) pour personnaliser les agents.</li>"
        "<li><strong>Usage</strong> : contenus que tu crees (produits, conversations, competences, memoire), "
        "isoles par compte.</li>"
        "<li><strong>Session</strong> : jeton de connexion (cookie/stockage local) et horodatage.</li>"
        "<li><strong>Paiement</strong> : gere par Stripe. Nous ne stockons PAS ton numero de carte ; seul un "
        "identifiant client Stripe est conserve pour lier ton abonnement.</li>"
        "<li><strong>Cle IA (BYOK)</strong> : si tu connectes ta propre cle (Anthropic, OpenAI, Ollama...), "
        "elle est conservee dans TON navigateur et transmise a chaque requete vers le fournisseur via notre "
        "serveur ; elle n'est pas stockee durablement cote serveur.</li></ul>"
        "<h2>Finalites et base legale</h2>"
        "<p>Fournir le service et ton compte (execution du contrat), traiter les paiements (obligation "
        "contractuelle/legale), ameliorer et securiser le service (interet legitime). Aucune revente de donnees.</p>"
        "<h2>Sous-traitants</h2>"
        "<p>Hebergement (Hostinger), paiement (Stripe), fournisseurs de modeles IA que TU choisis "
        "(Anthropic, OpenAI, Google, Mistral, DeepSeek, ou Ollama en local). Les prompts envoyes a un "
        "fournisseur IA sont soumis a la politique de ce fournisseur.</p>"
        "<h2>Duree de conservation</h2>"
        "<p>Les donnees de compte sont conservees tant que le compte est actif, puis supprimees sur demande "
        "ou apres une periode d'inactivite prolongee. Les donnees de facturation sont conservees selon les "
        "obligations legales comptables.</p>"
        "<h2>Tes droits (RGPD)</h2>"
        "<p>Tu disposes des droits d'acces, de rectification, d'effacement, de portabilite, de limitation et "
        f"d'opposition. Pour les exercer : <a href='mailto:{_CONTACT}'>{_CONTACT}</a>. Tu peux aussi saisir la "
        "CNIL (cnil.fr).</p>"
        "<h2>Securite</h2>"
        "<p>Mots de passe haches, connexions chiffrees (HTTPS), en-tetes de securite, limitation de debit, "
        "isolation des donnees entre comptes.</p>"
    )
    return _page("Politique de confidentialite", corps)


@router.get("/cgu", response_class=HTMLResponse)
def cgu():
    corps = (
        "<h2>1. Objet</h2>"
        "<p>NEOGEN est un systeme multi-agents qui aide a creer, gerer et faire evoluer des applications et "
        "contenus assistes par IA. Les presentes conditions regissent l'utilisation du service en ligne "
        "(version hebergee) edite par " + _EDITEUR + " (" + _MARQUE + ").</p>"
        "<h2>2. Compte</h2>"
        "<p>La creation d'un compte requiert une adresse email valide et un mot de passe. Tu es responsable de "
        "la confidentialite de tes identifiants et des actions realisees depuis ton compte.</p>"
        "<h2>3. Modele IA (BYOK) et credits</h2>"
        "<p>Sur la version hebergee, l'usage des agents necessite de connecter ta propre cle IA. Un palier "
        "gratuit offre un credit mensuel (GEN) ; des paliers payants offrent davantage de capacites via "
        "abonnement Stripe. La version auto-hebergee (open source, BSL 1.1) est gratuite avec Ollama.</p>"
        "<h2>4. Usage acceptable</h2>"
        "<p>Il est interdit d'utiliser le service pour des contenus illegaux, de tenter d'en corrompre la "
        "securite, de contourner le paywall, ou d'abuser des ressources. L'editeur peut suspendre un compte "
        "en cas d'abus.</p>"
        "<h2>5. Propriete intellectuelle</h2>"
        "<p>Le coeur logiciel est sous Business Source License 1.1. Tu conserves la propriete des contenus que "
        "tu crees. L'editeur conserve ses droits sur la marque et l'interface.</p>"
        "<h2>6. Disponibilite et responsabilite</h2>"
        "<p>Le service est fourni « en l'etat », sans garantie de disponibilite continue. Dans les limites de "
        "la loi, la responsabilite de l'editeur est limitee ; les sorties generees par l'IA doivent etre "
        "verifiees par l'utilisateur avant tout usage.</p>"
        "<h2>7. Resiliation</h2>"
        "<p>Tu peux supprimer ton compte a tout moment. Un abonnement payant est annulable ; il reste actif "
        "jusqu'a la fin de la periode en cours.</p>"
        "<h2>8. Droit applicable</h2>"
        "<p>Les presentes conditions sont soumises au droit francais. A defaut de resolution amiable, les "
        "tribunaux francais sont competents.</p>"
    )
    return _page("Conditions generales d'utilisation", corps)
