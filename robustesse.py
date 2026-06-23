"""
NEOGEN - Socle de robustesse : le "coup d'avance" universel.

Doctrine NEOGEN (appliquee partout) :
  - le nom = la promesse  - fonctionnel & teste  - automatique  - idempotent
  - erreur capturee -> loguee -> solutionnee  - toujours un coup d'avance.

Ce module est la fondation transverse. TOUT le reste s'y branche pour ne jamais
echouer silencieusement et pour anticiper les pannes (Ollama eteint, cle absente,
reseau coupe, container tombe) par une degradation gracieuse.

Briques :
  journaliser()          journal structure unique (data/journal_systeme.jsonl), sanitize, borne.
  reessayer()            retry + backoff exponentiel, chaque echec logue, derniere erreur remontee.
  garde() / protege      execution qui NE PLANTE JAMAIS : logue + renvoie un defaut.
  deja_fait/marquer_fait idempotence par cle (persistee), TTL optionnel.
  Disjoncteur            circuit-breaker par ressource : coupe apres N echecs, re-essaie apres cooldown.
  battement()/sante()    heartbeat des composants (cron, telegram, agent) -> etat de sante observable.

Aucune dependance lourde : stdlib + sanitizer. Thread-safe (verrous).
Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-23.
"""
from __future__ import annotations

import json
import os
import threading
import time
import traceback
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Iterable

try:
    from sanitizer import nettoyer
except Exception:  # le socle ne doit jamais dependre d'un import qui echoue
    def nettoyer(x):  # type: ignore
        return x

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(BASE_DIR, "data")
JOURNAL = os.path.join(_DATA, "journal_systeme.jsonl")
IDEMPOTENCE = os.path.join(_DATA, "idempotence.json")
SANTE = os.path.join(_DATA, "sante.json")

_LOCK_JOURNAL = threading.Lock()
_LOCK_IDEM = threading.Lock()
_LOCK_SANTE = threading.Lock()
_LOCK_CB = threading.Lock()

# Rotation simple : si le journal depasse cette taille, on garde la moitie recente.
_JOURNAL_MAX_OCTETS = 2_000_000
NIVEAUX = ("debug", "info", "succes", "alerte", "erreur", "critique")


# ── Journal structure ─────────────────────────────────────────────────────────

def journaliser(evenement: str, niveau: str = "info", *, source: str = "", **details) -> dict:
    """Ecrit une entree de journal structuree (sanitizee, bornee). Ne leve jamais.
    Retourne l'entree ecrite (utile pour les tests/chaînage)."""
    entree = {
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%d %H:%M:%S"),
        "niveau": niveau if niveau in NIVEAUX else "info",
        "source": str(source)[:60],
        "evenement": str(nettoyer(evenement))[:500],
    }
    if details:
        # Sanitize chaque valeur texte ; borne la taille pour ne pas exploser le fichier.
        safe = {}
        for k, v in details.items():
            if isinstance(v, str):
                safe[k] = str(nettoyer(v))[:1000]
            elif isinstance(v, (int, float, bool)) or v is None:
                safe[k] = v
            else:
                safe[k] = str(nettoyer(str(v)))[:1000]
        entree["details"] = safe
    try:
        with _LOCK_JOURNAL:
            os.makedirs(_DATA, exist_ok=True)
            _rotation_si_besoin()
            with open(JOURNAL, "a", encoding="utf-8") as f:
                f.write(json.dumps(entree, ensure_ascii=False) + "\n")
    except Exception:
        pass  # un journal qui echoue ne doit JAMAIS casser l'appelant
    return entree


