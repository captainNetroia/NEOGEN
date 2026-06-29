"""
NEOGEN - Forge d'interface : une idee d'interface devient du VRAI CSS, applique a l'ecran.

Probleme resolu : les idees d'INTERFACE (« replier les listes trop longues », « agrandir le
chat des agents », « rendre plus compact ») n'avaient AUCUN effet. La forge de code genere des
fonctions Python ; le data-driven esthetique n'etait pas consomme. Ici, une idee d'interface est
traduite par le LLM en CSS reel, assaini, puis applique via un override charge par l'ecran.

POURQUOI C'EST SUR (le gardien laisse passer sans faille) :
  - L'override vit dans data/ui_overrides.css -> cible deja autorisee par noyau.autoriser().
    On ne touche JAMAIS ui.py / app.js / les 23 fichiers du noyau.
  - Le CSS est assaini : aucun acces reseau (url() externe, @import), aucun script. Au pire
    l'affichage est moche -> bouton « reinitialiser » qui vide l'override. Reversible.
  - Le CSS s'applique dans le NAVIGATEUR, pas sur le serveur : zero risque pour le noyau/les donnees.

PORTEE (admin vs public, decision Jordan) :
  - ADMIN -> aperçu puis applique directement a SON interface (et pourra publier).
  - PUBLIC -> son idee REMONTE en proposition (telemetrie) que l'admin verifie et valide ;
    le public ne s'auto-applique jamais un CSS sur la version publique.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-26.
"""
from __future__ import annotations

import os
import re

import robustesse as rob
import user_namespace as _ns

BASE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(BASE, "data")
_OVERRIDES = os.path.join(_DATA, "ui_overrides.css")  # base (maître) — défaut pour l'owner


def _overrides_path(user: dict | None = None) -> str:
    """Chemin du CSS d'override pour cet utilisateur.
    Owner/maître → data/ui_overrides.css ; utilisateur web → data/users/{id}/ui_overrides.css."""
    if _ns.a_un_sac(user):
        return _ns.data_path(user, "ui_overrides.css")
    return _OVERRIDES


def _cible_relative(user: dict | None = None) -> str:
    """Cible relative (pour noyau.autoriser) : reste sous data/ dans tous les cas."""
    chemin = _overrides_path(user)
    rel = os.path.relpath(chemin, BASE).replace("\\", "/")
    return rel

MODEL = "claude-opus-4-8"
_MAX_CSS = 12000  # un override raisonnable ; au-dela on refuse (anti-emballement)

# Selecteurs que le CSS peut viser, documentes pour le LLM (vocabulaire reel de l'UI).
# Couvre TOUTES les listes de l'app : si une liste manque ici, l'app ne peut pas la reorganiser.
_SELECTEURS = {
    "#pensee-list": "liste des pensees (onglet Evolution) — TRES longue, a compacter en priorite",
    "#hub-props-list": "liste des propositions d'evolution",
    "#evo-changelog": "liste des changements de la generation (onglet Evolution) — longue",
    "#evo-cellules": "liste des cellules de code forgees",
    "#produit-grid": "GRILLE des produits/creations (section Production) — longue, scroll interminable",
    "#skills-list": "liste des competences apprises (section Cerveaux) — longue",
    ".agent-chat-log": "zone de messages d'un chat d'agent (agrandir = min-height/height)",
    ".card, .creation-card": "une carte de creation/produit",
    ".panel": "un panneau de section",
    ".section": "une section entiere",
    "body": "toute la page (densite globale)",
}

# Termes interdits dans le CSS (fail-closed) : reseau, script, injection.
_TERMES_INTERDITS = ("@import", "url(http", "url('http", 'url("http', "url(//", "url(data:",
                     "expression(", "javascript:", "behavior:", "-moz-binding", "</style",
                     "<script", "@charset", "@namespace")


# ── Assainissement du CSS (fail-closed) ─────────────────────────────────────────

def _css_sain(css: str) -> tuple[bool, str]:
    """Verifie qu'un CSS ne contient aucun acces reseau ni script. En cas de doute -> refuse."""
    if not isinstance(css, str) or not css.strip():
        return False, "CSS vide"
    if len(css) > _MAX_CSS:
        return False, f"CSS trop long ({len(css)} > {_MAX_CSS})"
    bas = css.lower()
    for terme in _TERMES_INTERDITS:
        if terme in bas:
            return False, f"terme interdit dans le CSS : '{terme}' (reseau/script proscrit)"
    # url() n'est tolere que vide ou relatif ; tout url( restant suspect -> refus prudent.
    for m in re.findall(r"url\(([^)]*)\)", bas):
        cible = m.strip().strip('"').strip("'")
        if cible and not cible.startswith(("#", "/savoir", "data:image/svg")):
            return False, f"url() non autorise dans le CSS : '{cible[:40]}'"
    return True, "ok"


