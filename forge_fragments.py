"""
NEOGEN - Forge de fragments : une idee devient un VRAI bloc HTML/CSS injecte a l'ecran.

Le chainon manquant entre la forge CSS (cosmetique seulement) et le patch direct de ui.py
(lourd, restart). Ici, une idee d'interface devient un fragment HTML+CSS reel (un panel, une
carte, une section de contenu, un tableau) injecte a un POINT D'ANCRAGE de la page. Contrairement
au CSS, ce sont de vrais elements nouveaux ; contrairement au patch ui.py, c'est data-driven donc
sans risque pour le moteur et reversible en un clic.

POURQUOI C'EST SUR :
  - Les fragments vivent dans data/fragments_ui.json -> cible deja autorisee par le noyau.
    On ne touche JAMAIS ui.py / app.js / les fichiers du noyau.
  - Chaque fragment passe par noyau.presentation_sure() (fail-closed) : aucun script distant,
    aucun acces reseau externe, aucune exfiltration (cookie/localStorage), aucun terme du noyau.
  - Les balises dangereuses (<script>, <iframe>, <form>, <link>, <meta>...) sont refusees.
  - Le fragment est injecte dans le NAVIGATEUR a une zone balisee ; le serveur ne l'execute pas.
  - Reversibilite totale : supprimer un fragment le retire instantanement (pas de restart).

PORTEE (charte proprio) :
  - PROPRIETAIRE -> apercu puis applique directement (de vrais changements visibles).
  - PUBLIC -> son idee REMONTE en proposition que le proprio valide ; jamais auto-applique
    sur la version publique (un fragment public est servi a tous les visiteurs).

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-26.
"""
from __future__ import annotations

import json
import os
import re
import time

import robustesse as rob
import noyau

BASE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(BASE, "data")
_STORE = os.path.join(_DATA, "fragments_ui.json")

MODEL = "claude-opus-4-8"
_MAX_HTML = 16000

# Zones d'ancrage autorisees (doivent correspondre aux marqueurs <!-- FORGE:zone --> de ui.py).
ZONES = {
    "cerveau":     "section Cerveaux (sous les agents)",
    "production":  "section Production (sous la grille)",
    "compte":      "section Compte",
    "analyse":     "section Analyse (sous les metriques)",
    "evolution":   "section Evolution (sous le hub)",
    "integrations": "section Integrations",
    "landing":     "page d'accueil (sous les cartes de sections)",
}

# Balises HTML refusees dans un fragment (defense en profondeur, en plus du noyau).
_BALISES_INTERDITES = ("<script", "<iframe", "<object", "<embed", "<form", "<link",
                       "<meta", "<base", "<template", "<svg", "<foreignobject")


# ── I/O store ─────────────────────────────────────────────────────────────────

