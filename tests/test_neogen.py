"""
NEOGEN - Tests automatises (offline, aucun appel API)

Couvre : gateway (tiers, provider attr, ctx, sanitizer),
         registre/genealogie (enregistrer, lignee, diff code + gouvernance),
         pipeline (smoke test).
"""
import os
import sys
import json
import tempfile
import shutil

# Ajoute le dossier parent au path pour les imports NEOGEN
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Gateway ──────────────────────────────────────────────────────────────────

def test_gateway_tiers():
    from gateway import TIERS, client as gw_client, LLMContext
    for prov, tiers in TIERS.items():
        for tier, model in tiers.items():
            assert model, f"tier {tier} du provider {prov} vide"
    print("  [OK] tiers : tous les providers ont fort/moyen/leger")


def test_gateway_provider_attr():
    from gateway import _AnthropicAdapter, _GeminiAdapter, _OpenAICompatAdapter
    assert _AnthropicAdapter.provider == "anthropic"
    assert _GeminiAdapter.provider == "gemini"
    # OpenAI compat : provider set dans __init__
    class _FakeClient:
        class messages:
            @staticmethod
            def parse(**kw): ...
            @staticmethod
            def create(**kw): ...
    a = _AnthropicAdapter(_FakeClient(), "claude-opus-4-8")
    assert a.provider == "anthropic"
    print("  [OK] provider attr : adapters corrects")


