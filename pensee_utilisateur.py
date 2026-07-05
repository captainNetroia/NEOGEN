"""
NEOGEN - Pensee personnelle : version publique et bridee de La Pensee.

Cousin de pensee.py, mais isole au sac de chaque utilisateur web (jamais le cerveau
commun). Pas une extension de pensee.py : ce module a ses propres chemins, sa propre
amorce de savoir (limitee au sac de l'utilisateur), ses propres participants (personas
generiques, jamais les vrais agents systeme d'agent_core.PROFILS), et son propre mode
LLM par defaut (eco/local uniquement, ou BYOK — jamais la cle systeme).

Garde-fous (doctrine Jordan, 2026-07-04) :
  - Isolation totale : lit/ecrit exclusivement data/users/{id}/ via user_namespace.
    Ne touche JAMAIS data/pensees.jsonl (le cerveau commun de l'owner).
  - Savoir : uniquement evolution_gouvernee.regles_actives(user)/profils_custom(user)
    (deja scopes sac). Jamais savoir.charger_index() (savoir global partage).
  - Participants : personas generiques fixes, jamais agent_core.PROFILS (roster reel).
  - Modele LLM : eco (Ollama local) par defaut, ou client BYOK fourni par l'appelant.
    Jamais de cle systeme fort/mixte pour un compte web.
  - Proposition d'evolution : passe TOUJOURS par evolution_gouvernee.proposer(user=...),
    qui applique le garde-fou de contenu noyau.payload_sain() avant toute creation de
    proposition (voir noyau.py). Jamais d'application directe.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-07-04.
"""
from __future__ import annotations

import json
import time

import robustesse as rob
import user_namespace as _ns
from pensee import AMBIANCES, TYPES_PENSEE, _texte_de, _parser_json

# ── Constantes propres, plus strictes que la version owner ─────────────────────

SEUIL_BULLE_PERSO = 0.70
SEUIL_PROPOSITION_PERSO = 0.75
THROTTLE_S_PERSO = 300  # 5 min : plus large que les 60s owner (anti-spam public/cout)

# Personas generiques : jamais les vrais agents systeme (pas de fuite du roster reel).
_PARTICIPANTS_PERSO = [
    {"cle": "strategue", "titre": "Le Stratege"},
    {"cle": "explorateur", "titre": "L'Explorateur"},
    {"cle": "critique", "titre": "Le Critique"},
    {"cle": "pragmatique", "titre": "Le Pragmatique"},
]


def _pensees_path(user: dict | None) -> str:
    return _ns.data_path(user, "pensees_perso.jsonl")


def _config_path(user: dict | None) -> str:
    return _ns.data_path(user, "pensee_perso_config.json")


_CONFIG_DEFAUT_PERSO = {"mode": "eco", "intervalle_min": 120}


def _config_perso(user: dict | None) -> dict:
    """Lit la config perso. Defaut eco/local. Ne leve jamais."""
    cfg = dict(_CONFIG_DEFAUT_PERSO)
    try:
        import os
        chemin = _config_path(user)
        if os.path.exists(chemin):
            with open(chemin, encoding="utf-8") as f:
                cfg.update({k: v for k, v in json.load(f).items() if k in _CONFIG_DEFAUT_PERSO})
    except Exception:
        pass
    if cfg.get("mode") not in ("eco", "byok"):
        cfg["mode"] = "eco"
    try:
        cfg["intervalle_min"] = max(5, int(cfg.get("intervalle_min", 120)))
    except Exception:
        cfg["intervalle_min"] = 120
    return cfg


def _set_config_perso(user: dict | None, **champs) -> dict:
    import os
    cfg = _config_perso(user)
    for k in ("mode", "intervalle_min"):
        if k in champs and champs[k] is not None:
            cfg[k] = champs[k]
    if cfg.get("mode") not in ("eco", "byok"):
        cfg["mode"] = "eco"
    try:
        cfg["intervalle_min"] = max(5, int(cfg.get("intervalle_min", 120)))
    except Exception:
        cfg["intervalle_min"] = 120
    chemin = _config_path(user)
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


# ── Amorce : uniquement le sac de l'utilisateur, jamais le savoir global ───────

