"""
VIVARIUM - Incarner : l'IA donne une physique a n'importe quel mot

Jusqu'ici je reglais a la main que "eau" a densite 0.55, charge -0.3.
Ici, tu donnes un mot, et Claude lui attribue sa nature physique. Puis on
laisse deux mots incarnes se rencontrer, et le comportement emerge des lois.

C'est la fusion de matiere.py (la physique du sens) et de generator.py (l'IA).
Vrai appel a Claude (claude-opus-4-8). La nature attribuee est le JUGEMENT de
Claude sur la "physique" d'un mot : c'est reel, mais c'est une opinion, pas une
verite objective.

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-17.
"""

from __future__ import annotations
import sys

import anthropic
from pydantic import BaseModel, Field

from matiere import Matiere, rencontre, DEFAUT
from generator import _load_api_key, MODEL


class NaturePhysique(BaseModel):
    densite: float = Field(ge=0, le=1, description="poids/compacite : 0 leger, 1 lourd")
    fluidite: float = Field(ge=0, le=1, description="0 rigide garde sa forme, 1 coule/s'adapte")
    temperature: float = Field(ge=0, le=1, description="0 froid/inerte, 1 brulant/volatil")
    cohesion: float = Field(ge=0, le=1, description="0 se disperse, 1 tient fortement ensemble")
    charge: float = Field(ge=-1, le=1, description="affinite : -1 repousse, +1 attire")
    abstrait: bool = Field(description="true si c'est une idee, false si c'est une matiere physique")
    justification: str = Field(description="une phrase expliquant ces choix")


SYSTEME = (
    "Tu donnes une PHYSIQUE a un mot, pour un monde ou le sens a une matiere.\n"
    "On te donne un mot. Tu lui attribues des proprietes physiques coherentes avec ce "
    "qu'il evoque, sur ces echelles :\n"
    "- densite 0..1 : leger (fumee, idee) -> lourd (plomb, certitude)\n"
    "- fluidite 0..1 : rigide (pierre, dogme) -> coulant (eau, doute)\n"
    "- temperature 0..1 : froid/inerte (glace, calme) -> brulant/volatil (feu, colere)\n"
    "- cohesion 0..1 : se disperse (sable, rumeur) -> tient ensemble (acier, confiance)\n"
    "- charge -1..1 : repousse les autres (acide, mefiance) -> attire (aimant, amour)\n"
    "- abstrait : true pour une idee, false pour une matiere reelle\n"
    "Sois fidele a l'intuition qu'on a du mot. Une phrase de justification."
)


def incarner(mot: str, client: anthropic.Anthropic) -> tuple[Matiere, str]:
    """Demande a Claude la physique d'un mot, renvoie une Matiere + la justification."""
    resp = client.messages.parse(
        model=MODEL,
        max_tokens=8000,
        thinking={"type": "adaptive"},
        system=SYSTEME,
        messages=[{"role": "user", "content": f"Mot : {mot}"}],
        output_format=NaturePhysique,
    )
    n = resp.parsed_output
    if n is None:
        raise RuntimeError(f"Claude n'a pas pu incarner '{mot}' (stop_reason={resp.stop_reason})")
    m = Matiere(nom=mot, densite=n.densite, fluidite=n.fluidite, temperature=n.temperature,
                cohesion=n.cohesion, charge=n.charge, abstrait=n.abstrait)
    return m, n.justification


def confronter(mot_a: str, mot_b: str):
    client = anthropic.Anthropic(api_key=_load_api_key())

    print("=" * 70)
    print(f"VIVARIUM - INCARNER : '{mot_a}' rencontre '{mot_b}'")
    print(f"(Claude attribue la physique de chaque mot - vrai appel {MODEL})")
    print("=" * 70)

    a, just_a = incarner(mot_a, client)
    print(f"\n[Claude incarne] {a}")
    print(f"   justification : {just_a}")

    b, just_b = incarner(mot_b, client)
    print(f"\n[Claude incarne] {b}")
    print(f"   justification : {just_b}")

    print("\n--- ce qui emerge de leur rencontre (lois universelles, rien code par paire) ---")
    journal, produits = rencontre(a, b, DEFAUT)
    for ligne in journal:
        print("  " + ligne)
    for p in produits:
        print("   -> ne :", p)
    if not produits:
        print("   (aucune nouvelle matiere ; cf. le journal pour le comportement)")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) >= 2:
        confronter(args[0], args[1])
    else:
        confronter("glace", "feu")
