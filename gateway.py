"""
NEOGEN - Gateway multi-modele : un seul point d'appel LLM, plusieurs providers.

Abstrait l'appel LLM par TIER (fort / moyen / leger) et par PROVIDER (anthropic,
openai, gemini, deepseek, mistral, local). Le frontend envoie provider+modele+cle
ACTIFS dans la requete (headers X-LLM-*) ; le gateway les consomme PAR REQUETE, ne
les persiste JAMAIS, et le sanitizer garantit zero fuite en log/flux.

Anthropic reste le DEFAUT (cle credentials) si rien n'est connecte, via son SDK natif
(messages.parse structure + thinking adaptatif, meilleure qualite). Les autres providers
passent par HTTP : chat/completions compatible OpenAI (openai, deepseek, mistral, local)
ou generateContent (gemini), avec sortie JSON validee par Pydantic (best-effort honnete).

ASTUCE D'ARCHITECTURE : l'adaptateur expose la MEME interface .messages.parse /
.messages.create que le client Anthropic. Tout le pipeline existant (proposer, conseiller,
forger_adn, generer_reel, produire_le_mieux_reel...) recoit deja un `client` en parametre :
il suffit d'injecter l'adaptateur au sommet (api.py) pour router, sans toucher les modules.
La resilience (parse_resilient : circuit breaker + retries) enveloppe n'importe quel client
expose .messages.parse, donc les providers tiers en heritent gratuitement.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-20.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from sanitizer import nettoyer

# ---------------------------------------------------------------------------
# Tiers : modele par defaut, par provider. Coherent avec model-advisor.py
# (fort = le plus capable, leger = le plus rapide/econome).
# ---------------------------------------------------------------------------
TIERS = {
    "anthropic": {"fort": "claude-opus-4-8", "moyen": "claude-sonnet-5", "leger": "claude-haiku-4-5-20251001"},
    "openai":    {"fort": "gpt-5.5",         "moyen": "gpt-5.2",           "leger": "gpt-5-mini"},
    "gemini":    {"fort": "gemini-3.1-pro-preview", "moyen": "gemini-3.5-flash", "leger": "gemini-3.1-flash-lite"},
    "deepseek":  {"fort": "deepseek-v4-pro", "moyen": "deepseek-v4-flash", "leger": "deepseek-v4-flash"},
    "mistral":   {"fort": "mistral-large-latest", "moyen": "mistral-small-latest", "leger": "ministral-3-8b"},
    "moonshot":  {"fort": "kimi-k2.7-code", "moyen": "kimi-k2.6", "leger": "kimi-k2.7-code-highspeed"},
    "glm":       {"fort": "glm-5.2",          "moyen": "glm-4.5",           "leger": "glm-4.5-flash"},
    "local":     {"fort": "llama3.2",        "moyen": "llama3.2",          "leger": "qwen2.5"},
}

# ---------------------------------------------------------------------------
# ROUTEUR DE MODELE : analyse une demande et choisit le tier LE PLUS ECONOME
# possible (moins de tokens = moins cher = valeur client). Heuristique locale
# (aucun appel LLM -> gratuit, instantane). C'est le "modele adapte selon la
# demande" : tache simple -> leger ; tache complexe -> fort.
# ---------------------------------------------------------------------------

# Signaux de COMPLEXITE (poussent vers 'fort').
_MOTS_COMPLEXES = (
    "architecture", "refactor", "refonte", "analyse", "analyser", "strategie",
    "deboguer", "debug", "optimiser", "securite", "concevoir", "conception",
    "plan", "planifier", "raisonne", "demontre", "prouve", "compare", "evalue",
    "multi", "orchestr", "delegue", "genere une app", "cree une app", "code",
    "algorithme", "juridique", "rgpd", "conformite", "pourquoi", "explique en detail",
)
# Signaux de SIMPLICITE (autorisent 'leger').
_MOTS_SIMPLES = (
    "bonjour", "salut", "merci", "ok", "oui", "non", "liste", "lister",
    "affiche", "montre", "quelle heure", "resume court", "traduis", "reformule",
    "corrige la faute", "convertis", "combien",
)


def recommander_tier(demande: str) -> dict:
    """Analyse une demande et renvoie {tier, raison, score}. Heuristique, sans appel LLM.
    Vise l'economie : on ne monte en 'fort' que si la complexite le justifie."""
    txt = (demande or "").strip().lower()
    n = len(txt)
    score = 0
    raisons = []

    # Longueur : une longue demande est souvent plus complexe.
    if n > 600:
        score += 2; raisons.append("demande longue")
    elif n > 200:
        score += 1; raisons.append("demande moyenne")

    complexes = sum(1 for m in _MOTS_COMPLEXES if m in txt)
    simples = sum(1 for m in _MOTS_SIMPLES if m in txt)
    if complexes:
        score += complexes + 1; raisons.append(f"{complexes} signal(aux) de complexite")
    if simples and not complexes:
        score -= 1; raisons.append("formulation simple")

    # Questions multiples / etapes -> plus complexe.
    if txt.count("?") >= 2 or " puis " in txt or " ensuite " in txt or "\n" in txt.strip():
        score += 1; raisons.append("plusieurs etapes")

    if score >= 3:
        tier = "fort"
    elif score >= 1:
        tier = "moyen"
    else:
        tier = "leger"
    raison = ", ".join(raisons) or "demande simple"
    source = "heuristique"

    # Raffinement par le bandit (UCB1) : s'il a appris pour cette catégorie, il peut
    # proposer un tier plus économe qui réussit. Sinon on garde l'heuristique.
    try:
        import routeur_bandit
        categorie = routeur_bandit.categoriser(demande)
        choix, src = routeur_bandit.choisir(categorie, defaut=tier)
        if src in ("bandit", "exploration") and choix:
            tier = choix
            source = src
            raison = f"{raison} | bandit[{categorie}]:{src}"
        return {"tier": tier, "score": score, "raison": raison,
                "categorie": categorie, "source": source}
    except Exception:
        return {"tier": tier, "score": score, "raison": raison,
                "categorie": "conversation", "source": source}