# ── Generation du CSS a partir de l'idee (LLM) ───────────────────────────────────

def _client():
    """Client Anthropic avec la cle SYSTEME (jamais en clair). Repli explicite si absente."""
    import anthropic
    from credentials_loader import lire_cred
    cle = lire_cred("anthropic-api.env", "ANTHROPIC_API_KEY")
    if not cle:
        raise RuntimeError("cle Anthropic systeme introuvable (credentials/anthropic-api.env)")
    return anthropic.Anthropic(api_key=cle)


def _prompt_systeme() -> str:
    sels = "\n".join(f"  {s} : {d}" for s, d in _SELECTEURS.items())
    return (
        "Tu es le forgeron d'interface de NEOGEN. On te donne une idee d'amelioration de "
        "l'interface, tu produis du CSS reel qui la realise. L'UI est sombre, moderne, en panneaux.\n\n"
        f"SELECTEURS DISPONIBLES (n'en vise pas d'autres) :\n{sels}\n\n"
        "REGLES ABSOLUES :\n"
        "- CSS pur uniquement. AUCUN acces reseau : pas de @import, pas de url(http...), pas de "
        "url() externe, pas d'image distante. Pas de script, pas d'expression().\n"
        "- Si l'idee parle de listes trop longues / scroll interminable / interface indigeste : "
        "applique max-height (240-360px) + overflow-y:auto a TOUS les conteneurs de listes a la fois "
        "(#pensee-list, #hub-props-list, #evo-changelog, #evo-cellules, #produit-grid, #skills-list), "
        "pour que CHAQUE liste devienne une zone scrollable compacte. N'en oublie aucune.\n"
        "- Pour 'agrandir le chat' : augmente min-height/height de .agent-chat-log.\n"
        "- Pour 'plus compact / dense' : reduis paddings et margins des .card et des enfants de listes.\n"
        "- Reste sobre et lisible (l'UI est sombre : evite les fonds clairs agressifs).\n"
        "- Ne casse pas la mise en page : prefere des ajustements cibles.\n\n"
        "Reponds par un objet JSON STRICT, sans texte autour :\n"
        '{"css": "<le CSS, sans balise style>", "explication": "<1-2 phrases : ce que ca change visuellement>"}'
    )


def generer_apercu(idee: str, *, _client_inj=None) -> dict:
    """Traduit une idee d'interface en CSS reel (NON applique). Renvoie {ok, css, explication}.
    Le CSS est assaini avant d'etre renvoye. Ne leve jamais."""
    idee = (idee or "").strip()[:600]
    if not idee:
        return {"ok": False, "raison": "idee vide"}
    try:
        import json
        cl = _client_inj or _client()
        res = cl.messages.create(
            model=MODEL, max_tokens=4000,
            system=_prompt_systeme(),
            messages=[{"role": "user", "content": f"Idee d'interface : {idee}"}],
        )
        brut = "".join(getattr(b, "text", "") or (b.get("text", "") if isinstance(b, dict) else "")
                       for b in (res.content if isinstance(res.content, list) else []))
        data = _parser_json(brut)
        if not data or not data.get("css"):
            return {"ok": False, "raison": "le modele n'a pas produit de CSS exploitable"}
        css = str(data["css"]).strip()
        ok, motif = _css_sain(css)
        if not ok:
            rob.journaliser(f"forge interface : CSS refuse ({motif})", "alerte", source="forge_interface")
            return {"ok": False, "raison": motif}
        return {"ok": True, "css": css,
                "explication": str(data.get("explication", "")).strip()[:300]}
    except Exception as e:
        rob.journaliser(f"forge interface : generation echouee : {e}", "erreur", source="forge_interface")
        return {"ok": False, "raison": f"generation echouee : {e}"}


def _parser_json(txt: str):
    import json
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


# ── Blocs nommés : plusieurs CSS coexistent sans s'écraser ───────────────────────