def _rotation_si_besoin() -> None:
    """Garde la moitie recente du journal s'il devient trop gros (best-effort)."""
    try:
        if not os.path.exists(JOURNAL) or os.path.getsize(JOURNAL) < _JOURNAL_MAX_OCTETS:
            return
        with open(JOURNAL, encoding="utf-8") as f:
            lignes = f.readlines()
        garder = lignes[len(lignes) // 2:]
        with open(JOURNAL, "w", encoding="utf-8") as f:
            f.writelines(garder)
    except Exception:
        pass


def lire_journal(limite: int = 100, niveau_min: str | None = None,
                 source: str | None = None) -> list[dict]:
    """Dernieres entrees du journal (plus recentes d'abord), filtrables."""
    if not os.path.exists(JOURNAL):
        return []
    seuil = NIVEAUX.index(niveau_min) if niveau_min in NIVEAUX else 0
    out = []
    try:
        with open(JOURNAL, encoding="utf-8") as f:
            for ligne in f:
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    e = json.loads(ligne)
                except Exception:
                    continue
                if NIVEAUX.index(e.get("niveau", "info")) < seuil:
                    continue
                if source and e.get("source") != source:
                    continue
                out.append(e)
    except Exception:
        return []
    return list(reversed(out))[:limite]


# ── Retry + backoff exponentiel ────────────────────────────────────────────────

def reessayer(fn: Callable, *, tentatives: int = 3, delai: float = 1.0, backoff: float = 2.0,
              exceptions: tuple = (Exception,), nom: str = "", source: str = "",
              sur_echec: Callable | None = None) -> Any:
    """Execute fn() ; en cas d'exception, re-essaie avec backoff exponentiel.
    Chaque echec est logue. Si tout echoue, appelle sur_echec() si fourni, sinon releve.
    'nom' = libelle de l'operation pour le journal."""
    label = nom or getattr(fn, "__name__", "operation")
    derniere = None
    d = delai
    for essai in range(1, max(1, tentatives) + 1):
        try:
            res = fn()
            if essai > 1:
                journaliser(f"{label} : reussi apres {essai} essais", "succes", source=source)
            return res
        except exceptions as e:
            derniere = e
            journaliser(f"{label} : echec essai {essai}/{tentatives}", "alerte",
                        source=source, erreur=str(e))
            if essai < tentatives:
                time.sleep(d)
                d *= backoff
    journaliser(f"{label} : echec definitif apres {tentatives} essais", "erreur",
                source=source, erreur=str(derniere))
    if sur_echec is not None:
        return sur_echec(derniere)
    raise derniere if derniere else RuntimeError(f"{label} a echoue")


def avec_reessai(*, tentatives: int = 3, delai: float = 1.0, backoff: float = 2.0,
                 exceptions: tuple = (Exception,), source: str = ""):
    """Decorateur : applique reessayer() a une fonction."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            return reessayer(lambda: fn(*a, **k), tentatives=tentatives, delai=delai,
                             backoff=backoff, exceptions=exceptions,
                             nom=fn.__name__, source=source)
        return wrapper
    return deco


# ── Garde anti-crash : ne plante jamais ────────────────────────────────────────

@contextmanager
def garde(operation: str, *, source: str = "", reraise: bool = False):
    """Bloc protege : toute exception est capturee + loguee (jamais propagee, sauf reraise)."""
    try:
        yield
    except Exception as e:
        journaliser(f"{operation} : exception capturee", "erreur", source=source,
                    erreur=str(e), trace=traceback.format_exc()[-800:])
        if reraise:
            raise


def protege(fn: Callable, *, defaut: Any = None, operation: str = "", source: str = "") -> Any:
    """Execute fn() en absorbant toute exception ; logue et renvoie 'defaut' a l'echec."""
    label = operation or getattr(fn, "__name__", "operation")
    try:
        return fn()
    except Exception as e:
        journaliser(f"{label} : exception capturee", "erreur", source=source,
                    erreur=str(e), trace=traceback.format_exc()[-800:])
        return defaut


# ── Idempotence : une operation marquee n'est pas refaite ───────────────────────

def _lire_idem() -> dict:
    if not os.path.exists(IDEMPOTENCE):
        return {}
    try:
        with open(IDEMPOTENCE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _ecrire_idem(d: dict) -> None:
    os.makedirs(_DATA, exist_ok=True)
    with open(IDEMPOTENCE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def deja_fait(cle: str, *, ttl_s: float | None = None) -> bool:
    """True si 'cle' a deja ete marquee faite (et non expiree si ttl)."""
    with _LOCK_IDEM:
        d = _lire_idem()
        e = d.get(cle)
        if not e:
            return False
        if ttl_s is not None and (time.time() - e.get("ts", 0)) > ttl_s:
            return False
        return True


def marquer_fait(cle: str, **meta) -> None:
    """Marque 'cle' comme faite (idempotence). meta optionnelle (sanitizee)."""
    with _LOCK_IDEM:
        d = _lire_idem()
        d[cle] = {"ts": time.time(), **{k: str(nettoyer(str(v)))[:200] for k, v in meta.items()}}
        # Borne : garde les 1000 plus recentes.
        if len(d) > 1000:
            items = sorted(d.items(), key=lambda kv: kv[1].get("ts", 0), reverse=True)[:1000]
            d = dict(items)
        _ecrire_idem(d)


def une_seule_fois(cle: str, fn: Callable, *, ttl_s: float | None = None, defaut: Any = None) -> Any:
    """Execute fn() seulement si 'cle' n'a pas deja ete faite. Idempotent. Renvoie le resultat
    ou 'defaut' si deja fait/echec."""
    if deja_fait(cle, ttl_s=ttl_s):
        return defaut
    res = protege(fn, defaut=defaut, operation=f"une_seule_fois[{cle}]")
    marquer_fait(cle)
    return res


# ── Disjoncteur (circuit-breaker) par ressource ─────────────────────────────────

class Disjoncteur:
    """Coupe une ressource defaillante apres N echecs consecutifs ; re-tente apres cooldown.
    Etats : ferme (ok) -> ouvert (coupe) -> demi-ouvert (1 essai test) -> ferme/ouvert.
    Sert a anticiper : si Ollama tombe, on arrete de marteler et on logue clairement."""
    _instances: dict[str, "Disjoncteur"] = {}

    def __init__(self, nom: str, seuil: int = 3, cooldown_s: float = 60.0):
        self.nom = nom
        self.seuil = seuil
        self.cooldown_s = cooldown_s
        self.echecs = 0
        self.ouvert_depuis = 0.0

    @classmethod
    def pour(cls, nom: str, seuil: int = 3, cooldown_s: float = 60.0) -> "Disjoncteur":
        with _LOCK_CB:
            d = cls._instances.get(nom)
            if d is None:
                d = cls(nom, seuil, cooldown_s)
                cls._instances[nom] = d
            return d

    def disponible(self) -> bool:
        """True si on peut tenter la ressource (ferme, ou demi-ouvert apres cooldown)."""
        if self.echecs < self.seuil:
            return True
        if (time.time() - self.ouvert_depuis) >= self.cooldown_s:
            return True  # demi-ouvert : on autorise un essai test
        return False

    def succes(self) -> None:
        if self.echecs:
            journaliser(f"disjoncteur '{self.nom}' : ressource retablie", "succes", source="robustesse")
        self.echecs = 0
        self.ouvert_depuis = 0.0

    def echec(self) -> None:
        self.echecs += 1
        if self.echecs == self.seuil:
            self.ouvert_depuis = time.time()
            journaliser(f"disjoncteur '{self.nom}' : OUVERT ({self.echecs} echecs) -> ressource coupee {self.cooldown_s}s",
                        "alerte", source="robustesse")

    def appeler(self, fn: Callable, *, defaut: Any = None) -> Any:
        """Execute fn() sous protection du disjoncteur. Si ouvert : renvoie defaut sans appeler."""
        if not self.disponible():
            journaliser(f"disjoncteur '{self.nom}' ouvert : appel court-circuite", "info", source="robustesse")
            return defaut
        try:
            res = fn()
            self.succes()
            return res
        except Exception as e:
            self.echec()
            journaliser(f"disjoncteur '{self.nom}' : echec d'appel", "erreur", source="robustesse", erreur=str(e))
            return defaut


# ── Heartbeat / sante des composants ────────────────────────────────────────────

def _lire_sante() -> dict:
    if not os.path.exists(SANTE):
        return {}
    try:
        with open(SANTE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def battement(composant: str, **etat) -> None:
    """Enregistre un 'je suis vivant' horodate pour un composant (cron, telegram, agent...)."""
    with _LOCK_SANTE:
        d = _lire_sante()
        d[composant] = {"dernier": time.time(),
                        "iso": time.strftime("%Y-%m-%d %H:%M:%S"),
                        **{k: (v if isinstance(v, (int, float, bool)) or v is None
                               else str(nettoyer(str(v)))[:200]) for k, v in etat.items()}}
        try:
            os.makedirs(_DATA, exist_ok=True)
            with open(SANTE, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def sante(seuil_silence_s: float = 300.0) -> dict:
    """Etat de sante observable : pour chaque composant, vivant=True si battement recent."""
    d = _lire_sante()
    now = time.time()
    composants = {}
    for nom, e in d.items():
        age = now - e.get("dernier", 0)
        composants[nom] = {
            "vivant": age <= seuil_silence_s,
            "age_s": int(age),
            "iso": e.get("iso"),
            **{k: v for k, v in e.items() if k not in ("dernier", "iso")},
        }
    return {"composants": composants, "ts": now}


# ── Auto-verification ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile
    print("=" * 64)
    print("NEOGEN - ROBUSTESSE : auto-verification")
    print("=" * 64)
    # Isolation : redirige les fichiers vers un dossier temporaire.
    tmp = tempfile.mkdtemp()
    JOURNAL = os.path.join(tmp, "j.jsonl")
    IDEMPOTENCE = os.path.join(tmp, "i.json")
    SANTE = os.path.join(tmp, "s.json")
    _DATA = tmp

    # 1) Journal
    journaliser("test info", "info", source="auto")
    journaliser("test erreur", "erreur", source="auto", erreur="boom")
    assert len(lire_journal()) == 2
    assert len(lire_journal(niveau_min="erreur")) == 1
    print("  journal : ecriture + filtre niveau OK")

    # 2) Retry : echoue 2 fois puis reussit
    compteur = {"n": 0}
    def flaky():
        compteur["n"] += 1
        if compteur["n"] < 3:
            raise ValueError("pas encore")
        return "ok"
    assert reessayer(flaky, tentatives=5, delai=0.01, nom="flaky") == "ok"
    assert compteur["n"] == 3
    # Retry : echec definitif -> sur_echec
    assert reessayer(lambda: (_ for _ in ()).throw(RuntimeError("x")),
                     tentatives=2, delai=0.01, sur_echec=lambda e: "fallback") == "fallback"
    print("  reessayer : succes apres retries + fallback OK")

    # 3) Garde / protege
    assert protege(lambda: 1 / 0, defaut="securise") == "securise"
    with garde("bloc test"):
        raise KeyError("capturee")
    print("  garde / protege : aucune exception propagee OK")

    # 4) Idempotence
    assert not deja_fait("k1")
    marquer_fait("k1")
    assert deja_fait("k1")
    runs = {"n": 0}
    une_seule_fois("k2", lambda: runs.update(n=runs["n"] + 1))
    une_seule_fois("k2", lambda: runs.update(n=runs["n"] + 1))
    assert runs["n"] == 1, runs
    # TTL : expire -> refaisable
    marquer_fait("k3")
    assert deja_fait("k3", ttl_s=100)
    time.sleep(0.02)
    assert not deja_fait("k3", ttl_s=0.01)
    print("  idempotence : marquer / une_seule_fois / TTL OK")

    # 5) Disjoncteur
    cb = Disjoncteur.pour("test_res", seuil=2, cooldown_s=0.05)
    assert cb.appeler(lambda: "ok") == "ok"
    cb.appeler(lambda: (_ for _ in ()).throw(RuntimeError("1")))
    cb.appeler(lambda: (_ for _ in ()).throw(RuntimeError("2")))
    assert not cb.disponible(), "doit etre ouvert apres 2 echecs"
    time.sleep(0.06)
    assert cb.disponible(), "doit etre demi-ouvert apres cooldown"
    cb.appeler(lambda: "retabli")
    assert cb.disponible() and cb.echecs == 0
    print("  disjoncteur : ouverture / cooldown / retablissement OK")

    # 6) Heartbeat / sante
    battement("cron", taches=3)
    s = sante()
    assert s["composants"]["cron"]["vivant"] is True
    assert s["composants"]["cron"]["taches"] == 3
    print("  battement / sante : composant vivant detecte OK")

    print("=" * 64)
    print("  TOUT VERT.")
    print("=" * 64)
