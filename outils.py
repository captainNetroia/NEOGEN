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


def outil_contexte_navigateur(**kw) -> str:
    """Lit l'URL et le titre de la page web active dans le navigateur de l'utilisateur.
    Utilise Chrome DevTools Protocol si disponible, sinon le titre de la fenêtre."""
    import time
    import rpa
    if not _agent_pret():
        return _MSG_AGENT_ABSENT
    t0 = rpa.request_browser_context()
    # Attendre que l'agent hôte réponde (max 5s)
    for _ in range(25):
        time.sleep(0.2)
        ctx = rpa.get_browser_context()
        if ctx.get("ts", 0) > t0:
            url = ctx.get("url") or "(URL non disponible — lance Chrome avec --remote-debugging-port=9222)"
            titre = ctx.get("titre") or "(titre inconnu)"
            return nettoyer(f"Page active : {titre}\nURL : {url}")
    return "Contexte navigateur non reçu (timeout 5s). L'agent local est-il connecté ?"


def outil_executer_mission_rpa(objectif: str = "", actions: Any = None,
                                infos_utilisateur: str = "", **kw) -> str:
    """Exécute une mission RPA avec pre-flight (collecte d'infos manquantes) et
    retry automatique (max 3 tentatives par action). Le seul blocage légitime :
    une info que seul l'utilisateur peut fournir. Tout blocage technique est géré seul."""
    import time
    import rpa
    if not _agent_pret():
        return _MSG_AGENT_ABSENT
    if not objectif:
        return "Fournis un 'objectif' décrivant ce que la mission doit accomplir."
    if not actions:
        return "Fournis la liste 'actions' à exécuter (même liste que controler_ecran)."
    if isinstance(actions, str):
        try:
            import json as _j
            actions = _j.loads(actions)
        except Exception:
            return "Le paramètre 'actions' doit être une liste JSON."
    if isinstance(actions, dict):
        actions = [actions]

    MAX_RETRY = 3
    contexte_infos = f" Informations fournies par l'utilisateur : {infos_utilisateur}." if infos_utilisateur else ""
    rapport = [f"Mission : {objectif}", f"{len(actions)} action(s) à exécuter."]

    for i, action in enumerate(actions):
        succes = False
        derniere_erreur = ""
        for tentative in range(1, MAX_RETRY + 1):
            action_id = rpa.RpaQueue.push(action)
            res = rpa.wait_result(action_id, timeout=30)
            statut = res.get("status", "timeout")

            if statut == "executed":
                rapport.append(f"  ✓ Action {i+1}/{len(actions)} ({action.get('action')}) OK"
                                + (f" [tentative {tentative}]" if tentative > 1 else ""))
                succes = True
                break

            elif statut == "rejected":
                rapport.append(f"  ✗ Action {i+1} rejetée par l'utilisateur — mission arrêtée.")
                return nettoyer("\n".join(rapport))

            else:
                derniere_erreur = res.get("error") or statut
                rapport.append(f"  ↺ Action {i+1} tentative {tentative} échouée : {derniere_erreur}")

                if tentative < MAX_RETRY:
                    # Capture screenshot pour comprendre le blocage
                    t_shot = rpa.request_screenshot()
                    img = None
                    for _ in range(15):
                        time.sleep(0.3)
                        img = rpa.get_screenshot(apres=t_shot)
                        if img:
                            break
                    if img:
                        consigne = (
                            f"Tu pilotes cet écran pour : {objectif}.{contexte_infos} "
                            f"L'action '{action.get('action')}' vient d'échouer ({derniere_erreur}). "
                            "En UNE PHRASE : quel est le blocage visible ? Est-ce une INFO MANQUANTE "
                            "(champ formulaire, identifiant, données) ou un PROBLÈME TECHNIQUE "
                            "(page erreur, chargement, CAPTCHA, élément décalé) ?"
                        )
                        try:
                            diagnostic = gateway.voir(_ctx_from(kw), img, consigne)
                            rapport.append(f"    Vision : {str(diagnostic)[:200]}")
                            # Si l'agent détecte une info manquante → escalader
                            diag_lower = str(diagnostic).lower()
                            if any(k in diag_lower for k in ("info manquante", "identifiant",
                                                              "formulaire", "données", "renseigner",
                                                              "saisir", "entrer")):
                                rapport.append(f"\n⚠ Info manquante détectée à l'action {i+1}.")
                                rapport.append(f"Contexte : {str(diagnostic)[:300]}")
                                rapport.append("Fournis l'information via 'infos_utilisateur' et relance.")
                                return nettoyer("\n".join(rapport))
                        except Exception:
                            pass

        if not succes:
            rapport.append(f"  ✗ Action {i+1} bloquée après {MAX_RETRY} tentatives : {derniere_erreur}")
            rapport.append("Blocage technique persistant — vérifier manuellement.")
            return nettoyer("\n".join(rapport))

    rapport.append(f"\n✓ Mission accomplie : {len(actions)} action(s) exécutées avec succès.")
    return nettoyer("\n".join(rapport))


