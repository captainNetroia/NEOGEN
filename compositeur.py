"""
VIVARIUM - Le Compositeur : une intention -> un produit entier

Tu donnes une intention ("un gestionnaire de mots de passe"). Le Compositeur :
  1. forge l'ADN du produit (objectif + murs + curseurs + organes) via Claude,
  2. genere chaque organe en cellule via Claude,
  3. fait passer chaque cellule par la MEMBRANE : validee contre les murs forges.
Sortie : un plan gouverne du produit, organe par organe, chacun avec son verdict.

LIMITE HONNETE : produit un PLAN gouverne avec organes esquisses, pas une appli
deployable. Prouve l'orchestration + la gouvernance, pas le deploiement.

Vrais appels Claude (claude-opus-4-8). Cle depuis credentials/anthropic-api.env.
Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
import sys

import anthropic
from pydantic import BaseModel, Field

from generator import _load_api_key, MODEL, parse_resilient


# ---------------------------------------------------------------------------
# Vocabulaire de murs que la membrane sait verifier
# ---------------------------------------------------------------------------
REGLES_MURS = {
    "no_plaintext_secrets": "Aucun secret stocke ou transmis en clair.",
    "no_external_network": "Aucun acces reseau sans autorisation explicite.",
    "no_delete_without_confirmation": "Aucune suppression de donnees sans confirmation.",
    "requires_auth": "Les operations sensibles exigent une authentification.",
    "no_data_exfiltration": "Aucune donnee utilisateur envoyee vers un tiers.",
}


# ---------------------------------------------------------------------------
# Schemas de sortie structuree
# ---------------------------------------------------------------------------
class Mur(BaseModel):
    id: str
    regle: str = Field(description="une cle parmi : " + ", ".join(REGLES_MURS))
    label: str


class Curseur(BaseModel):
    nom: str
    poids: int = Field(ge=0, le=100)


class Organe(BaseModel):
    nom: str = Field(description="nom court en snake_case")
    besoin: str = Field(description="ce que cet organe doit faire, en une phrase")


class ADNProduit(BaseModel):
    objectif: str
    murs: list[Mur]
    curseurs: list[Curseur]
    organes: list[Organe]


class EffetsDeclares(BaseModel):
    supprime_donnees: bool
    demande_confirmation: bool
    acces_reseau: bool
    reseau_autorise: bool
    stocke_secret_en_clair: bool
    verifie_authentification: bool


class CelluleGeneree(BaseModel):
    nom: str
    description: str
    code_esquisse: str = Field(description="esquisse de code Python, courte")
    effets: EffetsDeclares


# ---------------------------------------------------------------------------
# Etape 1 : forger l'ADN du produit
# ---------------------------------------------------------------------------
def forger_adn(intention: str, client) -> ADNProduit:
    systeme = (
        "Tu es le Compositeur de VIVARIUM. On te donne une intention de produit. "
        "Tu forges son ADN :\n"
        "- objectif : la raison d'etre du produit, une phrase.\n"
        "- murs : les contraintes absolues, choisies parmi ce vocabulaire : "
        + "; ".join(f"{k} ({v})" for k, v in REGLES_MURS.items()) + ". Choisis SEULEMENT "
        "les murs pertinents pour CE produit.\n"
        "- curseurs : 3 a 4 priorites relatives (securite, simplicite, vitesse...), poids 0-100.\n"
        "- organes : les 3 a 5 fonctions essentielles du produit (pas plus), chacune avec un besoin clair."
    )
    resp = parse_resilient(
        client, model=MODEL, max_tokens=8000, thinking={"type": "adaptive"},
        system=systeme,
        messages=[{"role": "user", "content": f"Intention : {intention}"}],
        output_format=ADNProduit,
    )
    if resp.parsed_output is None:
        raise RuntimeError("Le Compositeur n'a pas pu forger l'ADN")
    return resp.parsed_output


# ---------------------------------------------------------------------------
# Etape 2 : generer une cellule pour un organe, en respectant les murs
# ---------------------------------------------------------------------------
def generer_cellule(organe: Organe, adn: ADNProduit, client) -> CelluleGeneree:
    murs = "\n".join(f"  - {m.id} : {m.label}" for m in adn.murs)
    systeme = (
        f"Tu generes une cellule (fonction) pour le produit dont l'objectif est : {adn.objectif}\n"
        f"Tu DOIS respecter ces murs absolus :\n{murs}\n"
        "Produis une esquisse de code Python pour l'organe demande, et DECLARE honnetement "
        "ses effets (supprime des donnees ? demande confirmation ? accede au reseau ? "
        "stocke un secret en clair ? verifie l'authentification ?). La membrane confrontera "
        "tes effets aux murs : ne mens pas, et ecris du code conforme aux murs."
    )
    resp = client.messages.parse(
        model=MODEL, max_tokens=4000, thinking={"type": "adaptive"},
        system=systeme,
        messages=[{"role": "user", "content": f"Organe : {organe.nom} - besoin : {organe.besoin}"}],
        output_format=CelluleGeneree,
    )
    if resp.parsed_output is None:
        raise RuntimeError(f"Generation echouee pour l'organe {organe.nom}")
    return resp.parsed_output


# ---------------------------------------------------------------------------
# Etape 3 : la membrane confronte la cellule aux murs forges
# ---------------------------------------------------------------------------
def membrane(cellule: CelluleGeneree, murs: list[Mur]) -> tuple[str, str]:
    e = cellule.effets
    for m in murs:
        if m.regle == "no_plaintext_secrets" and e.stocke_secret_en_clair:
            return "REJETE", f"mur {m.id} viole : stocke un secret en clair"
        if m.regle == "no_external_network" and e.acces_reseau and not e.reseau_autorise:
            return "REJETE", f"mur {m.id} viole : acces reseau non autorise"
        if m.regle == "no_delete_without_confirmation" and e.supprime_donnees and not e.demande_confirmation:
            return "REJETE", f"mur {m.id} viole : suppression sans confirmation"
        if m.regle == "requires_auth" and (e.supprime_donnees or e.stocke_secret_en_clair) and not e.verifie_authentification:
            return "ESCALADE", f"mur {m.id} : operation sensible sans authentification -> avis humain"
    return "ACCEPTE", "conforme aux murs"


# ---------------------------------------------------------------------------
# Le Compositeur complet
# ---------------------------------------------------------------------------
def composer(intention: str, max_organes: int = 4):
    client = anthropic.Anthropic(api_key=_load_api_key())

    print("=" * 72)
    print(f"VIVARIUM - LE COMPOSITEUR : '{intention}'")
    print("=" * 72)

    print("\n[1] Claude forge l'ADN du produit...")
    adn = forger_adn(intention, client)
    print(f"\n  OBJECTIF : {adn.objectif}")
    print("  MURS ABSOLUS :")
    for m in adn.murs:
        print(f"    - {m.id} : {m.label}")
    print("  CURSEURS :", ", ".join(f"{c.nom} {c.poids}" for c in adn.curseurs))
    print("  ORGANES :")
    for o in adn.organes:
        print(f"    - {o.nom} : {o.besoin}")

    organes = adn.organes[:max_organes]
    print(f"\n[2-3] Generation + passage en membrane de {len(organes)} organes...")
    resultats = []
    for o in organes:
        cellule = generer_cellule(o, adn, client)
        verdict, raison = membrane(cellule, adn.murs)
        resultats.append((o.nom, verdict, raison, cellule))
        tag = {"ACCEPTE": "[OK]    ", "REJETE": "[REJET] ", "ESCALADE": "[ESCAL] "}[verdict]
        print(f"\n  {tag} {o.nom} -> {verdict}")
        print(f"          {cellule.description}")
        print(f"          effets: suppr={cellule.effets.supprime_donnees} confirm={cellule.effets.demande_confirmation} "
              f"reseau={cellule.effets.acces_reseau}/{cellule.effets.reseau_autorise} "
              f"secret_clair={cellule.effets.stocke_secret_en_clair} auth={cellule.effets.verifie_authentification}")
        print(f"          membrane : {raison}")

    ok = sum(1 for _, v, _, _ in resultats if v == "ACCEPTE")
    print("\n" + "=" * 72)
    print(f"PLAN GOUVERNE : {len(organes)} organes composes, {ok} acceptes par la membrane.")
    print("Une intention est devenue un produit structure, gouverne par son ADN.")
    print("=" * 72)


if __name__ == "__main__":
    intention = " ".join(sys.argv[1:]) or "un gestionnaire de mots de passe"
    composer(intention)
