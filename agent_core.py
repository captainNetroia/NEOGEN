"""
NEOGEN - Moteur d'agents conversationnels (le coeur du systeme multi-agents).

Un SEUL moteur, plusieurs agents specialises. Chaque agent = ce moteur + un
profil (role + outils autorises + tier de modele). Le moteur tient une
conversation multi-tours, REFLECHIT, choisit un OUTIL (parmi les fonctions
NEOGEN existantes), l'execute, lit le RESULTAT, et recommence jusqu'a repondre.

Protocole : ReAct via JSON structure (AgentStep). On s'appuie sur gateway.parse
qui garantit un JSON conforme sur TOUS les providers (anthropic, openai, gemini,
deepseek, mistral, local) -> l'agent fonctionne quel que soit le modele choisi
par l'utilisateur, sans tool-calling specifique a un provider.

Gouvernance conservee : les outils sont des fonctions NEOGEN vettees ; le
controle d'ecran exige le consentement cote hote ; la creation passe par la
sandbox + l'orchestrateur gouverne ; humain dernier mot.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-21.
"""

from __future__ import annotations

import json
from typing import Any, Callable
from pydantic import BaseModel, Field

import gateway
from sanitizer import nettoyer


# ---------------------------------------------------------------------------
# Le pas de raisonnement : l'agent reflechit puis SOIT appelle un outil SOIT
# repond. Schema impose a tous les providers via gateway.parse.
# ---------------------------------------------------------------------------
class AgentStep(BaseModel):
    pensee: str = Field(description="Ton raisonnement court et clair, visible par l'utilisateur (1 a 3 phrases).")
    outil: str | None = Field(default=None, description="Nom EXACT d'un outil a appeler, ou null si tu reponds directement.")
    arguments: str = Field(default="", description='Parametres de l\'outil sous forme d\'une CHAINE JSON, ex: {"agent": "createur", "mission": "..."}. Chaine vide si aucun parametre.')
    reponse: str | None = Field(default=None, description="Ta reponse finale a l'utilisateur, ou null si tu appelles encore un outil.")


def _parse_args(s) -> dict:
    """Parse la chaine JSON d'arguments en dict. Tolerant : ne leve jamais."""
    if isinstance(s, dict):
        return s
    if not s or not isinstance(s, str):
        return {}
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# BOITE A OUTILS : chaque outil enveloppe une fonction NEOGEN existante.
# Imports paresseux (dans les fonctions) pour : eviter les cycles, permettre le
# smoke test hors-ligne, et ne charger les modules lourds qu'a l'usage.
# Chaque outil renvoie une CHAINE lisible (re-injectee au modele + affichee).
# ---------------------------------------------------------------------------

def _ctx_from(kw: dict):
    """Recupere le LLMContext eventuellement passe par le moteur (cle/provider actifs)."""
    return kw.get("_ctx")


def outil_discerner(intention: str = "", **kw) -> str:
    from proposer import proposer
    cl = gateway.client(_ctx_from(kw), tier="moyen")
    p = proposer(intention, cl)
    return nettoyer(
        f"Discernement -> valeur:{getattr(p,'valeur','?')}/10 "
        f"faisabilite:{getattr(p,'faisabilite','?')}/10 clarte:{getattr(p,'clarte','?')}/10. "
        f"Reformulation: {getattr(p,'reformulation','(n/a)')}"
    )


def outil_conseiller(intention: str = "", **kw) -> str:
    from conseillers import conseiller
    cl = gateway.client(_ctx_from(kw), tier="moyen")
    c = conseiller(intention, cl)
    return nettoyer(str(c.model_dump() if hasattr(c, "model_dump") else c))[:1500]


