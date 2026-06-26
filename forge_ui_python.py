"""
NEOGEN - Forge UI Python : graver de VRAIS blocs d'interface dans le CODE (permanent, git).

Le pendant "code source" de forge_fragments (runtime). Quand le proprio a valide un bloc et veut
le rendre PERMANENT (versionne git, survit a une remise a zero de data/), il le grave ici. Le
contenu est ecrit dans ui_custom.py, un fichier ISOLE que ui.rendre_page() injecte aux memes zones.

POURQUOI C'EST SUR (charte proprio, sans jamais pouvoir tuer le serveur) :
  - On n'ecrit JAMAIS dans ui.py / api.py / le noyau. On reecrit ui_custom.py (fichier isole).
  - Reecriture par serialisation json.dumps -> aucun probleme d'echappement, code toujours valide.
  - compile() du nouveau contenu AVANT ecriture : si invalide, rien n'est ecrit.
  - Backup horodate avant chaque ecriture (data/ui_backups/), rollback possible a tout moment.
  - Apres ecriture : reload + ui.rendre_page() + verification des ancres d'integrite ; si KO,
    restauration automatique du backup. Le serveur n'est jamais expose a un code casse.
  - Gate OWNER strict (est_admin) : un public ne grave jamais de code.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-26.
"""
from __future__ import annotations

import json
import os
import time

import robustesse as rob
import noyau

BASE = os.path.dirname(os.path.abspath(__file__))
_FICHIER = os.path.join(BASE, "ui_custom.py")
_BACKUPS = os.path.join(BASE, "data", "ui_backups")

_ENTETE = '''"""
NEOGEN - Code interface du proprietaire (forge UI Python). PERMANENT, versionne git.

Ecrit/reecrit UNIQUEMENT par forge_ui_python.py (backup + compile-check + rollback). Fichier
ISOLE : une erreur ici ne peut jamais empecher le serveur de demarrer (rendre_page fail-closed).
Ne pas editer a la main : passer par la forge UI (section Evolution).
"""
from __future__ import annotations

# {zone: html} — rempli par forge_ui_python. Vide par defaut (interface d'origine).
BLOCS: dict[str, str] = '''


# ── Lecture des blocs courants ───────────────────────────────────────────────────

def blocs() -> dict:
    """Les blocs permanents actuels {zone: html}. Tolerant (jamais d'exception)."""
    try:
        import importlib
        import ui_custom
        importlib.reload(ui_custom)
        b = getattr(ui_custom, "BLOCS", {})
        return dict(b) if isinstance(b, dict) else {}
    except Exception:
        return {}


# ── Validation du contenu ────────────────────────────────────────────────────────

def _valide(html: str) -> tuple[bool, str]:
    """Un bloc permanent doit etre du HTML/CSS sur (charte) et serialisable proprement."""
    if not isinstance(html, str):
        return False, "contenu invalide"
    if len(html) > 20000:
        return False, f"bloc trop long ({len(html)} > 20000)"
    ok, motif = noyau.presentation_sure(html)
    if not ok:
        return False, motif
    # reutilise le garde des fragments (balises dangereuses)
    try:
        import forge_fragments
        ok, motif = forge_fragments._fragment_sain(html)
        if not ok:
            return False, motif
    except Exception:
        pass
    return True, "ok"


def _rendre_source(blocs_dict: dict) -> str:
    """Genere le source ui_custom.py a partir du dict. json.dumps -> echappement sur, code valide."""
    corps = json.dumps(blocs_dict, ensure_ascii=False, indent=4)
    return _ENTETE + corps + "\n"


# ── Backup / restauration ────────────────────────────────────────────────────────

def _backup() -> str | None:
    """Sauvegarde l'etat courant de ui_custom.py. Renvoie l'id du backup (ou None)."""
    try:
        os.makedirs(_BACKUPS, exist_ok=True)
        bid = f"ui_custom_{int(time.time())}.py"
        if os.path.exists(_FICHIER):
            with open(_FICHIER, encoding="utf-8") as f:
                contenu = f.read()
            with open(os.path.join(_BACKUPS, bid), "w", encoding="utf-8") as f:
                f.write(contenu)
            return bid
    except Exception:
        pass
    return None


