"""
NEOGEN - Orchestrateur de delegation agentique

Le differenciateur face aux agents "yolo" (type Hermes) : NEOGEN decompose une
intention en ORGANES, DELEGUE chaque organe a un sous-agent au TIER de modele
adapte a sa difficulte (via gateway multi-provider), puis ASSEMBLE le tout sous
GOUVERNANCE (membrane + scan + conteneur durci + auto-reparation).

Flux :
  1. ADN (forger_adn)                     -> objectif + murs + organes (tier fort)
  2. PLAN (concevoir_plan)                -> contrat d'interface : pour chaque organe
     une signature exacte + un TIER (fort/moyen/leger selon difficulte) + le code
     d'assemblage + les effets declares du produit assemble (confrontes par la membrane)
  3. DELEGATION (par organe)              -> un sous-agent genere SA fonction au tier choisi
     (modele resolu par le gateway selon le provider actif). Statut live par SSE.
  4. ASSEMBLAGE + GOUVERNANCE             -> on reinjecte le code assemble dans le pipeline
     existant (pipeline.fabriquer) : membrane + scan statique + conteneur durci +
     auto-reparation + ledger + lignee. Zero gouvernance perdue.

GARDE-FOUS : chaque sous-agent reste dans les murs de l'ADN ; le code assemble passe
les 3 garde-fous comme tout produit ; Docker socket = machine dediee uniquement ;
l'humain garde le dernier mot sur l'assemblage final (rien n'est promu sans validation).

HONNETETE : recoller des pieces d'IA peut laisser des bugs d'integration ; l'auto-
reparation re-delegue les organes avec le feedback d'erreur. Les tiers sont une
estimation de difficulte par l'architecte, pas une garantie.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-20.
"""

from __future__ import annotations
import sys

from pydantic import BaseModel, Field

import gateway
from compositeur import forger_adn, EffetsDeclares
from usine import ModuleGenere
from usine_multi_organes import assembler
from generator import parse_resilient
from pipeline import fabriquer, _client
import registre as _reg


# ---------------------------------------------------------------------------
# Plan de delegation : contrat d'interface enrichi d'un TIER par organe
# ---------------------------------------------------------------------------
class OrganePlan(BaseModel):
    nom_fonction: str = Field(description="nom de la fonction, snake_case")
    signature: str = Field(description="la ligne def complete avec types, ex: def calculer(x: float) -> float:")
    role: str = Field(description="ce que fait cet organe, une phrase")
    tier: str = Field(description="difficulte de cet organe : 'fort' (logique complexe/critique), "
                                  "'moyen' (standard), 'leger' (trivial/utilitaire)")
    difficulte: str = Field(default="", description="courte justification du tier choisi")


class PlanDelegation(BaseModel):
    organes: list[OrganePlan] = Field(description="3 a 5 organes aux signatures coherentes entre elles")
    code_assemblage: str = Field(description="le code qui orchestre ces fonctions + un bloc "
                                             "if __name__=='__main__' avec une demo et des assert")
    effets: EffetsDeclares = Field(description="effets DECLARES du produit assemble (la membrane les confronte aux murs)")


class ImplOrgane(BaseModel):
    code: str = Field(description="le code complet de la fonction demandee, rien d'autre")


_TIERS_VALIDES = {"fort", "moyen", "leger"}


def _tier_sain(t: str) -> str:
    t = (t or "moyen").strip().lower()
    return t if t in _TIERS_VALIDES else "moyen"


