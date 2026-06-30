"""
NEOGEN - ECLAIR : Echange Compresse Latent Auditable Intelligent Rapide.

Constat (boucle ReAct, agent_core.dialoguer) : a chaque etape, TOUT l'historique
des messages est reenvoye au modele. Les observations d'outils (jusqu'a 2000
caracteres chacune) sont donc rejouees integralement a chaque appel suivant : le
cout grossit avec chaque etape, alors que seules les dernieres etapes comptent
encore pour la decision en cours.

ECLAIR applique la "temperature semantique" : les derniers messages (canal chaud,
proches de l'instant present) restent intacts ; les plus anciens (canal froid)
sont reduits a une EMPREINTE courte (resume tronque) plutot qu'un dialogue
integral rejoue. La confiance ne vient plus de la lisibilite complete du passe
mais de l'empreinte verifiable -> meme principe que la pensee "Empreinte
auditable plutot que dialogue lisible".

Garanties : ne mute JAMAIS la liste source (le caller garde son historique
complet pour son propre bookkeeping ; seule la VUE envoyee a l'API est compressee).
Ne leve jamais (repli : renvoie les messages tels quels).

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-30.
"""
from __future__ import annotations

FENETRE_CHAUDE = 4        # nb de derniers messages gardes intacts (canal chaud)
LONGUEUR_EMPREINTE = 140  # caracteres conserves pour un message compresse (canal froid)


def empreinte(texte: str, n: int = LONGUEUR_EMPREINTE) -> str:
    """Reduit un texte a une empreinte courte et lisible. Ne leve jamais."""
    t = (texte or "").strip()
    if len(t) <= n:
        return t
    return t[:n].rstrip() + "…"


def compresser_messages(messages: list[dict], chaud: int = FENETRE_CHAUDE) -> list[dict]:
    """Vue compressee des messages pour l'appel API : les `chaud` derniers messages
    restent intacts (canal chaud), les plus anciens sont reduits a une empreinte
    (canal froid). Ne mute jamais `messages`. Repli : renvoie `messages` si besoin."""
    try:
        if not isinstance(messages, list) or len(messages) <= chaud:
            return messages
        seuil = len(messages) - chaud
        out = []
        for i, m in enumerate(messages):
            if i >= seuil or not isinstance(m, dict):
                out.append(m)
                continue
            contenu = m.get("content", "")
            if isinstance(contenu, str) and len(contenu) > LONGUEUR_EMPREINTE:
                out.append({**m, "content": empreinte(contenu)})
            else:
                out.append(m)
        return out
    except Exception:
        return messages


def gain_estime(messages: list[dict], chaud: int = FENETRE_CHAUDE) -> dict:
    """Caracteres brut vs compresse -> pourcentage economise. Pour l'audit (transparence :
    Jordan peut voir combien ECLAIR a reellement reduit). Ne leve jamais."""
    try:
        def _taille(lst):
            return sum(len(m.get("content", "") or "") for m in lst if isinstance(m, dict))
        brut = _taille(messages)
        compresse = _taille(compresser_messages(messages, chaud))
        gain_pct = round(100 * (1 - compresse / brut), 1) if brut else 0.0
        return {"brut": brut, "compresse": compresse, "gain_pct": gain_pct}
    except Exception:
        return {"brut": 0, "compresse": 0, "gain_pct": 0.0}


# ── Auto-verification (aucun appel reseau) ───────────────────────────────────────
if __name__ == "__main__":
    print("=" * 64)
    print("NEOGEN - ECLAIR : auto-verification (offline)")
    print("=" * 64)

    # 1. Court historique (<= fenetre chaude) : rien ne change.
    court = [{"role": "user", "content": "bonjour"}] * 3
    assert compresser_messages(court) == court
    print("  historique court : inchange OK")

    # 2. Long historique : les anciens messages longs sont compresses, les recents intacts.
    long_obs = "x" * 1800
    historique = []
    for i in range(8):
        historique.append({"role": "assistant", "content": f'{{"outil":"o{i}"}}'})
        historique.append({"role": "user", "content": f"[Resultat o{i}] {long_obs}"})
    vue = compresser_messages(historique, chaud=4)
    # Les 4 derniers messages doivent etre identiques aux originaux (canal chaud).
    assert vue[-4:] == historique[-4:], "le canal chaud doit rester intact"
    # Les messages anciens longs doivent etre raccourcis.
    anciens_compresses = [m for m in vue[:-4] if len(m.get("content", "")) > LONGUEUR_EMPREINTE + 5]
    assert not anciens_compresses, "le canal froid doit etre compresse"
    print("  canal chaud intact + canal froid compresse OK")

    # 3. Ne mute jamais la liste source.
    avant = json_avant = [dict(m) for m in historique]
    compresser_messages(historique, chaud=4)
    assert historique == avant, "la liste source ne doit jamais etre mutee"
    print("  liste source non mutee OK")

    # 4. Gain mesurable et coherent.
    g = gain_estime(historique, chaud=4)
    assert g["gain_pct"] > 50, f"gain attendu > 50% sur un historique tres verbeux : {g}"
    assert g["compresse"] < g["brut"]
    print(f"  gain mesure : {g['gain_pct']}% ({g['brut']} -> {g['compresse']} caracteres) OK")

    # 5. Repli : entree invalide -> renvoie tel quel, ne leve jamais.
    assert compresser_messages(None) is None
    assert compresser_messages([]) == []
    assert compresser_messages("pas une liste") == "pas une liste"
    print("  repli sur entree invalide (ne leve jamais) OK")

    print("=" * 64)
    print("  TOUT VERT.")
    print("=" * 64)
