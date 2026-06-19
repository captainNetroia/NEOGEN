"""
NEOGEN - Generateur de cellules via Claude
Etape v2 : remplace le generateur simule par du vrai code genere par Claude.

Donne un besoin en langage naturel ("ajoute une recherche de notes"), Claude
renvoie une cellule structuree (nom, description, effets declares, scores
curseurs, et le code Python reel). La cellule passe ensuite par la Membrane de
NEOGEN.py, qui la valide contre les murs du noyau grave.

Cle API : chargee depuis C:\\Netroia\\credentials\\anthropic-api.env (jamais en dur).
Modele : claude-opus-4-8, thinking adaptatif, sortie structuree (Pydantic).
"""

import os
import re
import time
from pathlib import Path

import anthropic
from pydantic import BaseModel, Field

from NEOGEN import Cell, Genome

CRED_FILE = Path(r"C:\Netroia\credentials\anthropic-api.env")
MODEL = "claude-opus-4-8"


# ---------------------------------------------------------------------------
# Resilience : circuit breaker + retries (porte de NetroPraxis circuit_breaker.rs)
# Protege contre les pannes API transitoires (ECONNRESET, timeouts, surcharge, 5xx).
# ---------------------------------------------------------------------------
class CircuitBreaker:
    def __init__(self, seuil: int = 4, cooldown: float = 30.0):
        self.seuil, self.cooldown = seuil, cooldown
        self.echecs, self.ouvert_jusqu = 0, 0.0

    def disponible(self) -> bool:
        return time.time() >= self.ouvert_jusqu

    def succes(self):
        self.echecs, self.ouvert_jusqu = 0, 0.0

    def echec(self):
        self.echecs += 1
        if self.echecs >= self.seuil:
            self.ouvert_jusqu = time.time() + self.cooldown


_BREAKER = CircuitBreaker()

_MARQUEURS_TRANSITOIRES = ("connection", "timeout", "timed out", "overloaded", "econnreset",
                           "reset by peer", "temporarily", "503", "502", "529", "rate limit", "429")


def _est_transitoire(e: Exception) -> bool:
    nom = type(e).__name__.lower()
    txt = str(e).lower()
    if any(k in nom for k in ("connection", "timeout", "ratelimit", "internalserver", "overloaded")):
        return True
    return any(k in txt for k in _MARQUEURS_TRANSITOIRES)


def parse_resilient(client, *, tentatives: int = 3, base_delai: float = 2.0, **kwargs):
    """Wrappe client.messages.parse : retries (backoff) sur erreurs transitoires + circuit breaker.
    Les erreurs non-transitoires (400, refus, schema) remontent immediatement."""
    if not _BREAKER.disponible():
        raise RuntimeError("Circuit API ouvert : trop d'echecs recents, protection active. Reessayer plus tard.")
    derniere = None
    for i in range(tentatives):
        try:
            r = client.messages.parse(**kwargs)
            _BREAKER.succes()
            return r
        except Exception as e:
            derniere = e
            if not _est_transitoire(e):
                _BREAKER.echec()
                raise
            _BREAKER.echec()
            if not _BREAKER.disponible() or i == tentatives - 1:
                break
            time.sleep(base_delai * (2 ** i))
    raise derniere


# ---------------------------------------------------------------------------
# Chargement de la cle API depuis les credentials (jamais dans le code)
# ---------------------------------------------------------------------------
def _load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    if CRED_FILE.exists():
        for line in CRED_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r'^(?:export\s+)?([A-Z0-9_]+)\s*=\s*"?([^"]+)"?$', line)
            if m and ("ANTHROPIC" in m.group(1) or m.group(2).startswith("sk-ant-")):
                return m.group(2)
    raise RuntimeError(
        "Cle Anthropic introuvable. Definir ANTHROPIC_API_KEY ou la placer "
        f"dans {CRED_FILE}"
    )


# ---------------------------------------------------------------------------
# Schema de sortie structuree : ce que Claude doit renvoyer
# ---------------------------------------------------------------------------
class DeclaredEffects(BaseModel):
    """Effets que la cellule PRETEND avoir. La Membrane les confronte au reel."""
    deletes_data: bool = Field(description="La fonction supprime-t-elle des donnees ?")
    asks_confirmation: bool = Field(description="Demande-t-elle confirmation avant de supprimer ?")
    network_access: bool = Field(description="Accede-t-elle au reseau / a l'exterieur ?")
    authorized_network: bool = Field(description="Si reseau, est-ce explicitement autorise ?")


