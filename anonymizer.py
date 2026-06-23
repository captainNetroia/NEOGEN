"""
NEOGEN - Anonymiseur RGPD.

Nettoie les données avant envoi télémétrie :
  - emails, IPs, clés API, tokens JWT, noms propres courants
  - URLs avec paramètres, numéros de carte, IBAN
Remplace par des marqueurs [REDACTED_TYPE].
"""
from __future__ import annotations

import re

# Patterns ordonnés du plus spécifique au plus général.
_PATTERNS = [
    # Clés API / tokens (sk_, pk_, Bearer, etc.)
    (re.compile(r'\b(sk|pk|rk|whsec|AIza|ya29|ghp|ghs|glpat|xoxb|xoxp)[-_][A-Za-z0-9_\-]{10,}', re.I), "[REDACTED_KEY]"),
    # JWT
    (re.compile(r'eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]*'), "[REDACTED_JWT]"),
    # Emails
    (re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'), "[REDACTED_EMAIL]"),
    # IPv4
    (re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'), "[REDACTED_IP]"),
    # IBAN
    (re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{4,}(?:\s?\d{4}){1,7}\b'), "[REDACTED_IBAN]"),
    # Numéros de carte (13-19 chiffres consécutifs)
    (re.compile(r'\b(?:\d[ \-]?){13,19}\b'), "[REDACTED_CARD]"),
    # URLs avec query string potentiellement sensibles
    (re.compile(r'https?://[^\s"\'<>]+\?[^\s"\'<>]+'), "[REDACTED_URL_PARAMS]"),
    # Chemins Windows avec username
    (re.compile(r'[A-Z]:\\Users\\[^\\]+', re.I), "[REDACTED_PATH]"),
    # Chemins Unix home
    (re.compile(r'/home/[^/\s]+'), "[REDACTED_PATH]"),
]

# Champs à supprimer entièrement d'un dict (clé insensible à la casse).
_CHAMPS_SENSIBLES = frozenset([
    "password", "mot_de_passe", "secret", "token", "api_key", "apikey",
    "stripe_secret_key", "stripe_webhook_secret", "authorization",
    "credit_card", "carte", "iban", "cvv", "cvc",
])


def nettoyer_texte(texte: str) -> str:
    """Applique tous les patterns regex sur un texte libre."""
    if not isinstance(texte, str):
        return texte
    for pattern, remplacement in _PATTERNS:
        texte = pattern.sub(remplacement, texte)
    return texte


def nettoyer_dict(data: dict, profondeur: int = 5) -> dict:
    """
    Nettoie récursivement un dict :
    - supprime les champs sensibles connus
    - anonymise les valeurs string
    """
    if profondeur <= 0:
        return {}
    result = {}
    for k, v in data.items():
        if str(k).lower() in _CHAMPS_SENSIBLES:
            result[k] = "[REDACTED]"
        elif isinstance(v, dict):
            result[k] = nettoyer_dict(v, profondeur - 1)
        elif isinstance(v, list):
            result[k] = [
                nettoyer_dict(i, profondeur - 1) if isinstance(i, dict)
                else nettoyer_texte(str(i)) if isinstance(i, str)
                else i
                for i in v
            ]
        elif isinstance(v, str):
            result[k] = nettoyer_texte(v)
        else:
            result[k] = v
    return result


if __name__ == "__main__":
    assert "[REDACTED_EMAIL]" in nettoyer_texte("contact@netroia.com")
    assert "[REDACTED_KEY]" in nettoyer_texte("sk_live_abc1234567890xyz")
    assert "[REDACTED_IP]" in nettoyer_texte("IP: 192.168.1.1")
    assert "[REDACTED_JWT]" in nettoyer_texte("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.abc")
    assert "[REDACTED_PATH]" in nettoyer_texte(r"C:\Users\Jordan\secrets.txt")
    d = nettoyer_dict({"email": "x@y.com", "token": "sk_live_xxx", "message": "ok"})
    assert d["token"] == "[REDACTED]"
    assert "[REDACTED_EMAIL]" in d["email"]
    assert d["message"] == "ok"
    print("anonymizer.py : tous les tests OK")
