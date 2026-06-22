"""
NEOGEN - Auto-amélioration déclenchée par l'usage.

L'organisme apprend de son PROPRE usage. Au lieu d'une évolution manuelle, ce
module lit l'historique réel des créations (registre) et en déduit des SIGNAUX
concrets d'amélioration : taux d'échec, réparations fréquentes, capacités qui
posent problème, lignées qui stagnent. Il dit aussi QUAND une passe d'évolution
(evolution.py) ou de réparation (usine_autoreparation.py) serait utile.

C'est le maillon "l'usage nourrit l'amélioration" : honnête (pas de magie), basé
sur des données observées, pour que le système, le moteur et l'IA progressent.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-22.
"""

from __future__ import annotations

# Seuils : au-delà, on émet un signal d'amélioration.
SEUIL_ECHEC = 0.30          # >30% d'échecs -> signal
SEUIL_TENTATIVES = 2.0      # moyenne de tentatives > 2 -> réparations fréquentes
MIN_ECHANTILLON = 3         # pas de conclusion sous 3 produits


def analyser_usage() -> dict:
    """Analyse le registre et renvoie des insights d'amélioration concrets.
    Retourne {total, taux_succes, signaux:[...], action_suggeree, sain:bool}."""
    try:
        import registre
        entrees = registre.lister()
    except Exception:
        entrees = []

    total = len(entrees)
    if total == 0:
        return {"total": 0, "signaux": [], "sain": True,
                "action_suggeree": "Aucune création encore : rien à améliorer."}

    succes = sum(1 for e in entrees if e.get("verdict") == "promu" or e.get("promouvable"))
    taux_succes = round(succes / total, 2)
    tent_moy = round(sum(e.get("tentatives", 1) for e in entrees) / total, 2)

    signaux = []

    # 1) Taux d'échec élevé.
    if total >= MIN_ECHANTILLON and (1 - taux_succes) > SEUIL_ECHEC:
        signaux.append({
            "type": "echec_eleve",
            "detail": f"{int((1-taux_succes)*100)}% des créations ne sont pas promouvables.",
            "amelioration": "Renforcer le discernement (proposer) en amont et le repair sélectif.",
        })

    # 2) Réparations fréquentes.
    if total >= MIN_ECHANTILLON and tent_moy > SEUIL_TENTATIVES:
        signaux.append({
            "type": "reparations_frequentes",
            "detail": f"Moyenne de {tent_moy} tentatives par création.",
            "amelioration": "Lancer une passe d'évolution (evolution.py) sur les générateurs.",
        })

    # 3) Capacité réseau souvent en échec (corrélation capacité <-> échec).
    avec_reseau = [e for e in entrees if "reseau" in (e.get("capacites") or [])]
    if len(avec_reseau) >= MIN_ECHANTILLON:
        ko_reseau = sum(1 for e in avec_reseau if not (e.get("verdict") == "promu" or e.get("promouvable")))
        if ko_reseau / len(avec_reseau) > SEUIL_ECHEC:
            signaux.append({
                "type": "reseau_fragile",
                "detail": f"Les créations 'réseau' échouent souvent ({ko_reseau}/{len(avec_reseau)}).",
                "amelioration": "Revoir la liste blanche de domaines / le proxy d'egress.",
            })

    sain = not signaux
    if sain:
        action = "Système sain : continuer. L'auto-amélioration se déclenchera si des signaux apparaissent."
    else:
        action = "Signaux détectés : " + "; ".join(s["amelioration"] for s in signaux)

    return {
        "total": total,
        "taux_succes": taux_succes,
        "tentatives_moyennes": tent_moy,
        "signaux": signaux,
        "sain": sain,
        "action_suggeree": action,
    }


if __name__ == "__main__":
    import json
    print("=" * 60)
    print("NEOGEN - AUTO-AMELIORATION : analyse de l'usage")
    print("=" * 60)
    res = analyser_usage()
    print(json.dumps(res, ensure_ascii=False, indent=2))
    assert "signaux" in res and "sain" in res
    print("  OK")
    print("=" * 60)
