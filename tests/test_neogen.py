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