# Providers parlant l'API chat/completions compatible OpenAI.
_OPENAI_COMPAT = {
    "openai":   "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "mistral":  "https://api.mistral.ai/v1",
    "moonshot": "https://api.moonshot.ai/v1",   # Kimi (Moonshot AI), compatible OpenAI
    "glm":      "https://open.bigmodel.cn/api/paas/v4/",   # Zhipu AI GLM, compatible OpenAI
    "local":    "http://localhost:11434/v1",   # Ollama, mode compatible OpenAI
}
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

_TIMEOUT = httpx.Timeout(400.0, connect=15.0)  # Ollama CPU-only : ~6 tok/s, 2000 tok peut prendre >180s


# ---------------------------------------------------------------------------
# Contexte d'appel : provider + modele + cle, fournis PAR REQUETE.
# Jamais persiste. La cle vit le temps de la requete puis disparait.
# ---------------------------------------------------------------------------
@dataclass
class LLMContext:
    provider: str = "anthropic"
    model: str | None = None      # override explicite ; sinon resolu par tier
    api_key: str | None = None    # par requete, JAMAIS persiste ni logge
    base_url: str | None = None   # pour local / endpoint custom


def contexte_depuis_headers(provider=None, model=None, key=None, base=None) -> LLMContext | None:
    """Construit un LLMContext depuis les en-tetes X-LLM-*. None si rien de connecte
    (=> Anthropic par defaut via credentials)."""
    if not provider:
        return None
    provider = provider.strip().lower()
    base = (base or "").strip() or None
    if provider == "local" and not base:
        # Champ base URL vide cote frontend (utilisateur qui n'a rien tape/colle, le
        # placeholder grise n'est PAS une vraie valeur envoyee) : sans ce repli, gateway.
        # client() retombe sur _OPENAI_COMPAT["local"]="localhost:11434", qui depuis
        # l'interieur du conteneur Docker pointe vers le conteneur LUI-MEME (jamais
        # l'hote) -> "Connection refused" systematique. NEOGEN_OLLAMA_BASE (config VPS)
        # est prioritaire si definie, sinon host.docker.internal (Docker Desktop local).
        import os
        serveur = os.environ.get("NEOGEN_OLLAMA_BASE", "").strip()
        base = serveur or "http://host.docker.internal:11434/v1"
    if provider == "local" and base and "host.docker.internal" in base:
        # host.docker.internal ne fonctionne QUE sur Docker Desktop (Mac/Windows), jamais
        # sur un VPS Linux ou l'utilisateur suivrait le tuto par defaut affiche dans l'app
        # sans savoir que cette instance a besoin d'une autre adresse. Repli transparent
        # sur la config serveur (NEOGEN_OLLAMA_BASE) si definie, sinon on garde tel quel
        # (le cas Docker Desktop reste inchange).
        import os
        serveur = os.environ.get("NEOGEN_OLLAMA_BASE", "").strip()
        if serveur and "host.docker.internal" not in serveur:
            base = serveur
    return LLMContext(provider=provider,
                      model=(model or "").strip() or None,
                      api_key=(key or "").strip() or None,
                      base_url=base)


