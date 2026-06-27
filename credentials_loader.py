"""
NEOGEN - Chargement des credentials : SOURCE UNIQUE de vérité.

Avant : 4 implémentations dupliquées (api._load_cred, planificateur._cle_systeme,
generator._load_api_key, passerelle_telegram._token). Un correctif de sécurité
devait être répété 4 fois. Ici : une seule fonction, les autres délèguent.

Ordre de résolution : variable d'env d'abord, puis credentials/ (Docker puis dev local).
Aucune clé n'est loguée ni mise en cache.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-23. (dette F003)
"""
from __future__ import annotations

import os
from pathlib import Path

# Dossiers fouillés, dans l'ordre : Docker (volume monté) puis dev local.
def _dossiers() -> list[Path]:
    ici = Path(__file__).parent
    return [
        Path("/app/credentials"),
        ici / "credentials",
        ici.parent / "credentials",
    ]


def lire_cred(fichier: str, cle: str) -> str:
    """Retourne la valeur de 'cle' : env[cle] d'abord, sinon credentials/{fichier}.
    Chaîne vide si introuvable. Ne lève jamais, ne logue jamais la valeur."""
    val = os.environ.get(cle, "")
    if val:
        return val
    for dossier in _dossiers():
        p = dossier / fichier
        try:
            if p.exists():
                for ligne in p.read_text(encoding="utf-8").splitlines():
                    ligne = ligne.strip()
                    if ligne.startswith(cle + "="):
                        return ligne.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            continue
    return ""


# Mapping provider -> (fichier, clé) pour la résolution multi-provider (cron, gateway système).
PROVIDER_CRED = {
    "anthropic": ("anthropic-api.env", "ANTHROPIC_API_KEY"),
    "openai":    ("openai-api.env",    "OPENAI_API_KEY"),
    "gemini":    ("gemini-api.env",    "GEMINI_API_KEY"),
    "deepseek":  ("deepseek-api.env",  "DEEPSEEK_API_KEY"),
    "mistral":   ("mistral-api.env",   "MISTRAL_API_KEY"),
    "moonshot":  ("moonshot.env",      "MOONSHOT_API_KEY"),
    "glm":       ("zhipu-glm-api.env", "ZHIPU_GLM_API_KEY"),
}


def cle_provider(provider: str) -> str:
    """Clé SYSTEME de l'instance pour un provider (jamais celle d'un utilisateur). Vide si absente."""
    info = PROVIDER_CRED.get((provider or "").lower())
    return lire_cred(*info) if info else ""


if __name__ == "__main__":
    import tempfile
    print("=" * 56)
    print("NEOGEN - CREDENTIALS_LOADER : auto-vérification")
    print("=" * 56)
    # env prioritaire
    os.environ["TEST_CRED_KEY"] = "valeur_env"
    assert lire_cred("inexistant.env", "TEST_CRED_KEY") == "valeur_env"
    del os.environ["TEST_CRED_KEY"]
    # lecture fichier
    d = tempfile.mkdtemp()
    (Path(d) / "x.env").write_text('MA_CLE="abc123"\nAUTRE=zzz\n', encoding="utf-8")
    import credentials_loader as _self
    _self._dossiers = lambda: [Path(d)]   # type: ignore
    assert _self.lire_cred("x.env", "MA_CLE") == "abc123"
    assert _self.lire_cred("x.env", "ABSENTE") == ""
    assert _self.lire_cred("nope.env", "MA_CLE") == ""
    print("  env prioritaire / lecture fichier / clé absente : OK")
    print("=" * 56)