_BLOC_START = "/* NEOGEN-BLOC:{} START */"
_BLOC_END   = "/* NEOGEN-BLOC:{} END */"
_BLOC_RE    = re.compile(
    r"/\* NEOGEN-BLOC:([^\s*]+) START \*/\n?(.*?)\n?/\* NEOGEN-BLOC:\1 END \*/",
    re.DOTALL
)


def _slug_titre(titre: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", titre.lower())[:40].strip("_") or "bloc"


def _lire_blocs(css: str) -> dict:
    """Parse les blocs nommés ; le reste (CSS legacy sans marqueurs) est stocké sous '_legacy'."""
    blocs: dict[str, str] = {}
    for m in _BLOC_RE.finditer(css):
        blocs[m.group(1)] = m.group(2).strip()
    restant = _BLOC_RE.sub("", css).strip()
    if restant:
        blocs["_legacy"] = restant
    return blocs


def _fusionner_blocs(blocs: dict) -> str:
    """Reconstruit un CSS continu à partir des blocs nommés."""
    parts = []
    for nom, contenu in blocs.items():
        if nom == "_legacy":
            parts.append(contenu)
        else:
            parts.append(f"{_BLOC_START.format(nom)}\n{contenu}\n{_BLOC_END.format(nom)}")
    return "\n\n".join(p for p in parts if p)


def _sauvegarder_override(chemin: str) -> None:
    """Backup du CSS courant avant écrasement (<chemin>_backup.css)."""
    try:
        if os.path.exists(chemin):
            backup = chemin.replace(".css", "_backup.css")
            import shutil
            shutil.copy2(chemin, backup)
    except Exception:
        pass


# ── Application / lecture / reinitialisation ─────────────────────────────────────

def overrides_actuels(user: dict | None = None) -> str:
    """Le CSS d'override courant pour cet utilisateur (vide si aucun).
    Owner → CSS maître ; utilisateur web → CSS de SON sac (isolé des autres)."""
    chemin = _overrides_path(user)
    try:
        if os.path.exists(chemin):
            with open(chemin, encoding="utf-8") as f:
                return f.read()
    except Exception:
        pass
    return ""


def appliquer(css: str, *, user: dict | None = None, titre: str = "") -> dict:
    """Applique le CSS à l'interface de l'utilisateur. Re-assainit (defense en profondeur).
    Owner → interface maître (data/) ; utilisateur web → SON sac (data/users/{id}/), isolé.
    Le CSS s'applique dans le navigateur uniquement (jamais le serveur). Renvoie {ok, portee, ...}.
    Ne leve jamais."""
    with rob.garde("appliquer interface", source="forge_interface"):
        ok, motif = _css_sain(css)
        if not ok:
            return {"ok": False, "raison": motif}

        # Garde du noyau : la cible reste sous data/ (sac de l'utilisateur ou base) ; fail-closed.
        import noyau
        cible = _cible_relative(user)
        autorise, motif_n = noyau.autoriser({
            "type": "esthetique", "cible": cible,
            "payload": {"css_len": len(css)}, "titre": titre or "evolution interface",
            "raison": "forge interface"})
        if not autorise:
            return {"ok": False, "raison": motif_n}

        chemin = _overrides_path(user)
        a_sac = _ns.a_un_sac(user)
        # Application (additivement via blocs nommés) — sur le sac de l'utilisateur OU sur le maître.
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        _sauvegarder_override(chemin)
        blocs = _lire_blocs(overrides_actuels(user))
        cle = _slug_titre(titre) if titre else f"bloc_{abs(hash(css)) % 100000}"
        blocs[cle] = css
        css_final = _fusionner_blocs(blocs)
        with open(chemin, "w", encoding="utf-8") as f:
            f.write(css_final)
        if not a_sac:
            # Seules les évolutions du MAÎTRE alimentent le changelog d'évolution de NEOGEN.
            try:
                import evolution_gouvernee
                evolution_gouvernee._notifier_generation(
                    "interface", titre or "evolution interface", f"override CSS applique ({len(css)} car.)")
            except Exception:
                pass
        rob.journaliser(
            f"forge interface : override applique ({len(css)} car., {'sac user' if a_sac else 'maitre'})",
            "succes", source="forge_interface")
        return {"ok": True, "portee": "sac" if a_sac else "complet", "applique": True}
    return {"ok": False, "raison": "erreur capturee (voir journal)"}


def reinitialiser(user: dict | None = None) -> dict:
    """Vide l'override d'interface de l'utilisateur : retour a l'apparence d'origine. Reversible."""
    try:
        chemin = _overrides_path(user)
        if os.path.exists(chemin):
            os.remove(chemin)
        rob.journaliser("forge interface : override reinitialise", "info", source="forge_interface")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "raison": str(e)}


