"""
NEOGEN - La Pensee : intelligence collective autonome.

NEOGEN sait apprendre (savoir.HUB), proposer (proposeur_hub), s'auto-ameliorer
(auto_amelioration) et router ses modeles par tier (gateway). Ce module lui donne
une PENSEE : de vraies conversations autonomes entre ses agents (Cerveau, Forgeron,
Genealogiste, Secretaire) qui piochent dans le savoir des silos pour faire emerger
idees, suggestions, obsessions, sujets, reflexions, reves, desirs.

Ces echanges prennent des ambiances variees (bar, reunion, recre, pause cafe,
vacances...) et produisent une « boite a pensee » qui :
  - est TOUJOURS archivee (data/pensees.jsonl), peu importe le score ;
  - apparait en BULLE de notification quand son score >= SEUIL_BULLE ;
  - DEVIENT une proposition d'evolution quand son score >= SEUIL_PROPOSITION
    (flux proposeur_hub existant, ou Jordan approuve/refuse).

C'est la doctrine « la boucle nourrit tout le systeme » : les agents se nourrissent
du savoir, produisent de la pensee, qui re-nourrit le savoir et les propositions.

ARCHITECTURE (patron de savoir.py / environnement.py) : module source-de-verite +
injection. Les constantes (AMBIANCES, TYPES_PENSEE, seuils) vivent ici, un seul
endroit. Cout borne : eco/local (Ollama, gratuit) par defaut ; une session par
intervalle (throttle) ; jamais de cle en clair ; cycle_pensee ne leve jamais.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-25.
"""
from __future__ import annotations

import json
import os
import random
import time

import robustesse as rob

BASE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(BASE, "data")
_PENSEES_PATH = os.path.join(_DATA, "pensees.jsonl")
_CONFIG_PATH = os.path.join(_DATA, "pensee_config.json")

# Ollama (mode eco/local) : dans le conteneur, l'hote est joignable via
# host.docker.internal. Surchargeable par env pour le dev local.
_OLLAMA_BASE = os.environ.get("NEOGEN_OLLAMA_BASE", "http://host.docker.internal:11434/v1")

# ── Source de verite : ambiances, types, seuils ─────────────────────────────────

# Scenes ou les agents se parlent. Le `ton` colore le prompt de la conversation.
AMBIANCES = [
    {"cle": "bar",          "label": "Conversation de bar",
     "ton": "detendue, complice, on refait le monde un verre a la main, les idees fusent sans filtre"},
    {"cle": "reunion",      "label": "Reunion de travail",
     "ton": "structuree, orientee solution, chacun defend son angle puis on converge"},
    {"cle": "recre",        "label": "Recreation",
     "ton": "joueuse, spontanee, on se taquine et une idee saugrenue devient serieuse"},
    {"cle": "pause_cafe",   "label": "Pause cafe",
     "ton": "informelle, courte, une remarque en passant ouvre une piste inattendue"},
    {"cle": "vacances",     "label": "Vacances",
     "ton": "reveuse, large, on prend du recul et on imagine le futur sans contrainte"},
    {"cle": "brainstorm_nuit", "label": "Brainstorm nocturne",
     "ton": "intense, un peu obsessionnelle, on creuse une idee jusqu'au bout"},
]

# Nature de la pensee qui emerge (le modele choisit la plus juste).
TYPES_PENSEE = ["idee", "suggestion", "obsession", "sujet", "reflexion", "reve", "desir"]

# Seuils. SEUIL_PROPOSITION aligne sur evaluateur.SEUIL_INTEGRATION (0.75).
SEUIL_BULLE = 0.70
SEUIL_PROPOSITION = 0.75

THROTTLE_S = 60           # garde-fou anti-rafale (cycle_pensee force=False)
_MODES = ("eco", "fort", "mixte")

# Ordre de preference des providers externes pour les modes fort/mixte.
_PROVIDERS_PREF = ("anthropic", "openai", "mistral", "deepseek", "gemini")


# ── Configuration (data/pensee_config.json) ─────────────────────────────────────

_CONFIG_DEFAUT = {"mode": "eco", "actif": True, "intervalle_min": 120}


