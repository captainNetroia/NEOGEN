"""
NEOGEN - ANCRE : Ancre de divergence latente.

Constat (boucle ReAct, agent_core.dialoguer) : a chaque etape, l'agent choisit un outil et
des arguments sans relecture explicite de la demande d'origine. Sur une boucle longue
(plusieurs etapes), la trajectoire peut deriver loin de l'intention initiale sans que rien
ne le signale, jusqu'a la reponse finale - trop tard pour corriger.

ANCRE fixe la derniere intention humaine validee (le message d'origine de l'appel) comme
reference, et mesure a chaque etape l'ecart lexical entre cette ancre et la pensee en
cours. Mesure purement locale (mots-cles + troncature, aucun appel reseau, aucun cout
supplementaire) - coherent avec l'objectif d'ECLAIR de reduire le cout, pas d'en ajouter.

Calibrage (corrige le 2026-06-30 apres test live) : un Jaccard brut sur l'ensemble des mots
penalise a tort les pensees courtes ("Je commence par lister...") comparees a une ancre
longue et detaillee, meme parfaitement alignees - le ratio s'ecroule juste parce que l'ancre
a plus de mots. Fix : (1) filtrage des mots-outils francais (stopwords) + troncature a 5
caracteres (rapproche "lister"/"liste", "creations"/"creation"...), (2) score asymetrique
cote etape (combien des mots-cles de l'ETAPE sont absents de l'ancre, pas l'inverse) pour ne
pas punir une ancre verbeuse.

Quand l'ecart depasse le seuil : SIGNAL (evenement 'derive' emis, visible dans l'audit) +
REFORMULATION (un rappel de l'ancre est injecte dans les messages pour que l'agent se
recadre lui-meme). Ne bloque JAMAIS l'action en cours et ne modifie jamais la decision de
l'agent : la derniere main reste humaine (Jordan), ANCRE ne fait qu'eclairer, jamais arbitrer.

Garanties : ne leve jamais (repli : pas de derive detectee).

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-30.
"""
from __future__ import annotations
import re

from eclair import empreinte

SEUIL_DERIVE = 0.85    # score au-dela duquel on signale une derive
MOTS_MIN_ANCRE = 3     # sous ce nombre de mots-cles dans l'ancre, la mesure n'est pas fiable
MOTS_MIN_ETAPE = 2     # sous ce nombre de mots-cles dans l'etape, pas assez de signal pour juger
LONGUEUR_STEM = 5       # troncature grossiere pour rapprocher singulier/pluriel/conjugaisons

_MOT = re.compile(r"[a-zà-ÿ]+", re.IGNORECASE)

# Mots-outils francais courants : leur presence/absence ne dit rien du sujet traite.
_STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "en", "que", "qui", "quoi",
    "pour", "par", "dans", "sur", "avec", "sans", "si", "ce", "cet", "cette", "ces", "cela", "ça",
    "je", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles", "me", "te", "se", "lui", "y",
    "au", "aux", "sa", "son", "ses", "leur", "leurs", "ma", "mon", "mes", "ta", "ton", "tes",
    "est", "es", "suis", "sont", "etre", "ai", "as", "a", "avons", "avez", "ont", "avoir",
    "ne", "pas", "plus", "puis", "donc", "car", "mais", "alors", "ainsi", "ensuite", "maintenant",
    "tres", "bien", "comme", "tout", "toute", "tous", "toutes", "ici", "la", "deja", "encore",
}


def _mots_cles(texte: str) -> set[str]:
    """Mots-cles stemmes (stopwords retires, troncature grossiere). Ne leve jamais."""
    try:
        mots = _MOT.findall((texte or "").lower())
        return {m[:LONGUEUR_STEM] for m in mots if len(m) > 2 and m not in _STOPWORDS}
    except Exception:
        return set()


def distance(ancre: str, texte: str) -> float:
    """Distance [0..1] : part des mots-cles de `texte` absents de l'ancre (0 = tout est
    couvert par l'ancre, 1 = aucun mot-cle commun). Asymetrique cote `texte` pour ne pas
    punir une ancre longue. Ne leve jamais (repli : 0.0, pas de derive)."""
    try:
        a, t = _mots_cles(ancre), _mots_cles(texte)
        if len(a) < MOTS_MIN_ANCRE or len(t) < MOTS_MIN_ETAPE:
            return 0.0
        return round(1 - (len(a & t) / len(t)), 3)
    except Exception:
        return 0.0


def verifier(ancre: str, etape_texte: str, seuil: float = SEUIL_DERIVE) -> dict:
    """Verifie si l'etape courante s'eloigne de l'ancre. Ne leve jamais."""
    try:
        score = distance(ancre, etape_texte)
        return {"derive": score >= seuil, "score": score, "seuil": seuil}
    except Exception:
        return {"derive": False, "score": 0.0, "seuil": seuil}


def rappel(ancre: str) -> dict:
    """Message de recadrage a injecter dans l'historique quand une derive est signalee.
    Reste un simple RAPPEL (jamais un ordre) : l'agent garde la main sur sa reponse."""
    return {"role": "user", "content": f"[Rappel ancre] Objectif initial : {empreinte(ancre)}"}


# ── Auto-verification (aucun appel reseau) ───────────────────────────────────────
if __name__ == "__main__":
    print("=" * 64)
    print("NEOGEN - ANCRE : auto-verification (offline)")
    print("=" * 64)

    ancre = "Cree un rapport de lisibilite du code Python du projet"

    # 1. Etape alignee sur l'ancre : pas de derive.
    proche = "Analyse le code Python du projet pour generer le rapport de lisibilite"
    v = verifier(ancre, proche)
    assert v["derive"] is False, v
    print(f"  etape alignee : score {v['score']} -> pas de derive OK")

    # 2. Etape totalement hors-sujet : derive signalee.
    loin = "Envoyer un message Telegram a propos de la meteo de demain a Paris"
    v = verifier(ancre, loin)
    assert v["derive"] is True, v
    print(f"  etape hors-sujet : score {v['score']} -> derive signalee OK")

    # 3. Ancre trop courte : mesure non fiable -> jamais de derive.
    v = verifier("ok", loin)
    assert v["derive"] is False
    print("  ancre trop courte : repli sans derive OK")

    # 4. Rappel : contient une empreinte courte de l'ancre, jamais tronque a vide.
    r = rappel(ancre)
    assert r["role"] == "user"
    assert "Objectif initial" in r["content"]
    assert ancre.split()[0] in r["content"]
    print("  rappel d'ancre bien forme OK")

    # 5. Repli : entrees invalides -> jamais de derive, jamais d'exception.
    assert verifier(None, None)["derive"] is False
    assert distance(None, None) == 0.0
    print("  repli sur entrees invalides (ne leve jamais) OK")

    print("=" * 64)
    print("  TOUT VERT.")
    print("=" * 64)