# ── Auto-verification offline (LLM mocke, aucun reseau) ──────────────────────────

if __name__ == "__main__":
    import tempfile

    print("=" * 64)
    print("NEOGEN - FORGE INTERFACE : auto-verification (offline)")
    print("=" * 64)

    _tmp = tempfile.mkdtemp()
    _DATA = _tmp
    _OVERRIDES = os.path.join(_tmp, "ui_overrides.css")
    os.environ["NEOGEN_OWNER_UNLIMITED"] = "1"  # se faire passer pour admin dans le test
    # Le test tourne hors de l'arbo data/ : on route les chemins vers le temp et on
    # fournit une cible maître valide (data/...) pour que noyau.autoriser passe offline.
    _sacs_tmp = {}
    def _overrides_path(user=None):
        if user and user.get("id") and not _ns.est_owner(user):
            p = os.path.join(_tmp, "users", user["id"], "ui_overrides.css")
            _sacs_tmp[user["id"]] = p
            return p
        return _OVERRIDES
    def _cible_relative(user=None):
        if user and user.get("id") and not _ns.est_owner(user):
            return f"data/users/{user['id']}/ui_overrides.css"
        return "data/ui_overrides.css"

    class _Bloc:
        def __init__(self, t): self.text = t
    class _Res:
        def __init__(self, t): self.content = [_Bloc(t)]
    class _Msgs:
        def __init__(self, payload): self._p = payload
        def create(self, **kw): return _Res(self._p)
    class _Client:
        def __init__(self, payload): self.messages = _Msgs(payload)

    # 1. CSS propre -> apercu OK + assainissement passe.
    bon = '{"css": "#pensee-list{max-height:340px;overflow:auto}.agent-chat-log{min-height:520px}", "explication": "Listes compactes et chat plus grand."}'
    ap = generer_apercu("replie les listes trop longues et agrandis le chat", _client_inj=_Client(bon))
    assert ap["ok"] and "max-height" in ap["css"], ap
    print("  apercu CSS propre OK ->", ap["explication"])

    # 2. Application admin -> override ecrit.
    r = appliquer(ap["css"], user={"role": "admin"}, titre="test")
    assert r["ok"] and r["portee"] == "complet", r
    assert "max-height" in overrides_actuels(), "l'override doit etre persiste"
    print("  application admin OK -> override persiste")

    # 3. CSS avec acces reseau -> REFUSE (fail-closed).
    mauvais = '{"css": "body{background:url(http://evil.test/x.png)}", "explication": "x"}'
    ap2 = generer_apercu("mets une image de fond distante", _client_inj=_Client(mauvais))
    assert not ap2["ok"] and "url" in ap2["raison"].lower(), ap2
    print("  CSS avec reseau REFUSE ->", ap2["raison"])

    # 4. Reinitialisation -> override vide.
    assert reinitialiser()["ok"] and overrides_actuels() == ""
    print("  reinitialisation OK -> retour a l'origine")

    # 5. @import refuse aussi.
    ok, motif = _css_sain("@import url(x.css); body{color:red}")
    assert not ok, motif
    print("  @import refuse ->", motif)

    # 6. ISOLATION PAR SAC : un user web applique son CSS sans toucher le maître ni les autres.
    os.environ["NEOGEN_OWNER_UNLIMITED"] = "0"
    os.environ["NEOGEN_OWNER_EMAIL"] = "admin@example.com"
    alice = {"id": "alice", "email": "alice@x.com"}
    bob = {"id": "bob", "email": "bob@x.com"}
    ra = appliquer("body{--ntr:1}#pensee-list{max-height:200px}", user=alice, titre="alice-style")
    assert ra["ok"] and ra["portee"] == "sac", ra
    assert "max-height:200px" in overrides_actuels(alice), "alice doit voir SON css"
    assert overrides_actuels(bob) == "", "bob ne doit PAS voir le css d'alice (isolation)"
    assert overrides_actuels({"email": "admin@example.com"}) == "", "le maitre intact"
    print("  isolation par sac OK -> alice voit son CSS, bob/maitre intacts")

    print("=" * 64)
    print("  TOUT VERT : la forge d'interface est sure, isolee et reversible.")
    print("=" * 64)
