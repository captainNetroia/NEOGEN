"""
NEOGEN - Le Noyau : ce qui est GRAVE et ne peut JAMAIS etre modifie par l'evolution.

NEOGEN sait desormais s'auto-evoluer (evolution_gouvernee.py) : ajouter des fonctions,
skills, regles, lois, agents, modeles, savoir, esthetique, sections, integrations...
La Pensee peut proposer ces changements ; l'humain consent ; le systeme s'applique.

Mais une auto-modification incontrolee pourrait reecrire sa propre gouvernance. Ce module
est le GARDIEN : il definit la frontiere entre le NOYAU (ADN + murs, immuable) et les
couches FORGEABLES, et fournit `autoriser(changement)` qui REFUSE tout ce qui touche au
noyau. Fail-closed : en cas de doute, on refuse.

Doctrine (heritee de evolution.py) : AUTONOMIE sur les couches apprenables/forgeables,
ZERO AUTONOMIE sur l'etalon et les murs graves. NEOGEN modifie son comportement et ses
outils en ALIMENTANT DES STORES runtime (data-driven) ; le code Python du noyau, lui,
n'est jamais reecrit. C'est ainsi que « modifier son code sans toucher au noyau » est a
la fois reel ET sur.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-26.
"""
from __future__ import annotations

import os

import capacites

# ---------------------------------------------------------------------------
# L'ADN : la vision de base de NEOGEN. Immuable. Aucune evolution ne la touche.
# (Texte de reference ; les principes ci-dessous en sont la traduction executable.)
# ---------------------------------------------------------------------------
ADN = {
    "mission": (
        "Transformer une intention en application/outil gouverne, genere et execute en "
        "securite. NEOGEN apprend, propose, l'humain garde le dernier mot."
    ),
    "principes_inviolables": [
        "humain_dernier_mot",          # aucune action irreversible sans consentement
        "isolation_du_code_genere",    # le code non fiable ne touche jamais l'hote/la prod
        "securite_graduee",            # une capacite accordee ne supprime pas la securite
        "mesure_contre_etalon",        # on mesure sa qualite, on ne reecrit pas l'etalon
        "transparence",                # tout changement est trace et notifie
    ],
}

# ---------------------------------------------------------------------------
# LES MURS : invariants de securite. Reference la source de verite capacites.py.
# Ces cles ne peuvent JAMAIS etre desactivees ni contournees par un changement.
# ---------------------------------------------------------------------------
MURS = {nom: desc for nom, desc in capacites.INVARIANTS_CREATEUR}

# Mots-cles interdits dans tout payload de changement (tentative de toucher au noyau).
_TERMES_INTERDITS = (
    "--privileged", "cap_add", "cap-add", "--cap-add", "no-new-privileges=false",
    "security-opt", "--user 0", "user: root", "runas root", "--network host",
    "privileged", "disable isolation", "désactive l'isolation", "desactive l'isolation",
    "sans sandbox", "sans conteneur", "bypass", "contourner la securite",
    "owner_unlimited", "neogen_owner", "subprocess", "os.system", "eval(", "exec(",
    "rm -rf", "credentials", "api_key", "secret", "shpat_", "sk-ant", "supprime les murs",
)

# ---------------------------------------------------------------------------
# ZONES PROTEGEES : fichiers du noyau que l'evolution ne peut JAMAIS ecrire.
# (L'evolution est data-driven : elle n'ecrit que dans data/. Cette liste est une
#  defense en profondeur, au cas ou un changement tenterait de cibler un fichier.)
# ---------------------------------------------------------------------------
ZONES_PROTEGEES = {
    "noyau.py", "capacites.py", "evolution_gouvernee.py",
    "executeur_conteneur.py", "executeur_reseau.py",
    "evolution.py", "matiere.py", "apprentissage.py", "selection.py",
    "antigoodhart.py", "invention.py",
    "quotas.py", "robustesse.py", "sanitizer.py", "anonymizer.py",
    "credentials_loader.py", "api.py", "gateway.py",
    "orchestrateur.py", "generator.py", "membrane.py",
    "routes/auth.py", "auth.py",
}