# ---------------------------------------------------------------------------
# Resultats : memes attributs que le SDK Anthropic (.parsed_output / .content).
# ---------------------------------------------------------------------------
class _ParseResult:
    def __init__(self, parsed_output, stop_reason="end_turn"):
        self.parsed_output = parsed_output
        self.stop_reason = stop_reason


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _CreateResult:
    def __init__(self, text):
        self.content = [_Block(text)]
        self.stop_reason = "end_turn"


def _text_of(content) -> str:
    """Normalise un content Anthropic (str ou liste de blocs) en texte simple."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for b in content:
            if isinstance(b, dict):
                out.append(b.get("text", ""))
            else:
                out.append(getattr(b, "text", ""))
        return "".join(out)
    return str(content)


def _strip_fences(txt: str) -> str:
    """Retire un eventuel encadrement ```json ... ``` autour du JSON."""
    s = txt.strip()
    if s.startswith("```"):
        s = s[3:]
        if s[:4].lower() == "json":
            s = s[4:]
        if s.endswith("```"):
            s = s[:-3]
    return s.strip()


# ---------------------------------------------------------------------------
# Adaptateurs : tous exposent .messages.parse(...) et .messages.create(...)
# ---------------------------------------------------------------------------
class _Messages:
    def __init__(self, adapter):
        self._a = adapter

    def parse(self, **kw):
        return self._a._parse(**kw)

    def create(self, **kw):
        return self._a._create(**kw)


class _BaseAdapter:
    provider: str = "anthropic"

    def __init__(self, model):
        self.model = model
        self.messages = _Messages(self)


class _AnthropicAdapter(_BaseAdapter):
    """Enveloppe le client Anthropic natif et impose le modele actif (tier/selection).
    Absorbe les differences entre modeles : Haiku ne supporte pas le thinking adaptatif."""
    provider = "anthropic"

    def __init__(self, real_client, model):
        super().__init__(model)
        self._c = real_client

    def _adapter_kw(self, kw):
        kw.pop("model", None)
        # Haiku ne supporte pas adaptive thinking : on le retire pour ce modele.
        if "haiku" in self.model and "thinking" in kw:
            kw.pop("thinking", None)
        return kw

    def _parse(self, **kw):
        return self._c.messages.parse(model=self.model, **self._adapter_kw(kw))

    def _create(self, **kw):
        kw.pop("response_json", None)  # specifique OpenAI-compat/Gemini, sans equivalent Anthropic
        return self._c.messages.create(model=self.model, **self._adapter_kw(kw))


class _OpenAICompatAdapter(_BaseAdapter):
    """openai / deepseek / mistral / local (Ollama) : API chat/completions."""

    def __init__(self, provider, model, api_key, base_url):
        super().__init__(model)
        self.provider: str = provider
        self.api_key = api_key
        self.base_url = (base_url or _OPENAI_COMPAT[provider]).rstrip("/")

    def _is_reasoning(self) -> bool:
        # o1 / o3 / o4-mini : parametres differents (max_completion_tokens, pas de system)
        return self.provider == "openai" and self.model[:1] == "o" and self.model[:3] != "ope"

    def _chat(self, system, messages, max_tokens, response_json):
        msgs = []
        reasoning = self._is_reasoning()
        if system and not reasoning:
            msgs.append({"role": "system", "content": system})
        for m in messages:
            content = _text_of(m["content"])
            if system and reasoning and not msgs:
                content = system + "\n\n" + content  # o-series : pas de role system
            msgs.append({"role": m["role"], "content": content})
        body = {"model": self.model, "messages": msgs}
        if reasoning:
            body["max_completion_tokens"] = max_tokens or 8000
        else:
            body["max_tokens"] = max_tokens or 4096
        if response_json:
            body["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            r = httpx.post(f"{self.base_url}/chat/completions", json=body,
                           headers=headers, timeout=_TIMEOUT)
        except Exception as e:
            raise RuntimeError(nettoyer(f"{self.provider} injoignable : {e}"))
        if r.status_code >= 400:
            raise RuntimeError(nettoyer(f"{self.provider} HTTP {r.status_code} : {r.text[:400]}"))
        data = r.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except Exception:
            raise RuntimeError(nettoyer(f"{self.provider} : reponse inattendue : {str(data)[:300]}"))

    def _parse(self, *, output_format, system=None, messages, max_tokens=None, **kw):
        schema = json.dumps(output_format.model_json_schema(), ensure_ascii=False)
        sys2 = (system or "") + (
            "\n\nIMPORTANT : reponds UNIQUEMENT avec un objet JSON valide, conforme "
            "STRICTEMENT a ce schema JSON (aucun texte, aucune explication hors du JSON) :\n" + schema
        )
        txt = _strip_fences(self._chat(sys2, messages, max_tokens, response_json=True))
        try:
            parsed = output_format.model_validate_json(txt)
        except Exception as e:
            raise RuntimeError(nettoyer(f"{self.provider} : JSON non conforme au schema : {e}"))
        return _ParseResult(parsed)

    def _create(self, *, system=None, messages, max_tokens=None, response_json=False, **kw):
        return _CreateResult(self._chat(system, messages, max_tokens, response_json=response_json))


class _GeminiAdapter(_BaseAdapter):
    """Google Gemini : API generateContent (REST)."""
    provider = "gemini"

    def __init__(self, model, api_key, base_url):
        super().__init__(model)
        self.api_key = api_key
        self.base_url = (base_url or _GEMINI_BASE).rstrip("/")

    def _gen(self, system, messages, max_tokens, response_json):
        contents = []
        for m in messages:
            role = "model" if m["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": _text_of(m["content"])}]})
        body = {"contents": contents,
                "generationConfig": {"maxOutputTokens": max_tokens or 4096}}
        if system:
            body["system_instruction"] = {"parts": [{"text": system}]}
        if response_json:
            body["generationConfig"]["responseMimeType"] = "application/json"
        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        try:
            r = httpx.post(url, json=body, headers={"Content-Type": "application/json"}, timeout=_TIMEOUT)
        except Exception as e:
            raise RuntimeError(nettoyer(f"gemini injoignable : {e}"))
        if r.status_code >= 400:
            raise RuntimeError(nettoyer(f"gemini HTTP {r.status_code} : {r.text[:400]}"))
        data = r.json()
        try:
            return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        except Exception:
            raise RuntimeError(nettoyer(f"gemini : reponse inattendue : {str(data)[:300]}"))

    def _parse(self, *, output_format, system=None, messages, max_tokens=None, **kw):
        schema = json.dumps(output_format.model_json_schema(), ensure_ascii=False)
        sys2 = (system or "") + (
            "\n\nIMPORTANT : reponds UNIQUEMENT avec un objet JSON valide, conforme "
            "STRICTEMENT a ce schema JSON :\n" + schema
        )
        txt = _strip_fences(self._gen(sys2, messages, max_tokens, response_json=True))
        try:
            parsed = output_format.model_validate_json(txt)
        except Exception as e:
            raise RuntimeError(nettoyer(f"gemini : JSON non conforme au schema : {e}"))
        return _ParseResult(parsed)

    def _create(self, *, system=None, messages, max_tokens=None, response_json=False, **kw):
        return _CreateResult(self._gen(system, messages, max_tokens, response_json=response_json))


# ---------------------------------------------------------------------------
# Fabrique : resout (provider, modele, cle) et renvoie l'adaptateur adequat.
# ---------------------------------------------------------------------------
def _tiers_provider(provider: str) -> dict:
    """Tiers d'un provider : TIERS du noyau, sinon modeles ajoutes par evolution gouvernee
    (data-driven). Les modeles custom n'ECRASENT jamais un provider du noyau."""
    base = TIERS.get(provider, {})
    if base:
        return base
    try:
        import evolution_gouvernee
        return evolution_gouvernee.modeles_custom().get(provider, {})
    except Exception:
        return {}


