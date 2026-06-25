"""
NEOGEN - Reseau du savoir : le maillon MONTANT du reseau d'intelligence distribuee.

Jusqu'ici le reseau etait DESCENDANT (les skills communautaires redescendaient via
le registre). Ici on ferme la boucle : une instance qui a forge un skill a HAUTE
VALEUR (verdict evaluateur.decision == "partage") le CONTRIBUE au pot commun.

Securite d'abord (surtout en LOCAL) :
  - environnement.politique() decide : auto (serveur) / consent (local) / off.
  - en mode "consent", rien ne part sans opt-in explicite (consentement "tout"
    cote telemetrie, ou NEOGEN_CONTRIBUTION=on au niveau instance).
  - sanitizer : un skill contenant un secret n'est JAMAIS contribue (fail-closed).
  - anonymizer : payload nettoye, aucune donnee utilisateur, aucun identifiant direct.
  - file d'attente locale -> transmission groupee, videe seulement si l'envoi reussit.

Endpoint : NEOGEN_CONTRIBUTION_ENDPOINT (defaut https://telemetrie.netroia.tech/v1/contribute).
Jordan cure ensuite les contributions vers registry/skills-community.json.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-25.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

import evaluateur
import environnement

BASE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(BASE, "data")
_QUEUE = os.path.join(_DATA, "contributions_attente.jsonl")

_ENDPOINT_DEFAUT = "https://telemetrie.netroia.tech/v1/contribute"


# ── Evaluation : un skill merite-t-il d'etre partage ? ──────────────────────────

def _grain_skill(skill: dict) -> dict:
    contenu = " ".join(filter(None, [
        skill.get("titre", ""),
        skill.get("description", ""),
        (skill.get("instructions", "") or "")[:200],
    ])).strip()[:600]
    return {
        "id": hashlib.sha256(("skill:" + skill.get("nom", "")).encode()).hexdigest()[:16],
        "domaine": "skill",
        "type": "competence",
        "contenu": contenu,
        "score": 0.0,
        "ts": skill.get("cree_le", time.time()),
        "usages": int(skill.get("usages", 0)),
        "meta": {"nom": skill.get("nom", "")},
    }


def _skills_evalues() -> list[tuple[dict, dict]]:
    """(skill, grain scoré) pour tous les skills non-socle. Score = corpus complet."""
    try:
        import competences
        skills = [s for s in competences.lister() if not s.get("socle")]
    except Exception:
        return []
    grains = [_grain_skill(s) for s in skills]
    for g in grains:
        g["score"] = evaluateur.scorer_grain(g, grains)
    return list(zip(skills, grains))


# ── Garde-fous securite ─────────────────────────────────────────────────────────

def _sans_secret(skill: dict) -> bool:
    """Fail-closed : tout skill dont le texte contient un secret est refuse."""
    try:
        import sanitizer
        texte = " ".join([
            skill.get("description", "") or "",
            skill.get("instructions", "") or "",
        ])
        return not sanitizer.contient_secret(texte)
    except Exception:
        return False  # dans le doute, on ne contribue pas


def _consent_instance() -> bool:
    """Opt-in explicite en mode 'consent' (local) : env instance OU un user 'tout'."""
    if os.environ.get("NEOGEN_CONTRIBUTION", "").strip().lower() == "on":
        return True
    try:
        import telemetrie
        consents = telemetrie._lire_consents()
        return any((v or {}).get("niveau") == "tout" for v in consents.values())
    except Exception:
        return False


def _payload(skill: dict, score: float) -> dict:
    """Construit le payload contribue : metadonnees du skill seulement, anonymise.
    Aucune donnee utilisateur, aucun identifiant direct."""
    import anonymizer
    brut = {
        "nom": skill.get("nom", ""),
        "titre": skill.get("titre", ""),
        "description": skill.get("description", ""),
        "instructions": skill.get("instructions", ""),
        "outils": skill.get("outils", []),
        "score": round(float(score), 3),
    }
    return anonymizer.nettoyer_dict(brut)


# ── Decision + mise en file ─────────────────────────────────────────────────────

def candidat(grain: dict) -> bool:
    """Le grain merite-t-il d'etre partage ? (consomme evaluateur.decision)
    "partage" ET "integration" sont au-dessus du seuil de partage : un skill assez
    bon pour etre integre est a fortiori assez bon pour etre contribue."""
    return evaluateur.decision(float(grain.get("score", 0))) in ("partage", "integration")


def _enfiler(payload: dict) -> None:
    os.makedirs(_DATA, exist_ok=True)
    with open(_QUEUE, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _deja_en_file(nom: str) -> bool:
    if not os.path.exists(_QUEUE):
        return False
    try:
        with open(_QUEUE, encoding="utf-8") as f:
            for ligne in f:
                ligne = ligne.strip()
                if ligne and json.loads(ligne).get("nom") == nom:
                    return True
    except Exception:
        return False
    return False


def contribuer(skill: dict, grain: dict, user_id: str | None = None) -> dict:
    """Evalue + filtre + met en file un skill candidat. Idempotent. Ne leve jamais.
    Retourne {statut: 'file'|'ignore'|'refuse', raison}."""
    pol = environnement.politique()
    if pol["contribution"] == "off":
        return {"statut": "ignore", "raison": "contribution desactivee (env)"}
    if not candidat(grain):
        return {"statut": "ignore", "raison": "score sous le seuil de partage"}
    if not _sans_secret(skill):
        return {"statut": "refuse", "raison": "secret detecte (fail-closed)"}
    if pol["contribution"] == "consent":
        consent = (user_id and _user_consent_tout(user_id)) or _consent_instance()
        if not consent:
            return {"statut": "ignore", "raison": "pas de consentement (local)"}
    nom = skill.get("nom", "")
    if _deja_en_file(nom):
        return {"statut": "ignore", "raison": "deja en file"}
    _enfiler(_payload(skill, grain.get("score", 0)))
    return {"statut": "file", "raison": "candidat mis en file de contribution"}


def _user_consent_tout(user_id: str) -> bool:
    try:
        import telemetrie
        return telemetrie.get_consentement(user_id) == "tout"
    except Exception:
        return False


# ── Transmission groupee ────────────────────────────────────────────────────────

def transmettre(endpoint_url: str | None = None, instance_id: str = "") -> dict:
    """Envoie la file de contributions vers l'endpoint. Vide la file si succes.
    Ne leve jamais. Retourne {ok, statut_http|erreur, envoyes}."""
    pol = environnement.politique()
    if pol["contribution"] == "off":
        return {"ok": True, "envoyes": 0, "detail": "contribution desactivee"}
    endpoint = (endpoint_url or os.environ.get("NEOGEN_CONTRIBUTION_ENDPOINT", _ENDPOINT_DEFAUT)).strip()
    if not endpoint:
        return {"ok": True, "envoyes": 0, "detail": "aucun endpoint"}
    if not os.path.exists(_QUEUE):
        return {"ok": True, "envoyes": 0, "detail": "rien a transmettre"}
    contributions = []
    with open(_QUEUE, encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if ligne:
                try:
                    contributions.append(json.loads(ligne))
                except Exception:
                    continue
    if not contributions:
        return {"ok": True, "envoyes": 0, "detail": "file vide"}
    import urllib.request
    payload = json.dumps({
        "instance": hashlib.sha256((instance_id or "neogen").encode()).hexdigest()[:12],
        "contexte": pol["contexte"],
        "version": "1",
        "contributions": contributions,
        "ts": time.time(),
    }, ensure_ascii=False).encode()
    try:
        req = urllib.request.Request(
            endpoint, data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "NEOGEN/1"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            statut = resp.status
        if 200 <= statut < 300:
            os.remove(_QUEUE)  # vide seulement si l'envoi a reussi
            return {"ok": True, "statut_http": statut, "envoyes": len(contributions)}
        return {"ok": False, "statut_http": statut, "envoyes": 0}
    except Exception as e:
        return {"ok": False, "erreur": str(e)[:200], "envoyes": 0}


# ── Cycle complet (appele par auto_amelioration, hebdomadaire) ──────────────────

def cycle_contribution(endpoint_url: str | None = None, user_id: str | None = None,
                       transmettre_apres: bool = True) -> dict:
    """Scanne les skills, met en file les candidats au partage, transmet.
    Consomme evaluateur.decision(). Respecte environnement + securite. Ne leve jamais."""
    pol = environnement.politique()
    if pol["contribution"] == "off":
        return {"contexte": pol["contexte"], "contribution": "off", "files": 0}
    files = 0
    for skill, grain in _skills_evalues():
        r = contribuer(skill, grain, user_id=user_id)
        if r.get("statut") == "file":
            files += 1
    res = {"contexte": pol["contexte"], "contribution": pol["contribution"], "files": files}
    if transmettre_apres:
        res["transmission"] = transmettre(endpoint_url)
    return res


def etat() -> dict:
    """Vue observable : politique d'env + taille de la file."""
    en_file = 0
    if os.path.exists(_QUEUE):
        try:
            with open(_QUEUE, encoding="utf-8") as f:
                en_file = sum(1 for l in f if l.strip())
        except Exception:
            en_file = 0
    return {"environnement": environnement.resume(), "en_file": en_file}