# ---------------------------------------------------------------------------
# Couches FORGEABLES : ce que l'evolution PEUT creer/modifier (data-driven).
#   TYPES_PERSO   : preference personnelle -> applicable en local meme cote public (bride).
#   TYPES_SYSTEME : reforme l'application reelle -> ADMIN uniquement ;
#                   cote public -> remonte en proposition d'evolution.
# ---------------------------------------------------------------------------
TYPES_PERSO = {"regle", "idee", "esthetique", "skill"}
TYPES_SYSTEME = {"fonction", "capacite", "section", "agent", "savoir", "modele",
                 "integration", "loi"}
TYPES_FORGEABLES = TYPES_PERSO | TYPES_SYSTEME

# ---------------------------------------------------------------------------
# Privileges : qui peut quoi.
# ---------------------------------------------------------------------------

def est_admin(user: dict | None) -> bool:
    """Admin = proprietaire (instance perso NEOGEN_OWNER_UNLIMITED ou email owner).
    Reutilise quotas.palier (source de verite). L'admin a la super-capacite COMPLETE."""
    try:
        import quotas
        return quotas.palier(user) == "enterprise"
    except Exception:
        return False


def portee(type_: str, user: dict | None) -> str:
    """Determine la portee d'un changement selon le type et le demandeur.
      'complet'      : admin -> applique au live (peut reformer l'app reelle).
      'local_bride'  : public + type perso -> applique a SA propre experience (bride).
      'remonte'      : public + type systeme -> devient une proposition pour l'admin.
    """
    if est_admin(user):
        return "complet"
    if type_ in TYPES_PERSO:
        return "local_bride"
    return "remonte"


# ---------------------------------------------------------------------------
# LE GARDIEN : autorise ou refuse un changement. Fail-closed.
# ---------------------------------------------------------------------------

def autoriser(changement: dict) -> tuple[bool, str]:
    """Verifie qu'un changement ne touche JAMAIS le noyau (ADN + murs + zones).
    Renvoie (ok, raison). En cas de doute -> refuse (fail-closed)."""
    if not isinstance(changement, dict):
        return False, "changement invalide (pas un objet)"

    type_ = (changement.get("type") or "").strip().lower()
    if type_ not in TYPES_FORGEABLES:
        return False, f"type '{type_}' non forgeable (hors couches autorisees)"

    # 1. Cible : aucun fichier du noyau ne peut etre vise.
    cible = (changement.get("cible") or "").strip().replace("\\", "/").lstrip("./")
    if cible:
        base = cible.split("/")[-1]
        if cible in ZONES_PROTEGEES or base in {z.split("/")[-1] for z in ZONES_PROTEGEES}:
            return False, f"cible '{cible}' dans une zone protegee du noyau"
        # l'evolution est data-driven : toute cible hors data/ est suspecte.
        if not cible.startswith("data/"):
            return False, f"cible '{cible}' hors de data/ (l'evolution est data-driven)"

    # 2. Cles de murs / ADN : interdiction d'y toucher.
    for cle in _aplatir_cles(changement.get("payload", {})):
        cl = cle.lower()
        if cl in MURS or cl in ("adn", "murs", "invariants", "flags_invariants",
                                "zones_protegees", "principes_inviolables"):
            return False, f"cle '{cle}' appartient au noyau (ADN/murs)"

    # 3. Termes interdits dans tout le contenu serialise (defense en profondeur).
    blob = _serialiser(changement.get("payload", {})).lower() + " " + \
        (changement.get("titre", "") + " " + changement.get("raison", "")).lower()
    for terme in _TERMES_INTERDITS:
        if terme in blob:
            return False, f"terme interdit detecte : '{terme}' (tentative de toucher au noyau/securite)"

    # 4. Capacite/integration : ne peut JAMAIS accorder reseau sans liste blanche,
    #    ni desactiver l'isolation. La securite reste graduee.
    if type_ in ("capacite", "integration", "modele"):
        pl = changement.get("payload", {}) if isinstance(changement.get("payload"), dict) else {}
        if pl.get("reseau") and not pl.get("domaines_autorises"):
            return False, "reseau demande sans liste blanche de domaines (securite graduee)"

    return True, "ok"