def client(ctx: LLMContext | None = None, tier: str = "fort"):
    """Renvoie un client expose .messages.parse / .messages.create pour le provider du ctx.
    ctx None ou provider anthropic sans cle => Anthropic par defaut (cle credentials).
    Un provider AJOUTE par evolution gouvernee (OpenAI-compatible + base_url) est route
    via l'adaptateur OpenAI-compat."""
    ctx = ctx or LLMContext()
    provider = (ctx.provider or "anthropic").lower()
    tiers = _tiers_provider(provider)
    model = ctx.model or tiers.get(tier) or TIERS["anthropic"]["fort"]
    base_url = ctx.base_url or (tiers.get("base_url") if isinstance(tiers, dict) else None)

    if provider == "anthropic":
        import anthropic
        from generator import _load_api_key
        key = ctx.api_key or _load_api_key()
        return _AnthropicAdapter(anthropic.Anthropic(api_key=key), model)

    if provider == "gemini":
        if not ctx.api_key:
            raise RuntimeError("cle API requise pour le provider 'gemini'")
        return _GeminiAdapter(model, ctx.api_key, base_url)

    # openai / deepseek / mistral / local (noyau) OU provider custom OpenAI-compatible
    # ajoute par evolution (reconnu par son base_url custom).
    if provider in _OPENAI_COMPAT or base_url:
        if not ctx.api_key and provider != "local":
            raise RuntimeError(f"cle API requise pour le provider '{provider}'")
        return _OpenAICompatAdapter(provider, model, ctx.api_key, base_url)

    raise RuntimeError(f"provider inconnu : '{provider}'")