def outil_objectif_rpa(objectif: str = "", infos_utilisateur: str = "", **kw) -> str:
    """Exécute une mission RPA depuis un objectif en langage naturel.
    Capture l'écran, génère automatiquement les actions via LLM, exécute avec retry x3.
    Si des informations manquent (identifiant, mot de passe, valeur), les demande explicitement.
    params: {objectif, infos_utilisateur?}"""
    import json as _j
    import time as _t
    import rpa
    if not objectif.strip():
        return "Fournis un 'objectif' décrivant la mission en langage naturel."
    if not _agent_pret():
        return _MSG_AGENT_ABSENT

    infos = infos_utilisateur.strip()

    # Capture screenshot pour ancrer le LLM sur l'état réel de l'écran
    screen_b64 = None
    t_shot = rpa.request_screenshot()
    for _ in range(15):
        _t.sleep(0.3)
        screen_b64 = rpa.get_screenshot(apres=t_shot)
        if screen_b64:
            break

    _SYSTEM = (
        "Tu es un agent RPA expert. Tu pilotes physiquement un ordinateur Windows.\n"
        "Actions disponibles : click(x,y), double_click(x,y), right_click(x,y), "
        "type(text), press(key), hotkey(keys:[]), scroll(x,y,direction,amount), "
        "open_url(url), screenshot(), sleep(ms).\n\n"
        "Réponds en JSON STRICT (sans bloc markdown) :\n"
        "{ \"infos_manquantes\": [{\"question\": \"...\", \"champ\": \"id\"}], \"actions\": [{...}] }\n"
        "RÈGLES : si des données spécifiques non fournies sont nécessaires (identifiant, "
        "mot de passe, SIRET, valeur formulaire) → infos_manquantes + actions vide. "
        "Sinon génère la séquence complète avec coordonnées précises."
    )
    prompt = f"Objectif : {objectif}"
    if infos:
        prompt += f"\nInformations disponibles : {infos}"
    if screen_b64:
        prompt += "\nL'écran actuel est fourni ci-joint."
    else:
        prompt += "\nAucun écran disponible — génère un plan d'actions générique."

    try:
        if screen_b64:
            text = gateway.voir(_ctx_from(kw), screen_b64, f"{_SYSTEM}\n\n{prompt}")
        else:
            cli = gateway.client(_ctx_from(kw), tier="fort")
            resp = cli.messages.create(
                messages=[{"role": "user", "content": prompt}],
                system=_SYSTEM, max_tokens=2000,
            )
            text = "".join(getattr(b, "text", "") for b in resp.content)

        text = text.strip()
        if "```" in text:
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else parts[0]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        plan = _j.loads(text)
    except Exception as e:
        return nettoyer(f"Erreur analyse objectif : {e}")

    manquantes = plan.get("infos_manquantes") or []
    actions = plan.get("actions") or []

    if manquantes:
        questions = "\n".join(f"  - {m['question']}" for m in manquantes)
        champs = ", ".join(m.get("champ", "?") for m in manquantes)
        return nettoyer(
            f"Informations nécessaires pour '{objectif}' :\n{questions}\n\n"
            f"Relance avec infos_utilisateur contenant : {champs}"
        )
    if not actions:
        return "Aucune action générée pour cet objectif."

    return outil_executer_mission_rpa(
        objectif=objectif, actions=actions, infos_utilisateur=infos, **kw
    )