def outil_creer_application(intention: str = "", persistance: bool = False,
                            reseau=False, domaines=None, **kw) -> str:
    """Cree une application de A a Z : decompose, delegue, assemble, gouverne (sandbox).
    'reseau' peut etre un booleen, une liste de domaines, ou {"domaines":[...]}.
    'domaines' = liste blanche des domaines autorises (OBLIGATOIRE si l'app a besoin d'internet)."""
    from orchestrateur import orchestrer
    from capacites import Capacites
    import registre
    emit = kw.get("_emit")
    # Le modele peut passer reseau/domaines sous plusieurs formes : on normalise.
    doms = []
    if isinstance(reseau, dict):
        doms = reseau.get("domaines") or reseau.get("domaines_autorises") or []
        reseau_on = True
    elif isinstance(reseau, (list, tuple)):
        doms = list(reseau)
        reseau_on = True
    else:
        reseau_on = bool(reseau)
    if domaines:
        doms = domaines if isinstance(domaines, (list, tuple)) else [domaines]
    cap = Capacites(persistance=bool(persistance), reseau=reseau_on,
                    domaines_autorises=[str(d).strip() for d in doms if str(d).strip()])

    def progress(evt: dict):
        if emit:
            safe = {k: (nettoyer(v) if isinstance(v, str) else v) for k, v in evt.items()}
            emit({"type": "forge", **safe})

    r = orchestrer(intention, ctx=_ctx_from(kw), cap=cap, reparer=True,
                   max_tentatives=3, enregistrer=True, progress=progress)
    produit_id = None
    if r.succes:
        entrees = registre.lister()
        if entrees:
            produit_id = entrees[-1]["id"]
    return nettoyer(
        f"Creation {'reussie' if r.succes else 'echouee'} (verdict:{r.verdict}, "
        f"tentatives:{r.tentatives}, lignes:{r.lignes}). "
        f"produit_id={produit_id}. Lecons: {'; '.join((r.lecons or [])[:3])}"
    )


def outil_lister_creations(**kw) -> str:
    import registre
    entrees = registre.lister()
    if not entrees:
        return "Aucune creation pour le moment."
    lignes = [f"- {e.get('id')} | {e.get('intention','?')[:60]} | verdict:{e.get('verdict','?')}"
              for e in entrees[-20:]]
    return nettoyer("Creations (20 dernieres):\n" + "\n".join(lignes))


def outil_genealogie(produit_id: str = "", **kw) -> str:
    import registre
    lign = registre.lignee_produit(produit_id)
    if not lign:
        return f"Aucune lignee trouvee pour {produit_id}."
    return nettoyer(f"Lignee de {produit_id} : {len(lign)} generation(s). "
                    + " -> ".join(e.get("id", "?") for e in lign))


def outil_controler_ecran(actions: Any = None, **kw) -> str:
    """Envoie des actions souris/clavier a l'agent local. Consentement requis cote hote."""
    import rpa
    if not actions:
        return "Aucune action fournie."
    if isinstance(actions, dict):
        actions = [actions]
    ids = rpa.RpaQueue.push_multiple(actions)
    return (f"{len(ids)} action(s) envoyee(s) a l'agent local. "
            "L'utilisateur doit donner son consentement sur sa machine pour qu'elles s'executent.")


def outil_lister_routines(**kw) -> str:
    import rpa
    recs = rpa.list_recordings()
    if not recs:
        return "Aucune routine apprise pour le moment."
    return nettoyer("Routines apprises:\n" + "\n".join(
        f"- {r.get('id')} | {r.get('name')} | {r.get('steps')} etapes" for r in recs[:20]))


def outil_rejouer_routine(routine_id: str = "", **kw) -> str:
    import rpa
    ids = rpa.replay_recording(routine_id)
    if ids is None:
        return f"Routine introuvable : {routine_id}."
    return f"Routine '{routine_id}' envoyee a l'agent local ({len(ids)} actions, consentement requis)."


def outil_ouvrir_url(url: str = "", **kw) -> str:
    """Ouvre une page web dans le navigateur de l'utilisateur (via l'agent local, consentement requis)."""
    import rpa
    url = (url or "").strip()
    if not url:
        return "Aucune URL fournie."
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    rpa.RpaQueue.push({"action": "open_url", "url": url})
    return f"Demande d'ouverture de {url} envoyee a l'agent local (consentement requis cote utilisateur)."