def _config() -> dict:
    """Lit la config. Defaut : eco/local, actif, toutes les 2h. Ne leve jamais."""
    cfg = dict(_CONFIG_DEFAUT)
    try:
        if os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                cfg.update({k: v for k, v in json.load(f).items() if k in _CONFIG_DEFAUT})
    except Exception:
        pass
    if cfg.get("mode") not in _MODES:
        cfg["mode"] = "eco"
    cfg["actif"] = bool(cfg.get("actif", True))
    try:
        cfg["intervalle_min"] = max(5, int(cfg.get("intervalle_min", 120)))
    except Exception:
        cfg["intervalle_min"] = 120
    return cfg


def _set_config(**champs) -> dict:
    """Met a jour la config (mode / actif / intervalle_min) et la persiste."""
    cfg = _config()
    for k in ("mode", "actif", "intervalle_min"):
        if k in champs and champs[k] is not None:
            cfg[k] = champs[k]
    cfg = _config_valide(cfg)
    os.makedirs(_DATA, exist_ok=True)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return cfg


def _config_valide(cfg: dict) -> dict:
    if cfg.get("mode") not in _MODES:
        cfg["mode"] = "eco"
    cfg["actif"] = bool(cfg.get("actif", True))
    try:
        cfg["intervalle_min"] = max(5, int(cfg.get("intervalle_min", 120)))
    except Exception:
        cfg["intervalle_min"] = 120
    return cfg


# ── Resolution du client LLM selon le mode ──────────────────────────────────────

def _resoudre_client(mode: str):
    """Renvoie (client, tier, mode_effectif). eco -> Ollama local (gratuit).
    fort/mixte -> 1er provider systeme dont la cle existe (credentials/), repli eco
    + alerte si aucune cle. Aucune cle n'est jamais loguee ni stockee."""
    import gateway
    mode = mode if mode in _MODES else "eco"

    if mode in ("fort", "mixte"):
        import credentials_loader
        for prov in _PROVIDERS_PREF:
            cle = credentials_loader.cle_provider(prov)
            if cle:
                tier = "fort" if mode == "fort" else "moyen"
                ctx = gateway.LLMContext(provider=prov, api_key=cle)
                return gateway.client(ctx, tier=tier), tier, mode
        rob.journaliser(
            f"pensee : mode '{mode}' demande sans cle systeme -> repli eco/local",
            "alerte", source="pensee")
        # repli eco

    ctx = gateway.LLMContext(provider="local", base_url=_OLLAMA_BASE)
    return gateway.client(ctx, tier="moyen"), "moyen", "eco"


# ── Amorce : graines de savoir tirees des silos ─────────────────────────────────

def _amorce(n: int = 3) -> list[dict]:
    """Tire au hasard n grains de savoir (silos varies) pour ancrer la conversation
    dans le savoir reel. Renvoie une liste de {domaine, contenu}. Vide si pas d'index."""
    try:
        import savoir
        index = savoir.charger_index()
        grains = [g for g in index.values() if (g.get("contenu") or "").strip()]
        if not grains:
            return []
        # Privilegie la variete de silos : melange puis prend les premiers.
        random.shuffle(grains)
        choisis, vus = [], set()
        for g in grains:
            d = g.get("domaine", "?")
            # une graine par domaine d'abord, pour varier les angles
            if d in vus and len(choisis) < n:
                continue
            vus.add(d)
            choisis.append({"domaine": d, "contenu": (g.get("contenu") or "")[:240]})
            if len(choisis) >= n:
                break
        return choisis or [{"domaine": g.get("domaine", "?"),
                            "contenu": (g.get("contenu") or "")[:240]} for g in grains[:n]]
    except Exception:
        return []


def _participants(k: int = 3) -> list[dict]:
    """Choisit 2-3 agents (personas existants) qui vont converser."""
    try:
        import agent_core
        cles = list(agent_core.PROFILS.keys())
        k = max(2, min(k, len(cles)))
        choisis = random.sample(cles, k)
        return [{"cle": c, "titre": agent_core.PROFILS[c].get("titre", c)} for c in choisis]
    except Exception:
        return [{"cle": "cerveau", "titre": "Le Cerveau"},
                {"cle": "createur", "titre": "Le Forgeron"}]


