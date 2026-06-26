"""
NEOGEN - Définitions des outils agents (boîte à outils).

Extrait de agent_core.py (dette F010) : chaque outil enveloppe une fonction
NEOGEN existante et renvoie une chaîne lisible (ré-injectée au modèle + affichée).
Imports paresseux dans les fonctions : évite les cycles, permet le smoke test
hors-ligne, ne charge les modules lourds qu'à l'usage.

agent_core.py importe OUTILS depuis ce module et orchestre les agents via
dialoguer(). Cette séparation permet de modifier/ajouter un outil sans toucher
au moteur ReAct.

Conception : Jordan VINCENT (NetroIA) avec Claude.
"""

from __future__ import annotations

import json
from typing import Any, Callable

import gateway
from sanitizer import nettoyer


# ---------------------------------------------------------------------------
# Helpers internes utilisés par les outils
# ---------------------------------------------------------------------------

def _ctx_from(kw: dict):
    """Récupère le LLMContext éventuellement passé par le moteur (clé/provider actifs)."""
    return kw.get("_ctx")


def _contexte_memoire() -> str:
    """Résumé des souvenirs pour personnaliser proposer/conseiller (wiring de cohérence)."""
    try:
        import memoire_agent
        return memoire_agent.resume_pour_prompt(limite=8)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# BOÎTE À OUTILS : chaque outil enveloppe une fonction NEOGEN existante.
# ---------------------------------------------------------------------------

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
    """Crée une application de A à Z : décompose, délègue, assemble, gouverne (sandbox).
    'reseau' peut être un booléen, une liste de domaines, ou {"domaines":[...]}.
    'domaines' = liste blanche des domaines autorisés (OBLIGATOIRE si l'app a besoin d'internet)."""
    from orchestrateur import orchestrer
    from capacites import Capacites
    import registre
    emit = kw.get("_emit")
    _u = kw.get("_user")
    if _u:
        import quotas
        v = quotas.verifier(_u, "creations")
        if not v["autorise"]:
            return f"Limite atteinte : {v['raison']}"
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
        if _u:
            try:
                import quotas
                quotas.incrementer(_u["id"], "creations")
            except Exception:
                pass
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
    """Envoie des actions souris/clavier à l'agent local. Consentement requis côté hôte."""
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
    """Capture l'écran de l'utilisateur et l'analyse avec un modèle vision."""
    import time
    import rpa
    if not _agent_pret():
        return _MSG_AGENT_ABSENT
    t0 = rpa.request_screenshot()
    img = None
    for _ in range(24):
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


# ── Méta-outils : l'agent forge ses PROPRES compétences ──────────────────────

def outil_creer_skill(nom: str = "", description: str = "", instructions: str = "",
                      outils=None, **kw) -> str:
    """Crée une compétence réutilisable (skill) qui devient invocable immédiatement."""
    import competences
    if not nom or not instructions:
        return "Pour creer un skill : fournis au moins 'nom' et 'instructions'."
    if isinstance(outils, str):
        outils = [outils]
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
    competences.enregistrer_usage(nom)
    txt = (f"COMPETENCE '{s['nom']}' — {s.get('description','')}\n"
           f"Instructions a appliquer maintenant :\n{s.get('instructions','')}\n")
    if s.get("outils"):
        txt += f"Outils a utiliser : {', '.join(s['outils'])}.\n"
    if contexte:
        txt += f"Contexte fourni : {contexte}\n"
    txt += (
        "\n── BOUCLE SATISFACTION (obligatoire) ──\n"
        "Après avoir appliqué ce skill, DEMANDE à l'utilisateur : 'Ce résultat vous convient-il ?'\n"
        "• OUI → enregistrer_usage déjà fait, continue.\n"
        "• NON → propose DEUX options :\n"
        "  A) Adapter ce skill : reformule ses instructions avec l'utilisateur, puis creer_skill "
        "avec le MÊME nom (écrase l'existant).\n"
        "  B) Créer un nouveau skill personnalisé : construis-le ensemble, creer_skill nouveau nom.\n"
        "Après adaptation ou création → JUGE la valeur générique du skill :\n"
        "  - Utile uniquement à cet utilisateur (spécifique) → reste local, rien à faire.\n"
        "  - Potentiellement utile à TOUS les utilisateurs NEOGEN → signale : "
        "'Ce skill pourrait enrichir le registre communautaire et le système NEOGEN lui-même.'\n"
    )
    return nettoyer(txt)[:4000]