class CursorScores(BaseModel):
    """Auto-evaluation honnete de la cellule sur les curseurs du noyau (0-100)."""
    simplicite: int = Field(ge=0, le=100)
    vitesse: int = Field(ge=0, le=100)
    lisibilite: int = Field(ge=0, le=100)


class GeneratedCell(BaseModel):
    name: str = Field(description="Nom de fonction en snake_case, sans espaces")
    description: str = Field(description="Une phrase decrivant ce que fait la cellule")
    code: str = Field(description="Le code Python complet de la fonction, autonome")
    declared_effects: DeclaredEffects
    cursor_scores: CursorScores


# ---------------------------------------------------------------------------
# Construction du prompt systeme a partir du noyau grave
# ---------------------------------------------------------------------------
def _system_prompt(genome: Genome) -> str:
    murs = "\n".join(f"  - {w['id']} : {w['label']}" for w in genome.walls)
    curseurs = ", ".join(f"{k} ({v})" for k, v in genome.cursors.items())
    return (
        "Tu es le generateur de cellules de NEOGEN, un organisme logiciel a noyau grave.\n"
        "On te donne un besoin. Tu produis UNE fonction Python autonome, et tu declares "
        "honnetement ses effets. Ta cellule sera mise en quarantaine et confrontee aux murs : "
        "si tu mens sur tes effets, elle est rejetee.\n\n"
        f"OBJECTIF DU PROJET : {genome.objective}\n\n"
        f"MURS ABSOLUS (a ne jamais violer) :\n{murs}\n\n"
        f"CURSEURS d'arbitrage (pondere par le noyau) : {curseurs}\n\n"
        "REGLES :\n"
        "- Declare deletes_data=true si la fonction supprime quoi que ce soit, et dans ce cas "
        "asks_confirmation doit refleter la realite de ton code.\n"
        "- Declare network_access=true si ton code touche au reseau ; authorized_network "
        "uniquement si l'autorisation est explicite et visible dans le code.\n"
        "- N'essaie jamais de contourner un mur. Si le besoin l'exige, ecris le code conforme "
        "(ex : demander confirmation avant suppression).\n"
        "- Scores curseurs : auto-evaluation honnete de 0 a 100.\n"
        "- Le code doit etre du Python pur, autonome, sans dependance exotique."
    )


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
def generate_cell(need: str, genome: Genome, origin: str = "generated") -> Cell:
    """Demande a Claude une cellule pour 'need', renvoie une NEOGEN.Cell prete pour la Membrane."""
    client = anthropic.Anthropic(api_key=_load_api_key())

    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=_system_prompt(genome),
        messages=[{"role": "user", "content": f"Besoin : {need}"}],
        output_format=GeneratedCell,
    )
    g = response.parsed_output
    if g is None:
        raise RuntimeError(
            f"Claude n'a pas produit de cellule valide (stop_reason={response.stop_reason})"
        )

    cell = Cell(
        name=g.name,
        description=g.description,
        origin=origin,
        declared_effects=g.declared_effects.model_dump(),
        cursor_scores=g.cursor_scores.model_dump(),
        actual_effects={},  # le code genere fait ce qu'il declare ; la quarantaine verifie
        parent="claude:" + MODEL,
    )
    cell.code = g.code  # le code Python genere, attache pour la suite (apoptose/execution)
    return cell


if __name__ == "__main__":
    import sys

    BASE = Path(__file__).resolve().parent
    genome = Genome(str(BASE / "genome.json"))
    besoin = " ".join(sys.argv[1:]) or "Ajoute une recherche plein texte dans les notes"

    print(f"[GENERATOR] Besoin : {besoin}")
    print(f"[GENERATOR] Appel a {MODEL} (thinking adaptatif)...\n")
    cell = generate_cell(besoin, genome)
    print(f"Cellule generee : {cell.name}")
    print(f"  Description : {cell.description}")
    print(f"  Effets declares : {cell.declared_effects}")
    print(f"  Scores curseurs : {cell.cursor_scores}")
    print("\n--- Code genere ---")
    print(cell.code)

    # On la passe immediatement par la Membrane pour la valider contre les murs.
    from NEOGEN import NEOGEN

    def humain(c):
        eff = c.effective_effects()
        ok = bool((eff.get("deletes_data") and eff.get("asks_confirmation"))
                  or (eff.get("network_access") and eff.get("authorized_network")))
        return (ok, "garde-fou present" if ok else "protection insuffisante")

    v = NEOGEN(str(BASE / "genome.json"), human_decision=humain)
    decision, reason, score = v.integrate(cell)
    print(f"\n[MEMBRANE] {decision} (score={score})")
    print(f"           {reason}")