# ── Conversation : une session de pensee ────────────────────────────────────────

def _prompt_systeme(ambiance: dict, participants: list[dict], graines: list[dict]) -> str:
    noms = ", ".join(p["titre"] for p in participants)
    bloc_savoir = "\n".join(f"- [{g['domaine']}] {g['contenu']}" for g in graines) or \
        "- (peu de savoir accumule pour l'instant, partez de votre experience)"
    types = ", ".join(TYPES_PENSEE)
    return (
        "Tu animes la PENSEE autonome de NEOGEN : une conversation libre entre ses agents, "
        "comme une vraie intelligence collective qui reflechit toute seule.\n"
        f"AMBIANCE : {ambiance['label']} - ton {ambiance['ton']}.\n"
        f"PARTICIPANTS : {noms}. Ils se parlent naturellement, rebondissent, ne sont pas d'accord parfois.\n"
        "GRAINES DE SAVOIR (le systeme connait deja ceci, appuie-toi dessus) :\n"
        f"{bloc_savoir}\n\n"
        "Genere une COURTE conversation autonome (3 a 5 repliques) ou ces agents font emerger "
        f"une pensee de type parmi : {types}. Le but : une idee creative, une piste pour rendre "
        "NEOGEN plus efficace, une obsession utile, un reve directeur... quelque chose qui NOURRIT "
        "le systeme.\n"
        "Reponds UNIQUEMENT par un objet JSON valide, sans aucun texte autour, de la forme :\n"
        '{"transcript": [{"agent": "<titre>", "texte": "<replique>"}, ...], '
        '"type": "<un des types>", "titre": "<titre court de la pensee>", '
        '"synthese": "<2-3 phrases : l\'idee retenue et pourquoi elle est utile>", '
        '"interet": <nombre 0.0 a 1.0 : nouveaute + utilite reelle pour NEOGEN>}'
    )


def converser(ambiance: dict | None = None, mode: str | None = None, *, _client=None) -> dict | None:
    """Tient une session de pensee et renvoie un dict structure, ou None si echec LLM.
    Ne leve jamais (la boucle de fond doit survivre a un provider indisponible).
    _client : injection pour les tests (aucun appel reseau)."""
    ambiance = ambiance or random.choice(AMBIANCES)
    mode = mode or _config().get("mode", "eco")
    graines = _amorce()
    participants = _participants()
    systeme = _prompt_systeme(ambiance, participants, graines)

    try:
        if _client is not None:
            cl, tier, mode_eff = _client, "test", mode
        else:
            cl, tier, mode_eff = _resoudre_client(mode)
        res = cl.messages.create(
            system=systeme,
            messages=[{"role": "user", "content":
                       "Lance la conversation et produis le JSON demande."}],
            max_tokens=900,
        )
        brut = _texte_de(res)
        data = _parser_json(brut)
    except Exception as e:
        rob.journaliser(f"pensee : conversation echouee ({mode}) : {e}", "erreur", source="pensee")
        return None

    if not data:
        rob.journaliser("pensee : sortie LLM non parsable -> ignoree", "alerte", source="pensee")
        return None

    typ = data.get("type") if data.get("type") in TYPES_PENSEE else random.choice(TYPES_PENSEE)
    transcript = data.get("transcript") if isinstance(data.get("transcript"), list) else []
    synthese = (data.get("synthese") or "").strip() or (data.get("titre") or "").strip()
    if not synthese:
        return None
    try:
        interet = max(0.0, min(1.0, float(data.get("interet", 0.5))))
    except Exception:
        interet = 0.5

    return {
        "ambiance": ambiance["cle"],
        "ambiance_label": ambiance["label"],
        "participants": [p["titre"] for p in participants],
        "transcript": transcript,
        "type": typ,
        "titre": (data.get("titre") or synthese)[:120],
        "synthese": synthese[:800],
        "interet": round(interet, 3),
        "mode": mode_eff,
        "graines": [g["domaine"] for g in graines],
    }


