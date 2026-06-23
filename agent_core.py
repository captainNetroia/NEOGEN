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


def _contexte_memoire() -> str:
    """Résumé des souvenirs pour personnaliser proposer/conseiller (wiring de cohérence)."""
    try:
        import memoire_agent
        return memoire_agent.resume_pour_prompt(limite=8)
    except Exception:
        return ""


def outil_discerner(intention: str = "", **kw) -> str:
    from proposer import proposer
    cl = gateway.client(_ctx_from(kw), tier="moyen")
    p = proposer(intention, cl, contexte=_contexte_memoire())
    return nettoyer(
        f"Discernement -> valeur:{getattr(p,'valeur','?')}/10 "
        f"faisabilite:{getattr(p,'faisabilite','?')}/10 clarte:{getattr(p,'clarte','?')}/10. "
        f"Reformulation: {getattr(p,'reformulation','(n/a)')}"
    )


def outil_conseiller(intention: str = "", **kw) -> str:
    from conseillers import conseiller
    cl = gateway.client(_ctx_from(kw), tier="moyen")
    c = conseiller(intention, cl, contexte=_contexte_memoire())
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
    # Quota freemium : la création via le chat compte comme une création (cohérence
    # avec le studio). Invité (pas de _user) : non compté mais autorisé.
    _u = kw.get("_user")
    if _u:
        import quotas
        v = quotas.verifier(_u, "creations")
        if not v["autorise"]:
            return f"Limite atteinte : {v['raison']}"
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
    skill_msg = ""
    if r.succes:
        entrees = registre.lister()
        if entrees:
            produit_id = entrees[-1]["id"]
        # Quota consommé sur succès (cohérence avec le studio).
        if _u:
            try:
                import quotas
                quotas.incrementer(_u["id"], "creations")
            except Exception:
                pass
        # Wiring cohérence : une création réussie cristallise une compétence réutilisable
        # ("comment refaire ce type de produit") -> le savoir-faire s'accumule (auto,
        # idempotent : pas de doublon pour des intentions du même type).
        try:
            import competences, registre as _reg
            cap_txt = []
            if persistance:
                cap_txt.append("persistance")
            if reseau_on:
                cap_txt.append("reseau:" + ",".join(cap.domaines_autorises) if cap.domaines_autorises else "reseau")
            instructions = (
                f"Pour creer ce type de produit : utilise creer_application avec une intention "
                f"du genre \"{intention[:120]}\". Capacites typiques : {', '.join(cap_txt) or 'aucune'}. "
                f"Reference : produit {produit_id}."
            )
            # Signature = type de produit (slug d'intention) -> dédoublonnage par famille.
            sig = "creer:" + _reg._slug(intention)
            s = competences.cristalliser_auto(
                nom=f"creer {intention[:32]}",
                description=f"Refaire un produit similaire a : {intention[:80]}",
                instructions=instructions,
                outils=["creer_application"],
                signature=sig,
            )
            skill_msg = f" Competence apprise automatiquement : '{s['nom']}'." if s else ""
        except Exception:
            skill_msg = ""
    return nettoyer(
        f"Creation {'reussie' if r.succes else 'echouee'} (verdict:{r.verdict}, "
        f"tentatives:{r.tentatives}, lignes:{r.lignes}). "
        f"produit_id={produit_id}. Lecons: {'; '.join((r.lecons or [])[:3])}.{skill_msg}"
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


_MSG_AGENT_ABSENT = ("L'agent local n'est PAS lance : impossible de controler l'ecran. "
                     "Demande a l'utilisateur de lancer l'agent local (icone barre systeme, "
                     "ou double-clic sur Lancer-Agent-NEOGEN.bat) puis de reessayer.")


def _agent_pret() -> bool:
    import rpa
    return rpa.is_agent_connected()


def outil_controler_ecran(actions: Any = None, **kw) -> str:
    """Envoie des actions souris/clavier a l'agent local. Consentement requis cote hote."""
    import rpa
    if not _agent_pret():
        return _MSG_AGENT_ABSENT
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
    if not _agent_pret():
        return _MSG_AGENT_ABSENT
    ids = rpa.replay_recording(routine_id)
    if ids is None:
        return f"Routine introuvable : {routine_id}."
    return f"Routine '{routine_id}' envoyee a l'agent local ({len(ids)} actions, consentement requis)."


def outil_ouvrir_url(url: str = "", **kw) -> str:
    """Ouvre une page web dans le navigateur de l'utilisateur (via l'agent local, consentement requis)."""
    import rpa
    if not _agent_pret():
        return _MSG_AGENT_ABSENT
    url = (url or "").strip()
    if not url:
        return "Aucune URL fournie."
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    rpa.RpaQueue.push({"action": "open_url", "url": url})
    return f"Demande d'ouverture de {url} envoyee a l'agent local (consentement requis cote utilisateur)."


def outil_fermer_onglet(**kw) -> str:
    """Ferme l'onglet actif du navigateur (raccourci Ctrl+W) via l'agent local."""
    import rpa
    if not _agent_pret():
        return _MSG_AGENT_ABSENT
    rpa.RpaQueue.push({"action": "hotkey", "keys": ["ctrl", "w"], "guard": "close_tab"})
    return ("Demande de fermeture de l'onglet actif (Ctrl+W) envoyee a l'agent local. "
            "Note : si NEOGEN est l'onglet au premier plan, la fermeture sera refusee "
            "pour ne pas fermer l'application ; mets l'onglet a fermer au premier plan.")


def outil_regarder_ecran(objectif: str = "", **kw) -> str:
    """Capture l'ecran de l'utilisateur et l'ANALYSE avec un modele vision.
    Donne des yeux a l'agent : il peut lire un formulaire, reperer un bouton et ses coordonnees.
    'objectif' precise ce qu'on cherche (ex: 'trouver le champ email et le bouton connexion')."""
    import time
    import rpa
    if not _agent_pret():
        return _MSG_AGENT_ABSENT
    t0 = rpa.request_screenshot()
    # On attend que l'agent local capture et renvoie l'image (consentement requis cote hote).
    img = None
    for _ in range(24):  # ~12 s max
        time.sleep(0.5)
        img = rpa.get_screenshot(apres=t0)
        if img:
            break
    if not img:
        return ("Aucune capture recue. Verifie que l'agent local est lance et que tu as "
                "autorise l'action sur ta machine.")
    consigne = (
        "Tu es les yeux d'un agent qui pilote cet ecran. Decris ce qui est visible et, pour "
        "chaque element cliquable ou champ pertinent par rapport a l'objectif, donne sa position "
        "approximative en pixels (x,y) dans l'image. Objectif : " + (objectif or "decrire l'ecran") +
        "\nReponds de facon concise et structuree (liste : element -> (x,y))."
    )
    try:
        analyse = gateway.voir(_ctx_from(kw), img, consigne)
    except Exception as e:
        return nettoyer(f"Vision indisponible : {e}. (Le modele actif voit-il les images ? "
                        "Pour Ollama, installe un modele vision : `ollama pull llama3.2-vision`.)")
    return nettoyer("Analyse de l'ecran :\n" + str(analyse))[:2500]


# ── Méta-outils : l'agent forge ses PROPRES compétences (comme skill-creator) ──

def outil_creer_skill(nom: str = "", description: str = "", instructions: str = "",
                      outils=None, **kw) -> str:
    """Crée une compétence réutilisable (skill) qui devient invocable immédiatement."""
    import competences
    if not nom or not instructions:
        return "Pour creer un skill : fournis au moins 'nom' et 'instructions'."
    if isinstance(outils, str):
        outils = [outils]
    # On ne garde que des références d'outils existants (gouvernance).
    valides = [o for o in (outils or []) if o in OUTILS]
    s = competences.creer(nom, description, instructions, valides, auto=kw.get("_auto", False))
    return (f"Competence '{s['nom']}' creee et disponible des maintenant "
            f"(invoquable via utiliser_skill). Outils mobilises : {', '.join(s['outils']) or 'aucun'}.")


def outil_lister_skills(**kw) -> str:
    import competences
    skills = competences.lister()
    if not skills:
        return "Aucune competence apprise pour le moment. Tu peux en creer une avec creer_skill."
    return nettoyer("Competences apprises :\n" + "\n".join(
        f"- {s['nom']} : {s.get('description','')}" for s in skills[:20]))


def outil_utiliser_skill(nom: str = "", contexte: str = "", **kw) -> str:
    """Invoque une compétence apprise : récupère ses instructions et les applique."""
    import competences
    s = competences.charger(nom)
    if not s:
        return f"Competence '{nom}' introuvable. Liste-les avec lister_skills."
    # Usage tracé : pertinence + signal pour l'auto-amélioration.
    competences.enregistrer_usage(nom)
    # On renvoie les instructions à l'agent appelant : il les applique dans son raisonnement.
    txt = (f"COMPETENCE '{s['nom']}' — {s.get('description','')}\n"
           f"Instructions a appliquer maintenant :\n{s.get('instructions','')}\n")
    if s.get("outils"):
        txt += f"Outils a utiliser : {', '.join(s['outils'])}.\n"
    if contexte:
        txt += f"Contexte fourni : {contexte}"
    return nettoyer(txt)[:3000]


# ── Mémoire cross-session : l'agent se souvient d'une session à l'autre ────────

def outil_memoriser(contenu: str = "", type: str = "fait", **kw) -> str:
    """Enregistre un fait durable (sur l'utilisateur, ses preferences, ses projets)."""
    import memoire_agent
    if not contenu.strip():
        return "Rien a memoriser : fournis 'contenu'."
    s = memoire_agent.memoriser(contenu, type)
    if not s:
        return "Contenu vide apres nettoyage."
    return f"Memorise ([{s['type']}]) : {s['contenu']}"


def outil_rappeler(requete: str = "", **kw) -> str:
    """Rappelle ce que l'agent sait deja (souvenirs des sessions precedentes)."""
    import memoire_agent
    souvenirs = memoire_agent.rappeler(requete)
    if not souvenirs:
        return "Aucun souvenir pertinent."
    return nettoyer("Souvenirs :\n" + "\n".join(
        f"- [{m.get('type','fait')}] {m.get('contenu','')}" for m in souvenirs))


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
    "fermer_onglet":     (outil_fermer_onglet,     "Ferme l'onglet/la page web actif du navigateur (Ctrl+W). params: {} (aucun)"),
    "regarder_ecran":    (outil_regarder_ecran,    "REGARDE l'ecran de l'utilisateur (capture + analyse vision) pour voir avant d'agir : lire un formulaire, reperer un bouton et ses coordonnees. params: {objectif}"),
    "creer_skill":       (outil_creer_skill,       "Cree une COMPETENCE reutilisable (skill) : un savoir-faire nomme que tu pourras reinvoquer. A faire quand tu reussis une tache utile et reproductible. params: {nom, description, instructions, outils?}"),
    "lister_skills":     (outil_lister_skills,     "Liste les competences (skills) deja apprises. params: {}"),
    "utiliser_skill":    (outil_utiliser_skill,    "Invoque une competence apprise : applique son savoir-faire. params: {nom, contexte?}"),
    "memoriser":         (outil_memoriser,         "Memorise un fait DURABLE sur l'utilisateur/ses preferences/ses projets (se souvenir entre sessions). params: {contenu, type?: user|preference|projet|fait}"),
    "rappeler":          (outil_rappeler,          "Rappelle ce que tu sais deja (souvenirs des sessions precedentes). params: {requete?}"),
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
                   "lister_routines", "rejouer_routine", "ouvrir_url", "fermer_onglet", "regarder_ecran",
                   "creer_skill", "lister_skills", "utiliser_skill", "memoriser", "rappeler"],
        "role": (
            "Tu es LE CERVEAU de NEOGEN, l'agent superieur. Tu comprends la demande de Jordan, "
            "tu reponds POUR lui, et tu COORDONNES les agents specialises. Pour toute tache concrete "
            "de creation, de gestion des creations, ou d'assistance quotidienne, tu DELEGUES a l'agent "
            "adapte via l'outil 'deleguer' (agents: createur, genealogiste, secretaire). Tu synthetises "
            "les resultats en une reponse claire. Tu vises l'efficacite et le resultat concret.\n"
            "TU APPRENDS : quand tu accomplis une tache utile et reproductible (une suite d'etapes "
            "qui pourrait resservir), CRISTALLISE-la en competence via 'creer_skill' (nom court, "
            "description du 'quand l'utiliser', instructions claires). Avant d'agir, regarde si une "
            "competence existante (lister_skills) correspond deja : si oui, utilise-la (utiliser_skill). "
            "C'est ainsi que tu deviens plus puissant a chaque session."
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
        "outils": ["conseiller", "controler_ecran", "lister_routines", "rejouer_routine", "ouvrir_url", "fermer_onglet", "regarder_ecran", "memoriser", "rappeler"],
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
            "Si tu n'as pas l'info necessaire, demande-la avant d'agir."
        ),
    },
}