# ── Mémoire cross-session ─────────────────────────────────────────────────────

def outil_memoriser(contenu: str = "", type: str = "fait", **kw) -> str:
    """Enregistre un fait durable (sur l'utilisateur, ses préférences, ses projets)."""
    import memoire_agent
    if not contenu.strip():
        return "Rien a memoriser : fournis 'contenu'."
    s = memoire_agent.memoriser(contenu, type)
    if not s:
        return "Contenu vide apres nettoyage."
    return f"Memorise ([{s['type']}]) : {s['contenu']}"


def outil_rappeler(requete: str = "", **kw) -> str:
    """Rappelle ce que l'agent sait déjà (souvenirs des sessions précédentes)."""
    import memoire_agent
    souvenirs = memoire_agent.rappeler(requete)
    if not souvenirs:
        return "Aucun souvenir pertinent."
    return nettoyer("Souvenirs :\n" + "\n".join(
        f"- [{m.get('type','fait')}] {m.get('contenu','')}" for m in souvenirs))


def outil_lire_fichier(chemin: str = "", **kw) -> str:
    """Lit un fichier PDF/PPTX/DOCX/TXT depuis un chemin local et retourne son contenu."""
    import outils_fichiers
    return nettoyer(outils_fichiers.lire_fichier_chemin(chemin))[:8000]


def outil_creer_rapport(titre: str = "Rapport", contenu: str = "",
                        format: str = "docx", **kw) -> str:
    """Crée un rapport téléchargeable. format : docx (défaut), pdf, excel, csv, pptx, html."""
    import outils_fichiers as _of
    fmt = (format or "docx").strip().lower()
    if fmt == "pdf":
        nom = _of.creer_rapport_pdf(titre, contenu)
    elif fmt in ("excel", "xlsx", "xls"):
        nom = _of.creer_rapport_excel(titre, contenu); fmt = "xlsx"
    elif fmt == "csv":
        nom = _of.creer_rapport_csv(titre, contenu)
    elif fmt in ("pptx", "ppt", "powerpoint", "presentation"):
        nom = _of.creer_rapport_pptx(titre, contenu); fmt = "pptx"
    elif fmt in ("html", "htm", "web"):
        nom = _of.creer_rapport_html(titre, contenu); fmt = "html"
    else:
        nom = _of.creer_rapport_docx(titre, contenu); fmt = "docx"
    if not nom:
        return f"[format {fmt} non disponible — rebuild Docker requis]"
    return nettoyer(f"Rapport {fmt.upper()} créé : /fichiers/rapports/{nom}")


def outil_forger_bloc(idee: str = "", zone: str = "evolution", **kw) -> str:
    """Genere et applique un fragment HTML dans la zone indiquee (runtime, securise)."""
    if not idee:
        return "[forger_bloc] idee requise"
    import forge_fragments as _ff
    apercu = _ff.generer_apercu(idee.strip(), zone)
    if not apercu.get("ok"):
        return f"[forger_bloc] refuse : {apercu.get('raison', 'echec')}"
    res = _ff.appliquer(apercu["html"], zone, titre=apercu.get("titre", ""),
                        user={"owner": True})
    if res.get("ok"):
        return nettoyer(f"[forger_bloc] '{apercu.get('titre', '')}' applique en zone '{zone}' ({res.get('action', '')})")
    return f"[forger_bloc] echec : {res.get('raison', 'inconnu')}"