def outil_remote_control(enabled: str = "on", **kw) -> str:
    """Active ou désactive le mode contrôle total (consent_level=auto).
    En mode 'on' : l'agent agit sans popup de consentement.
    En mode 'off' : retour au mode séquence (fenêtre 120 s).
    params: {enabled:'on'/'off'}"""
    import rpa
    activer = str(enabled).lower().strip() in ("on", "1", "true", "oui", "activer", "yes", "auto")
    rpa.save_settings({
        "consent_level": "auto" if activer else "sequence",
        "sequence_duration": 120,
    })
    if activer:
        return "Mode contrôle total activé — l'agent agit sans popup de consentement."
    return "Mode séquence restauré — l'agent demandera le consentement (fenêtre 120 s)."


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
# Outils du Veilleur : scanner_tensions / remonter_alerte / ancrer_tension
# ---------------------------------------------------------------------------

def outil_scanner_tensions(**kw) -> str:
    """Scanne les registres actifs pour détecter les tensions (skills vides, directives
    contradictoires, règles sans code, artefacts non liés). Classe par sévérité."""
    import pathlib, time as _time
    racine = pathlib.Path(__file__).parent

    tensions: list[dict] = []

    # 1. Parcours utilisateur (coherence_auto)
    try:
        import coherence_auto
        rapport = coherence_auto.audit_journeys()
        for t in rapport.get("tensions", []):
            tensions.append({"source": "parcours", "sev": "moyen",
                             "desc": t.get("raison", "")})
    except Exception:
        pass

    # 2. Skills sans instructions
    try:
        p = racine / "data" / "savoir.jsonl"
        if p.exists():
            for ligne in p.read_text(encoding="utf-8").splitlines():
                ligne = ligne.strip()
                if not ligne:
                    continue
                d = json.loads(ligne)
                if d.get("type") == "skill" and not (d.get("instructions") or "").strip():
                    tensions.append({"source": "skill", "sev": "faible",
                                     "desc": f"skill '{d.get('nom','?')}' : instructions vides"})
    except Exception:
        pass

    # 3. Agents custom avec rôle trop court (< 30 car)
    try:
        p = racine / "data" / "agents_custom.json"
        if p.exists():
            agents = json.loads(p.read_text(encoding="utf-8"))
            for cle, a in agents.items():
                role = (a.get("role") or "").strip()
                if len(role) < 30:
                    tensions.append({"source": "agent", "sev": "faible",
                                     "desc": f"agent '{cle}' : role trop court ({len(role)} car)"})
    except Exception:
        pass

    # 4. Règles requiert_code non ancrées dans le code
    try:
        p = racine / "data" / "regles_actives.json"
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            py_srcs = {f.stem: f.read_text(encoding="utf-8", errors="ignore")
                       for f in racine.glob("*.py")}
            for cle in data.get("regles_code_requis", {}):
                if not any(cle in src for src in py_srcs.values()):
                    tensions.append({"source": "regle", "sev": "bloquant",
                                     "desc": f"regle '{cle}' requiert code — non ancrée"})
    except Exception:
        pass

    if not tensions:
        return "[scanner_tensions] aucune tension detectee — systeme coherent"

    ordre = {"bloquant": 0, "moyen": 1, "faible": 2}
    tensions.sort(key=lambda t: ordre.get(t["sev"], 9))
    lignes = [f"[scanner_tensions] {len(tensions)} tension(s) :"]
    for t in tensions:
        lignes.append(f"  [{t['sev'].upper()}] [{t['source']}] {t['desc']}")
    return nettoyer("\n".join(lignes))


