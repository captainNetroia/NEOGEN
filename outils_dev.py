"""
NEOGEN - Outils de l'Ingenieur : les YEUX et les MAINS sur le code de l'application.

Jusqu'ici, quand Jordan donnait vie a une idee technique, NEOGEN forgeait une cellule
isolee (data/cellules_forgees/) mais ne savait NI lire son propre code source, NI le
modifier, NI raisonner sur ce qui manque pour qu'un objectif fonctionne vraiment. Il
fallait revenir vers Claude Code (externe) pour le moindre changement.

Ce module donne a l'agent INGENIEUR le pouvoir de faire ce que fait un developpeur expert :
  - DIAGNOSTIQUER : lire le code source, chercher dedans, cartographier les modules,
    consulter la sante/coherence du systeme.
  - CODER ce qui manque : forger une capacite (vrai code genere, teste en sandbox, valide
    contre les murs, integre A CHAUD via capacites_forgees) puis l'ANCRER dans le flux pour
    qu'elle agisse toute seule (avant_validation_code, apres_erreur, periodique...).
  - MODIFIER un module existant : proposer un patch teste (analyse syntaxique + sauvegarde),
    ecrit dans data/patches_proposes/. Si la cible est le NOYAU -> escalade : autorisation
    explicite de Jordan requise (le mur). Sinon -> patch applicatif sous controle + rebuild signale.
  - DELEGUER : creer des bebe-agents specialises, appeler les autres agents (via appeler_agent).

DOCTRINE :
  - Le code packagee dans l'image Docker ne se hot-patch pas (culture DevSecOps : on teste,
    on redeploie). L'extension A CHAUD passe donc par les CELLULES forgees (data/, bind-mounte,
    rechargees sans rebuild). Un patch de module = proposition testee + rebuild signale.
  - Murs intouchables : credentials = mur absolu ; noyau = autorisation Jordan ; le reste
    (applicatif) = patchable sous controle. classer_cible/autoriser_patch_code (noyau.py) gardent.
  - Aucune fonction ne leve : tout est enveloppe rob.garde / try. Lecture du code = libre
    (sauf secrets). Ecriture reelle du code source = jamais sans test ; noyau = jamais sans Jordan.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-28.
"""
from __future__ import annotations

import json
import os
import re
import time

from sanitizer import nettoyer

BASE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(BASE, "data")
_PATCHES_DIR = os.path.join(_DATA, "patches_proposes")
_BACKUPS_DIR = os.path.join(_DATA, "backups_code")
_AUTORISATIONS = os.path.join(_DATA, "autorisations_requises.json")
_REBUILD = os.path.join(_DATA, "rebuild_requis.json")

# Extensions de fichiers source que l'Ingenieur peut lire/parcourir.
_EXT_SOURCE = (".py", ".js", ".html", ".css", ".json", ".md", ".yml", ".yaml", ".txt")
# Dossiers ignores a la lecture/recherche (bruit, volumineux, hors code).
_IGNORE_DIRS = {"__pycache__", ".git", "node_modules", "data", "credentials",
                "backups_code", ".venv", "venv", "archive", "_archive"}
_MAX_LECTURE = 16000     # caracteres max retournes pour une lecture de fichier
_MAX_RESULTATS = 40      # resultats max pour une recherche


# ── Helpers chemin (fail-closed : jamais en dehors du projet) ─────────────────────

def _resoudre(chemin: str) -> tuple[str | None, str]:
    """Resout un chemin relatif au projet et verifie qu'il reste dans BASE. (abspath|None, raison)."""
    c = (chemin or "").strip().replace("\\", "/").lstrip("./")
    if not c:
        return None, "chemin vide"
    if ".." in c.split("/"):
        return None, "remontee de chemin interdite (..)"
    absolu = os.path.normpath(os.path.join(BASE, c))
    if not (absolu == BASE or absolu.startswith(BASE + os.sep)):
        return None, "hors du projet NEOGEN"
    return absolu, "ok"


# ── DIAGNOSTIC : lire / chercher / cartographier le code source ───────────────────