def _amorce_perso(user: dict | None, n: int = 3) -> list[dict]:
    """Grains de savoir issus UNIQUEMENT du sac de l'utilisateur (regles/idees/agents
    custom qu'il a lui-meme forges) — jamais savoir.charger_index() (savoir partage
    de tous les utilisateurs). Ne leve jamais."""
    try:
        import evolution_gouvernee as _evo
        regles = _evo.regles_actives(user)
        grains = []
        for idee in (regles.get("idees") or [])[:n]:
            if isinstance(idee, str) and idee.strip():
                grains.append({"domaine": "idee_perso", "contenu": idee.strip()[:240]})
        for cle, val in list((regles.get("regles") or {}).items())[:n]:
            grains.append({"domaine": "regle_perso", "contenu": f"{cle}: {val}"[:240]})
        return grains[:n]
    except Exception:
        return []


def _participants_perso() -> list[dict]:
    """Personas generiques fixes : jamais les vrais agents systeme (agent_core.PROFILS)."""
    return list(_PARTICIPANTS_PERSO)


def _prompt_systeme_perso(participants: list[dict], graines: list[dict],
                          sujet: str | None = None) -> str:
    noms = ", ".join(p["titre"] for p in participants)
    bloc_savoir = "\n".join(f"- [{g['domaine']}] {g['contenu']}" for g in graines) or \
        "- (pas encore de savoir personnel accumule, partez d'une reflexion generale)"
    types = ", ".join(TYPES_PENSEE)
    bloc_sujet = (
        f"SUJET PROPOSE PAR L'UTILISATEUR : « {sujet} ». La conversation porte sur ce sujet.\n"
        if sujet else ""
    )
    return (
        "Tu animes une reflexion personnelle pour un utilisateur de NEOGEN : une petite "
        "conversation entre personas fictifs qui l'aident a faire emerger une idee utile "
        "POUR SON PROPRE PROJET (pas pour le systeme NEOGEN lui-meme).\n"
        f"PARTICIPANTS (personas fictifs, pas de vrais agents) : {noms}.\n"
        f"{bloc_sujet}"
        "SAVOIR PERSONNEL DE L'UTILISATEUR (ce qu'il a deja note/forge) :\n"
        f"{bloc_savoir}\n\n"
        "Genere une COURTE conversation (3 a 5 repliques) qui fait emerger une pensee de "
        f"type parmi : {types}. Le but : une idee utile pour le projet PERSONNEL de "
        "l'utilisateur, jamais pour modifier NEOGEN lui-meme (le systeme partage).\n"
        "Si la pensee debouche sur un changement CONCRET pour son propre espace (une regle, "
        "une idee, un savoir a retenir), ajoute un champ "
        '"evolution" : {"type": "<regle|idee|savoir>", "payload": {...}, "raison": "<pourquoi>"}. '
        "Reste UNIQUEMENT dans les types regle/idee/savoir — jamais agent ni modele. "
        "Sinon, omets ce champ. Tu ne proposes JAMAIS rien qui toucherait a la securite, "
        "l'authentification, les autres utilisateurs, le code source ou l'infrastructure : "
        "seulement des notes/regles utiles pour CE projet personnel.\n"
        "Reponds UNIQUEMENT par un objet JSON valide, sans aucun texte autour, de la forme :\n"
        '{"transcript": [{"agent": "<titre>", "texte": "<replique>"}, ...], '
        '"type": "<un des types>", "titre": "<titre court de la pensee>", '
        '"synthese": "<2-3 phrases : l\'idee retenue et pourquoi elle est utile>", '
        '"interet": <nombre 0.0 a 1.0>}'
    )


# ── Conversation ────────────────────────────────────────────────────────────────

