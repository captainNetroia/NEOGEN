"""
VIVARIUM - Sanitizer fail-closed (porte de NetroPraxis/coach-dev-local)

Gardien : aucune donnee (entree client, sortie d'erreur d'un produit, intention) ne doit
atteindre un log, un ledger ou un LLM avec un secret en clair. On detecte et on redacte
les secrets courants (cles AWS, tokens GitHub, JWT, cles API, mots de passe, cles privees).

REGLE FAIL-CLOSED : si le sanitizer lui-meme echoue, on NE laisse PAS passer la donnee :
on renvoie un placeholder entierement redacte. Bloquer plutot que fuiter.

Concu d'apres le sanitizer de NetroPraxis (sanitizer.ts / sanitizer/mod.rs).
Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-18.
"""

from __future__ import annotations
import re

# (motif, etiquette) - ordre important (du plus specifique au plus generique)
_MOTIFS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "CLE_PRIVEE"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"), "CLE_ANTHROPIC"),
    (re.compile(r"\bshpat_[a-fA-F0-9]{32}\b"), "TOKEN_SHOPIFY"),
    (re.compile(r"\bghp_[A-Za-z0-9]{36}\b"), "TOKEN_GITHUB"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"), "TOKEN_GITHUB"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "CLE_OPENAI"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "CLE_AWS"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"), "JWT"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "CLE_GOOGLE"),
    (re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd|pwd|authorization|bearer)\b\s*[:=]\s*['\"]?([^\s'\"]{8,})"), "SECRET"),
]

_REDACTED = "[REDACTED:{}]"


def contient_secret(texte: str) -> bool:
    if not isinstance(texte, str):
        return False
    return any(m.search(texte) for m, _ in _MOTIFS)


def nettoyer(texte) -> str:
    """Redacte les secrets d'un texte. Fail-closed : sur erreur, redacte tout."""
    if texte is None:
        return ""
    try:
        s = texte if isinstance(texte, str) else str(texte)
        for motif, etiquette in _MOTIFS:
            if etiquette == "SECRET":
                # garde le nom de la cle, redacte la valeur
                s = motif.sub(lambda m: f"{m.group(1)}={_REDACTED.format('SECRET')}", s)
            else:
                s = motif.sub(_REDACTED.format(etiquette), s)
        return s
    except Exception:
        return "[REDACTED:FAIL_CLOSED]"


def nettoyer_valeur(v):
    """Nettoie recursivement une valeur (dict/list/str). Les autres types sont laisses tels quels."""
    try:
        if isinstance(v, str):
            return nettoyer(v)
        if isinstance(v, dict):
            return {k: nettoyer_valeur(x) for k, x in v.items()}
        if isinstance(v, list):
            return [nettoyer_valeur(x) for x in v]
        return v
    except Exception:
        return "[REDACTED:FAIL_CLOSED]"


if __name__ == "__main__":
    print("=" * 64)
    print("VIVARIUM - SANITIZER (fail-closed) : demo")
    print("=" * 64)
    echantillons = [
        "voici ma cle AWS AKIA1234567890ABCDEF dans le texte",
        "token=ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        "authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.abc123",
        "password = SuperSecret123!",
        "un texte parfaitement normal sans aucun secret",
    ]
    for e in echantillons:
        print(f"\n  avant : {e}")
        print(f"  apres : {nettoyer(e)}")
    print("\n" + "=" * 64)
    print("Aucun secret ne franchit le sanitizer. Sur panne interne : tout est redacte.")
    print("=" * 64)