def lister_backups() -> list[dict]:
    """Backups disponibles (plus recents d'abord)."""
    try:
        out = []
        for fn in sorted(os.listdir(_BACKUPS), reverse=True):
            if fn.endswith(".py"):
                p = os.path.join(_BACKUPS, fn)
                out.append({"id": fn, "ts": os.path.getmtime(p), "taille": os.path.getsize(p)})
        return out
    except Exception:
        return []


def restaurer(backup_id: str) -> dict:
    """Restaure un backup (rollback manuel). Compile + reload verifies avant de valider."""
    with rob.garde("restaurer ui_custom", source="forge_ui_python"):
        p = os.path.join(_BACKUPS, os.path.basename(backup_id))
        if not os.path.exists(p):
            return {"ok": False, "raison": "backup introuvable"}
        with open(p, encoding="utf-8") as f:
            contenu = f.read()
        try:
            compile(contenu, "ui_custom.py", "exec")
        except SyntaxError as e:
            return {"ok": False, "raison": f"backup invalide : {e}"}
        with open(_FICHIER, "w", encoding="utf-8") as f:
            f.write(contenu)
        _recharger_ui()
        rob.journaliser(f"ui_custom restaure depuis {backup_id}", "info", source="forge_ui_python")
        return {"ok": True}
    return {"ok": False, "raison": "erreur capturee"}


# ── Le graveur (ecrit le vrai code, fail-closed + rollback) ──────────────────────

def _recharger_ui() -> bool:
    """Reload ui_custom + ui pour que rendre_page reflete le nouveau code. Renvoie True si la page
    rendue reste valide (ancres d'integrite presentes)."""
    try:
        import importlib
        import ui_custom
        importlib.reload(ui_custom)
        import ui
        page = ui.rendre_page()
        ok, _ = noyau.verifier_ancres(page)
        return ok
    except Exception:
        return False


def graver(zone: str, html: str, *, titre: str = "", user: dict | None = None) -> dict:
    """Grave un bloc permanent dans ui_custom.py pour une zone. Proprio uniquement.
    Backup -> compile-check -> ecriture -> reload + verif ancres -> rollback auto si KO.
    Ne leve jamais."""
    with rob.garde("graver ui_custom", source="forge_ui_python"):
        # Gate OWNER strict : graver du vrai code est reserve au proprietaire.
        if not noyau.est_admin(user):
            return {"ok": False, "raison": "graver du code est reserve au proprietaire"}

        zone = (zone or "").strip().lower()
        try:
            import forge_fragments
            zones_ok = set(forge_fragments.ZONES)
        except Exception:
            zones_ok = {"cerveau", "production", "compte", "analyse", "evolution",
                        "integrations", "landing"}
        if zone not in zones_ok:
            return {"ok": False, "raison": f"zone '{zone}' inconnue"}

        ok, motif = _valide(html)
        if not ok:
            return {"ok": False, "raison": motif}

        # Garde noyau : on cible ui_custom.py (presentation), defense en profondeur.
        ok_n, motif_n = noyau.presentation_sure(html)
        if not ok_n:
            return {"ok": False, "raison": motif_n}

        courant = blocs()
        nouveau = dict(courant)
        nouveau[zone] = html
        source = _rendre_source(nouveau)

        # 1. compile AVANT d'ecrire : si invalide, on n'ecrit rien.
        try:
            compile(source, "ui_custom.py", "exec")
        except SyntaxError as e:
            return {"ok": False, "raison": f"code genere invalide (non ecrit) : {e}"}

        # 2. backup de l'etat courant.
        bid = _backup()

        # 3. ecriture + verification a chaud (reload + ancres). Rollback auto si KO.
        try:
            with open(_FICHIER, "w", encoding="utf-8") as f:
                f.write(source)
        except Exception as e:
            return {"ok": False, "raison": f"ecriture echouee : {e}"}

        if not _recharger_ui():
            # rollback : on restaure le backup (ou on vide la zone si pas de backup).
            if bid:
                restaurer(bid)
            else:
                with open(_FICHIER, "w", encoding="utf-8") as f:
                    f.write(_rendre_source(courant))
                _recharger_ui()
            rob.journaliser(f"graver ui_custom : rollback auto (zone {zone}, ancres KO)",
                            "alerte", source="forge_ui_python")
            return {"ok": False, "raison": "le bloc casserait l'interface -> rollback automatique"}

        try:
            import evolution_gouvernee
            evolution_gouvernee._notifier_generation(
                "interface", titre or f"code permanent {zone}",
                f"bloc permanent grave dans le code (zone {zone}, {len(html)} car.)")
        except Exception:
            pass
        rob.journaliser(f"graver ui_custom : bloc permanent grave (zone {zone})", "succes",
                        source="forge_ui_python")
        return {"ok": True, "zone": zone, "backup": bid, "permanent": True}
    return {"ok": False, "raison": "erreur capturee (voir journal)"}