if __name__ == "__main__":
    print("=" * 64)
    print("NEOGEN - RESEAU DU SAVOIR (montant) : auto-verification")
    print("=" * 64)

    # Environnement de test : forcer local + opt-out -> rien ne part
    os.environ["NEOGEN_ENV"] = "local"
    os.environ["NEOGEN_CONTRIBUTION"] = "off"
    g = {"score": 0.9, "domaine": "skill", "meta": {}}
    assert candidat(g) is True, "0.9 doit etre au-dessus du seuil de partage"
    r = contribuer({"nom": "x", "instructions": "rien"}, g)
    assert r["statut"] == "ignore" and "desactivee" in r["raison"], r
    print("  opt-out (env) : aucune contribution -> OK")

    # local sans consentement -> ignore
    os.environ["NEOGEN_CONTRIBUTION"] = ""
    r = contribuer({"nom": "x", "description": "util", "instructions": "fais X"}, g)
    assert r["statut"] == "ignore" and "consentement" in r["raison"], r
    print("  local sans consentement : ignore (securite) -> OK")

    # local + opt-in instance -> mais secret detecte -> refuse (fail-closed)
    os.environ["NEOGEN_CONTRIBUTION"] = "on"
    r = contribuer({"nom": "y", "description": "d", "instructions": "ma cle sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789"}, g)
    assert r["statut"] == "refuse", r
    print("  secret detecte : refuse (fail-closed) -> OK")

    # score faible -> ignore
    gfaible = {"score": 0.2, "domaine": "skill", "meta": {}}
    assert candidat(gfaible) is False
    print("  score sous le seuil : non candidat -> OK")

    # nettoyage
    if os.path.exists(_QUEUE):
        os.remove(_QUEUE)
    for k in ("NEOGEN_ENV", "NEOGEN_CONTRIBUTION"):
        os.environ.pop(k, None)
    print("=" * 64)
    print("  TOUT VERT.")
    print("=" * 64)