# ---------------------------------------------------------------------------
# 2. PLAN : l'architecte conçoit le contrat + assigne un tier par organe
# ---------------------------------------------------------------------------
def concevoir_plan(adn, client) -> PlanDelegation:
    organes = "\n".join(f"  - {o.nom} : {o.besoin}" for o in adn.organes)
    murs = "\n".join(f"  - {m.id} : {m.label}" for m in adn.murs) or "  (aucun)"
    systeme = (
        f"Tu es l'ARCHITECTE-ORCHESTRATEUR d'un produit Python. Objectif : {adn.objectif}\n"
        f"Organes pressentis :\n{organes}\n\nMurs absolus a respecter :\n{murs}\n\n"
        "Conçois le PLAN DE DELEGATION :\n"
        "1) Pour 3 a 5 organes, donne une signature de fonction EXACTE (ligne def avec types), "
        "coherentes entre elles (les sorties des uns alimentent les entrees des autres).\n"
        "2) Pour CHAQUE organe, assigne un TIER de modele selon sa difficulte reelle :\n"
        "   - 'fort'  : logique metier complexe, algorithme delicat, securite, partie critique\n"
        "   - 'moyen' : implementation standard, transformation de donnees courante\n"
        "   - 'leger' : utilitaire trivial (formatage, validation simple, getter)\n"
        "   Sois discriminant : tout n'est pas 'fort'. La delegation au bon tier est la valeur.\n"
        "3) Ecris le CODE D'ASSEMBLAGE : l'orchestration qui appelle ces fonctions dans le bon "
        "ordre, plus un bloc if __name__=='__main__' avec une demo et des assert prouvant que "
        "tout marche.\n"
        "4) DECLARE honnetement les EFFETS du produit assemble (supprime des donnees ? demande "
        "confirmation ? accede au reseau ? reseau autorise ? stocke un secret en clair ? verifie "
        "l'authentification ?). La membrane confrontera ces effets aux murs : ne mens pas.\n\n"
        "Les organes seront implementes SEPAREMENT par des sous-agents : les signatures doivent "
        "suffire a les ecrire independamment. Python pur, stdlib uniquement, aucune I/O fichier "
        "ni reseau sauf si un mur l'autorise explicitement."
    )
    resp = parse_resilient(
        client, model=gateway.TIERS["anthropic"]["fort"], max_tokens=8000, thinking={"type": "adaptive"},
        system=systeme,
        messages=[{"role": "user", "content": "Conçois le plan de delegation complet."}],
        output_format=PlanDelegation,
    )
    if resp.parsed_output is None:
        raise RuntimeError("Le plan de delegation n'a pas pu etre conçu")
    plan = resp.parsed_output
    for o in plan.organes:
        o.tier = _tier_sain(o.tier)
    return plan


# ---------------------------------------------------------------------------
# 3. DELEGATION : un sous-agent implemente UN organe a son tier
# ---------------------------------------------------------------------------
def deleguer_organe(plan: PlanDelegation, organe: OrganePlan, client, feedback=None) -> ImplOrgane:
    toutes = "\n".join(f"  {o.signature}   # {o.role}" for o in plan.organes)
    systeme = (
        "Tu es un SOUS-AGENT qui implemente UN organe d'un produit Python. Voici le contrat "
        f"complet (toutes ces fonctions existent) :\n{toutes}\n\n"
        f"Implemente UNIQUEMENT cette fonction, avec EXACTEMENT cette signature :\n"
        f"  {organe.signature}\n  role : {organe.role}\n\n"
        "Tu peux appeler les autres fonctions du contrat (elles existent). Renvoie le code "
        "complet de CETTE fonction seulement. Python pur, stdlib, aucune I/O fichier ni reseau."
    )
    if feedback:
        code_prec, erreur = feedback
        systeme += ("\n\n--- L'ASSEMBLAGE PRECEDENT A ECHOUE ---\nCorrige ta fonction pour resoudre "
                    f"ce probleme d'integration.\nERREUR :\n{erreur}")
    resp = parse_resilient(
        client, model=gateway.TIERS["anthropic"]["fort"], max_tokens=8000, thinking={"type": "adaptive"},
        system=systeme,
        messages=[{"role": "user", "content": f"Implemente {organe.nom_fonction}."}],
        output_format=ImplOrgane,
    )
    if resp.parsed_output is None:
        raise RuntimeError(f"Le sous-agent n'a pas implemente l'organe {organe.nom_fonction}")
    return resp.parsed_output


