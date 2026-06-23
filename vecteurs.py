"""
NEOGEN - Algèbre linéaire au service de la mémoire : TF-IDF + similarité cosinus.

Avant : le rappel mémoire et la pertinence des skills se faisaient par COMPTAGE de mots
communs (lexical brut). Ici : chaque texte devient un VECTEUR pondéré (TF-IDF), et la
proximité se mesure par le COSINUS de l'angle entre vecteurs. C'est de la vraie algèbre
linéaire (produit scalaire / normes), pur Python, zéro dépendance lourde (philosophie
zéro-build conservée).

Honnêteté : ce sont des vecteurs LEXICAUX (TF-IDF), pas des embeddings neuronaux. Ça capture
bien la similarité de termes (gros gain vs comptage), sans prétendre au sens profond. Un
backend d'embeddings neuronaux (via un provider) pourra être branché plus tard derrière la
même interface `classer()`.

Maths :
  tf(t,d)   = fréquence du terme t dans le document d (normalisée)
  idf(t)    = ln((1+N) / (1+df(t))) + 1     (df = nb de docs contenant t)
  tfidf     = tf * idf
  cosinus(u,v) = (u·v) / (||u|| · ||v||)     ∈ [0,1] pour des poids positifs

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-23.
"""
from __future__ import annotations

import math
import re
import unicodedata

# Mots vides FR/EN très fréquents : ils n'apportent pas de sens discriminant.
_STOP = frozenset("""
le la les un une des de du d en et à a au aux ce cette ces mon ma mes ton ta tes son sa ses
notre nos votre vos leur leurs je tu il elle on nous vous ils elles que qui quoi dont où est
sont être avoir fait pour par sur dans avec sans sous chez vers plus moins très bien
the a an of to in and or is are be was were it this that these those for on with as at by
i you he she we they my your his her our their do does done can will would should
""".split())


def _normaliser(texte: str) -> str:
    base = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode()
    return base.lower()


def tokeniser(texte: str) -> list[str]:
    """Texte -> liste de tokens normalisés (sans accents, sans mots vides, len>=2)."""
    mots = re.findall(r"[a-z0-9]+", _normaliser(texte))
    return [m for m in mots if len(m) >= 2 and m not in _STOP]


def _tf(tokens: list[str]) -> dict[str, float]:
    if not tokens:
        return {}
    n = len(tokens)
    compte: dict[str, float] = {}
    for t in tokens:
        compte[t] = compte.get(t, 0.0) + 1.0
    return {t: c / n for t, c in compte.items()}


def construire_idf(documents: list[str]) -> dict[str, float]:
    """IDF lissé sur un corpus de documents."""
    n = len(documents)
    df: dict[str, int] = {}
    for doc in documents:
        for t in set(tokeniser(doc)):
            df[t] = df.get(t, 0) + 1
    return {t: math.log((1 + n) / (1 + d)) + 1.0 for t, d in df.items()}


def vectoriser(texte: str, idf: dict[str, float]) -> dict[str, float]:
    """Vecteur TF-IDF creux (dict terme->poids) d'un texte, selon l'IDF du corpus."""
    tf = _tf(tokeniser(texte))
    return {t: w * idf.get(t, 1.0) for t, w in tf.items()}


def cosinus(u: dict[str, float], v: dict[str, float]) -> float:
    """Similarité cosinus entre deux vecteurs creux. 0 si l'un est nul."""
    if not u or not v:
        return 0.0
    # Produit scalaire sur l'intersection des termes.
    petit, grand = (u, v) if len(u) <= len(v) else (v, u)
    dot = sum(w * grand.get(t, 0.0) for t, w in petit.items())
    if dot == 0.0:
        return 0.0
    nu = math.sqrt(sum(w * w for w in u.values()))
    nv = math.sqrt(sum(w * w for w in v.values()))
    return dot / (nu * nv) if nu and nv else 0.0


def classer(requete: str, documents: list[str], limite: int | None = None,
            seuil: float = 0.0) -> list[tuple[int, float]]:
    """Classe les documents par similarité cosinus DÉCROISSANTE à la requête.
    Retourne [(index_doc, score), ...]. L'IDF est construit sur requête + documents
    (le terme de la requête absent du corpus garde un IDF par défaut)."""
    if not documents:
        return []
    idf = construire_idf([requete] + documents)
    vq = vectoriser(requete, idf)
    scores = []
    for i, doc in enumerate(documents):
        s = cosinus(vq, vectoriser(doc, idf))
        if s > seuil:
            scores.append((i, s))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:limite] if limite else scores


if __name__ == "__main__":
    print("=" * 60)
    print("NEOGEN - VECTEURS (TF-IDF + cosinus) : auto-vérification")
    print("=" * 60)
    # Propriétés du cosinus
    idf = construire_idf(["chat noir", "chien blanc", "chat blanc"])
    v1 = vectoriser("chat noir", idf)
    assert abs(cosinus(v1, v1) - 1.0) < 1e-9, "cosinus(v,v) doit valoir 1"
    assert cosinus(vectoriser("chat", idf), vectoriser("xyz", idf)) == 0.0, "termes disjoints -> 0"

    # Pertinence : une requête retrouve le bon document
    docs = [
        "Jordan préfère Stripe pour les paiements e-commerce",
        "La délégation parallèle utilise un pool de threads et l'isolation",
        "Le mode jugé génère deux stratégies et garde la meilleure",
    ]
    res = classer("comment fonctionne le paiement stripe", docs, limite=3)
    assert res and res[0][0] == 0, f"le doc paiement devrait sortir 1er : {res}"
    res2 = classer("threads et isolation des agents", docs)
    assert res2[0][0] == 1, f"le doc délégation devrait sortir 1er : {res2}"

    # Robustesse : requête vide / docs vides
    assert classer("", docs) == [] or classer("", docs)[0][1] >= 0
    assert classer("test", []) == []
    print("  cosinus(identité/disjoint) + classement pertinent + robustesse : OK")
    print("=" * 60)