def outil_lire_source(chemin: str = "", debut: int = 1, lignes: int = 0, **kw) -> str:
    """Lit un fichier source de l'application (.py/.js/.html/.json/.md/.yml...).
    Lecture LIBRE pour le diagnostic, SAUF les secrets (credentials). params:
    {chemin, debut? (1er n de ligne), lignes? (nb de lignes, 0=tout borne)}"""
    import noyau
    absolu, raison = _resoudre(chemin)
    if not absolu:
        return f"[lire_source] {raison}"
    cat = noyau.classer_cible(chemin)
    if cat == "credentials":
        return "[lire_source] refus : les credentials sont un mur absolu (jamais lus par cette voie)"
    if not os.path.isfile(absolu):
        return f"[lire_source] fichier introuvable : {chemin}"
    try:
        with open(absolu, encoding="utf-8", errors="replace") as f:
            contenu = f.readlines()
    except Exception as e:
        return f"[lire_source] erreur lecture : {e}"
    total = len(contenu)
    d = max(1, int(debut or 1))
    if lignes and int(lignes) > 0:
        extrait = contenu[d - 1: d - 1 + int(lignes)]
    else:
        extrait = contenu[d - 1:]
    txt = "".join(extrait)
    if len(txt) > _MAX_LECTURE:
        txt = txt[:_MAX_LECTURE] + f"\n[…tronque — fichier de {total} lignes, precise debut/lignes]"
    entete = f"[{chemin}] ({cat}, {total} lignes)\n"
    return nettoyer(entete + txt)


def outil_chercher_code(motif: str = "", glob: str = "*.py", **kw) -> str:
    """Cherche un motif (regex) dans le code source du projet. Renvoie fichier:ligne + extrait.
    Indispensable au diagnostic ('ou est defini X', 'qui appelle Y'). params: {motif, glob? (defaut *.py)}"""
    if not motif:
        return "[chercher_code] motif requis (texte ou regex)"
    try:
        rx = re.compile(motif, re.IGNORECASE)
    except re.error as e:
        return f"[chercher_code] regex invalide : {e}"
    suffixe = (glob or "*.py").replace("*", "").strip() or ".py"
    resultats: list[str] = []
    for racine, dirs, fichiers in os.walk(BASE):
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
        for nom in fichiers:
            if not nom.endswith(suffixe):
                continue
            chemin_abs = os.path.join(racine, nom)
            rel = os.path.relpath(chemin_abs, BASE).replace("\\", "/")
            try:
                with open(chemin_abs, encoding="utf-8", errors="replace") as f:
                    for i, ligne in enumerate(f, 1):
                        if rx.search(ligne):
                            resultats.append(f"  {rel}:{i}: {ligne.strip()[:160]}")
                            if len(resultats) >= _MAX_RESULTATS:
                                resultats.append(f"  […{_MAX_RESULTATS}+ resultats, affine le motif]")
                                return nettoyer(f"[chercher_code] '{motif}' :\n" + "\n".join(resultats))
            except Exception:
                continue
    if not resultats:
        return f"[chercher_code] aucun resultat pour '{motif}' (glob {glob})"
    return nettoyer(f"[chercher_code] '{motif}' ({len(resultats)} resultats) :\n" + "\n".join(resultats))


def outil_carte_code(sous_dossier: str = "", **kw) -> str:
    """Cartographie les modules du projet : liste les fichiers source + leur categorie
    (noyau/applicative/data). Donne a l'Ingenieur la vue d'ensemble pour savoir ou agir.
    params: {sous_dossier? (ex: 'routes')}"""
    import noyau
    base_scan = BASE
    if sous_dossier:
        absolu, raison = _resoudre(sous_dossier)
        if not absolu:
            return f"[carte_code] {raison}"
        base_scan = absolu
    noyau_f, app_f = [], []
    for racine, dirs, fichiers in os.walk(base_scan):
        dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
        for nom in sorted(fichiers):
            if not nom.endswith(_EXT_SOURCE):
                continue
            rel = os.path.relpath(os.path.join(racine, nom), BASE).replace("\\", "/")
            cat = noyau.classer_cible(rel)
            if cat == "noyau":
                noyau_f.append(rel)
            elif cat == "applicative":
                app_f.append(rel)
    lignes = [f"[carte_code] {len(noyau_f) + len(app_f)} fichiers source"]
    lignes.append(f"\nNOYAU (grave, patch = autorisation Jordan) — {len(noyau_f)} :")
    lignes += [f"  [mur] {f}" for f in noyau_f[:40]]
    lignes.append(f"\nAPPLICATIF (patchable sous controle) — {len(app_f)} :")
    lignes += [f"  {f}" for f in app_f[:60]]
    return nettoyer("\n".join(lignes))


# ── CODER : forger une capacite (a chaud) + l'ancrer dans le flux ─────────────────