def _charger() -> dict:
    if not os.path.exists(_STORE):
        return {}
    try:
        with open(_STORE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _sauver(data: dict) -> None:
    os.makedirs(_DATA, exist_ok=True)
    with open(_STORE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Assainissement (fail-closed) ────────────────────────────────────────────────

def _fragment_sain(html: str) -> tuple[bool, str]:
    """Verifie qu'un fragment HTML/CSS est sur : passe la charte du noyau + aucune balise
    dangereuse. En cas de doute -> refuse."""
    if not isinstance(html, str) or not html.strip():
        return False, "fragment vide"
    if len(html) > _MAX_HTML:
        return False, f"fragment trop long ({len(html)} > {_MAX_HTML})"
    ok, motif = noyau.presentation_sure(html)
    if not ok:
        return False, motif
    bas = html.lower()
    for balise in _BALISES_INTERDITES:
        if balise in bas:
            return False, f"balise interdite dans un fragment : '{balise}>' (charte proprio)"
    return True, "ok"


# ── Generation du fragment a partir de l'idee (LLM) ──────────────────────────────

def _client():
    import anthropic
    from credentials_loader import lire_cred
    cle = lire_cred("anthropic-api.env", "ANTHROPIC_API_KEY")
    if not cle:
        raise RuntimeError("cle Anthropic systeme introuvable (credentials/anthropic-api.env)")
    return anthropic.Anthropic(api_key=cle)


def _prompt_systeme(zone: str) -> str:
    return (
        "Tu es le forgeron de fragments de NEOGEN. On te donne une idee de bloc d'interface, "
        "tu produis un VRAI fragment HTML + CSS (inline dans une balise <style>) qui la realise. "
        "L'UI existe en DEUX themes (clair ET sombre, bascule utilisateur via la classe 'dark' "
        "sur <body>), moderne, en panneaux 'glass'. Le fragment sera injecte dans : " + zone + ".\n\n"
        "REGLES ABSOLUES (securite, charte du proprietaire) :\n"
        "- HTML + CSS UNIQUEMENT. AUCUN <script>, <iframe>, <form>, <link>, <meta>, <object>, <svg>.\n"
        "- AUCUN acces reseau : pas de url(http...), pas de @import, pas d'image distante, pas de fetch.\n"
        "- Pas d'attribut onclick/onload/onerror, pas de javascript:. Du contenu, pas du comportement.\n"
        "- Utilise les classes existantes quand c'est pertinent : 'panel', 'glass', 'card'. "
        "Reste sobre, lisible.\n"
        "- OBLIGATOIRE pour la compatibilite 2 themes : n'utilise JAMAIS de couleur de texte/fond "
        "fixe codee en dur (ex: color:#d8ffd8, background:rgba(0,16,6,.82)). Utilise les variables "
        "CSS du theme deja definies globalement : var(--txt) texte principal, var(--mut) texte "
        "secondaire/discret, var(--acc) couleur d'accent verte, var(--bg) fond de page, "
        "var(--line)/var(--brd) bordures discretes. Ces variables changent automatiquement de "
        "valeur selon le theme actif : ton fragment doit rester lisible et coherent dans les DEUX "
        "sans code special par theme. Seuls les elements decoratifs tres discrets (glow, ombre "
        "portee) peuvent utiliser une couleur fixe faiblement opaque (rgba(0,255,65,.05-.15)), "
        "jamais un fond ou un texte entier.\n"
        "- Encapsule TOUT dans un seul <div>. Le CSS dans un <style> en tete du fragment, "
        "scope tes classes avec un prefixe unique (ex: .frg-xxx) pour ne rien casser ailleurs.\n\n"
        "Reponds par un objet JSON STRICT, sans texte autour :\n"
        '{"html": "<le fragment complet : <style>...</style> + <div>...</div>>", '
        '"titre": "<titre court du bloc>", "explication": "<1-2 phrases : ce que ca ajoute>"}'
    )


def generer_apercu(idee: str, zone: str, *, _client_inj=None) -> dict:
    """Traduit une idee en fragment HTML+CSS reel (NON applique). Renvoie {ok, html, titre,
    explication, zone}. Le fragment est assaini avant d'etre renvoye. Ne leve jamais."""
    idee = (idee or "").strip()[:800]
    zone = (zone or "").strip().lower()
    if not idee:
        return {"ok": False, "raison": "idee vide"}
    if zone not in ZONES:
        return {"ok": False, "raison": f"zone '{zone}' inconnue (zones : {', '.join(ZONES)})"}
    try:
        cl = _client_inj or _client()
        res = cl.messages.create(
            model=MODEL, max_tokens=6000,
            system=_prompt_systeme(ZONES[zone]),
            messages=[{"role": "user", "content": f"Idee de bloc : {idee}"}],
        )
        brut = "".join(getattr(b, "text", "") or (b.get("text", "") if isinstance(b, dict) else "")
                       for b in (res.content if isinstance(res.content, list) else []))
        data = _parser_json(brut)
        if not data or not data.get("html"):
            return {"ok": False, "raison": "le modele n'a pas produit de fragment exploitable"}
        html = str(data["html"]).strip()
        ok, motif = _fragment_sain(html)
        if not ok:
            rob.journaliser(f"forge fragment : refuse ({motif})", "alerte", source="forge_fragments")
            return {"ok": False, "raison": motif}
        return {"ok": True, "html": html, "zone": zone,
                "titre": str(data.get("titre", "")).strip()[:80] or "Bloc",
                "explication": str(data.get("explication", "")).strip()[:300]}
    except Exception as e:
        rob.journaliser(f"forge fragment : generation echouee : {e}", "erreur", source="forge_fragments")
        return {"ok": False, "raison": f"generation echouee : {e}"}


def _parser_json(txt: str):
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
        i, j = s.find("{"), s.rfind("}")
        if 0 <= i < j:
            try:
                return json.loads(s[i:j + 1])
            except Exception:
                return None
    return None


def _slug(txt: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (txt or "").lower()).strip("_")
    return s[:32] or "frag"


# ── Application / lecture / suppression ──────────────────────────────────────────

def appliquer(html: str, zone: str, *, titre: str = "", user: dict | None = None,
              frag_id: str | None = None) -> dict:
    """Applique le fragment (proprio) ou le remonte en proposition (public). Re-assainit.
    Si frag_id fourni et existant -> mise a jour + bump version. Sinon -> creation v1.
    Ne leve jamais."""
    with rob.garde("appliquer fragment", source="forge_fragments"):
        zone = (zone or "").strip().lower()
        if zone not in ZONES:
            return {"ok": False, "raison": f"zone '{zone}' inconnue"}
        ok, motif = _fragment_sain(html)
        if not ok:
            return {"ok": False, "raison": motif}

        # Garde du noyau : cible data/ (autorisee), defense en profondeur.
        autorise, motif_n = noyau.autoriser({
            "type": "section", "cible": "data/fragments_ui.json",
            "payload": {"zone": zone, "html_len": len(html)},
            "titre": titre or "fragment interface", "raison": "forge fragment"})
        if not autorise:
            return {"ok": False, "raison": motif_n}

        portee = noyau.portee("section", user)
        # PUBLIC -> remonte en proposition, jamais auto-applique sur la version publique.
        if portee == "remonte" or not noyau.est_admin(user):
            try:
                import proposeur_hub
                prop = proposeur_hub.proposer_depuis_evolution({
                    "type": "section", "payload": {"html": html, "zone": zone},
                    "cible": "data/fragments_ui.json",
                    "titre": titre or "Fragment interface (public)",
                    "raison": "propose par un utilisateur via la forge de fragments"})
                return {"ok": True, "portee": "remonte", "proposition": prop,
                        "raison": "remonte en proposition (a valider par le proprio)"}
            except Exception as e:
                return {"ok": False, "raison": f"remontee echouee : {e}"}

        # PROPRIO -> persiste dans la zone.
        store = _charger()
        liste = store.setdefault(zone, [])
        # Déduplication : si un fragment avec le même titre (slug) existe dans la zone,
        # réutiliser son ID (mise à jour) plutôt que créer un doublon timestamp.
        slug_titre = _slug(titre) if titre else ""
        fid = frag_id or next(
            (f["id"] for f in liste if _slug(f.get("titre", "")) == slug_titre),
            slug_titre + "_" + format(int(time.time()) % 100000, "x")
        )
        existant = next((f for f in liste if f.get("id") == fid), None)
        if existant:
            existant["version"] = _bump_version(existant.get("version") or "1")
            existant["html"] = html
            existant["titre"] = titre[:80] or existant.get("titre", "Bloc")
            existant["maj_le"] = time.time()
            action = f"mis a jour v{existant['version']}"
        else:
            liste.append({"id": fid, "titre": titre[:80] or "Bloc", "html": html,
                          "zone": zone, "actif": True, "version": "1", "ts": time.time()})
            action = "cree v1"
        _sauver(store)
        try:
            import evolution_gouvernee
            evolution_gouvernee._notifier_generation(
                "section", titre or f"fragment {zone}", f"fragment '{fid}' {action} (zone {zone})")
        except Exception:
            pass
        # CONSCIENCE : un fragment applique est une capacite d'interface VIVANTE (integree a l'ecran).
        try:
            import conscience
            conscience.enregistrer(f"frag:{zone}:{fid}", type="interface",
                                   titre=titre or f"Bloc {zone}", statut="integree",
                                   note=f"fragment {action} en zone {zone}", store="fragments_ui.json",
                                   hook_point=f"UI/zone:{zone}", consomme_par=["ui (injection HTML)"])
        except Exception:
            pass
        rob.journaliser(f"forge fragment : '{fid}' {action} (zone {zone})", "succes",
                        source="forge_fragments")
        return {"ok": True, "portee": "complet", "id": fid, "zone": zone, "action": action}
    return {"ok": False, "raison": "erreur capturee (voir journal)"}


def _bump_version(v: str) -> str:
    s = str(v).lstrip("v")
    if "." not in s:
        return s + ".1"
    parts = s.split(".")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)
    except (ValueError, IndexError):
        return s + ".1"


def fragments_pour_zone(zone: str) -> str:
    """HTML concatene des fragments ACTIFS d'une zone (pour injection a l'ancre). Vide si aucun.
    Re-assaini a la lecture (defense en profondeur : un store altere ne passe pas)."""
    store = _charger()
    out = []
    for f in store.get((zone or "").lower(), []):
        if not f.get("actif", True):
            continue
        html = f.get("html", "")
        ok, _ = _fragment_sain(html)
        if ok:
            out.append(f'<!-- fragment:{f.get("id","")} -->\n{html}')
    return "\n".join(out)


def lister() -> dict:
    """Tous les fragments par zone (sans le HTML complet : metadonnees pour l'UI de pilotage)."""
    store = _charger()
    return {z: [{"id": f.get("id"), "titre": f.get("titre"), "zone": z,
                 "actif": f.get("actif", True), "version": f.get("version", "1"),
                 "taille": len(f.get("html", ""))}
                for f in frags]
            for z, frags in store.items()}


def fragment(zone: str, frag_id: str) -> dict | None:
    """Un fragment complet (avec HTML) pour previsualisation/edition."""
    for f in _charger().get((zone or "").lower(), []):
        if f.get("id") == frag_id:
            return f
    return None


def basculer(zone: str, frag_id: str) -> dict:
    """Active/desactive un fragment (sans le supprimer). Reversibilite douce."""
    store = _charger()
    for f in store.get((zone or "").lower(), []):
        if f.get("id") == frag_id:
            f["actif"] = not f.get("actif", True)
            _sauver(store)
            return {"ok": True, "actif": f["actif"]}
    return {"ok": False, "raison": "fragment introuvable"}


def supprimer(zone: str, frag_id: str) -> dict:
    """Retire un fragment definitivement (rollback instantane, pas de restart)."""
    store = _charger()
    z = (zone or "").lower()
    avant = len(store.get(z, []))
    store[z] = [f for f in store.get(z, []) if f.get("id") != frag_id]
    if len(store[z]) == avant:
        return {"ok": False, "raison": "fragment introuvable"}
    _sauver(store)
    # CONSCIENCE : la capacite d'interface n'est plus vivante -> obsolete (coherence honnete).
    try:
        import conscience
        if conscience.obtenir(f"frag:{z}:{frag_id}"):
            conscience.maj_statut(f"frag:{z}:{frag_id}", "obsolete", note="fragment supprime de l'ecran")
    except Exception:
        pass
    rob.journaliser(f"forge fragment : '{frag_id}' supprime (zone {z})", "info", source="forge_fragments")
    return {"ok": True}


# ── Auto-verification offline (LLM mocke, aucun reseau) ──────────────────────────

if __name__ == "__main__":
    import tempfile

    print("=" * 64)
    print("NEOGEN - FORGE FRAGMENTS : auto-verification (offline)")
    print("=" * 64)

    _DATA = tempfile.mkdtemp()
    _STORE = os.path.join(_DATA, "fragments_ui.json")
    os.environ["NEOGEN_OWNER_UNLIMITED"] = "1"

    class _Bloc:
        def __init__(self, t): self.text = t
    class _Res:
        def __init__(self, t): self.content = [_Bloc(t)]
    class _Msgs:
        def __init__(self, p): self._p = p
        def create(self, **kw): return _Res(self._p)
    class _Client:
        def __init__(self, p): self.messages = _Msgs(p)

    # 1. Fragment propre -> apercu OK.
    bon = '{"html": "<style>.frg-x{padding:10px}</style><div class=\\"panel glass frg-x\\"><h3>Carte vivante</h3><p>Etat du systeme.</p></div>", "titre": "Carte vivante", "explication": "Ajoute un panel d etat."}'
    ap = generer_apercu("ajoute un panel carte vivante", "evolution", _client_inj=_Client(bon))
    assert ap["ok"] and "panel" in ap["html"], ap
    print("  apercu fragment propre OK ->", ap["titre"])

    # 2. Application proprio -> persiste + injectable.
    r = appliquer(ap["html"], "evolution", titre="Carte vivante", user={"role": "admin"})
    assert r["ok"] and r["portee"] == "complet", r
    inj = fragments_pour_zone("evolution")
    assert "Carte vivante" in inj, "le fragment doit etre injectable"
    print("  application proprio OK -> fragment injectable dans la zone")

    # 3. Re-application (meme id) -> bump version.
    r2 = appliquer(ap["html"], "evolution", titre="Carte vivante", user={"role": "admin"}, frag_id=r["id"])
    assert r2["ok"] and r2["action"].startswith("mis a jour v1.1"), r2
    print("  re-application -> bump", r2["action"])

    # 4. Fragment avec <script> -> REFUSE.
    mauvais = '{"html": "<div><script>alert(1)</script></div>", "titre": "x", "explication": "x"}'
    ap2 = generer_apercu("mets un script", "evolution", _client_inj=_Client(mauvais))
    assert not ap2["ok"] and "balise interdite" in ap2["raison"], ap2
    print("  fragment avec <script> REFUSE ->", ap2["raison"])

    # 5. Fragment avec fetch reseau -> REFUSE.
    mauvais2 = '{"html": "<div onclick=\\"fetch(\'http://evil.test\')\\">x</div>", "titre": "x", "explication": "x"}'
    ap3 = generer_apercu("exfiltre", "evolution", _client_inj=_Client(mauvais2))
    assert not ap3["ok"], ap3
    print("  fragment avec reseau externe REFUSE ->", ap3["raison"])

    # 6. Suppression -> rollback instantane.
    assert supprimer("evolution", r["id"])["ok"]
    assert fragments_pour_zone("evolution") == "", "la zone doit etre vide apres suppression"
    print("  suppression -> rollback instantane OK")

    print("=" * 64)
    print("  TOUT VERT : la forge de fragments est sure, versionnee et reversible.")
    print("=" * 64)
