"""
NEOGEN - AUDIT ECLAIR : traduction humaine, declenchee (pas continue).

ECLAIR (eclair.py) compresse l'historique envoye au modele ; ANCRE (ancre_divergence.py)
detecte une derive sans bloquer l'agent. Ces deux mecanismes rendent la boucle plus opaque
au premier coup d'oeil (moins de texte integral rejoue, recadrages discrets) - il faut donc
un moyen de revenir en langage humain, a la demande, sans ajouter d'appel LLM (zero cout
supplementaire, comme ECLAIR et ANCRE).

AUDIT ECLAIR lit l'historique REEL de la boucle (`messages`, deja produit par
agent_core.dialoguer) et en extrait un resume humain en 4 lignes :
  CE QUI A ETE FAIT / CE QUI A DERIVE / POURQUOI / PROCHAINE DECISION.

Declenchement : sur anomalie (au moins une derive detectee) ou a la demande explicite -
jamais a chaque etape (sinon ca redevient aussi bruyant que le dialogue integral qu'ECLAIR
voulait justement eviter).

Garanties : ne leve jamais (repli : resume degrade mais jamais d'exception).

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-30.
"""
from __future__ import annotations
import json
import re

from eclair import empreinte

_RE_RESULTAT = re.compile(r"^\[Resultat ([^\]]+)\] (.*)", re.DOTALL)
_RE_DELEGATION = re.compile(r"^\[Resultat delegation a ([^\]]+)\] (.*)", re.DOTALL)
_RE_ERREUR = re.compile(r"^\[Erreur outil\] (.*)", re.DOTALL)
_RE_REFUS = re.compile(r"^\[Acces refuse\] (.*)", re.DOTALL)
_RE_RAPPEL = re.compile(r"^\[Rappel ancre\] (.*)", re.DOTALL)


def extraire(messages: list[dict]) -> dict:
    """Relit l'historique d'une boucle ReAct et en extrait les faits (outils, derives,
    erreurs). Aucune interpretation du modele : seulement ce qui est ecrit dans `messages`.
    Ne leve jamais (repli : structure vide)."""
    try:
        outils, derives, erreurs = [], [], []
        for m in messages if isinstance(messages, list) else []:
            if not isinstance(m, dict):
                continue
            contenu = m.get("content", "")
            if not isinstance(contenu, str):
                continue
            if m.get("role") == "assistant":
                try:
                    appel = json.loads(contenu)
                    if isinstance(appel, dict) and appel.get("outil"):
                        outils.append(appel["outil"])
                except (json.JSONDecodeError, TypeError):
                    pass
                continue
            if _RE_DELEGATION.match(contenu) or _RE_RESULTAT.match(contenu):
                pass  # deja compte via l'appel assistant correspondant (pas de doublon)
            elif (mm := _RE_ERREUR.match(contenu)):
                erreurs.append(empreinte(mm.group(1), 100))
            elif (mm := _RE_REFUS.match(contenu)):
                erreurs.append(empreinte(mm.group(1), 100))
            elif (mm := _RE_RAPPEL.match(contenu)):
                derives.append(empreinte(mm.group(1), 100))
        return {"outils": outils, "derives": derives, "erreurs": erreurs}
    except Exception:
        return {"outils": [], "derives": [], "erreurs": []}


def auditer(messages: list[dict], reponse_finale: str = "") -> str:
    """Resume humain en 4 lignes de ce qu'a fait l'agent. Jamais d'appel LLM, jamais
    d'exception (repli : resume minimal)."""
    try:
        f = extraire(messages)
        fait = (", ".join(f["outils"]) if f["outils"] else "aucune action outil") + \
               f" ({len(f['outils'])} etape{'s' if len(f['outils']) != 1 else ''})"
        if f["derives"]:
            derive = f"{len(f['derives'])} alerte(s) -> recadrage applique vers : " + f["derives"][0]
        else:
            derive = "aucune"
        if f["erreurs"]:
            pourquoi = "rencontre : " + f["erreurs"][0]
        elif f["derives"]:
            pourquoi = "la trajectoire s'eloignait de la demande d'origine, rappel injecte"
        else:
            pourquoi = "deroulement normal, aligne avec la demande"
        decision = empreinte(reponse_finale, 160) if reponse_finale else \
            "aucune reponse finale - boucle interrompue ou en attente"
        return (
            f"CE QUI A ETE FAIT : {fait}\n"
            f"CE QUI A DERIVE : {derive}\n"
            f"POURQUOI : {pourquoi}\n"
            f"PROCHAINE DECISION : {decision}"
        )
    except Exception:
        return "AUDIT indisponible (resume non genere)."


# ── Auto-verification (aucun appel reseau) ───────────────────────────────────────
if __name__ == "__main__":
    print("=" * 64)
    print("NEOGEN - AUDIT ECLAIR : auto-verification (offline)")
    print("=" * 64)

    historique = [
        {"role": "assistant", "content": json.dumps({"outil": "rechercher", "arguments": "{}"})},
        {"role": "user", "content": "[Resultat rechercher] 3 resultats trouves sur le sujet X"},
        {"role": "assistant", "content": json.dumps({"outil": "ecrire", "arguments": "{}"})},
        {"role": "user", "content": "[Erreur outil] disque plein"},
        {"role": "user", "content": "[Rappel ancre] Objectif initial : faire un rapport de lisibilite"},
    ]

    # 1. extraire() retrouve outils + derive + erreur depuis le texte brut, sans LLM.
    f = extraire(historique)
    assert f["outils"] == ["rechercher", "ecrire"], f
    assert len(f["derives"]) == 1
    assert len(f["erreurs"]) == 1
    print("  extraction outils/derives/erreurs depuis l'historique brut OK")

    # 2. auditer() produit les 4 lignes attendues.
    texte = auditer(historique, reponse_finale="Rapport genere malgre l'erreur disque.")
    for ligne in ("CE QUI A ETE FAIT", "CE QUI A DERIVE", "POURQUOI", "PROCHAINE DECISION"):
        assert ligne in texte, f"ligne manquante : {ligne}"
    assert "rechercher" in texte and "ecrire" in texte
    print("  resume 4 lignes complet OK")

    # 3. Deroulement normal (sans derive ni erreur) -> message rassurant, pas alarmant.
    propre = [
        {"role": "assistant", "content": json.dumps({"outil": "lire_fichier", "arguments": "{}"})},
        {"role": "user", "content": "[Resultat lire_fichier] contenu lu avec succes"},
    ]
    texte2 = auditer(propre, reponse_finale="Voici le contenu demande.")
    assert "aucune" in texte2.split("CE QUI A DERIVE :")[1].splitlines()[0]
    assert "deroulement normal" in texte2
    print("  deroulement normal (sans derive/erreur) OK")

    # 4. Repli : entrees invalides -> jamais d'exception.
    assert extraire(None) == {"outils": [], "derives": [], "erreurs": []}
    assert auditer(None) != ""
    assert "PROCHAINE DECISION" in auditer([], reponse_finale="")
    print("  repli sur entrees invalides (ne leve jamais) OK")

    print("=" * 64)
    print("  TOUT VERT.")
    print("=" * 64)
