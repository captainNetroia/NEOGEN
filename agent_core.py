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

Outils extraits dans outils.py (dette F010).

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-21.
"""

from __future__ import annotations

import json
from typing import Callable
from pydantic import BaseModel, Field

import gateway
from sanitizer import nettoyer
from outils import OUTILS  # boîte à outils extraite (dette F010)


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
# PROFILS d'agents : role + outils autorises + tier. Le Cerveau a en plus
# l'outil special "deleguer" (gere dans la boucle, pas dans OUTILS).
# ---------------------------------------------------------------------------
PROFILS: dict[str, dict] = {
    "cerveau": {
        "titre": "Le Cerveau",
        "tier": "fort",
        "delegue": True,
        "outils": ["lister_creations", "genealogie", "conseiller", "controler_ecran",
                   "lister_routines", "rejouer_routine", "ouvrir_url", "fermer_onglet", "regarder_ecran",
                   "creer_skill", "lister_skills", "utiliser_skill", "memoriser", "rappeler",
                   "lire_fichier", "creer_rapport"],
        "role": (
            "Tu es LE CERVEAU de NEOGEN, l'agent superieur. Tu comprends la demande de Jordan, "
            "tu reponds POUR lui, et tu COORDONNES les agents specialises. Pour toute tache concrete "
            "de creation, de gestion des creations, ou d'assistance quotidienne, tu DELEGUES a l'agent "
            "adapte via l'outil 'deleguer' (agents: createur, genealogiste, secretaire). Tu synthetises "
            "les resultats en une reponse claire. Tu vises l'efficacite et le resultat concret.\n"
            "REGLE SKILLS — 4 etapes obligatoires :\n"
            "1. AVANT toute tache concrete (resumer, analyser, rediger, extraire, automatiser, "
            "remplir, comparer, classifier, traduire, generer, planifier...) : verifie si un skill "
            "correspond via lister_skills, puis invoque utiliser_skill. Tu juges seul — tu n'attends "
            "PAS la demande de l'utilisateur.\n"
            "2. APRES avoir livre le resultat : DEMANDE a l'utilisateur 'Ce resultat vous convient-il ?'\n"
            "3. Si non satisfait → propose : (A) adapter le skill existant (creer_skill meme nom), "
            "ou (B) creer un nouveau skill personnalise ensemble.\n"
            "4. Apres adaptation/creation → JUGE la valeur generique : si le skill est utile a TOUS "
            "les utilisateurs NEOGEN (pas seulement a Jordan), signale qu'il peut enrichir le registre "
            "communautaire et le systeme NEOGEN lui-meme — c'est ainsi que l'application devient plus "
            "efficace pour tout le monde.\n"
            "Si aucun skill ne correspond au depart : accomplis la tache, puis propose de cristalliser "
            "via creer_skill."
        ),
    },
    "createur": {
        "titre": "Le Forgeron",
        "tier": "fort",
        "delegue": False,
        "outils": ["discerner", "conseiller", "creer_application", "controler_ecran", "ouvrir_url", "fermer_onglet"],
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
        "outils": ["conseiller", "controler_ecran", "lister_routines", "rejouer_routine", "ouvrir_url", "fermer_onglet", "regarder_ecran", "memoriser", "rappeler", "lire_fichier", "creer_rapport", "creer_skill", "lister_skills", "utiliser_skill"],
        "role": (
            "Tu es LE SECRETAIRE-CONSEILLER de NEOGEN. Tu aides Jordan au quotidien : conseil, "
            "administration, organisation, navigation web et dans l'application. Tu peux prendre le "
            "controle de l'ecran (avec consentement) et rejouer des routines apprises pour automatiser "
            "les taches repetitives.\n"
            "REGLES DE LUCIDITE (importantes) :\n"
            "- Avant de cliquer ou remplir quoi que ce soit, utilise 'regarder_ecran' pour VOIR "
            "reellement l'ecran : tu sauras ou sont les champs/boutons (coordonnees) au lieu de deviner.\n"
            "- N'invente JAMAIS une URL. Si tu n'es pas certain de l'adresse exacte d'un site, "
            "dis-le et propose de chercher, plutot que d'ouvrir une URL approximative.\n"
            "- Ne promets que ce que tes outils permettent reellement. Pour remplir un formulaire : "
            "d'abord 'regarder_ecran', puis cliquer le champ (controler_ecran), puis taper le texte. "
            "Si tu n'as pas l'info necessaire, demande-la avant d'agir.\n"
            "REGLE SKILLS — 4 etapes obligatoires :\n"
            "1. AVANT toute tache concrete : verifie si un skill correspond, puis invoque utiliser_skill.\n"
            "2. APRES le resultat : demande si l'utilisateur est satisfait.\n"
            "3. Si non → propose d'adapter le skill ou d'en creer un nouveau ensemble.\n"
            "4. Apres adaptation/creation → juge la valeur generique : si utile a tous → signale "
            "qu'il peut enrichir le registre communautaire et le systeme NEOGEN."
        ),
    },
}

# Le Cerveau peut deleguer a ces agents.
_DELEGABLES = ("createur", "genealogiste", "secretaire")

# Agents du NOYAU : jamais ecrases par un bebe-agent custom (evolution gouvernee).
_PROFILS_NOYAU = frozenset(PROFILS.keys())


def rafraichir_profils() -> int:
    """Fusionne les bebe-agents custom (crees par evolution_gouvernee, data-driven) dans
    PROFILS. Idempotent. Les agents du noyau ne sont JAMAIS ecrases ; delegue force a
    False (anti-escalade : un bebe-agent ne peut pas orchestrer le Cerveau)."""
    try:
        import evolution_gouvernee
        customs = evolution_gouvernee.profils_custom()
    except Exception:
        return 0
    n = 0
    for cle, prof in (customs or {}).items():
        if cle in _PROFILS_NOYAU or not isinstance(prof, dict):
            continue
        p = dict(prof)
        p["delegue"] = False
        PROFILS[cle] = p
        n += 1
    return n


# Charge les bebe-agents custom au demarrage du module (best-effort, jamais bloquant).
try:
    rafraichir_profils()
except Exception:
    pass

MAX_ETAPES = 8

# Outils "significatifs" : une trajectoire qui en enchaîne >=2 distincts et REUSSIT
# constitue une procédure reproductible -> cristallisée automatiquement (par contexte).
# On exclut l'introspection (lister_*, rappeler) et les méta-outils de skill (anti-bruit/récursion).
_OUTILS_PROCEDURE = {
    "creer_application", "controler_ecran", "ouvrir_url", "regarder_ecran",
    "fermer_onglet", "rejouer_routine", "conseiller", "discerner", "memoriser",
}


def _cristalliser_trajectoire(role: str, message: str, outils_reussis: list[str]) -> None:
    """Cristallise AUTOMATIQUEMENT une procédure si la trajectoire le justifie (par contexte).
    Idempotent : une même séquence d'outils ne crée qu'une compétence. Déterministe (zéro coût LLM)."""
    distincts = [o for i, o in enumerate(outils_reussis) if o not in outils_reussis[:i]]
    pertinents = [o for o in distincts if o in _OUTILS_PROCEDURE]
    if len(pertinents) < 2:
        return
    try:
        import competences
        sequence = " -> ".join(o for o in outils_reussis if o in _OUTILS_PROCEDURE)
        sig = "traj:" + "+".join(sorted(pertinents))
        mots = " ".join((message or "").split()[:5])[:40] or "procedure"
        competences.cristalliser_auto(
            nom=f"proc {mots}",
            description=f"Procédure réussie ({role}) : {', '.join(pertinents)}.",
            instructions=(f"Pour une demande du type \"{(message or '')[:120]}\", enchaîne ces outils "
                          f"dans cet ordre : {sequence}. Vérifie le résultat de chaque étape avant la suivante."),
            outils=pertinents,
            signature=sig,
        )
    except Exception:
        pass


# Bornes anti-derive du contexte envoye au modele (perf + cout) :
MAX_TOURS_HIST = 8        # derniers messages de l'historique conserves
MAX_LONGUEUR_MSG = 4000   # caracteres max par message (les vieux gros messages sont coupes)
MAX_MESSAGES_BOUCLE = 24  # taille max de la liste messages pendant la boucle ReAct


def _tronquer_historique(hist: list[dict] | None) -> list[dict]:
    """Garde les derniers tours et borne la taille de chaque message."""
    if not hist:
        return []
    recent = hist[-MAX_TOURS_HIST:]
    out = []
    for m in recent:
        if not isinstance(m, dict):
            continue
        contenu = m.get("content", "")
        if isinstance(contenu, str) and len(contenu) > MAX_LONGUEUR_MSG:
            contenu = contenu[:MAX_LONGUEUR_MSG] + " […tronque]"
        out.append({"role": m.get("role", "user"), "content": contenu})
    return out


def _savoir_pertinent(requete: str, k: int = 3) -> str:
    """Interroge le Hub du savoir et renvoie un bloc 'SAVOIR PERTINENT' a injecter.
    Tolerant : ne leve jamais (le Hub peut etre vide ou indisponible)."""
    if not requete or not requete.strip():
        return ""
    try:
        import savoir
        resultats = savoir.HUB.chercher(requete, k=k)
    except Exception:
        return ""
    if not resultats:
        return ""
    lignes = []
    for r in resultats:
        g = r.get("grain", {})
        contenu = (g.get("contenu", "") or "").strip()
        if not contenu:
            continue
        lignes.append(f"  - [{g.get('domaine', '?')}] {contenu[:200]}")
    if not lignes:
        return ""
    return ("\n\nSAVOIR PERTINENT (tire de l'experience accumulee de NEOGEN, "
            "utilise-le si c'est utile pour cette demande) :\n" + "\n".join(lignes))


def _systeme(role: str, profil: dict, eco: bool = False, requete: str = "") -> str:
    """Construit le prompt systeme : role + protocole + liste d'outils autorises."""
    outils = list(profil.get("outils", []))
    desc = "\n".join(f"  - {n} : {OUTILS[n][1]}" for n in outils if n in OUTILS)
    if profil.get("delegue"):
        desc += ("\n  - deleguer : confie une mission a un agent specialise. "
                 'arguments JSON {"agent": "createur|genealogiste|secretaire", "mission": "..."}.')
    skills_bloc = ""
    try:
        import competences
        skills_bloc = competences.resume_pour_prompt()
    except Exception:
        skills_bloc = ""
    memoire_bloc = ""
    try:
        import memoire_agent
        memoire_bloc = memoire_agent.resume_pour_prompt()
    except Exception:
        memoire_bloc = ""
    savoir_bloc = _savoir_pertinent(requete, k=3)
    design_bloc = ""
    try:
        import design
        design_bloc = design.bloc_pour_prompt("agent")
    except Exception:
        design_bloc = ""
    directives_bloc = _directives_actives()
    return nettoyer(
        f"{role}\n\n"
        "FONCTIONNEMENT : tu reponds TOUJOURS et UNIQUEMENT par UN SEUL objet JSON, sans aucun texte "
        "autour, sans balises de code. L'objet a exactement ces 4 cles : pensee, outil, arguments, reponse.\n"
        '- Pour REPONDRE a l\'utilisateur : {"pensee": "courte", "outil": null, "arguments": "", "reponse": "ta reponse"}\n'
        '- Pour APPELER un outil : {"pensee": "courte", "outil": "nom_exact", "arguments": "{\\"cle\\": \\"valeur\\"}", "reponse": null}\n'
        '  Exemple concret : {"pensee": "Je liste les creations.", "outil": "lister_creations", "arguments": "", "reponse": null}\n'
        "- 'arguments' est TOUJOURS une chaine de texte JSON (vide si l'outil n'a pas de parametre). "
        "Ne mets jamais les parametres ailleurs.\n"
        "- N'invente jamais un outil hors de la liste. Si aucun outil n'est utile, reponds directement.\n\n"
        + ("MODE ECONOMIE : sois DIRECT et CONCIS. Va droit au but, pas de preambule ni de "
           "redondance, pas de reformulation de la question. Reponse la plus courte qui repond "
           "vraiment. N'appelle un outil que s'il est indispensable.\n\n" if eco else "")
        + "OUTILS DISPONIBLES :\n" + desc + skills_bloc + memoire_bloc + savoir_bloc
        + design_bloc + directives_bloc
    )