def outil_remonter_alerte(source: str = "", description: str = "",
                          impact: str = "", suggestion: str = "", **kw) -> str:
    """Formate une tension détectée en signal lisible pour Jordan.
    Ne propose jamais d'action autonome — Jordan décide."""
    if not description:
        return "[remonter_alerte] description requise"
    lignes = [
        "ALERTE VEILLEUR",
        f"  Source    : {source or 'non precisee'}",
        f"  Probleme  : {description}",
        f"  Impact    : {impact or 'a evaluer'}",
        f"  Note      : {suggestion or 'aucune suggestion — Jordan decide'}",
        "  Decision  : Jordan (le Veilleur ne fait rien sans accord)",
    ]
    return nettoyer("\n".join(lignes))


def outil_ancrer_tension(cle: str = "", source: str = "", mots_cles: str = "",
                         statut: str = "ouverte", **kw) -> str:
    """Trace une tension dans le fil de memoire transversal avec son statut
    (ouverte / prise_en_charge / resolue). Idempotent : met a jour si existe."""
    import pathlib, time as _time
    if not cle:
        return "[ancrer_tension] cle requise"
    if statut not in ("ouverte", "prise_en_charge", "resolue"):
        statut = "ouverte"
    racine = pathlib.Path(__file__).parent
    p = racine / "data" / "tensions_veilleur.jsonl"
    p.parent.mkdir(exist_ok=True)

    existants: list[dict] = []
    if p.exists():
        for ligne in p.read_text(encoding="utf-8").splitlines():
            ligne = ligne.strip()
            if ligne:
                try:
                    existants.append(json.loads(ligne))
                except Exception:
                    pass

    entree = {"cle": cle, "source": source, "mots_cles": mots_cles,
              "statut": statut, "ts": _time.time()}
    idx = next((i for i, e in enumerate(existants) if e.get("cle") == cle), None)
    action = "mise a jour" if idx is not None else "ancree"
    if idx is not None:
        existants[idx] = entree
    else:
        existants.append(entree)

    p.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in existants) + "\n",
        encoding="utf-8")
    return nettoyer(f"[ancrer_tension] tension '{cle}' {action} (statut: {statut})")


def outil_appeler_agent(cle: str = "", mission: str = "", **kw) -> str:
    """Appelle un autre agent NEOGEN et retourne sa reponse directement dans le contexte.
    Pair-a-pair : tout agent peut appeler tout autre (sauf lui-meme). Profondeur max 3.
    Utile pour deleguer selon l'expertise : Architecte -> Veilleur (coherence),
    Analyste -> Architecte (recommandation), Secretaire -> Architecte (skill technique).
    params: {cle (nom agent), mission (texte de la tache)}"""
    caller = kw.get("_caller", "")
    profondeur = int(kw.get("_profondeur", 0))
    ctx = kw.get("_ctx")
    emit = kw.get("_emit")
    user = kw.get("_user")

    cle = (cle or "").strip().lower()
    mission = (mission or "").strip()

    if not cle:
        return "[appeler_agent] cle requise — ex: {cle: 'veilleur', mission: '...'}"
    if not mission:
        return "[appeler_agent] mission requise"
    if cle == caller:
        return f"[appeler_agent] un agent ne peut pas s'appeler lui-meme ('{cle}')"
    if profondeur >= 3:
        return "[appeler_agent] profondeur maximale (3) atteinte — stoppe la cascade"

    import agent_core as _ac
    _ac.rafraichir_profils()
    if cle not in _ac.PROFILS:
        agents_dispo = sorted(_ac.PROFILS.keys())
        return nettoyer(f"[appeler_agent] agent '{cle}' inconnu. Disponibles : {', '.join(agents_dispo)}")

    try:
        obs = _ac.dialoguer(cle, mission, ctx=ctx, emit=emit,
                            _profondeur=profondeur + 1, eco=False, user=user)
    except Exception as e:
        return nettoyer(f"[appeler_agent] erreur lors de l'appel a '{cle}' : {e}")

    return nettoyer(f"[Agent {cle}] {obs}")