# Le Cerveau peut deleguer a ces agents.
_DELEGABLES = ("createur", "genealogiste", "secretaire")

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
        return  # pas une procédure : rien à cristalliser
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
    """Garde les derniers tours et borne la taille de chaque message.
    Evite d'envoyer un historique enorme (localStorage jusqu'a 40 messages) a l'API."""
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


def _systeme(role: str, profil: dict, eco: bool = False) -> str:
    """Construit le prompt systeme : role + protocole + liste d'outils autorises."""
    outils = list(profil.get("outils", []))
    desc = "\n".join(f"  - {n} : {OUTILS[n][1]}" for n in outils if n in OUTILS)
    if profil.get("delegue"):
        desc += ("\n  - deleguer : confie une mission a un agent specialise. "
                 'arguments JSON {"agent": "createur|genealogiste|secretaire", "mission": "..."}.')
    # Compétences apprises + mémoire cross-session : injectées dynamiquement.
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
        + "OUTILS DISPONIBLES :\n" + desc + skills_bloc + memoire_bloc
    )


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
    """Parse TOLERANT d'un AgentStep (robuste face aux petits modeles Ollama).
    - extrait le JSON meme imparfait ; gere le cas ou le modele renvoie le SCHEMA
      ({"properties": {...}}) ; defaults pour champs manquants ;
    - si rien d'exploitable : traite le texte comme une reponse directe (jamais de plantage)."""
    obj = _extraire_json(txt)
    if not isinstance(obj, dict):
        s = (txt or "").strip()
        if _est_step_brut(s):
            return AgentStep(pensee="", reponse=_MSG_STEP_BRUT)
        return AgentStep(pensee="", reponse=s or "...")
    # Le modele a recopie le schema au lieu d'une instance.
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
    # Rien d'exploitable -> reponse directe = texte brut (l'agent repond toujours).
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

    systeme = _systeme(profil["role"], profil, eco=eco)
    messages: list[dict] = _tronquer_historique(historique)
    messages.append({"role": "user", "content": message})

    # Délégation : profondeur 1 en gratuit, 2 en premium (delegation_complete).
    _premium = bool(user and user.get("premium"))
    _max_prof = 2 if _premium else 1

    # Choix du tier : figé par profil, ou recommandé selon la demande en mode éco.
    tier = profil.get("tier", "fort")
    _bandit_cat = None      # catégorie pour récompenser le bandit en fin de dialogue
    if eco:
        reco = gateway.recommander_tier(message)
        # On ne descend jamais sous le tier requis par une vraie complexite, mais on
        # economise quand la demande est simple (ex: Cerveau "fort" -> "leger" pour "bonjour").
        tier = reco["tier"]
        _bandit_cat = reco.get("categorie")
        _emit({"type": "eco", "tier": tier, "raison": reco["raison"]})

    cl = _client or gateway.client(ctx, tier=tier)

    def _maj_bandit(succes: bool):
        """Récompense le routeur bandit (boucle fermée d'apprentissage du tier optimal)."""
        if _profondeur == 0 and eco and _bandit_cat:
            try:
                import routeur_bandit
                routeur_bandit.recompenser(_bandit_cat, tier, succes)
            except Exception:
                pass

    _outils_reussis: list[str] = []   # trajectoire (pour cristallisation contextuelle)

    for _ in range(MAX_ETAPES):
        # Pendant la boucle, messages grossit (action/observation a chaque tour).
        # On borne en gardant le 1er message (la demande) + la queue recente.
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

        # Fin : reponse finale.
        if not step.outil:
            reponse = nettoyer(step.reponse or step.pensee or "")
            _emit({"type": "reponse", "agent": role, "texte": reponse})
            # Cristallisation contextuelle : la trajectoire réussie devient une compétence (auto).
            if _profondeur == 0 and _outils_reussis:
                _cristalliser_trajectoire(role, message, _outils_reussis)
            _maj_bandit(succes=bool(reponse))
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
            elif _profondeur >= _max_prof:
                obs = ("Delegation en cascade reservee au premium. " if not _premium
                       else "Profondeur de delegation maximale atteinte.")
            else:
                _emit({"type": "delegation", "de": role, "vers": cible, "mission": nettoyer(mission)})
                obs = dialoguer(cible, mission, ctx=ctx, emit=emit,
                                _client=_client, _profondeur=_profondeur + 1, eco=eco, user=user)
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
            obs = fn(_ctx=ctx, _emit=emit, _user=user, **params)
        except Exception as e:
            obs = nettoyer(f"Erreur outil {outil} : {e}")
        obs = nettoyer(str(obs))[:2000]
        # Trajectoire : on retient l'outil si l'observation n'est pas un échec manifeste.
        if not obs.lower().startswith(("erreur", "[erreur", "limite atteinte", "aucun", "l'agent local n'est pas")):
            _outils_reussis.append(outil)
        _emit({"type": "observation", "agent": role, "outil": outil, "texte": obs})
        _replay(outil)
        messages.append({"role": "user", "content": f"[Resultat {outil}] {obs}"})

    # Securite : trop d'etapes.
    msg = "J'ai atteint la limite d'etapes. Reformule ou precise ta demande."
    _emit({"type": "reponse", "agent": role, "texte": msg})
    _maj_bandit(succes=False)
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
    #    Le fake .create renvoie le JSON de chaque step (comme un vrai modele).
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