# nom outil -> (fonction, description courte pour le prompt)
OUTILS: dict[str, tuple[Callable, str]] = {
    "discerner":         (outil_discerner,         "Analyse une intention (valeur/faisabilite/clarte). params: {intention}"),
    "conseiller":        (outil_conseiller,        "Cadrage + conformite RGPD d'un besoin. params: {intention}"),
    "creer_application": (outil_creer_application, 'Cree une app/SaaS/gadget de A a Z (delegation + sandbox). params: {intention, persistance?, reseau?, domaines?}. Si l\'app a besoin d\'internet, mets reseau:true ET domaines:["api.exemple.com"] (liste blanche OBLIGATOIRE, sinon tout acces reseau est refuse).'),
    "lister_creations":  (outil_lister_creations,  "Liste les creations existantes. params: {}"),
    "genealogie":        (outil_genealogie,        "Lignee/generations d'une creation. params: {produit_id}"),
    "controler_ecran":   (outil_controler_ecran,   "Pilote souris/clavier via l'agent local (consentement requis). params: {actions:[{action,x,y,text,...}]}"),
    "lister_routines":   (outil_lister_routines,   "Liste les routines apprises par imitation. params: {}"),
    "rejouer_routine":   (outil_rejouer_routine,   "Rejoue une routine apprise. params: {routine_id}"),
    "ouvrir_url":        (outil_ouvrir_url,        "Ouvre une page web dans le navigateur de l'utilisateur (consentement requis). params: {url}"),
}


# ---------------------------------------------------------------------------
# PROFILS d'agents : role + outils autorises + tier. Le Cerveau a en plus
# l'outil special "deleguer" (gere dans la boucle, pas dans OUTILS).
# ---------------------------------------------------------------------------
PROFILS: dict[str, dict] = {
    "cerveau": {
        "titre": "Le Cerveau",
        "tier": "fort",
        "delegue": True,
        "outils": ["lister_creations", "genealogie", "conseiller", "controler_ecran",
                   "lister_routines", "rejouer_routine", "ouvrir_url"],
        "role": (
            "Tu es LE CERVEAU de NEOGEN, l'agent superieur. Tu comprends la demande de Jordan, "
            "tu reponds POUR lui, et tu COORDONNES les agents specialises. Pour toute tache concrete "
            "de creation, de gestion des creations, ou d'assistance quotidienne, tu DELEGUES a l'agent "
            "adapte via l'outil 'deleguer' (agents: createur, genealogiste, secretaire). Tu synthetises "
            "les resultats en une reponse claire. Tu vises l'efficacite et le resultat concret."
        ),
    },
    "createur": {
        "titre": "Le Forgeron",
        "tier": "fort",
        "delegue": False,
        "outils": ["discerner", "conseiller", "creer_application", "controler_ecran", "ouvrir_url"],
        "role": (
            "Tu es LE FORGERON de NEOGEN. Tu transformes une intention en application, logiciel, SaaS "
            "ou gadget PRET A L'EMPLOI. Tu utilises 'discerner' pour cadrer si besoin, puis "
            "'creer_application' qui decompose le projet en organes, delegue a des sous-agents et "
            "assemble le tout sous gouvernance (sandbox). Tu vises le produit fonctionnel le plus "
            "efficace, le plus directement utilisable."
        ),
    },
    "genealogiste": {
        "titre": "Le Genealogiste",
        "tier": "moyen",
        "delegue": False,
        "outils": ["lister_creations", "genealogie"],
        "role": (
            "Tu es LE GENEALOGISTE de NEOGEN. Tu geres et classifies les creations, tu expliques la "
            "genetique : lignees, generations, ce que chaque generation apporte. Tu aides Jordan a "
            "comprendre et organiser son catalogue de creations."
        ),
    },
    "secretaire": {
        "titre": "Le Secretaire",
        "tier": "moyen",
        "delegue": False,
        "outils": ["conseiller", "controler_ecran", "lister_routines", "rejouer_routine", "ouvrir_url"],
        "role": (
            "Tu es LE SECRETAIRE-CONSEILLER de NEOGEN. Tu aides Jordan au quotidien : conseil, "
            "administration, organisation, navigation web et dans l'application. Tu peux prendre le "
            "controle de l'ecran (avec consentement) et rejouer des routines apprises pour automatiser "
            "les taches repetitives."
        ),
    },
}

# Le Cerveau peut deleguer a ces agents.
_DELEGABLES = ("createur", "genealogiste", "secretaire")

MAX_ETAPES = 8