def converser_perso(user: dict | None, sujet: str | None = None,
                    byok_ctx=None, *, _client=None) -> dict | None:
    """Tient une session de pensee personnelle. Ne leve jamais.
    byok_ctx : contexte LLM fourni par l'appelant (BYOK), sinon repli Ollama local.
    _client : injection pour les tests (aucun appel reseau)."""
    sujet = (sujet or "").strip()[:300] or None
    graines = _amorce_perso(user)
    participants = _participants_perso()
    systeme = _prompt_systeme_perso(participants, graines, sujet=sujet)

    try:
        if _client is not None:
            cl, mode_eff = _client, "test"
        elif byok_ctx is not None:
            import gateway
            cl, mode_eff = gateway.client(byok_ctx, tier="moyen"), "byok"
        else:
            import gateway
            import os
            ollama_base = os.environ.get("NEOGEN_OLLAMA_BASE", "http://host.docker.internal:11434/v1")
            ctx = gateway.LLMContext(provider="local", base_url=ollama_base)
            cl, mode_eff = gateway.client(ctx, tier="moyen"), "eco"

        consigne = (f"Reflechis sur : « {sujet} ». Produis le JSON demande."
                    if sujet else "Lance la reflexion et produis le JSON demande.")
        res = cl.messages.create(
            system=systeme,
            messages=[{"role": "user", "content": consigne}],
            max_tokens=6000,  # marge large : certains modeles BYOK "reasoning" consomment
            response_json=True,  # des tokens de reflexion caches avant la reponse
        )
        brut = _texte_de(res)
        data = _parser_json(brut)
    except Exception as e:
        rob.journaliser(f"pensee_perso : conversation echouee : {e}", "erreur",
                        source="pensee_utilisateur")
        return None

    if not data:
        return None

    typ = data.get("type") if data.get("type") in TYPES_PENSEE else "idee"
    transcript = data.get("transcript") if isinstance(data.get("transcript"), list) else []
    synthese = (data.get("synthese") or "").strip() or (data.get("titre") or "").strip()
    if not synthese:
        return None
    try:
        interet = max(0.0, min(1.0, float(data.get("interet", 0.5))))
    except Exception:
        interet = 0.5

    evolution = data.get("evolution") if isinstance(data.get("evolution"), dict) else None
    # Bride cote code (en plus du prompt) : types autorises limites pour le public.
    if evolution and evolution.get("type") not in ("regle", "idee", "savoir"):
        evolution = None
    if evolution and not isinstance(evolution.get("payload"), dict):
        evolution = None

    return {
        "participants": [p["titre"] for p in participants],
        "transcript": transcript,
        "type": typ,
        "titre": (data.get("titre") or synthese)[:120],
        "synthese": synthese[:800],
        "interet": round(interet, 3),
        "mode": mode_eff,
        "evolution": evolution,
        "sujet": sujet,
    }


# ── Scoring (simplifie : pas d'evaluateur global, interet seul suffit ici) ─────

def _scorer_perso(pensee: dict) -> float:
    return round(float(pensee.get("interet", 0.5)), 3)


def _id_pensee_perso(pensee: dict) -> str:
    import hashlib
    cle = f"{pensee.get('titre', '')}|{pensee.get('synthese', '')[:120]}"
    return hashlib.sha256(cle.encode()).hexdigest()[:16]


# ── Archivage (dans le sac de l'utilisateur uniquement) ────────────────────────

def _enregistrer_perso(user: dict | None, pensee: dict, score: float) -> dict:
    from sanitizer import contient_secret, nettoyer
    import os

    record = dict(pensee)
    record["id"] = _id_pensee_perso(pensee)
    record["ts"] = time.time()
    record["score"] = score
    record["bulle"] = score >= SEUIL_BULLE_PERSO
    record["lue"] = False
    record["proposition"] = score >= SEUIL_PROPOSITION_PERSO

    for champ in ("titre", "synthese"):
        if contient_secret(record.get(champ, "")):
            record[champ] = nettoyer(record[champ])
    nettoyes = []
    for tour in record.get("transcript", []):
        if isinstance(tour, dict):
            t = (tour.get("texte") or "")
            nettoyes.append({"agent": tour.get("agent", ""),
                             "texte": nettoyer(t) if contient_secret(t) else t})
    record["transcript"] = nettoyes

    chemin = _pensees_path(user)
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _lire_perso(user: dict | None) -> list[dict]:
    import os
    chemin = _pensees_path(user)
    if not os.path.exists(chemin):
        return []
    out = []
    try:
        with open(chemin, encoding="utf-8") as f:
            for ligne in f:
                ligne = ligne.strip()
                if ligne:
                    try:
                        out.append(json.loads(ligne))
                    except Exception:
                        continue
    except Exception:
        return []
    return out


def _reecrire_perso(user: dict | None, pensees: list[dict]) -> None:
    import os
    chemin = _pensees_path(user)
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        for p in pensees:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")


# ── Cycle complet ────────────────────────────────────────────────────────────