# ---------------------------------------------------------------------------
# VISION : analyser une image (capture d'ecran) avec un modele multimodal.
# Donne des "yeux" a l'agent RPA. Chaque provider a son format d'image.
# ---------------------------------------------------------------------------
# Modeles vision par defaut, par provider (si le modele actif n'est pas multimodal).
VISION_MODELS = {
    "anthropic": "claude-sonnet-5",   # toute la famille Claude voit
    "openai":    "gpt-5.2",
    "gemini":    "gemini-3.5-flash",
    "local":     "llama3.2-vision",      # Ollama : necessite `ollama pull llama3.2-vision` (ou llava)
}


def voir(ctx: LLMContext | None, image_b64: str, prompt: str,
         mime: str = "image/png", max_tokens: int = 1500) -> str:
    """Envoie une image + une consigne a un modele multimodal, renvoie le texte.
    Choisit un modele VISION adapte au provider actif. FALLBACK (coup d'avance) : si le
    provider actif ne voit pas (ex: Ollama sans modele vision) ET qu'une cle Anthropic
    SYSTEME est dispo + NEOGEN_VISION_FALLBACK active, on bascule sur Claude (qui voit)."""
    ctx = ctx or LLMContext()
    try:
        return _voir_impl(ctx, image_b64, prompt, mime, max_tokens)
    except Exception as e_primaire:
        import os as _os
        if _os.environ.get("NEOGEN_VISION_FALLBACK", "").strip().lower() in ("1", "true", "yes", "on") \
           and (ctx.provider or "").lower() != "anthropic":
            try:
                from generator import _load_api_key
                cle_sys = _load_api_key()
                if cle_sys:
                    ctx_fb = LLMContext(provider="anthropic", api_key=cle_sys)
                    return ("[vision via fallback systeme] "
                            + _voir_impl(ctx_fb, image_b64, prompt, mime, max_tokens))
            except Exception:
                pass
        raise e_primaire