def _directives_actives() -> str:
    """Le TRADUCTEUR comportemental : injecte les regles / lois / idees validees (evolution
    gouvernee) dans le prompt systeme. C'est ce qui rend une idee 'donnee-vie' de nature
    comportementale REELLEMENT active sur le comportement des agents, au lieu de rester une
    note morte dans un JSON que personne ne lit. Tolerant : ne leve jamais."""
    try:
        import evolution_gouvernee
        store = evolution_gouvernee.regles_actives()
    except Exception:
        return ""
    lignes = []
    for cle, val in (store.get("regles") or {}).items():
        if isinstance(val, str):
            lignes.append(f"- {cle.replace('_', ' ')} : {val[:160]}")
        elif isinstance(val, dict):
            intention = val.get("action") or val.get("texte") or val.get("nom") or cle
            lignes.append(f"- {cle.replace('_', ' ')} : {str(intention)[:160]}")
    for loi in (store.get("lois") or []):
        lignes.append(f"- (loi a respecter) {str(loi)[:160]}")
    for idee in (store.get("idees") or []):
        lignes.append(f"- (intention directrice) {str(idee)[:160]}")
    if not lignes:
        return ""
    return ("\n\nDIRECTIVES ACTIVES (regles et intentions que ton createur a validees ; "
            "respecte-les dans ton comportement et tes reponses) :\n" + "\n".join(lignes[:25]))