def _aplatir_cles(obj, prefixe="") -> list[str]:
    """Liste recursive des cles d'un dict (pour detecter une cle de mur cachee)."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append(str(k))
            out.extend(_aplatir_cles(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_aplatir_cles(v))
    return out


def _serialiser(obj) -> str:
    import json
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)


def resume() -> dict:
    """Vue lisible du noyau pour /health et l'UI (jamais de secret)."""
    return {
        "adn": {"mission": ADN["mission"], "principes": ADN["principes_inviolables"]},
        "murs": list(MURS.keys()),
        "zones_protegees": sorted(ZONES_PROTEGEES),
        "types_forgeables": {"perso": sorted(TYPES_PERSO), "systeme": sorted(TYPES_SYSTEME)},
    }


# ---------------------------------------------------------------------------
# Auto-verification offline.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 64)
    print("NEOGEN - NOYAU : auto-verification (gardien fail-closed)")
    print("=" * 64)

    # Autorise : un changement forgeable propre, ciblant data/.
    ok, r = autoriser({"type": "regle", "payload": {"style_reponse": "direct"},
                       "cible": "data/regles_actives.json"})
    assert ok, r
    print("  autorise : regle perso data-driven -> OK")

    # Refuse : type hors couches.
    ok, r = autoriser({"type": "gouvernance", "payload": {}})
    assert not ok and "non forgeable" in r, r
    print("  refuse : type non forgeable -> OK")

    # Refuse : cible un fichier du noyau.
    ok, r = autoriser({"type": "fonction", "cible": "capacites.py", "payload": {}})
    assert not ok and "zone protegee" in r, r
    print("  refuse : cible capacites.py (mur) -> OK")

    # Refuse : cible hors data/.
    ok, r = autoriser({"type": "fonction", "cible": "routes/savoir.py", "payload": {}})
    assert not ok, r
    print("  refuse : cible hors data/ -> OK")

    # Refuse : cle de mur dans le payload.
    ok, r = autoriser({"type": "regle", "payload": {"non_root": False}})
    assert not ok and "noyau" in r, r
    print("  refuse : cle de mur 'non_root' dans payload -> OK")

    # Refuse : terme interdit (tentative de privilege).
    ok, r = autoriser({"type": "capacite", "payload": {"flags": "--privileged"}})
    assert not ok and "interdit" in r, r
    print("  refuse : flag --privileged -> OK")

    # Refuse : reseau sans liste blanche.
    ok, r = autoriser({"type": "integration", "payload": {"reseau": True, "domaines_autorises": []}})
    assert not ok and "liste blanche" in r, r
    print("  refuse : reseau sans liste blanche (securite graduee) -> OK")

    # Portee : admin vs public.
    import quotas as _q
    _bak = os.environ.get("NEOGEN_OWNER_UNLIMITED", "")
    os.environ["NEOGEN_OWNER_UNLIMITED"] = "1"
    assert portee("agent", None) == "complet"
    os.environ["NEOGEN_OWNER_UNLIMITED"] = ""
    assert portee("regle", None) == "local_bride"      # public + perso
    assert portee("agent", None) == "remonte"          # public + systeme
    os.environ["NEOGEN_OWNER_UNLIMITED"] = _bak
    print("  portee : admin=complet, public/perso=local_bride, public/systeme=remonte -> OK")

    print("=" * 64)
    print("  TOUT VERT : le noyau est garde, fail-closed, data-driven.")
    print("=" * 64)