def _voir_impl(ctx: LLMContext, image_b64: str, prompt: str, mime: str, max_tokens: int) -> str:
    provider = (ctx.provider or "anthropic").lower()
    model = VISION_MODELS.get(provider, VISION_MODELS["anthropic"])

    if provider == "anthropic":
        import anthropic
        from generator import _load_api_key
        key = ctx.api_key or _load_api_key()
        cl = anthropic.Anthropic(api_key=key)
        res = cl.messages.create(
            model=model, max_tokens=max_tokens,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": image_b64}},
            ]}],
        )
        return _text_of(res.content)

    if provider in _OPENAI_COMPAT:
        base = (ctx.base_url or _OPENAI_COMPAT[provider]).rstrip("/")
        headers = {"Content-Type": "application/json"}
        if ctx.api_key:
            headers["Authorization"] = f"Bearer {ctx.api_key}"
        body = {"model": model, "max_tokens": max_tokens, "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
            ]}]}
        try:
            r = httpx.post(f"{base}/chat/completions", json=body, headers=headers, timeout=_TIMEOUT)
        except Exception as e:
            raise RuntimeError(nettoyer(f"{provider} vision injoignable : {e}"))
        if r.status_code >= 400:
            raise RuntimeError(nettoyer(f"{provider} vision HTTP {r.status_code} : {r.text[:300]}"))
        return r.json()["choices"][0]["message"]["content"] or ""

    if provider == "gemini":
        base = (ctx.base_url or _GEMINI_BASE).rstrip("/")
        body = {"contents": [{"role": "user", "parts": [
            {"text": prompt},
            {"inlineData": {"mimeType": mime, "data": image_b64}},
        ]}], "generationConfig": {"maxOutputTokens": max_tokens}}
        url = f"{base}/models/{model}:generateContent?key={ctx.api_key}"
        try:
            r = httpx.post(url, json=body, headers={"Content-Type": "application/json"}, timeout=_TIMEOUT)
        except Exception as e:
            raise RuntimeError(nettoyer(f"gemini vision injoignable : {e}"))
        if r.status_code >= 400:
            raise RuntimeError(nettoyer(f"gemini vision HTTP {r.status_code} : {r.text[:300]}"))
        data = r.json()
        return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])

    raise RuntimeError(f"vision non supportee pour le provider '{provider}'")


def ctx_pour_tier(ctx: LLMContext | None) -> LLMContext | None:
    """Clone le contexte en effacant le modele explicite, pour que le TIER resolve le
    modele (delegation par tier de l'orchestrateur). Garde provider + cle + base_url."""
    if ctx is None:
        return None
    return LLMContext(provider=ctx.provider, model=None,
                      api_key=ctx.api_key, base_url=ctx.base_url)


def resume_ctx(ctx: LLMContext | None) -> str:
    """Resume lisible et SANS cle du contexte, pour affichage/trace."""
    if ctx is None or not ctx.provider:
        return "anthropic (defaut, cle credentials)"
    m = ctx.model or "(tier par defaut)"
    return f"{ctx.provider} / {m}" + (" + cle fournie" if ctx.api_key else "")


if __name__ == "__main__":
    # Verif sans appel reseau : resolution de tiers + sanitization.
    print("=" * 64)
    print("NEOGEN - GATEWAY : auto-verification (sans appel reseau)")
    print("=" * 64)
    for prov in TIERS:
        row = " | ".join(f"{t}={TIERS[prov][t]}" for t in ("fort", "moyen", "leger"))
        print(f"  {prov:10s} : {row}")
    faux = "sk-proj-" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6"  # format realiste (>=20 alnum)
    ctx = contexte_depuis_headers("openai", "gpt-4o", faux)
    resume = resume_ctx(ctx)
    print("\n  resume (jamais de cle) :", resume)
    assert faux not in resume, "fuite : la cle apparait dans le resume !"
    assert faux not in nettoyer(f"erreur openai avec cle {faux}"), "fuite : sanitizer ne redacte pas la cle !"
    print("  garde-fous OK : resume sans cle + sanitizer redacte une vraie cle en log.")

    # repli host.docker.internal -> NEOGEN_OLLAMA_BASE (jamais resolu sur un VPS Linux,
    # ce tuto par defaut de l'app ne marche que sur Docker Desktop Mac/Windows).
    import os as _os
    _os.environ["NEOGEN_OLLAMA_BASE"] = "http://172.20.0.1:11434/v1"
    ctx_vps = contexte_depuis_headers("local", "qwen2.5", None, "http://host.docker.internal:11434/v1")
    assert ctx_vps.base_url == "http://172.20.0.1:11434/v1", ctx_vps.base_url
    _os.environ.pop("NEOGEN_OLLAMA_BASE", None)
    # sans NEOGEN_OLLAMA_BASE definie (dev local Docker Desktop) : valeur inchangee.
    ctx_local = contexte_depuis_headers("local", "qwen2.5", None, "http://host.docker.internal:11434/v1")
    assert ctx_local.base_url == "http://host.docker.internal:11434/v1", ctx_local.base_url
    print("  repli VPS OK : host.docker.internal -> NEOGEN_OLLAMA_BASE si definie, inchange sinon.")
    print("=" * 64)