def _texte_de(res) -> str:
    """Extrait le texte d'un resultat .create (blocs Anthropic ou _CreateResult gateway)."""
    c = getattr(res, "content", None)
    if isinstance(c, list):
        out = []
        for b in c:
            out.append(b.get("text", "") if isinstance(b, dict) else (getattr(b, "text", "") or ""))
        return "".join(out)
    return str(c or "")


def _extraire_json(txt: str):
    """Recupere le premier objet JSON d'un texte (tolerant : fences, prefixes)."""
    s = (txt or "").strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s[:4].lower() == "json":
            s = s[4:]
        s = s.strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    import re
    m = re.search(r"\{.*\}", s, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


_STEP_MARQUEURS = ('"outil"', '"pensee"', '"arguments"')


def _est_step_brut(s: str) -> bool:
    """Vrai si le texte ressemble a un JSON de step agent plutot qu'une reponse lisible."""
    stripped = s.strip()
    return stripped.startswith("{") and sum(1 for k in _STEP_MARQUEURS if k in stripped) >= 2


_MSG_STEP_BRUT = "Je n'ai pas pu formuler une reponse structuree. Reformule ta demande."


def _parse_step(txt: str) -> AgentStep:
    """Parse TOLERANT d'un AgentStep (robuste face aux petits modeles Ollama)."""
    obj = _extraire_json(txt)
    if not isinstance(obj, dict):
        s = (txt or "").strip()
        if _est_step_brut(s):
            return AgentStep(pensee="", reponse=_MSG_STEP_BRUT)
        return AgentStep(pensee="", reponse=s or "...")
    if "pensee" not in obj and isinstance(obj.get("properties"), dict):
        inner = obj["properties"]
        obj = {k: (v.get("default") if isinstance(v, dict) and "default" in v else v)
               for k, v in inner.items()}
    pensee = obj.get("pensee")
    outil = obj.get("outil")
    arguments = obj.get("arguments")
    reponse = obj.get("reponse")
    if isinstance(arguments, dict):
        arguments = json.dumps(arguments, ensure_ascii=False)
    arguments = arguments if isinstance(arguments, str) else ""
    pensee = pensee if isinstance(pensee, str) else ""
    outil = outil.strip() if isinstance(outil, str) and outil.strip() else None
    reponse = reponse if isinstance(reponse, str) and reponse.strip() else None
    if not outil and not reponse and not pensee:
        s = (txt or "").strip()
        if _est_step_brut(s):
            return AgentStep(pensee="", reponse=_MSG_STEP_BRUT)
        return AgentStep(pensee="", reponse=s or "...")
    return AgentStep(pensee=pensee, outil=outil, arguments=arguments, reponse=reponse)


def dialoguer(role: str, message: str, historique: list[dict] | None = None,
              ctx=None, emit: Callable[[dict], None] | None = None,
              _client=None, _profondeur: int = 0, eco: bool = False, user=None) -> str:
    """
    Fait avancer un agent jusqu'a une reponse. Retourne la reponse finale (str).
    - role : cle de PROFILS (cerveau/createur/genealogiste/secretaire)
    - message : message courant de l'utilisateur
    - historique : [{role:'user'|'assistant', content:str}] des tours precedents
    - ctx : LLMContext (provider/cle actifs) ou None (anthropic par defaut)
    - emit : callback(evt:dict) pour streamer pensee/action/observation (SSE)
    - _client : injecte pour les tests (sinon resolu via gateway)
    - eco : mode economie -> le tier (modele) est choisi selon la demande (moins de tokens)
    """
    profil = PROFILS.get(role)
    if profil is None:
        raise ValueError(f"agent inconnu : {role}")

    def _emit(evt):
        if emit:
            emit(evt)

    systeme = _systeme(profil["role"], profil, eco=eco, requete=message)
    messages: list[dict] = _tronquer_historique(historique)
    messages.append({"role": "user", "content": message})

    _premium = bool(user and user.get("premium"))
    _max_prof = 2 if _premium else 1

    tier = profil.get("tier", "fort")
    _bandit_cat = None
    if eco:
        reco = gateway.recommander_tier(message)
        tier = reco["tier"]
        _bandit_cat = reco.get("categorie")
        _emit({"type": "eco", "tier": tier, "raison": reco["raison"]})

    cl = _client or gateway.client(ctx, tier=tier)

    def _maj_bandit(succes: bool):
        if _profondeur == 0 and eco and _bandit_cat:
            try:
                import routeur_bandit
                routeur_bandit.recompenser(_bandit_cat, tier, succes)
            except Exception:
                pass

    _outils_reussis: list[str] = []

    for _ in range(MAX_ETAPES):
        if len(messages) > MAX_MESSAGES_BOUCLE:
            messages = messages[:1] + messages[-(MAX_MESSAGES_BOUCLE - 1):]
        try:
            res = cl.messages.create(system=systeme, messages=messages, max_tokens=4000)
            step = _parse_step(_texte_de(res))
        except Exception as e:
            msg = nettoyer(f"Le modele n'a pas pu repondre : {e}")
            _emit({"type": "erreur", "message": msg})
            _maj_bandit(succes=False)
            return msg
        if step.pensee:
            _emit({"type": "pensee", "agent": role, "texte": nettoyer(step.pensee)})

        if not step.outil:
            reponse = nettoyer(step.reponse or step.pensee or "")
            _emit({"type": "reponse", "agent": role, "texte": reponse})
            if _profondeur == 0 and _outils_reussis:
                _cristalliser_trajectoire(role, message, _outils_reussis)
            _maj_bandit(succes=bool(reponse))
            return reponse

        outil = step.outil.strip()
        params = _parse_args(step.arguments)

        def _replay(o):
            messages.append({"role": "assistant",
                             "content": json.dumps({"outil": o, "arguments": step.arguments}, ensure_ascii=False)})

        if outil == "deleguer" and profil.get("delegue"):
            cible = str(params.get("agent", "")).strip().lower()
            mission = str(params.get("mission", "")).strip()
            if cible not in _DELEGABLES:
                obs = f"Agent '{cible}' inconnu. Choisis parmi: {', '.join(_DELEGABLES)}."
            elif not mission:
                obs = "Mission vide : precise la mission dans arguments JSON {\"agent\":..., \"mission\":...}."
            elif _profondeur >= _max_prof:
                obs = ("Delegation en cascade reservee au premium. " if not _premium
                       else "Profondeur de delegation maximale atteinte.")
            else:
                reco_del = gateway.recommander_tier(mission)
                tier_del = reco_del["tier"]
                _prov_del = (ctx.provider if ctx else None) or "anthropic"
                _model_del = gateway.TIERS.get(_prov_del, gateway.TIERS["anthropic"]).get(tier_del)
                ctx_adapte = gateway.LLMContext(
                    provider=_prov_del,
                    model=_model_del,
                    api_key=ctx.api_key if ctx else None,
                    base_url=ctx.base_url if ctx else None,
                )
                _emit({"type": "delegation", "de": role, "vers": cible,
                       "mission": nettoyer(mission), "tier": tier_del, "modele": _model_del or ""})
                obs = dialoguer(cible, mission, ctx=ctx_adapte, emit=emit,
                                _client=_client, _profondeur=_profondeur + 1, eco=eco, user=user)
            _replay("deleguer")
            messages.append({"role": "user", "content": f"[Resultat delegation a {cible}] {obs}"})
            continue

        if outil not in profil.get("outils", []) or outil not in OUTILS:
            obs = f"Outil '{outil}' non autorise pour cet agent. Outils: {', '.join(profil.get('outils', []))}."
            _emit({"type": "observation", "agent": role, "outil": outil, "texte": obs})
            messages.append({"role": "user", "content": f"[Erreur outil] {obs}"})
            continue

        _emit({"type": "action", "agent": role, "outil": outil, "parametres": params})
        fn = OUTILS[outil][0]
        try:
            obs = fn(_ctx=ctx, _emit=emit, _user=user, **params)
        except Exception as e:
            obs = nettoyer(f"Erreur outil {outil} : {e}")
        obs = nettoyer(str(obs))[:2000]
        if not obs.lower().startswith(("erreur", "[erreur", "limite atteinte", "aucun", "l'agent local n'est pas")):
            _outils_reussis.append(outil)
        _emit({"type": "observation", "agent": role, "outil": outil, "texte": obs})
        _replay(outil)
        messages.append({"role": "user", "content": f"[Resultat {outil}] {obs}"})

    msg = "J'ai atteint la limite d'etapes. Reformule ou precise ta demande."
    _emit({"type": "reponse", "agent": role, "texte": msg})
    _maj_bandit(succes=False)
    return msg


# ---------------------------------------------------------------------------
# Auto-verification hors-ligne
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 64)
    print("NEOGEN - AGENT_CORE : auto-verification (sans appel reseau)")
    print("=" * 64)

    for nom, p in PROFILS.items():
        for o in p["outils"]:
            assert o in OUTILS, f"profil {nom}: outil inconnu {o}"
    print(f"  {len(PROFILS)} profils, {len(OUTILS)} outils : coherence OK")

    def _as_text(step):
        return json.dumps({"pensee": step.pensee, "outil": step.outil,
                           "arguments": step.arguments, "reponse": step.reponse}, ensure_ascii=False)
    class _FakeMsgs:
        def __init__(self, steps): self._steps = steps; self.i = 0
        def create(self, **kw):
            s = self._steps[self.i]; self.i += 1
            class R: content = [{"text": _as_text(s)}]
            return R()
    class _FakeClient:
        def __init__(self, steps): self.messages = _FakeMsgs(steps)

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

    scen_cerveau = [
        AgentStep(pensee="Je delegue au genealogiste.", outil="deleguer",
                  arguments='{"agent": "genealogiste", "mission": "liste les creations"}'),
        AgentStep(pensee="Synthese.", reponse="Le genealogiste rapporte : alpha, beta."),
    ]
    scen_sous = [
        AgentStep(pensee="Je liste.", outil="lister_creations", arguments=""),
        AgentStep(pensee="Fini.", reponse="alpha, beta."),
    ]
    combined = _FakeClient(scen_cerveau[:1] + scen_sous + scen_cerveau[1:])
    evts2 = []
    rep2 = dialoguer("cerveau", "occupe-toi de mes creations",
                     emit=evts2.append, _client=combined)
    assert any(e["type"] == "delegation" for e in evts2), [e["type"] for e in evts2]
    print("  delegation cerveau -> sous-agent OK")

    print("=" * 64)
    print("  TOUT VERT.")
    print("=" * 64)