def outil_forger_capacite(besoin: str = "", titre: str = "", ancrage: str = "manuel", **kw) -> str:
    """CODE ce qui manque : forge une capacite (vrai code Python genere par un modele, teste en
    sandbox Docker durcie, valide contre les murs, integre A CHAUD) PUIS l'ancre dans le flux pour
    qu'elle agisse automatiquement. C'est la voie AUTOMATIQUE d'auto-amelioration (pas de rebuild).
    ancrage : manuel | avant_validation_code | apres_erreur | avant_reponse_agent | periodique.
    params: {besoin (description precise de la fonction a creer), titre?, ancrage?}"""
    if not besoin:
        return "[forger_capacite] besoin requis (decris precisement la fonction a creer)"
    import forge_evolution as _fe
    import uuid
    job = uuid.uuid4().hex[:12]
    try:
        r = _fe.forger(besoin, titre=titre or besoin[:60], job_id=job)
    except Exception as e:
        return f"[forger_capacite] erreur forge : {e}"
    if not r.get("ok"):
        return nettoyer(f"[forger_capacite] ECHEC apres {r.get('tentatives', '?')} tentative(s) : "
                        f"{r.get('raison', 'inconnu')}. Reformule le besoin ou simplifie.")
    nom = r.get("nom", "")
    statut = r.get("etat", "forgee")
    msg = (f"[forger_capacite] '{nom}' {statut} (score {r.get('score')}, "
           f"{r.get('tentatives')} tentative(s), verdict {r.get('verdict')})")
    point = (ancrage or "manuel").strip()
    if point and point != "manuel" and nom:
        try:
            import capacites_forgees as _cf
            anc = _cf.definir_ancrage(nom, point)
            if anc.get("ok"):
                msg += f" — ANCREE a '{point}' : agira automatiquement dans le flux."
            else:
                msg += f" — ancrage refuse : {anc.get('raison')}"
        except Exception as e:
            msg += f" — ancrage impossible : {e}"
    return nettoyer(msg)


def outil_ancrer_capacite(nom: str = "", point: str = "manuel", **kw) -> str:
    """Ancre une capacite forgee existante a un point du flux pour qu'elle s'auto-declenche.
    points : manuel | avant_validation_code | apres_erreur | avant_reponse_agent | periodique.
    params: {nom (cellule), point}"""
    if not nom:
        return "[ancrer_capacite] nom de capacite requis"
    try:
        import capacites_forgees as _cf
        r = _cf.definir_ancrage(nom, (point or "manuel").strip())
    except Exception as e:
        return f"[ancrer_capacite] erreur : {e}"
    if r.get("ok"):
        return nettoyer(f"[ancrer_capacite] '{nom}' ancree a '{r.get('point_ancrage')}' "
                        f"(s'auto-declenche desormais).")
    return f"[ancrer_capacite] refuse : {r.get('raison')}"


# ── MODIFIER un module : patch teste, escalade si mur ────────────────────────────