def _systeme(role: str, profil: dict) -> str:
    """Construit le prompt systeme : role + protocole + liste d'outils autorises."""
    outils = list(profil.get("outils", []))
    desc = "\n".join(f"  - {n} : {OUTILS[n][1]}" for n in outils if n in OUTILS)
    if profil.get("delegue"):
        desc += ("\n  - deleguer : confie une mission a un agent specialise. "
                 'arguments JSON {"agent": "createur|genealogiste|secretaire", "mission": "..."}.')
    return nettoyer(
        f"{role}\n\n"
        "FONCTIONNEMENT : a chaque tour tu produis un objet JSON {pensee, outil, arguments, reponse}.\n"
        "- Pour AGIR : 'outil' = un nom EXACT ci-dessous, 'arguments' = une CHAINE de texte JSON contenant "
        "les parametres de l'outil, 'reponse' = null.\n"
        '  Exemple : outil = deleguer, arguments = {"agent": "createur", "mission": "creer un gadget meteo"}\n'
        "- Pour REPONDRE : 'outil' = null, 'reponse' = ta reponse finale a l'utilisateur.\n"
        "- 'arguments' contient TOUJOURS les parametres de l'outil (jamais ailleurs). Chaine vide si l'outil n'en a pas.\n"
        "- 'pensee' est toujours rempli (court), visible par l'utilisateur.\n"
        "- N'invente jamais un outil hors de cette liste. Si aucun outil n'est utile, reponds directement.\n\n"
        "OUTILS DISPONIBLES :\n" + desc
    )


def dialoguer(role: str, message: str, historique: list[dict] | None = None,
              ctx=None, emit: Callable[[dict], None] | None = None,
              _client=None, _profondeur: int = 0) -> str:
    """
    Fait avancer un agent jusqu'a une reponse. Retourne la reponse finale (str).
    - role : cle de PROFILS (cerveau/createur/genealogiste/secretaire)
    - message : message courant de l'utilisateur
    - historique : [{role:'user'|'assistant', content:str}] des tours precedents
    - ctx : LLMContext (provider/cle actifs) ou None (anthropic par defaut)
    - emit : callback(evt:dict) pour streamer pensee/action/observation (SSE)
    - _client : injecte pour les tests (sinon resolu via gateway)
    """
    profil = PROFILS.get(role)
    if profil is None:
        raise ValueError(f"agent inconnu : {role}")

    def _emit(evt):
        if emit:
            emit(evt)

    systeme = _systeme(profil["role"], profil)
    messages: list[dict] = list(historique or [])
    messages.append({"role": "user", "content": message})

    cl = _client or gateway.client(ctx, tier=profil.get("tier", "fort"))

    for _ in range(MAX_ETAPES):
        res = cl.messages.parse(
            output_format=AgentStep, system=systeme,
            messages=messages, max_tokens=4000,
        )
        step: AgentStep = res.parsed_output
        _emit({"type": "pensee", "agent": role, "texte": nettoyer(step.pensee or "")})

        # Fin : reponse finale.
        if not step.outil:
            reponse = nettoyer(step.reponse or step.pensee or "")
            _emit({"type": "reponse", "agent": role, "texte": reponse})
            return reponse

        outil = step.outil.strip()
        params = _parse_args(step.arguments)

        def _replay(o):
            messages.append({"role": "assistant",
                             "content": json.dumps({"outil": o, "arguments": step.arguments}, ensure_ascii=False)})

        # Delegation (Cerveau uniquement).
        if outil == "deleguer" and profil.get("delegue"):
            cible = str(params.get("agent", "")).strip().lower()
            mission = str(params.get("mission", "")).strip()
            if cible not in _DELEGABLES:
                obs = f"Agent '{cible}' inconnu. Choisis parmi: {', '.join(_DELEGABLES)}."
            elif not mission:
                obs = "Mission vide : precise la mission dans arguments JSON {\"agent\":..., \"mission\":...}."
            elif _profondeur >= 2:
                obs = "Profondeur de delegation maximale atteinte."
            else:
                _emit({"type": "delegation", "de": role, "vers": cible, "mission": nettoyer(mission)})
                obs = dialoguer(cible, mission, ctx=ctx, emit=emit,
                                _client=_client, _profondeur=_profondeur + 1)
            _replay("deleguer")
            messages.append({"role": "user", "content": f"[Resultat delegation a {cible}] {obs}"})
            continue

        # Outil interdit pour ce profil.
        if outil not in profil.get("outils", []) or outil not in OUTILS:
            obs = f"Outil '{outil}' non autorise pour cet agent. Outils: {', '.join(profil.get('outils', []))}."
            _emit({"type": "observation", "agent": role, "outil": outil, "texte": obs})
            messages.append({"role": "user", "content": f"[Erreur outil] {obs}"})
            continue

        _emit({"type": "action", "agent": role, "outil": outil, "parametres": params})
        fn = OUTILS[outil][0]
        try:
            obs = fn(_ctx=ctx, _emit=emit, **params)
        except Exception as e:
            obs = nettoyer(f"Erreur outil {outil} : {e}")
        obs = nettoyer(str(obs))[:2000]
        _emit({"type": "observation", "agent": role, "outil": outil, "texte": obs})
        _replay(outil)
        messages.append({"role": "user", "content": f"[Resultat {outil}] {obs}"})

    # Securite : trop d'etapes.
    msg = "J'ai atteint la limite d'etapes. Reformule ou precise ta demande."
    _emit({"type": "reponse", "agent": role, "texte": msg})
    return msg


