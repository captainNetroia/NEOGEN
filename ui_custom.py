"""
NEOGEN - Code interface du proprietaire (forge UI Python). PERMANENT, versionne git.

Ecrit/reecrit UNIQUEMENT par forge_ui_python.py (backup + compile-check + rollback). Fichier
ISOLE : une erreur ici ne peut jamais empecher le serveur de demarrer (rendre_page fail-closed).
Ne pas editer a la main : passer par la forge UI (section Evolution).
"""
from __future__ import annotations

# {zone: html} — rempli par forge_ui_python. Vide par defaut (interface d'origine).
BLOCS: dict[str, str] = {}