def outil_proposer_evolution(type_evo: str = "", payload: str = "",
                             titre: str = "", raison: str = "", **kw) -> str:
    """Applique une evolution data-driven reelle : agent, regle, skill, modele, loi,
    idee, capacite, esthetique. ECRIT VRAIMENT dans les stores — c'est le seul outil
    qui modifie l'etat du systeme. payload = JSON string du changement.
    Admin local -> applique direct. Non-admin -> soumet en proposition."""
    TYPES_VALIDES = ("agent", "regle", "skill", "fonction", "modele", "loi",
                     "idee", "capacite", "esthetique", "savoir", "integration")
    type_evo = (type_evo or "").strip().lower()
    if not type_evo:
        return f"[proposer_evolution] type requis parmi : {', '.join(TYPES_VALIDES)}"
    if type_evo not in TYPES_VALIDES:
        return f"[proposer_evolution] type '{type_evo}' inconnu — valides : {', '.join(TYPES_VALIDES)}"

    # Parse payload JSON (l'agent envoie souvent une chaine)
    if isinstance(payload, dict):
        payload_dict = payload
    elif isinstance(payload, str) and payload.strip():
        try:
            payload_dict = json.loads(payload)
        except json.JSONDecodeError as e:
            return f"[proposer_evolution] payload JSON invalide : {e}\nRecu : {payload[:120]}"
    else:
        payload_dict = {}

    import evolution_gouvernee as _evo
    changement = {
        "type": type_evo,
        "payload": payload_dict,
        "titre": (titre or type_evo)[:120],
        "raison": (raison or "")[:300],
    }
    # 1. Application directe (admin = NEOGEN_OWNER_UNLIMITED=1 en local)
    try:
        res = _evo.appliquer(changement)
    except Exception as e:
        return f"[proposer_evolution] erreur interne : {e}"

    if res.get("ok"):
        return nettoyer(
            f"[proposer_evolution] applique (portee={res.get('portee','?')}) — "
            f"{res.get('detail', '')} [gen {res.get('generation', '?')}]")

    raison_echec = res.get("raison", "inconnu")
    # 2. Si refus parce que non-admin -> proposition en attente
    if any(k in raison_echec for k in ("remonte", "reserve", "admin")):
        try:
            res2 = _evo.proposer(type_evo, payload_dict, titre=titre, raison=raison)
            if res2.get("ok"):
                return nettoyer(
                    f"[proposer_evolution] soumis en proposition (validation Jordan requise) "
                    f"— prop_id={res2.get('prop_id', '?')}")
        except Exception as e2:
            return f"[proposer_evolution] echec proposition : {e2}"

    return f"[proposer_evolution] echec : {raison_echec}"


def _outil_integration_proxy(service: str = "", action: str = "", params: str = "", **kw) -> str:
    """Proxy vers outils_integ.outil_integration — évite l'import circulaire au module level."""
    from outils_integ import outil_integration
    return outil_integration(service=service, action=action, params=params, **kw)