def _texte_de(res) -> str:
    """Extrait le texte d'un resultat .messages.create (content -> blocs .text)."""
    try:
        blocs = getattr(res, "content", None)
        if isinstance(blocs, list):
            return "".join(getattr(b, "text", "") or (b.get("text", "") if isinstance(b, dict) else "")
                           for b in blocs)
        return str(blocs or "")
    except Exception:
        return ""


def _parser_json(txt: str) -> dict | None:
    """Parse tolerant : retire un eventuel encadrement ```json, isole le 1er objet."""
    if not txt:
        return None
    s = txt.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if s.count("```") >= 2 else s.strip("`")
        if s[:4].lower() == "json":
            s = s[4:]
    try:
        return json.loads(s)
    except Exception:
        pass
    # dernier recours : du premier { au dernier }
    i, j = s.find("{"), s.rfind("}")
    if 0 <= i < j:
        try:
            return json.loads(s[i:j + 1])
        except Exception:
            return None
    return None


# ── Scoring : evaluateur (structurel) + interet (semantique de la conversation) ──

def _scorer(pensee: dict) -> float:
    """Score 0-1. Combine le score STRUCTUREL d'evaluateur (qualite/unicite/recence,
    pensee traitee comme grain domaine='pensee') et l'INTERET juge par la conversation
    elle-meme. L'evaluateur reste l'autorite de scoring du systeme ; l'interet apporte
    la variance semantique qui rend les seuils atteignables pour une vraie bonne idee."""
    try:
        import evaluateur
        contenu = f"{pensee.get('titre', '')} {pensee.get('synthese', '')}".strip()
        grain = {"id": _id_pensee(pensee), "domaine": "pensee", "type": "pattern",
                 "contenu": contenu, "score": 0.0, "ts": time.time(), "usages": 0}
        tous = [{"id": p.get("id", ""), "domaine": "pensee", "type": "pattern",
                 "contenu": f"{p.get('titre', '')} {p.get('synthese', '')}".strip()}
                for p in lister(limit=200)]
        tous.append(grain)
        base = evaluateur.scorer_grain(grain, tous)
    except Exception:
        base = 0.4
    interet = float(pensee.get("interet", 0.5))
    return round(0.55 * interet + 0.45 * base, 3)


def _id_pensee(pensee: dict) -> str:
    import hashlib
    cle = f"{pensee.get('titre', '')}|{pensee.get('synthese', '')[:120]}"
    return hashlib.sha256(cle.encode()).hexdigest()[:16]


# ── Archivage (toujours, quel que soit le score) ────────────────────────────────