def cycle_pensee_perso(user: dict | None, force: bool = False, sujet: str | None = None,
                       byok_ctx=None, *, _client=None) -> dict:
    """Session complete de pensee personnelle : conversation -> score -> archive (sac) ;
    haut score + evolution -> validation programmatique (noyau.payload_sain) PUIS
    proposition dans le Hub (jamais d'application directe). NE LEVE JAMAIS."""
    uid = _ns.sac_id(user) or "anonyme"
    throttle_cle = f"pensee_perso:cycle:{uid}"
    if not force and rob.deja_fait(throttle_cle, ttl_s=THROTTLE_S_PERSO):
        return {"execute": False, "raison": "throttle (session recente)"}
    rob.marquer_fait(throttle_cle)

    with rob.garde("cycle pensee perso", source="pensee_utilisateur"):
        pensee = converser_perso(user, sujet=sujet, byok_ctx=byok_ctx, _client=_client)
        if not pensee:
            return {"execute": False, "raison": "aucune pensee produite"}

        score = _scorer_perso(pensee)
        record = _enregistrer_perso(user, pensee, score)

        proposition = None
        if score >= SEUIL_PROPOSITION_PERSO:
            evo = record.get("evolution")
            if isinstance(evo, dict) and evo.get("type"):
                try:
                    import evolution_gouvernee
                    proposition = evolution_gouvernee.proposer(
                        evo.get("type"), evo.get("payload", {}),
                        titre=record.get("titre", ""),
                        raison=evo.get("raison", "") or record.get("synthese", ""),
                        user=user)
                except Exception as e:
                    rob.journaliser(f"pensee_perso : evolution non proposee : {e}", "erreur",
                                    source="pensee_utilisateur")

        rob.journaliser(
            f"pensee_perso [{uid}/{record['type']}] score={score} bulle={record['bulle']} "
            f"prop={bool(proposition)} : {record['titre']}",
            "succes" if record["bulle"] else "info", source="pensee_utilisateur")

        return {"execute": True, "id": record["id"], "score": score,
                "bulle": record["bulle"], "type": record["type"],
                "titre": record["titre"], "transcript": record["transcript"],
                "synthese": record["synthese"],
                "proposition": proposition, "mode": record.get("mode"),
                "sujet": record.get("sujet")}
    return {"execute": False, "raison": "erreur capturee (voir journal)"}


# ── Lecture / notifications ─────────────────────────────────────────────────────

def lister_perso(user: dict | None, limit: int = 50) -> list[dict]:
    pensees = _lire_perso(user)
    pensees.sort(key=lambda p: float(p.get("ts", 0)), reverse=True)
    return pensees[:limit]


def bulles_non_lues_perso(user: dict | None) -> list[dict]:
    return [p for p in _lire_perso(user) if p.get("bulle") and not p.get("lue")]


def marquer_lue_perso(user: dict | None, pensee_id: str) -> dict:
    pensees = _lire_perso(user)
    trouve = False
    for p in pensees:
        if p.get("id") == pensee_id:
            p["lue"] = True
            trouve = True
    if trouve:
        _reecrire_perso(user, pensees)
    return {"ok": trouve, "id": pensee_id}


def marquer_archive_perso(user: dict | None, pensee_id: str) -> dict:
    import time as _time
    pensees = _lire_perso(user)
    trouve = False
    for p in pensees:
        if p.get("id") == pensee_id:
            p["archive"] = True
            p["archive_ts"] = _time.time()
            trouve = True
    if trouve:
        _reecrire_perso(user, pensees)
    return {"ok": trouve, "id": pensee_id}


def marquer_vie_donnee_perso(user: dict | None, pensee_id: str) -> dict:
    """Marque qu'un 'donner-vie' a deja ete tente sur cette pensee (empeche de la
    re-proposer indefiniment a chaque rechargement de la liste)."""
    import time as _time
    pensees = _lire_perso(user)
    trouve = False
    for p in pensees:
        if p.get("id") == pensee_id:
            p["vie_donnee"] = True
            p["vie_donnee_ts"] = _time.time()
            trouve = True
    if trouve:
        _reecrire_perso(user, pensees)
    return {"ok": trouve, "id": pensee_id}


def etat_perso(user: dict | None) -> dict:
    pensees = _lire_perso(user)
    return {
        "config": _config_perso(user),
        "total": len(pensees),
        "bulles_non_lues": sum(1 for p in pensees if p.get("bulle") and not p.get("lue")),
        "propositions_issues": sum(1 for p in pensees if p.get("proposition")),
        "seuils": {"bulle": SEUIL_BULLE_PERSO, "proposition": SEUIL_PROPOSITION_PERSO},
    }


# ── Auto-verification offline (aucun appel reseau) ──────────────────────────────