def _charger_json(chemin: str, defaut):
    try:
        if os.path.exists(chemin):
            with open(chemin, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return defaut


def _sauver_json(chemin: str, obj) -> None:
    try:
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def outil_proposer_patch(chemin: str = "", ancien: str = "", nouveau: str = "",
                         raison: str = "", **kw) -> str:
    """Prepare un patch teste sur un module existant (remplace 'ancien' par 'nouveau').
    Verifie la syntaxe du resultat, sauvegarde l'original, ecrit la proposition dans
    data/patches_proposes/ + signale qu'un rebuild est requis. Si la cible est le NOYAU
    -> escalade : ecrit une demande d'AUTORISATION pour Jordan (le mur), n'applique rien.
    params: {chemin, ancien (texte exact a remplacer), nouveau, raison}"""
    import noyau
    absolu, rmsg = _resoudre(chemin)
    if not absolu:
        return f"[proposer_patch] {rmsg}"
    if not os.path.isfile(absolu):
        return f"[proposer_patch] fichier introuvable : {chemin}"
    if not ancien:
        return "[proposer_patch] 'ancien' requis (le texte exact a remplacer)"
    try:
        with open(absolu, encoding="utf-8", errors="replace") as f:
            source = f.read()
    except Exception as e:
        return f"[proposer_patch] erreur lecture : {e}"
    if ancien not in source:
        return "[proposer_patch] 'ancien' introuvable tel quel dans le fichier (copie le texte exact)"
    if source.count(ancien) > 1:
        return (f"[proposer_patch] 'ancien' apparait {source.count(ancien)}x — ajoute du contexte "
                "pour qu'il soit unique")
    resultat = source.replace(ancien, nouveau, 1)

    # Gardien du code source (fail-closed) : credentials/inconnu -> refus ; noyau -> escalade.
    ok, cat, motif = noyau.autoriser_patch_code(chemin, resultat)
    if cat == "noyau":
        demandes = _charger_json(_AUTORISATIONS, [])
        demande = {"id": f"aut_{int(time.time())}_{len(demandes)}", "chemin": chemin,
                   "raison": raison or "(non precisee)", "categorie": "noyau",
                   "ancien": ancien[:400], "nouveau": nouveau[:400],
                   "ts": time.time(), "statut": "en_attente"}
        demandes.append(demande)
        _sauver_json(_AUTORISATIONS, demandes)
        try:
            import robustesse as rob
            rob.journaliser(f"PATCH NOYAU demande l'autorisation de Jordan : {chemin} ({raison})",
                            "alerte", source="ingenieur")
        except Exception:
            pass
        return nettoyer(f"[proposer_patch] MUR — '{chemin}' est dans le noyau. Patch NON applique. "
                        f"Demande d'autorisation #{demande['id']} ecrite pour Jordan (il decide).")
    if not ok:
        return f"[proposer_patch] refuse : {motif}"

    # Validation syntaxique du resultat (pour les .py).
    if chemin.strip().endswith(".py"):
        try:
            compile(resultat, chemin, "exec")
        except SyntaxError as e:
            return f"[proposer_patch] patch REJETE : le resultat casse la syntaxe ({e}). Corrige."

    # Sauvegarde de l'original + ecriture de la proposition (testee, prete a appliquer).
    backup = os.path.join(_BACKUPS_DIR, f"{os.path.basename(chemin)}.{int(time.time())}.bak")
    try:
        os.makedirs(_BACKUPS_DIR, exist_ok=True)
        with open(backup, "w", encoding="utf-8") as f:
            f.write(source)
    except Exception:
        backup = ""
    patchs = _charger_json(os.path.join(_PATCHES_DIR, "index.json"), [])
    pid = f"patch_{int(time.time())}_{len(patchs)}"
    diff = _mini_diff(ancien, nouveau)
    fiche = {"id": pid, "chemin": chemin, "categorie": cat, "raison": raison or "(non precisee)",
             "ancien": ancien, "nouveau": nouveau, "diff": diff, "backup": backup,
             "ts": time.time(), "statut": "propose", "syntaxe_ok": True}
    _sauver_json(os.path.join(_PATCHES_DIR, f"{pid}.json"), fiche)
    patchs.append({"id": pid, "chemin": chemin, "raison": fiche["raison"], "ts": fiche["ts"],
                   "statut": "propose"})
    _sauver_json(os.path.join(_PATCHES_DIR, "index.json"), patchs)
    outil_signaler_rebuild(raison=f"patch {pid} sur {chemin}")
    return nettoyer(f"[proposer_patch] patch {pid} sur '{chemin}' ({cat}) : syntaxe OK, original "
                    f"sauvegarde. Propose (prend effet au prochain rebuild). Diff :\n{diff}")


def _mini_diff(ancien: str, nouveau: str) -> str:
    """Diff lisible compact (premieres lignes -/+)."""
    a = (ancien or "").splitlines()[:8]
    b = (nouveau or "").splitlines()[:8]
    out = [f"  - {l}" for l in a] + [f"  + {l}" for l in b]
    return "\n".join(out)[:1000]


def outil_signaler_rebuild(raison: str = "", **kw) -> str:
    """Marque qu'un rebuild Docker est requis (un patch de module ne prend effet qu'apres rebuild).
    L'UI affiche un badge ; Jordan lance 'docker compose up -d --build'. params: {raison?}"""
    sig = _charger_json(_REBUILD, {"requis": False, "raisons": []})
    sig["requis"] = True
    sig.setdefault("raisons", []).append({"raison": raison or "(non precisee)", "ts": time.time()})
    sig["raisons"] = sig["raisons"][-20:]
    sig["ts"] = time.time()
    _sauver_json(_REBUILD, sig)
    return nettoyer(f"[signaler_rebuild] rebuild marque comme requis ({raison}).")


# ── DIAGNOSTIC INGENIEUR : vue 360 (sante + coherence + tensions + cellules) ──────

def outil_diagnostic_ingenieur(**kw) -> str:
    """Diagnostic 360 de l'Ingenieur : sante (journeys/services), coherence (tensions),
    cellules orphelines (forgees mais non integrees), patchs en attente, rebuild requis.
    Le point de depart de toute intervention. params: {}"""
    lignes = ["DIAGNOSTIC INGENIEUR"]
    # 1. Sante + coherence (reutilise les outils Veilleur).
    try:
        import outils as _o
        lignes.append("\n=== SANTE ===\n" + _o.outil_sante_appli(detail=False))
    except Exception as e:
        lignes.append(f"\n=== SANTE === indisponible : {e}")
    # 2. Cellules forgees mais non integrees (le code mort a reparer).
    try:
        import capacites_forgees as _cf
        cells = _cf.lister()
        orphelines = [c for c in cells if c.get("statut") not in ("integree",) and not c.get("integre")]
        lignes.append(f"\n=== CELLULES === {len(cells)} forgees")
        if orphelines:
            lignes.append("  Non integrees (a reparer) :")
            lignes += [f"   - {c.get('nom')} : {c.get('resume', c.get('description',''))[:80]}"
                       for c in orphelines[:10]]
    except Exception as e:
        lignes.append(f"\n=== CELLULES === indisponible : {e}")
    # 3. Patchs proposes + rebuild requis.
    patchs = _charger_json(os.path.join(_PATCHES_DIR, "index.json"), [])
    en_attente = [p for p in patchs if p.get("statut") == "propose"]
    if en_attente:
        lignes.append(f"\n=== PATCHS EN ATTENTE === {len(en_attente)}")
        lignes += [f"   - {p['id']} : {p['chemin']} ({p['raison']})" for p in en_attente[:8]]
    aut = _charger_json(_AUTORISATIONS, [])
    aut_attente = [a for a in aut if a.get("statut") == "en_attente"]
    if aut_attente:
        lignes.append(f"\n=== AUTORISATIONS NOYAU REQUISES === {len(aut_attente)} (Jordan decide)")
        lignes += [f"   - {a['id']} : {a['chemin']} ({a['raison']})" for a in aut_attente[:8]]
    rb = _charger_json(_REBUILD, {"requis": False})
    if rb.get("requis"):
        lignes.append(f"\n=== REBUILD REQUIS === {len(rb.get('raisons', []))} changement(s) en attente de "
                      "'docker compose up -d --build'")
    return nettoyer("\n".join(lignes))


# ── INSPECTER / REPARER une capacite forgee ──────────────────────────────────────

def outil_inspecter_capacite(nom: str = "", **kw) -> str:
    """Lit DIRECTEMENT le code source d'une capacite forgee depuis le registre
    (data/cellules_forgees.json + data/cellules_forgees/<nom>.py). En UNE etape
    tu obtiens : signature, resume, code complet, verdict sandbox, ancrage.
    UTILISER EN PREMIER quand une capacite echoue — pas besoin de chercher dans
    tous les fichiers source. Sans nom -> liste toutes les capacites avec leur statut.
    params: {nom? (nom exact de la capacite)}"""
    _REGISTRE = os.path.join(_DATA, "cellules_forgees.json")
    _CELLS_DIR = os.path.join(_DATA, "cellules_forgees")
    if not nom:
        if not os.path.isfile(_REGISTRE):
            return "[inspecter_capacite] registre data/cellules_forgees.json introuvable"
        try:
            with open(_REGISTRE, encoding="utf-8") as f:
                reg = json.load(f)
        except Exception as e:
            return f"[inspecter_capacite] erreur lecture registre : {e}"
        if not reg:
            return "[inspecter_capacite] registre vide — aucune capacite forgee"
        lignes_out = ["Capacites forgees (registre data/cellules_forgees.json) :"]
        for n, v in (reg.items() if isinstance(reg, dict) else {str(i): v for i, v in enumerate(reg)}.items()):
            sig = v.get("signature") or v.get("nom") or n
            resume = v.get("description") or v.get("resume", "")[:60]
            verdict = v.get("verdict", "?")
            ancrage = v.get("ancrage", "manuel")
            lignes_out.append(f"  - {n} : {sig} | verdict={verdict} ancrage={ancrage} — {resume}")
        return nettoyer("\n".join(lignes_out))
    # Inspecter une capacite specifique.
    if not os.path.isfile(_REGISTRE):
        return "[inspecter_capacite] registre data/cellules_forgees.json introuvable"
    try:
        with open(_REGISTRE, encoding="utf-8") as f:
            reg = json.load(f)
    except Exception as e:
        return f"[inspecter_capacite] erreur lecture registre : {e}"
    entree = reg.get(nom) if isinstance(reg, dict) else None
    if entree is None:
        # Cherche par nom dans une liste ou comme valeur imbriquee.
        if isinstance(reg, list):
            for item in reg:
                if isinstance(item, dict) and item.get("nom") == nom:
                    entree = item
                    break
    if entree is None:
        disponibles = list(reg.keys()) if isinstance(reg, dict) else [str(i) for i in range(len(reg))]
        return f"[inspecter_capacite] '{nom}' absent du registre. Disponibles : {disponibles}"
    # Retourner les metadonnees.
    lignes_out = [f"CAPACITE : {nom}",
                  f"Signature : {entree.get('signature', '?')}",
                  f"Resume : {entree.get('description') or entree.get('resume', '?')}",
                  f"Verdict sandbox : {entree.get('verdict', '?')}",
                  f"Ancrage : {entree.get('ancrage', 'manuel')}",
                  f"Fichier : {entree.get('fichier', '?')}"]
    # Lire le code source si disponible.
    fichier = entree.get("fichier") or ""
    chemin_code = os.path.join(_CELLS_DIR, fichier) if fichier and not os.path.isabs(fichier) else fichier
    if chemin_code and os.path.isfile(chemin_code):
        try:
            with open(chemin_code, encoding="utf-8", errors="replace") as f:
                code = f.read()
            lignes_out.append(f"\nCODE SOURCE ({len(code.splitlines())} lignes) :\n{code[:6000]}")
            if len(code) > 6000:
                lignes_out.append("[…code tronque — fichier complet via lire_source]")
        except Exception as e:
            lignes_out.append(f"\nCode inaccessible : {e}")
    else:
        # Essayer le chemin direct nom.py
        alt = os.path.join(_CELLS_DIR, f"{nom}.py")
        if os.path.isfile(alt):
            try:
                with open(alt, encoding="utf-8", errors="replace") as f:
                    code = f.read()
                lignes_out.append(f"\nCODE SOURCE :\n{code[:6000]}")
            except Exception as e:
                lignes_out.append(f"\nCode inaccessible : {e}")
        else:
            lignes_out.append("\nPas de fichier source trouve — la capacite peut etre in-memory uniquement.")
    return nettoyer("\n".join(lignes_out))


# ── MEMOIRE INTER-SESSION : journal des erreurs et resolutions de l'Ingenieur ────

_JOURNAL = os.path.join(_DATA, "journal_agents.json")  # shared across all agents
_MAX_JOURNAL = 500   # entrees max (FIFO)


def _mots_cles_journal(texte: str) -> list[str]:
    """Extrait les mots-cles significatifs pour la recherche de similarite."""
    stop = {"le", "la", "les", "de", "du", "des", "un", "une", "et", "ou",
            "est", "sont", "dans", "sur", "avec", "pour", "par", "que", "qui",
            "ne", "pas", "je", "tu", "il", "on", "nous", "vous", "ils", "ca",
            "the", "a", "an", "is", "in", "of", "to", "for", "with", "that"}
    mots = re.findall(r"[a-z_]{3,}", texte.lower())
    return [m for m in mots if m not in stop][:20]


def _charger_journal() -> list:
    try:
        if os.path.isfile(_JOURNAL):
            with open(_JOURNAL, encoding="utf-8") as f:
                d = json.load(f)
                return d if isinstance(d, list) else []
    except Exception:
        pass
    return []


def _sauver_journal(entrees: list) -> None:
    try:
        os.makedirs(_DATA, exist_ok=True)
        with open(_JOURNAL, "w", encoding="utf-8") as f:
            json.dump(entrees[-_MAX_JOURNAL:], f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def outil_consulter_journal(situation: str = "", agent: str = "", **kw) -> str:
    """Memoire inter-session de NEOGEN : consulte le journal des erreurs, resolutions et
    decouvertes validees par TOUS les agents lors des sessions precedentes.
    UTILISER EN DEBUT DE TACHE pour ne pas re-decouvrir ce qui est deja connu.
    Retourne les 5 entrees les plus pertinentes avec resolution complete.
    params: {situation (description tache ou erreur), agent? (filtrer par agent: ingenieur|veilleur...)}"""
    entrees = _charger_journal()
    if agent:
        entrees = [e for e in entrees if e.get("agent", "") == agent]
    if not entrees:
        return "[consulter_journal] Journal vide — aucune experience enregistree pour l'instant."
    if not situation:
        recentes = sorted(entrees, key=lambda e: e.get("ts", 0), reverse=True)[:10]
        lignes = ["JOURNAL AGENTS — 10 dernieres entrees :"]
        for e in recentes:
            lignes.append(f"\n[{e.get('iso','?')}][{e.get('agent','?')}] {e.get('categorie','?')} — {e.get('contexte','')[:60]}")
            lignes.append(f"  Erreur : {e.get('erreur','')[:80]}")
            lignes.append(f"  Resolution : {e.get('resolution','')[:120]}")
        return nettoyer("\n".join(lignes))
    # Recherche par mots-cles.
    mots_req = set(_mots_cles_journal(situation))
    scores = []
    for e in entrees:
        mots_e = set(e.get("mots_cles", []) + _mots_cles_journal(
            e.get("contexte", "") + " " + e.get("erreur", "")))
        inter = len(mots_req & mots_e)
        union = len(mots_req | mots_e) or 1
        score = inter / union
        if score > 0.05:
            scores.append((score, e))
    scores.sort(key=lambda x: -x[0])
    if not scores:
        return f"[consulter_journal] Aucune experience similaire trouvee pour : '{situation[:80]}'"
    lignes = [f"MEMOIRE : {len(scores)} experience(s) similaire(s) trouvee(s) :"]
    for sc, e in scores[:5]:
        succes_str = "OK" if e.get("succes") else "ECHEC"
        lignes.append(f"\n[{e.get('iso','?')}][{succes_str}][score:{sc:.2f}] {e.get('categorie','?')}")
        lignes.append(f"  Contexte : {e.get('contexte','')[:100]}")
        lignes.append(f"  Erreur   : {e.get('erreur','')[:100]}")
        lignes.append(f"  Resolution: {e.get('resolution','')}")
    return nettoyer("\n".join(lignes))


def outil_journaliser(contexte: str = "", erreur: str = "", resolution: str = "",
                      succes: bool = True, categorie: str = "general",
                      agent: str = "", **kw) -> str:
    """Enregistre une erreur et sa resolution dans le journal permanent inter-session
    (data/journal_agents.json), accessible a TOUS les agents lors des sessions futures.
    UTILISER APRES chaque resolution reussie (ou echec notable) pour capitaliser.
    params: {contexte (situation), erreur (message exact), resolution (ce qui a marche),
    succes? (bool, defaut True), categorie? (capacite|navigation|patch|forge|invocation|general),
    agent? (nom de l'agent qui journalise, ex: ingenieur|veilleur|cerveau)}"""
    if not contexte or not resolution:
        return "[journaliser] contexte et resolution requis"
    import uuid as _uuid
    entrees = _charger_journal()
    mots = _mots_cles_journal(f"{contexte} {erreur} {resolution}")
    iso = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    entree = {
        "id": str(_uuid.uuid4())[:8],
        "ts": time.time(),
        "iso": iso,
        "agent": agent or "inconnu",
        "categorie": categorie or "general",
        "contexte": contexte[:300],
        "erreur": erreur[:300],
        "resolution": resolution[:600],
        "mots_cles": mots,
        "succes": bool(succes),
    }
    entrees.append(entree)
    _sauver_journal(entrees)
    nb = len(entrees)
    return nettoyer(f"[journaliser] OK — entree #{nb} enregistree ({iso}). "
                    f"Journal agents : {nb} experience(s) totale(s).")


# ── DELEGUER : creer un bebe-agent specialise ────────────────────────────────────

def outil_creer_bebe_agent(cle: str = "", titre: str = "", role: str = "",
                           outils: str = "", **kw) -> str:
    """Cree un bebe-agent specialise (data-driven, fusionne dans PROFILS) pour une tache recurrente.
    L'Ingenieur s'en sert pour deleguer durablement. params: {cle (slug), titre, role (mission),
    outils? (liste separee par virgules, ex: 'sante_appli,lire_source')}"""
    cle = re.sub(r"[^a-z0-9_]+", "_", (cle or "").lower()).strip("_")
    if not cle or not role:
        return "[creer_bebe_agent] cle et role requis"
    liste_outils = [o.strip() for o in (outils or "").split(",") if o.strip()]
    payload = {"cle": cle, "titre": titre or cle.replace("_", " ").title(),
               "role": role, "outils": liste_outils, "tier": "moyen"}
    try:
        import evolution_gouvernee as _eg
        r = _eg.proposer("agent", payload, titre=titre or cle,
                         raison="cree par l'Ingenieur pour une tache recurrente")
        import agent_core as _ac
        _ac.rafraichir_profils()
    except Exception as e:
        return f"[creer_bebe_agent] erreur : {e}"
    return nettoyer(f"[creer_bebe_agent] agent '{cle}' cree/maj : {r.get('detail', r.get('raison', 'ok'))} "
                    f"(outils: {', '.join(liste_outils) or 'aucun'})")


# ── Lecture des files de patchs/autorisations (pour les routes UI) ───────────────

def lister_patchs() -> list[dict]:
    return _charger_json(os.path.join(_PATCHES_DIR, "index.json"), [])


def patch(pid: str) -> dict | None:
    return _charger_json(os.path.join(_PATCHES_DIR, f"{pid}.json"), None)


def lister_autorisations() -> list[dict]:
    return _charger_json(_AUTORISATIONS, [])


def etat_rebuild() -> dict:
    return _charger_json(_REBUILD, {"requis": False, "raisons": []})


def marquer_rebuild_fait() -> dict:
    _sauver_json(_REBUILD, {"requis": False, "raisons": [], "ts": time.time()})
    return {"ok": True}


def decider_autorisation(aid: str, accordee: bool) -> dict:
    """Jordan accorde/refuse une demande de patch noyau. N'APPLIQUE PAS le patch (c'est Claude Code
    + rebuild qui l'appliquent apres accord) : marque la decision pour tracabilite."""
    aut = _charger_json(_AUTORISATIONS, [])
    trouve = None
    for a in aut:
        if a.get("id") == aid:
            a["statut"] = "accordee" if accordee else "refusee"
            a["decide_ts"] = time.time()
            trouve = a
    if trouve is None:
        return {"ok": False, "raison": "demande introuvable"}
    _sauver_json(_AUTORISATIONS, aut)
    return {"ok": True, "statut": trouve["statut"], "demande": trouve}


# ── Auto-verification offline (aucun reseau, forge mockee) ───────────────────────

if __name__ == "__main__":
    import sys
    import tempfile
    import types

    print("=" * 64)
    print("NEOGEN - OUTILS_DEV : auto-verification (offline)")
    print("=" * 64)

    _tmp = tempfile.mkdtemp()
    _DATA = _tmp
    _PATCHES_DIR = os.path.join(_tmp, "patches_proposes")
    _BACKUPS_DIR = os.path.join(_tmp, "backups_code")
    _AUTORISATIONS = os.path.join(_tmp, "autorisations_requises.json")
    _REBUILD = os.path.join(_tmp, "rebuild_requis.json")

    # 1. lire_source : lit un vrai module applicatif, refuse credentials.
    r = outil_lire_source("outils_dev.py", debut=1, lignes=3)
    assert "outils_dev.py" in r and "applicative" in r, r
    r = outil_lire_source("credentials/stripe.env")
    assert "mur absolu" in r, r
    print("  lire_source : applicatif OK, credentials refuse OK")

    # 2. chercher_code : trouve une definition connue.
    r = outil_chercher_code("def outil_forger_capacite", glob="*.py")
    assert "outils_dev.py" in r, r
    print("  chercher_code : trouve la definition OK")

    # 3. carte_code : classe noyau vs applicatif.
    r = outil_carte_code()
    assert "NOYAU" in r and "APPLICATIF" in r and "noyau.py" in r, r
    print("  carte_code : noyau vs applicatif OK")

    # 4. proposer_patch sur un fichier applicatif temporaire -> teste + propose.
    cible = os.path.join(BASE, "_tmp_patch_cible.py")
    with open(cible, "w", encoding="utf-8") as f:
        f.write("def f():\n    return 1\n")
    try:
        r = outil_proposer_patch("_tmp_patch_cible.py", "return 1", "return 2", raison="test")
        assert "syntaxe OK" in r and "patch_" in r, r
        assert lister_patchs(), "le patch doit etre indexe"
        assert etat_rebuild().get("requis"), "rebuild doit etre signale"
        # patch qui casse la syntaxe -> rejete.
        r2 = outil_proposer_patch("_tmp_patch_cible.py", "return 1", "return (", raison="casse")
        assert "REJETE" in r2, r2
        print("  proposer_patch : applicatif teste+propose OK, syntaxe cassee rejetee OK")
    finally:
        os.remove(cible)

    # 5. proposer_patch sur le NOYAU -> escalade autorisation, aucun patch.
    r = outil_proposer_patch("noyau.py", "import os", "import os, sys", raison="test mur")
    assert "MUR" in r and "autorisation" in r, r
    assert lister_autorisations(), "une demande d'autorisation doit exister"
    print("  proposer_patch : NOYAU -> escalade autorisation Jordan OK")

    # 6. forger_capacite (forge mockee) + ancrage.
    faux_fe = types.ModuleType("forge_evolution")
    faux_fe.forger = lambda besoin, titre="", job_id="": {
        "ok": True, "nom": "cap_test", "etat": "integree", "score": 88.0,
        "tentatives": 1, "verdict": "ACCEPTE"}
    sys.modules["forge_evolution"] = faux_fe
    faux_cf = types.ModuleType("capacites_forgees")
    faux_cf.definir_ancrage = lambda nom, point: {"ok": True, "nom": nom, "point_ancrage": point}
    sys.modules["capacites_forgees"] = faux_cf
    r = outil_forger_capacite("Cree une fonction qui additionne", titre="Addition",
                              ancrage="periodique")
    assert "integree" in r and "ANCREE" in r, r
    print("  forger_capacite : forge + ancrage automatique OK")

    # 7. decider_autorisation.
    aid = lister_autorisations()[0]["id"]
    d = decider_autorisation(aid, accordee=True)
    assert d["ok"] and d["statut"] == "accordee", d
    print("  decider_autorisation : accord trace OK")

    print("=" * 64)
    print("  TOUT VERT : yeux (lire/chercher/carte), mains (forger/ancrer/patch), garde-fous murs.")
    print("=" * 64)