# ---------------------------------------------------------------------------
# 4. ORCHESTRATION : delegation + assemblage, sous gouvernance (pipeline.fabriquer)
# ---------------------------------------------------------------------------
def orchestrer(intention: str, ctx=None, *, cap=None, reparer=True, max_tentatives=3,
               enregistrer=True, progress=None):
    """Decompose l'intention, delegue chaque organe au bon tier, assemble sous gouvernance.
    ctx : LLMContext (provider/cle actifs). None = Anthropic par defaut.
    Reutilise pipeline.fabriquer pour membrane + scan + conteneur + auto-reparation + ledger.
    Renvoie le Resultat du pipeline (avec .plan attache)."""

    def _emit(evt):
        if progress is None:
            return
        try:
            progress(evt)
        except Exception:
            pass

    # Contexte de base (tier fort) pour l'architecture, et contexte par-tier pour la delegation.
    ctx_archi = ctx
    ctx_tiers = gateway.ctx_pour_tier(ctx)  # le tier choisira le modele par organe
    client_archi = gateway.client(ctx_archi, tier="fort") if ctx is not None else _client()

    _emit({"stade": "decomposition", "msg": "decomposition de l'intention en organes"})
    adn = forger_adn(intention, client_archi)
    plan = concevoir_plan(adn, client_archi)

    # Annonce le plan : la carte de delegation (organes + tier + modele resolu).
    apercu = []
    for o in plan.organes:
        cl = gateway.client(ctx_tiers, tier=o.tier)
        apercu.append({"organe": o.nom_fonction, "role": o.role, "tier": o.tier,
                       "modele": getattr(cl, "model", "?"), "difficulte": o.difficulte})
    _emit({"stade": "plan", "organes": apercu, "total": len(apercu),
           "msg": f"{len(apercu)} organes a deleguer"})

    volume_nom = ("viv_" + _reg._slug(intention)) if (cap and getattr(cap, "persistance", False)) else None

    # generer_fn pour le pipeline : delegue les organes, mais sur repair ne re-delegue
    # QUE les organes cites dans l'erreur — les autres sont reutilises du cache.
    _cache_impls: dict[str, str] = {}

    def generer_fn(_adn, feedback=None):
        impls = []
        erreur_txt = (feedback[1] if feedback else "").lower()
        for o in plan.organes:
            cl = gateway.client(ctx_tiers, tier=o.tier)
            modele = getattr(cl, "model", "?")
            # Reutilise si: repair en cours ET organe non cite dans l'erreur ET deja en cache.
            if feedback and o.nom_fonction not in erreur_txt and o.nom_fonction in _cache_impls:
                impls.append(_cache_impls[o.nom_fonction])
                _emit({"stade": "sous_agent", "organe": o.nom_fonction, "tier": o.tier,
                       "modele": modele, "statut": "reutilise"})
                continue
            _emit({"stade": "sous_agent", "organe": o.nom_fonction, "role": o.role,
                   "tier": o.tier, "modele": modele, "statut": "en_cours"})
            try:
                impl = deleguer_organe(plan, o, cl, feedback=feedback)
            except Exception as e:
                _emit({"stade": "sous_agent", "organe": o.nom_fonction, "tier": o.tier,
                       "modele": modele, "statut": "echec", "raison": str(e)[:200]})
                raise
            _cache_impls[o.nom_fonction] = impl.code
            impls.append(impl.code)
            _emit({"stade": "sous_agent", "organe": o.nom_fonction, "role": o.role,
                   "tier": o.tier, "modele": modele, "statut": "fait",
                   "lignes": len(impl.code.splitlines())})
        code = assembler(impls, plan.code_assemblage)
        _emit({"stade": "assemblage", "msg": "organes recolles via le contrat d'interface",
               "lignes": len(code.splitlines())})
        return ModuleGenere(code=code,
                            explication=f"Produit assemble par delegation ({len(plan.organes)} organes).",
                            effets=plan.effets)

    # On reutilise tout le pipeline gouverne : membrane + scan + conteneur + reparation + ledger + lignee.
    r = fabriquer(intention, lambda i: adn, generer_fn,
                  reparer=reparer, max_tentatives=max_tentatives, tracer=True,
                  cap=cap, volume_nom=volume_nom, progress=progress)
    r.plan = apercu

    if enregistrer and r.succes and r.code:
        entree = registre_enregistrer(intention, r)
        if progress is not None:
            _emit({"stade": "registre", "msg": f"produit enregistre : {entree}"})
    return r


def registre_enregistrer(intention, r) -> str:
    entree = _reg.enregistrer(intention, r.code, verdict=r.verdict,
                              tentatives=r.tentatives, lignes=r.lignes)
    return entree["id"]


# ---------------------------------------------------------------------------
# CLI : demo locale (chemin Anthropic par defaut)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    intention = " ".join(sys.argv[1:]) or "une calculatrice de pourboire qui repartit l'addition entre convives"
    print("=" * 72)
    print(f"NEOGEN - ORCHESTRATEUR DE DELEGATION : '{intention}'")
    print("=" * 72)

    def trace(evt):
        s = evt.get("stade")
        if s == "plan":
            print(f"\n[PLAN] {evt['total']} organes a deleguer :")
            for o in evt["organes"]:
                print(f"   - {o['organe']:24s} tier={o['tier']:6s} -> {o['modele']}")
        elif s == "sous_agent":
            st = evt.get("statut")
            if st == "en_cours":
                print(f"   [{evt['modele']}] delegue : {evt['organe']} ...", flush=True)
            elif st == "fait":
                print(f"      OK {evt['organe']} ({evt.get('lignes', '?')} lignes)")
            elif st == "echec":
                print(f"      ECHEC {evt['organe']} : {evt.get('raison')}")
        elif s == "assemblage":
            print(f"\n[ASSEMBLAGE] {evt.get('lignes')} lignes recollees.")
        elif s in ("membrane", "scan", "conteneur", "execution"):
            ok = evt.get("ok")
            mark = "OK" if ok else ("KO" if ok is False else "..")
            print(f"   [{s}] {mark} {evt.get('msg') or evt.get('raison') or ''}")

    r = orchestrer(intention, ctx=None, progress=trace)
    print("\n" + "=" * 72)
    print(f"  succes={r.succes} | {r.verdict} | {r.tentatives} tentative(s) | {r.lignes} lignes")
    if not r.succes and r.lecons:
        print("  lecons :", " | ".join(r.lecons))
    print("=" * 72)
    sys.exit(0 if r.succes else 1)