def outil_donner_vie(pensee_id: str = "", **kw) -> str:
    """Active une pensee existante (route son evolution ou lance une conversation dediee)."""
    if not pensee_id:
        return "[donner_vie] pensee_id requis"
    import pensee as _p
    import hashlib
    pensees = _p.lister(limit=200)
    found = next((x for x in pensees
                  if hashlib.sha256(
                      f"{x.get('titre', '')}|{x.get('synthese', '')[:120]}".encode()
                  ).hexdigest()[:16] == pensee_id), None)
    if not found:
        return f"[donner_vie] pensee '{pensee_id}' introuvable"
    evo = found.get("evolution")
    if isinstance(evo, dict) and evo.get("type"):
        try:
            import evolution_gouvernee as _eg
            res = _eg.proposer(evo["type"], evo.get("payload", {}),
                               titre=found.get("titre", ""),
                               raison=found.get("synthese", ""))
            _p.marquer_vie_donnee(pensee_id)
            return nettoyer(f"[donner_vie] evolution proposee : {res.get('detail', res.get('raison', ''))}")
        except Exception as e:
            return f"[donner_vie] erreur evolution : {e}"
    result = _p.cycle_pensee(force=True, sujet=found.get("titre", ""))
    _p.marquer_vie_donnee(pensee_id)
    return nettoyer(f"[donner_vie] conversation lancee — titre : {result.get('titre', '')} score={result.get('score', '?')}")


def outil_proposer_conversation(sujet: str = "", contexte: str = "", **kw) -> str:
    """Lance une conversation autonome sur un sujet specifique (force un cycle pensee)."""
    if not sujet:
        return "[proposer_conversation] sujet requis"
    import pensee as _p
    sujet_complet = sujet.strip() + (f" — {contexte.strip()}" if contexte.strip() else "")
    result = _p.cycle_pensee(force=True, sujet=sujet_complet)
    if not result.get("execute"):
        return f"[proposer_conversation] non execute : {result.get('raison', 'inconnu')}"
    return nettoyer(f"[proposer_conversation] conversation creee — '{result.get('titre', '')}' "
                    f"score={result.get('score', '?')} bulle={result.get('bulle', False)}")


# ---------------------------------------------------------------------------
# nom outil -> (fonction, description courte pour le prompt)
# ---------------------------------------------------------------------------
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
    "utiliser_skill":    (outil_utiliser_skill,    "Invoque une competence apprise : applique son savoir-faire + boucle satisfaction (demande si ok, adapte ou crée si non, juge valeur systeme). params: {nom, contexte?}"),
    "memoriser":         (outil_memoriser,         "Memorise un fait DURABLE sur l'utilisateur/ses preferences/ses projets (se souvenir entre sessions). params: {contenu, type?: user|preference|projet|fait}"),
    "rappeler":          (outil_rappeler,          "Rappelle ce que tu sais deja (souvenirs des sessions precedentes). params: {requete?}"),
    "lire_fichier":           (outil_lire_fichier,           "Lit un fichier PDF/PPTX/DOCX/TXT depuis un chemin local. params: {chemin}"),
    "creer_rapport":          (outil_creer_rapport,          "Cree un rapport telechargeable. params: {titre, contenu, format?} — format: docx (defaut), pdf, excel/xlsx, csv, pptx, html. Le contenu peut utiliser ## ### pour les titres/sections."),
    "forger_bloc":            (outil_forger_bloc,            "Genere et applique un fragment HTML dans l'interface (runtime, securise). params: {idee, zone?} — zone: cerveaux|creation|production|compte|analyse|evolution|integrations"),
    "donner_vie":             (outil_donner_vie,             "Active une pensee existante : route son evolution ou lance une conversation dediee. params: {pensee_id}"),
    "proposer_conversation":  (outil_proposer_conversation,  "Lance une conversation autonome sur un sujet (force un cycle pensee). params: {sujet, contexte?}"),
}