if __name__ == "__main__":
    import tempfile
    import os as _os

    print("=" * 64)
    print("NEOGEN - PENSEE PERSONNELLE : auto-verification (sans appel reseau)")
    print("=" * 64)

    _tmp = tempfile.mkdtemp()
    _ns._DATA = _tmp
    _ns._USERS_ROOT = _os.path.join(_tmp, "users")
    _os.environ["NEOGEN_OWNER_UNLIMITED"] = "0"
    _os.environ["NEOGEN_OWNER_EMAIL"] = ""

    class _FauxBloc:
        def __init__(self, texte): self.text = texte
    class _FauxRes:
        def __init__(self, texte): self.content = [_FauxBloc(texte)]
    class _FauxMessages:
        def __init__(self, interet, evolution=None): self._i = interet; self._e = evolution
        def create(self, **kw):
            payload = {
                "transcript": [
                    {"agent": "Le Stratege", "texte": "Et si on notait les priorites du projet ?"},
                    {"agent": "Le Pragmatique", "texte": "Bonne idee, ca aide a s'organiser."},
                ],
                "type": "idee",
                "titre": "Notes de priorites",
                "synthese": "Tenir une liste de priorites pour le projet personnel.",
                "interet": self._i,
            }
            if self._e:
                payload["evolution"] = self._e
            return _FauxRes(json.dumps(payload, ensure_ascii=False))
    class _FauxClient:
        def __init__(self, interet=0.9, evolution=None):
            self.messages = _FauxMessages(interet, evolution)

    user_a = {"id": "u_test_perso_a", "email": "a@test.local"}
    user_b = {"id": "u_test_perso_b", "email": "b@test.local"}

    # 1) Isolation : A et B ont des chemins de sac distincts
    assert _pensees_path(user_a) != _pensees_path(user_b)
    assert "u_test_perso_a" in _pensees_path(user_a)
    print("  isolation des chemins OK")

    # 2) Conversation via client factice
    p = converser_perso(user_a, _client=_FauxClient(0.9))
    assert p and p["type"] in TYPES_PENSEE and p["synthese"], p
    assert p["participants"] == [x["titre"] for x in _PARTICIPANTS_PERSO]
    print(f"  converser_perso OK -> type={p['type']}")

    # 3) evolution bridee : type hors liste blanche est ignore
    p_agent = converser_perso(user_a, _client=_FauxClient(
        0.9, evolution={"type": "agent", "payload": {"outils": ["controler_ecran"]}}))
    assert p_agent["evolution"] is None, "type 'agent' doit etre bloque cote code pour le public"
    print("  bridage type evolution (agent/modele exclus) OK")

    # 4) Cycle complet : archive dans le sac de A, jamais dans data/pensees.jsonl
    import sys, types as _types
    faux_evo = _types.ModuleType("evolution_gouvernee")
    faux_evo.proposer = lambda *a, **k: {"ok": True, "prop_id": "test", "portee": "sac"}
    sys.modules["evolution_gouvernee"] = faux_evo

    r = cycle_pensee_perso(user_a, force=True, _client=_FauxClient(
        0.95, evolution={"type": "regle", "payload": {"valeur": "prioriser par urgence"}}))
    assert r["execute"] and r["bulle"] and r["proposition"], r
    assert _os.path.exists(_pensees_path(user_a)), "doit ecrire dans le sac de A"
    assert not _os.path.exists(_os.path.join(_tmp, "pensees.jsonl")), \
        "ne doit JAMAIS ecrire dans le cerveau commun"
    print(f"  cycle_pensee_perso OK -> score={r['score']} bulle+proposition, sac isole")

    # 5) B ne voit jamais les pensees de A
    assert lister_perso(user_b) == [], "B ne doit voir aucune pensee de A"
    assert not _os.path.exists(_pensees_path(user_b)), "aucun fichier cree pour B"
    print("  cloisonnement A/B OK -> B ne voit rien de A")

    # 6) lister/bulles/marquer_lue sur le sac de A
    arch = lister_perso(user_a)
    assert len(arch) >= 1, arch
    nb_bulles = len(bulles_non_lues_perso(user_a))
    assert nb_bulles >= 1
    rid = bulles_non_lues_perso(user_a)[0]["id"]
    assert marquer_lue_perso(user_a, rid)["ok"] is True
    assert len(bulles_non_lues_perso(user_a)) == nb_bulles - 1
    print("  lister/bulles/marquer_lue OK")

    # 7) etat_perso coherent
    e = etat_perso(user_a)
    assert e["total"] >= 1 and e["config"]["mode"] == "eco"
    print(f"  etat_perso OK -> total={e['total']}")

    print("=" * 64)
    print("  TOUT VERT : la Pensee personnelle fonctionne, isolee, sans appel reseau.")
    print("=" * 64)