# ---------------------------------------------------------------------------
# Auto-verification hors-ligne : coherence profils/outils + boucle ReAct avec
# un client factice (aucun appel reseau).
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 64)
    print("NEOGEN - AGENT_CORE : auto-verification (sans appel reseau)")
    print("=" * 64)

    # 1) Tout outil cite dans un profil existe (sauf 'deleguer', gere a part).
    for nom, p in PROFILS.items():
        for o in p["outils"]:
            assert o in OUTILS, f"profil {nom}: outil inconnu {o}"
    print(f"  {len(PROFILS)} profils, {len(OUTILS)} outils : coherence OK")

    # 2) Boucle ReAct avec client factice : createur appelle un outil puis repond.
    class _FakeMsgs:
        def __init__(self, steps): self._steps = steps; self.i = 0
        def parse(self, **kw):
            s = self._steps[self.i]; self.i += 1
            class R: parsed_output = s
            return R()
    class _FakeClient:
        def __init__(self, steps): self.messages = _FakeMsgs(steps)

    # Stub un outil leger pour ne rien importer de lourd.
    OUTILS["lister_creations"] = (lambda **kw: "2 creations : alpha, beta", OUTILS["lister_creations"][1])

    scenario = [
        AgentStep(pensee="Je liste les creations.", outil="lister_creations", arguments=""),
        AgentStep(pensee="Voici le resultat.", reponse="Tu as 2 creations : alpha et beta."),
    ]
    evts = []
    rep = dialoguer("genealogiste", "liste mes creations",
                    emit=evts.append, _client=_FakeClient(scenario))
    assert "alpha" in rep, rep
    types = [e["type"] for e in evts]
    assert "action" in types and "observation" in types and "reponse" in types, types
    print("  boucle ReAct (action -> observation -> reponse) OK")

    # 3) Delegation : cerveau -> genealogiste.
    scen_cerveau = [
        AgentStep(pensee="Je delegue au genealogiste.", outil="deleguer",
                  arguments='{"agent": "genealogiste", "mission": "liste les creations"}'),
        AgentStep(pensee="Synthese.", reponse="Le genealogiste rapporte : alpha, beta."),
    ]
    scen_sous = [
        AgentStep(pensee="Je liste.", outil="lister_creations", arguments=""),
        AgentStep(pensee="Fini.", reponse="alpha, beta."),
    ]
    class _FakeRouter:
        """Renvoie un client different selon l'agent (via compteur d'appels parse)."""
        def __init__(self): self.c = _FakeClient(scen_cerveau); self.s = _FakeClient(scen_sous)
    # Pour ce test simple, on enchaine : le _client du cerveau et du sous-agent
    # doit differer. On passe un client qui sert d'abord le cerveau puis le sous-agent.
    combined = _FakeClient(scen_cerveau[:1] + scen_sous + scen_cerveau[1:])
    evts2 = []
    rep2 = dialoguer("cerveau", "occupe-toi de mes creations",
                     emit=evts2.append, _client=combined)
    assert any(e["type"] == "delegation" for e in evts2), [e["type"] for e in evts2]
    print("  delegation cerveau -> sous-agent OK")

    print("=" * 64)
    print("  TOUT VERT.")
    print("=" * 64)