# ---------------------------------------------------------------------------
# nom outil -> (fonction, description courte pour le prompt)
# ---------------------------------------------------------------------------
OUTILS: dict[str, tuple[Callable, str]] = {
    "discerner":         (outil_discerner,         "Analyse une intention (valeur/faisabilite/clarte). params: {intention}"),
    "conseiller":        (outil_conseiller,        "Cadrage + conformite RGPD d'un besoin. params: {intention}"),
    "creer_application": (outil_creer_application, 'Cree une app/SaaS/gadget de A a Z (delegation + sandbox). params: {intention, persistance?, reseau?, domaines?}. Si l\'app a besoin d\'internet, mets reseau:true ET domaines:["api.exemple.com"] (liste blanche OBLIGATOIRE, sinon tout acces reseau est refuse).'),
    "lister_creations":  (outil_lister_creations,  "Liste les creations existantes. params: {}"),
    "genealogie":        (outil_genealogie,        "Lignee/generations d'une creation. params: {produit_id}"),
    "controler_ecran":      (outil_controler_ecran,      "Pilote souris/clavier via l'agent local (consentement requis). params: {actions:[{action,x,y,text,...}]}"),
    "executer_mission_rpa": (outil_executer_mission_rpa, "Execute une mission RPA complete avec retry auto (max 3x) et pre-flight. Si bloque par une info manquante -> demande a l'utilisateur et s'arrete. params: {objectif, actions:[...], infos_utilisateur?}"),
    "objectif_rpa":         (outil_objectif_rpa,         "Execute une mission RPA depuis un objectif en langage naturel (capture ecran + LLM genere les actions + retry x3). Utiliser quand l'objectif est connu mais pas les actions precises. params: {objectif, infos_utilisateur?}"),
    "remote_control":       (outil_remote_control,       "Active (on) ou desactive (off) le mode controle total : l'agent agit sans popup de consentement. A activer avant une mission autonome longue. params: {enabled:'on'/'off'}"),
    "contexte_navigateur":  (outil_contexte_navigateur,  "Lit l'URL et le titre de la page web active dans le navigateur (CDP ou titre fenetre). params: {}"),
    "lister_routines":      (outil_lister_routines,      "Liste les routines apprises par imitation. params: {}"),
    "rejouer_routine":      (outil_rejouer_routine,      "Rejoue une routine apprise. params: {routine_id}"),
    "ouvrir_url":           (outil_ouvrir_url,           "Ouvre une page web dans le navigateur de l'utilisateur (consentement requis). params: {url}"),
    "fermer_onglet":        (outil_fermer_onglet,        "Ferme l'onglet/la page web actif du navigateur (Ctrl+W). params: {} (aucun)"),
    "regarder_ecran":       (outil_regarder_ecran,       "REGARDE l'ecran de l'utilisateur (capture + analyse vision) pour voir avant d'agir : lire un formulaire, reperer un bouton et ses coordonnees. params: {objectif}"),
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
    "scanner_tensions":       (outil_scanner_tensions,       "Scanne les registres NEOGEN pour détecter les tensions (skills vides, règles sans code, parcours KO, agents sans rôle). Classe par sévérité. params: {}"),
    "remonter_alerte":        (outil_remonter_alerte,        "Formate une tension détectée en signal lisible pour Jordan. Ne propose jamais d'action autonome. params: {source, description, impact?, suggestion?}"),
    "ancrer_tension":         (outil_ancrer_tension,         "Trace une tension dans le fil de mémoire transversal (ouverte/prise_en_charge/resolue). Idempotent. params: {cle, source?, mots_cles?, statut?}"),
    "proposer_evolution":     (outil_proposer_evolution,     "ÉCRIT VRAIMENT dans le système : agent, regle, skill, modele, loi, idee, capacite. C'est le seul outil qui modifie les stores data-driven. Si admin (local) -> applique direct. Sinon -> propose en attente. params: {type_evo, payload (JSON string), titre?, raison?}"),
    "appeler_agent":          (outil_appeler_agent,          "Appelle un autre agent NEOGEN et retourne sa reponse directement (pair-a-pair, profondeur max 3, auto-appel interdit). Pour deleguer selon expertise : Architecte->Veilleur, Analyste->Architecte, etc. params: {cle (nom agent), mission}"),
    "integration":            (_outil_integration_proxy,     "Appelle un service integre par l'utilisateur (Notion, Slack, GitHub, Telegram, Discord, HubSpot, Brevo, Airtable, Todoist, Calendly, Figma, Vercel, Perplexity, Tavily, ElevenLabs...). params: {service, action, params}"),
}