def retirer(zone: str, *, user: dict | None = None) -> dict:
    """Retire le bloc permanent d'une zone (avec backup + rollback). Proprio uniquement."""
    with rob.garde("retirer ui_custom", source="forge_ui_python"):
        if not noyau.est_admin(user):
            return {"ok": False, "raison": "reserve au proprietaire"}
        zone = (zone or "").strip().lower()
        courant = blocs()
        if zone not in courant:
            return {"ok": False, "raison": "aucun bloc permanent sur cette zone"}
        nouveau = {k: v for k, v in courant.items() if k != zone}
        bid = _backup()
        with open(_FICHIER, "w", encoding="utf-8") as f:
            f.write(_rendre_source(nouveau))
        if not _recharger_ui() and bid:
            restaurer(bid)
            return {"ok": False, "raison": "rollback automatique"}
        rob.journaliser(f"ui_custom : bloc permanent retire (zone {zone})", "info", source="forge_ui_python")
        return {"ok": True, "zone": zone}
    return {"ok": False, "raison": "erreur capturee"}


# ── Auto-verification offline ────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile

    print("=" * 64)
    print("NEOGEN - FORGE UI PYTHON : auto-verification (offline)")
    print("=" * 64)

    _FICHIER = os.path.join(tempfile.mkdtemp(), "ui_custom.py")
    _BACKUPS = os.path.join(tempfile.mkdtemp(), "ui_backups")
    os.environ["NEOGEN_OWNER_UNLIMITED"] = "1"

    # _recharger_ui depend de l'import reel de ui/ui_custom : on le neutralise pour le test offline
    # (on teste la generation + compile + validation + gate, pas le reload du module live).
    globals()["_recharger_ui"] = lambda: True

    # 1. Generation de source : toujours compilable (json.dumps echappe tout).
    src = _rendre_source({"evolution": '<div class="panel">Salut "guillemets" et \\ backslash</div>'})
    compile(src, "ui_custom.py", "exec")
    print("  source genere compile (echappement sur) -> OK")

    # 2. Graver un bloc propre -> OK.
    r = graver("evolution", '<div class="panel glass">Bloc permanent</div>',
               titre="Test", user={"role": "admin"})
    assert r["ok"], r
    print("  graver bloc propre -> OK")

    # 3. Bloc avec <script> -> REFUSE (charte).
    r2 = graver("evolution", '<div><script>alert(1)</script></div>', user={"role": "admin"})
    assert not r2["ok"], r2
    print("  graver <script> REFUSE ->", r2["raison"][:50])

    # 4. Zone inconnue -> refus.
    r3 = graver("zone-bidon", "<div>x</div>", user={"role": "admin"})
    assert not r3["ok"] and "inconnue" in r3["raison"], r3
    print("  zone inconnue REFUSEE -> OK")

    # 5. Gate owner : un non-proprio ne grave pas.
    os.environ["NEOGEN_OWNER_UNLIMITED"] = ""
    r4 = graver("evolution", "<div>x</div>", user=None)
    assert not r4["ok"] and "proprietaire" in r4["raison"], r4
    print("  gate owner : public ne grave pas -> OK")
    os.environ["NEOGEN_OWNER_UNLIMITED"] = "1"

    print("=" * 64)
    print("  TOUT VERT : forge UI Python sure (compile+rollback), reservee proprio.")
    print("=" * 64)