def test_gateway_ctx():
    from gateway import contexte_depuis_headers, resume_ctx, LLMContext
    ctx = contexte_depuis_headers("openai", "gpt-4o", "sk-fake-key-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    assert ctx is not None
    assert ctx.provider == "openai"
    assert ctx.model == "gpt-4o"
    resume = resume_ctx(ctx)
    assert "sk-fake" not in resume, "fuite cle dans resume"
    print("  [OK] ctx : provider/model ok, cle absente du resume")


def test_sanitizer():
    from sanitizer import nettoyer
    fausse = "sk-proj-" + "A" * 32
    assert fausse not in nettoyer(f"erreur avec cle {fausse}")
    print("  [OK] sanitizer : sk-proj-... redacte")


def test_breaker_per_provider():
    from generator import _breaker_pour, _BREAKERS
    class _FakeA:
        provider = "anthropic"
    class _FakeO:
        provider = "openai"
    ba = _breaker_pour(_FakeA())
    bo = _breaker_pour(_FakeO())
    assert ba is not bo, "les breakers doivent etre distincts par provider"
    assert _BREAKERS["anthropic"] is ba
    assert _BREAKERS["openai"] is bo
    print("  [OK] circuit breaker : instances isolees par provider")


# ── Registre / Genealogie ─────────────────────────────────────────────────────

def _registre_tmp():
    """Contexte temporaire pour le registre (isole des vraies donnees)."""
    import registre as reg
    tmp = tempfile.mkdtemp()
    orig = {
        "BASE": reg.BASE,
        "DIR_PRODUITS": reg.DIR_PRODUITS,
        "INDEX": reg.INDEX,
        "PROMOTIONS": reg.PROMOTIONS,
        "ACTIFS": reg.ACTIFS,
    }
    reg.BASE = tmp
    reg.DIR_PRODUITS = os.path.join(tmp, "produits")
    reg.INDEX = os.path.join(tmp, "registre.jsonl")
    reg.PROMOTIONS = os.path.join(tmp, "promotions.jsonl")
    reg.ACTIFS = os.path.join(tmp, "lineage_actif.jsonl")
    return tmp, orig


def _registre_restore(orig):
    import registre as reg
    for k, v in orig.items():
        setattr(reg, k, v)


def test_registre_enregistrer():
    import registre as reg
    tmp, orig = _registre_tmp()
    try:
        e = reg.enregistrer("faire un test", "print('ok')", verdict="ok", tentatives=1, lignes=1,
                            murs=["no_external_network"], capacites=["persistance"])
        assert e["murs"] == ["no_external_network"]
        assert e["capacites"] == ["persistance"]
        assert e["generation"] == 1
        assert e["parent_id"] is None
        print("  [OK] registre.enregistrer : murs/capacites persistes")
    finally:
        _registre_restore(orig)
        shutil.rmtree(tmp, ignore_errors=True)


def test_registre_genealogie():
    import registre as reg
    tmp, orig = _registre_tmp()
    try:
        e1 = reg.enregistrer("calculatrice", "def add(a,b): return a+b", verdict="ok",
                              tentatives=1, lignes=1, murs=["no_exec_system"])
        e2 = reg.enregistrer("calculatrice", "def add(a,b): return a+b\ndef sub(a,b): return a-b",
                              verdict="ok", tentatives=1, lignes=2,
                              murs=["no_exec_system", "no_external_network"])
        assert e2["generation"] == 2
        assert e2["parent_id"] == e1["id"]
        assert e2["lineage"] == e1["lineage"]
        lignee = reg.lignee_produit(e1["id"])
        assert len(lignee) == 2
        print("  [OK] genealogie : generation/parent_id/lineage corrects")
    finally:
        _registre_restore(orig)
        shutil.rmtree(tmp, ignore_errors=True)


def test_diff_gouvernance():
    import registre as reg
    tmp, orig = _registre_tmp()
    try:
        # Injection directe pour eviter la collision d'id (slug+seconde identiques
        # quand deux enregistrer() tournent dans la meme seconde).
        id1, id2 = "outil-20260101T000000", "outil-20260101T000001"
        lin = "outil"
        for eid, murs, caps, gen, parent in [
            (id1, ["no_exec_system"], [], 1, None),
            (id2, ["no_exec_system", "no_external_network"], ["persistance"], 2, id1),
        ]:
            entry = {"id": eid, "timestamp": "2026-01-01T00:00:00", "intention": "outil test",
                     "chemin": "produits/fake.py", "verdict": "ok", "tentatives": 1, "lignes": 1,
                     "promouvable": False, "lineage": lin, "generation": gen,
                     "parent_id": parent, "murs": murs, "capacites": caps}
            os.makedirs(os.path.dirname(reg.INDEX), exist_ok=True)
            with open(reg.INDEX, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

        g = reg.diff_gouvernance(id1, id2)
        assert "no_external_network" in g["murs_ajoutes"], f"murs_ajoutes={g['murs_ajoutes']}"
        assert "persistance" in g["capacites_ajoutees"], f"caps_ajoutees={g['capacites_ajoutees']}"
        assert g["murs_retires"] == []
        print("  [OK] diff_gouvernance : murs/capacites ajoutes/retires corrects")
    finally:
        _registre_restore(orig)
        shutil.rmtree(tmp, ignore_errors=True)


# ── Pipeline (smoke test) ────────────────────────────────────────────────────

def test_pipeline_smoke():
    from pipeline import smoke_test
    ok = smoke_test()
    assert ok, "smoke test pipeline echoue"
    # Note : smoke_test imprime ses propres lignes


# ── Orchestrateur (import + modeles) ─────────────────────────────────────────

def test_orchestrateur_imports():
    from orchestrateur import OrganePlan, PlanDelegation, ImplOrgane
    o = OrganePlan(nom_fonction="additionner", signature="def additionner(a: int, b: int) -> int:",
                   role="additionne deux entiers", tier="leger")
    assert o.tier == "leger"
    print("  [OK] orchestrateur : imports et modeles Pydantic ok")


# ── Robustesse (socle transverse) ─────────────────────────────────────────────

def test_robustesse():
    import robustesse as rob
    tmp = tempfile.mkdtemp()
    rob.JOURNAL = os.path.join(tmp, "j.jsonl")
    rob.IDEMPOTENCE = os.path.join(tmp, "i.json")
    rob.SANTE = os.path.join(tmp, "s.json")
    rob._DATA = tmp
    # retry : echoue 2x puis reussit
    c = {"n": 0}
    def flaky():
        c["n"] += 1
        if c["n"] < 3:
            raise ValueError("x")
        return "ok"
    assert rob.reessayer(flaky, tentatives=5, delai=0.01) == "ok"
    # protege : renvoie defaut sans planter
    assert rob.protege(lambda: int("pas_un_nombre"), defaut="safe") == "safe"
    # idempotence
    assert not rob.deja_fait("k")
    rob.marquer_fait("k")
    assert rob.deja_fait("k")
    # disjoncteur
    cb = rob.Disjoncteur.pour("t_test", seuil=2, cooldown_s=0.05)
    cb.appeler(lambda: (_ for _ in ()).throw(RuntimeError("a")))
    cb.appeler(lambda: (_ for _ in ()).throw(RuntimeError("b")))
    assert not cb.disponible()
    print("  [OK] robustesse : retry / protege / idempotence / disjoncteur")


# ── Quotas multi-paliers ───────────────────────────────────────────────────────

def test_quotas_paliers():
    import quotas
    assert quotas.palier({"premium": True}) == "essential"   # retro-compat
    assert quotas.palier({"palier": "power"}) == "power"
    assert not quotas.verifier({"id": "z"}, "deploiement")["autorise"]      # gratuit
    assert quotas.verifier({"id": "z", "palier": "essential"}, "deploiement")["autorise"]
    assert not quotas.verifier({"id": "z", "palier": "essential"}, "delegation_complete")["autorise"]
    assert quotas.verifier({"id": "z", "palier": "pro"}, "delegation_complete")["autorise"]
    assert quotas.verifier({"id": "z", "palier": "power"}, "vision")["autorise"]
    print("  [OK] quotas : paliers + fonctions deverrouillees par rang")


# ── Credits (Genyte) ───────────────────────────────────────────────────────────

def test_credits():
    import credits, tempfile as _tf
    t = _tf.mkdtemp()
    credits.SOLDES_FILE = os.path.join(t, "s.json")
    credits.TXNS_FILE = os.path.join(t, "t.jsonl")
    uid = "u_test"
    credits.crediter(uid, 100, "earn", "test")
    assert credits.solde(uid) == 100
    r = credits.debiter(uid, 30, "mode_juge")
    assert r["ok"] and credits.solde(uid) == 70
    assert not credits.debiter(uid, 999, "mode_juge")["ok"]
    assert credits.cout("mode_juge", "power") == 0
    assert credits.cout("delegation_complete", "gratuit") is None
    print("  [OK] credits : crediter/debiter/cout par palier")


# ── Competences (socle + cristallisation idempotente) ──────────────────────────

def test_competences_socle():
    import competences, robustesse as rob
    t = tempfile.mkdtemp()
    competences.SKILLS_DIR = os.path.join(t, "skills")
    rob._DATA = tempfile.mkdtemp()
    rob.IDEMPOTENCE = os.path.join(rob._DATA, "i.json")
    rob.JOURNAL = os.path.join(rob._DATA, "j.jsonl")
    competences.assurer_socle()
    skills = competences.lister()
    assert all(any(s["nom"] == b["nom"] for s in skills) for b in competences.SOCLE)
    assert competences.supprimer("discernement_avant_creation") is False  # socle protege
    a1 = competences.cristalliser_auto("x", "d", "i", ["discerner"], signature="sig_x")
    a2 = competences.cristalliser_auto("x", "d", "i", ["discerner"], signature="sig_x")
    assert a1 is not None and a2 is None  # idempotent
    print("  [OK] competences : socle present/protege + cristallisation idempotente")


# ── Orchestrateur : ordonnancement en vagues ────────────────────────────────────

def test_orchestrateur_vagues():
    from orchestrateur import ordonner_vagues
    class _O:
        def __init__(self, n, d=None): self.nom_fonction = n; self.depend_de = d or []
    v = ordonner_vagues([_O("C", ["B"]), _O("B", ["A"]), _O("A")])
    assert [[o.nom_fonction for o in w] for w in v] == [["A"], ["B"], ["C"]]
    assert len(ordonner_vagues([_O("X"), _O("Y")])) == 1  # paralleles
    assert sum(len(w) for w in ordonner_vagues([_O("P", ["Q"]), _O("Q", ["P"])])) == 2  # cycle
    print("  [OK] orchestrateur : vagues chaine/parallele/cycle")


# ── Auto-amelioration (analyse multi-sources) ───────────────────────────────────

def test_auto_amelioration():
    import auto_amelioration as aa
    assert aa._type_erreur("ZeroDivisionError: division by zero") == "ZeroDivisionError"
    res = aa.analyser_usage()
    assert "signaux" in res and "sources" in res and "points_forts" in res
    print("  [OK] auto-amelioration : analyse multi-sources structuree")


def test_anonymizer():
    import anonymizer
    assert "[REDACTED_EMAIL]" in anonymizer.nettoyer_texte("contact@netroia.com")
    assert "[REDACTED_KEY]" in anonymizer.nettoyer_texte("sk_live_abcdef0123456789xyz")
    d = anonymizer.nettoyer_dict({"token": "sk_live_xxx", "msg": "ok"})
    assert d["token"] == "[REDACTED]" and d["msg"] == "ok"
    print("  [OK] anonymizer : emails/cles/champs sensibles redactes")


def test_telemetrie():
    import telemetrie as tele
    t = tempfile.mkdtemp()
    tele.CONSENT_FILE = os.path.join(t, "c.json")
    tele.DATA_FILE = os.path.join(t, "d.jsonl")
    uid = "u_tele"
    assert tele.get_consentement(uid) == "aucun"
    assert not tele.enregistrer(uid, "erreur", {"x": 1})       # pas de consentement
    tele.set_consentement(uid, "erreurs")
    assert tele.enregistrer(uid, "erreur", {"x": 1})
    assert not tele.enregistrer(uid, "usage", {"x": 1})        # niveau insuffisant
    r = tele.effacer(uid)                                       # RGPD
    assert r["supprime_consent"] and r["supprime_lignes"] == 1
    print("  [OK] telemetrie : consentement gradue + effacement RGPD")


def test_boosts():
    import boosts, credits, tempfile as _tf
    t = _tf.mkdtemp()
    boosts.BOOSTS_FILE = os.path.join(t, "b.json")
    credits.SOLDES_FILE = os.path.join(t, "s.json")
    credits.TXNS_FILE = os.path.join(t, "tx.jsonl")
    uid = "u_boost"
    credits.crediter(uid, 200, "earn", "test")
    r = boosts.activer(uid, "flash_24h", "gratuit")
    assert r["ok"] and boosts.est_actif(uid, "flash_24h")
    assert not boosts.est_actif(uid, "flash_7j")
    print("  [OK] boosts : activation Flash + etat actif")


def test_recompenses():
    import recompenses, tempfile as _tf, sys as _sys, types as _types
    # Isole credits (pas d'effet de bord solde) + log temporaire
    _sys.modules["credits"] = _types.SimpleNamespace(crediter=lambda *a, **k: None)
    recompenses._credits = _sys.modules["credits"]
    recompenses.LOG_FILE = os.path.join(_tf.mkdtemp(), "r.json")
    uid = "u_reco"
    r1 = recompenses.declencher(uid, "premiere_creation")
    assert r1["ok"] and r1["gen_gagnes"] == 20
    assert not recompenses.declencher(uid, "premiere_creation")["ok"]  # one-shot
    print("  [OK] recompenses : gain + anti-rejeu (one-shot)")


def test_credentials_loader():
    import credentials_loader as cl
    os.environ["TEST_CL_KEY"] = "v"
    assert cl.lire_cred("x.env", "TEST_CL_KEY") == "v"
    del os.environ["TEST_CL_KEY"]
    assert cl.lire_cred("absent.env", "ABSENTE") == ""
    print("  [OK] credentials_loader : env prioritaire + absent")


def test_vecteurs():
    import vecteurs
    idf = vecteurs.construire_idf(["chat noir", "chien blanc"])
    v = vecteurs.vectoriser("chat noir", idf)
    assert abs(vecteurs.cosinus(v, v) - 1.0) < 1e-9          # identité = 1
    assert vecteurs.cosinus(vecteurs.vectoriser("chat", idf),
                            vecteurs.vectoriser("zzz", idf)) == 0.0  # disjoint = 0
    docs = ["paiement stripe e-commerce", "threads isolation delegation", "mode juge strategies"]
    r = vecteurs.classer("comment marche le paiement stripe", docs, limite=3)
    assert r and r[0][0] == 0                                 # bon doc en tête
    print("  [OK] vecteurs : cosinus + classement sémantique pertinent")


def test_routeur_bandit():
    import routeur_bandit as rb, tempfile as _tf
    rb.BANDIT_FILE = os.path.join(_tf.mkdtemp(), "b.json")
    assert rb.categoriser("cree une app") == "creation"
    assert rb.categoriser("ferme le navigateur") == "rpa"
    assert rb.recompense(True, "leger") > rb.recompense(True, "fort")   # coût
    assert rb.choisir("creation")[1] == "heuristique"                    # démarrage
    for _ in range(20):
        rb.recompenser("creation", "leger", False)
        rb.recompenser("creation", "moyen", True)
        rb.recompenser("creation", "fort", True)
    choix = [rb.choisir("creation")[0] for _ in range(20)]
    assert max(set(choix), key=choix.count) == "moyen"                   # converge vers cheap-qui-marche
    print("  [OK] routeur_bandit : UCB1 converge vers le tier économe qui réussit")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_gateway_tiers,
        test_gateway_provider_attr,
        test_gateway_ctx,
        test_sanitizer,
        test_breaker_per_provider,
        test_registre_enregistrer,
        test_registre_genealogie,
        test_diff_gouvernance,
        test_pipeline_smoke,
        test_orchestrateur_imports,
        test_robustesse,
        test_quotas_paliers,
        test_credits,
        test_competences_socle,
        test_orchestrateur_vagues,
        test_auto_amelioration,
        test_anonymizer,
        test_telemetrie,
        test_boosts,
        test_recompenses,
        test_credentials_loader,
        test_vecteurs,
        test_routeur_bandit,
    ]
    print("=" * 60)
    print("NEOGEN - TESTS AUTOMATISES (offline)")
    print("=" * 60)
    failed = []
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"  [ECHEC] {t.__name__} : {e}")
            failed.append(t.__name__)
    print("=" * 60)
    if failed:
        print(f"  ECHECS : {', '.join(failed)}")
        sys.exit(1)
    else:
        print(f"  TOUS LES TESTS PASSES ({len(tests)}/{len(tests)})")
        sys.exit(0)