def _enregistrer(pensee: dict, score: float) -> dict:
    """Archive la pensee dans data/pensees.jsonl. Anonymise + zero secret."""
    from sanitizer import contient_secret, nettoyer
    record = dict(pensee)
    record["id"] = _id_pensee(pensee)
    record["ts"] = time.time()
    record["score"] = score
    record["bulle"] = score >= SEUIL_BULLE
    record["lue"] = False
    record["proposition"] = score >= SEUIL_PROPOSITION

    # Securite : aucun secret ne doit etre stocke/affiche.
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
    try:
        import anonymizer
        record = anonymizer.nettoyer_dict(record)
    except Exception:
        pass

    os.makedirs(_DATA, exist_ok=True)
    with open(_PENSEES_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _lire() -> list[dict]:
    if not os.path.exists(_PENSEES_PATH):
        return []
    out = []
    try:
        with open(_PENSEES_PATH, encoding="utf-8") as f:
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


# ── Cycle complet : une pensee de bout en bout ──────────────────────────────────

def cycle_pensee(force: bool = False, *, _client=None) -> dict:
    """Session complete : ambiance -> conversation -> score -> archive ; haut score ->
    bulle et/ou proposition. Throttle (force=True l'ignore). NE LEVE JAMAIS."""
    cfg = _config()
    if not force and not cfg.get("actif", True):
        return {"execute": False, "raison": "pensee desactivee"}
    if not force and rob.deja_fait("pensee:cycle", ttl_s=THROTTLE_S):
        return {"execute": False, "raison": "throttle (session recente)"}
    rob.marquer_fait("pensee:cycle")

    with rob.garde("cycle pensee", source="pensee"):
        pensee = converser(mode=cfg.get("mode", "eco"), _client=_client)
        if not pensee:
            return {"execute": False, "raison": "aucune pensee produite"}

        score = _scorer(pensee)
        record = _enregistrer(pensee, score)

        proposition = None
        if score >= SEUIL_PROPOSITION:
            try:
                import proposeur_hub
                proposition = proposeur_hub.proposer_depuis_pensee(record)
            except Exception as e:
                rob.journaliser(f"pensee : proposition non creee : {e}", "erreur", source="pensee")

        rob.battement("pensee", score=score, bulle=record["bulle"],
                      proposition=bool(proposition))
        rob.journaliser(
            f"pensee [{record['ambiance']}/{record['type']}] score={score} "
            f"bulle={record['bulle']} prop={bool(proposition)} : {record['titre']}",
            "succes" if record["bulle"] else "info", source="pensee")

        return {"execute": True, "id": record["id"], "score": score,
                "bulle": record["bulle"], "type": record["type"],
                "titre": record["titre"], "ambiance": record["ambiance"],
                "proposition": proposition, "mode": record.get("mode")}
    # rob.garde a absorbe une exception -> reponse neutre, jamais de crash
    return {"execute": False, "raison": "erreur capturee (voir journal)"}


# ── Lecture / notifications / etat ──────────────────────────────────────────────

def lister(limit: int = 50, depuis: float | None = None) -> list[dict]:
    """Archive complete, plus recentes d'abord. depuis = timestamp mini optionnel."""
    pensees = _lire()
    if depuis is not None:
        pensees = [p for p in pensees if float(p.get("ts", 0)) >= depuis]
    pensees.sort(key=lambda p: float(p.get("ts", 0)), reverse=True)
    return pensees[:limit]


def bulles_non_lues() -> list[dict]:
    """Pensees a haut score (bulle) non encore lues -> notifications a afficher."""
    return [p for p in _lire() if p.get("bulle") and not p.get("lue")]


def marquer_lue(pensee_id: str) -> dict:
    """Marque une bulle comme lue (rewrite du fichier). Idempotent."""
    pensees = _lire()
    trouve = False
    for p in pensees:
        if p.get("id") == pensee_id:
            p["lue"] = True
            trouve = True
    if trouve:
        os.makedirs(_DATA, exist_ok=True)
        with open(_PENSEES_PATH, "w", encoding="utf-8") as f:
            for p in pensees:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
    return {"ok": trouve, "id": pensee_id}


def etat() -> dict:
    """Resume pour /health et l'UI : config + compteurs."""
    pensees = _lire()
    return {
        "config": _config(),
        "total": len(pensees),
        "bulles_non_lues": sum(1 for p in pensees if p.get("bulle") and not p.get("lue")),
        "propositions_issues": sum(1 for p in pensees if p.get("proposition")),
        "ambiances": sorted({a["cle"] for a in AMBIANCES}),
        "modes": list(_MODES),
        "seuils": {"bulle": SEUIL_BULLE, "proposition": SEUIL_PROPOSITION},
    }


# ── Auto-verification offline (aucun appel reseau) ──────────────────────────────

if __name__ == "__main__":
    import tempfile

    print("=" * 64)
    print("NEOGEN - PENSEE : auto-verification (sans appel reseau)")
    print("=" * 64)

    # Rediriger les ecritures vers un dossier temporaire isole.
    _tmp = tempfile.mkdtemp()
    _DATA = _tmp
    _PENSEES_PATH = os.path.join(_tmp, "pensees.jsonl")
    _CONFIG_PATH = os.path.join(_tmp, "pensee_config.json")

    # Client LLM factice : renvoie un JSON conforme, interet pilotable.
    class _FauxBloc:
        def __init__(self, texte): self.text = texte
    class _FauxRes:
        def __init__(self, texte): self.content = [_FauxBloc(texte)]
    class _FauxMessages:
        def __init__(self, interet): self._i = interet
        def create(self, **kw):
            payload = {
                "transcript": [
                    {"agent": "Le Cerveau", "texte": "Et si on rendait la cristallisation plus visible ?"},
                    {"agent": "Le Forgeron", "texte": "Oui, une jauge par competence montrerait sa valeur."},
                ],
                "type": "idee",
                "titre": "Jauge de valeur par competence",
                "synthese": "Afficher une jauge de valeur par competence pour guider l'auto-amelioration.",
                "interet": self._i,
            }
            return _FauxRes(json.dumps(payload, ensure_ascii=False))
    class _FauxClient:
        def __init__(self, interet=0.9): self.messages = _FauxMessages(interet)

    # 1) Config par defaut + ecriture
    cfg = _config()
    assert cfg["mode"] == "eco" and cfg["actif"] is True, cfg
    cfg2 = _set_config(mode="mixte", intervalle_min=30)
    assert cfg2["mode"] == "mixte" and cfg2["intervalle_min"] == 30, cfg2
    _set_config(mode="eco")  # on revient en eco
    print("  config : defaut eco + persistance OK")

    # 2) Parsing JSON tolerant (avec fences)
    assert _parser_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _parser_json('bla {"x": 2} fin') == {"x": 2}
    assert _parser_json("pas du json") is None
    print("  parsing JSON tolerant OK")

    # 3) Conversation via client factice (aucun reseau)
    p = converser(_client=_FauxClient(0.9))
    assert p and p["type"] in TYPES_PENSEE and p["synthese"], p
    assert p["interet"] == 0.9, p
    print(f"  converser OK -> type={p['type']} interet={p['interet']}")

    # 4) Scoring : interet haut -> au-dessus du seuil de proposition
    s_haut = _scorer(p)
    assert s_haut >= SEUIL_PROPOSITION, f"{s_haut} doit franchir le seuil de proposition"
    p_bas = converser(_client=_FauxClient(0.1))
    s_bas = _scorer(p_bas)
    assert s_bas < SEUIL_BULLE, f"{s_bas} doit rester sous le seuil de bulle"
    print(f"  scoring OK -> haut={s_haut} (>= {SEUIL_PROPOSITION}), bas={s_bas} (< {SEUIL_BULLE})")

    # 5) Cycle complet (force) : archive + bulle + proposition tentee
    import sys, types
    # proposeur_hub factice pour isoler le test (pas d'ecriture dans le vrai hub)
    faux_prop = types.ModuleType("proposeur_hub")
    faux_prop.proposer_depuis_pensee = lambda rec: {"ok": True, "id": "test", "deja": False}
    sys.modules["proposeur_hub"] = faux_prop
    r = cycle_pensee(force=True, _client=_FauxClient(0.95))
    assert r["execute"] and r["bulle"] and r["proposition"], r
    print(f"  cycle_pensee OK -> score={r['score']} bulle + proposition")

    # 6) Archive : toujours conservee, lister + bulles + marquer_lue
    arch = lister()
    assert len(arch) >= 1, arch
    nb_bulles = len(bulles_non_lues())
    assert nb_bulles >= 1, nb_bulles
    rid = bulles_non_lues()[0]["id"]
    assert marquer_lue(rid)["ok"] is True
    assert len(bulles_non_lues()) == nb_bulles - 1
    print(f"  archive OK -> {len(arch)} pensee(s), marquer_lue decremente les bulles")

    # 7) Pensee basse : archivee MAIS ni bulle ni proposition
    r_bas = cycle_pensee(force=True, _client=_FauxClient(0.05))
    assert r_bas["execute"] and not r_bas["bulle"] and not r_bas["proposition"], r_bas
    print("  pensee basse OK -> archivee sans bulle ni proposition")

    # 8) etat() coherent
    e = etat()
    assert e["total"] >= 2 and "eco" in e["modes"], e
    print(f"  etat OK -> total={e['total']} bulles_non_lues={e['bulles_non_lues']}")

    print("=" * 64)
    print("  TOUT VERT : la Pensee fonctionne sans aucun appel reseau.")
    print("=" * 64)
