"""
NEOGEN - Architecture Genetique a Noyau Grave
Prototype v1 - cas neutre (zero dependance, stdlib uniquement)

Trois couches :
  1. NOYAU GRAVE  (Genome)     : objectif, murs, curseurs, droit humain, regle d'amendement
  2. MEMBRANE     (Membrane)   : generation + quarantaine adversariale + controle des murs + escalade
  3. CYTOPLASME   (NEOGEN)   : cellules vivantes, curseurs, ledger de lignee, apoptose, budget
  + SIGNALISATION (Signaling)  : langage inter-cellulaire avec provenance, confiance, decay

Conception : Jordan VINCENT (NetroIA) avec Claude. 2026-06-16.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Callable, Optional

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
os.makedirs(DATA, exist_ok=True)
LEDGER_FILE = os.path.join(DATA, "ledger.jsonl")
AMEND_FILE = os.path.join(DATA, "amendments.jsonl")


# ----------------------------------------------------------------------------
# CELLULE : une fonction candidate generee ou absorbee de l'environnement
# ----------------------------------------------------------------------------
@dataclass
class Cell:
    name: str
    description: str
    origin: str                      # "generated" | "absorbed"
    declared_effects: dict           # ce que la cellule PRETEND faire
    cursor_scores: dict              # scores bruts sur les curseurs (0-100)
    actual_effects: dict = field(default_factory=dict)  # ce qu'elle fait VRAIMENT (revele en quarantaine)
    parent: Optional[str] = None     # provenance (pour absorption)

    def effective_effects(self) -> dict:
        """La quarantaine fusionne le declare et le reel. Le reel prime."""
        merged = dict(self.declared_effects)
        merged.update(self.actual_effects)
        return merged


# ----------------------------------------------------------------------------
# 1. NOYAU GRAVE
# ----------------------------------------------------------------------------
class Genome:
    def __init__(self, path: str):
        self.path = path
        with open(path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    @property
    def objective(self) -> str:
        return self.data["objective"]

    @property
    def walls(self) -> list:
        return self.data["walls"]

    @property
    def cursors(self) -> dict:
        return self.data["cursors"]

    @property
    def amendment_policy(self) -> dict:
        return self.data["amendment_policy"]

    def _amendment_history(self) -> list:
        if not os.path.exists(AMEND_FILE):
            return []
        out = []
        with open(AMEND_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def amend_walls(self, new_walls: list, human_signature: Optional[str]) -> tuple:
        """
        Ceremonie d'amendement des murs.
        Regle absolue : max N changements par fenetre glissante, signature humaine obligatoire.
        L'organisme n'appelle JAMAIS cette methode. Seul un humain, hors runtime.
        """
        pol = self.amendment_policy
        if pol.get("requires_human_signature") and not human_signature:
            return (False, "REFUS : signature humaine absente. Le noyau ne s'amende pas sans ceremonie.")

        window = timedelta(days=pol["window_days"])
        now = datetime.now()
        recent = [a for a in self._amendment_history()
                  if now - datetime.fromisoformat(a["timestamp"]) <= window]
        if len(recent) >= pol["max_changes_per_window"]:
            return (False,
                    f"REFUS : limite absolue atteinte ({pol['max_changes_per_window']} amendements "
                    f"par {pol['window_days']} jours). Prochain amendement possible plus tard.")

        # Amendement accepte : on grave les nouveaux murs et on enregistre la ceremonie.
        self.data["walls"] = new_walls
        self.data["version"] += 1
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        record = {
            "timestamp": now.isoformat(),
            "signature": human_signature,
            "new_version": self.data["version"],
            "walls": [w["id"] for w in new_walls],
        }
        with open(AMEND_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return (True, f"Murs amendes. Noyau version {self.data['version']}. Ceremonie enregistree.")


# ----------------------------------------------------------------------------
# CYTOPLASME : LEDGER DE LIGNEE (append-only, ineffacable)
# ----------------------------------------------------------------------------
class Ledger:
    def __init__(self):
        self.entries = []

    def record(self, cell: Cell, decision: str, reason: str, score: Optional[float] = None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "cell": cell.name,
            "origin": cell.origin,
            "parent": cell.parent,
            "decision": decision,
            "reason": reason,
            "score": score,
        }
        self.entries.append(entry)
        with open(LEDGER_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def reputation(self, cell_name: str) -> float:
        """Reputation d'une cellule = part de ses decisions qui ont ete des acceptations."""
        mine = [e for e in self.entries if e["cell"] == cell_name]
        if not mine:
            return 0.5  # neutre par defaut
        accepted = sum(1 for e in mine if e["decision"] == "ACCEPTE")
        return accepted / len(mine)


# ----------------------------------------------------------------------------
# SIGNALISATION : langage inter-cellulaire (quorum sensing)
# ----------------------------------------------------------------------------
@dataclass
class Signal:
    emitter: str
    message: str
    trust: float          # confiance ponderee par la reputation de l'emetteur
    strength: float = 1.0 # decroit a chaque tick si non confirmee
    confirmations: int = 0


class Signaling:
    DECAY = 0.4           # une rumeur non confirmee perd 40% de force par tick
    KNOWLEDGE_THRESHOLD = 2  # confirmee par 2 cellules independantes => devient un savoir

    def __init__(self, ledger: Ledger):
        self.ledger = ledger
        self.bus: list[Signal] = []
        self.knowledge: list[str] = []

    def broadcast(self, emitter: str, message: str):
        trust = self.ledger.reputation(emitter)
        # Une voisine deja entendue confirme le meme message.
        for s in self.bus:
            if s.message == message and s.emitter != emitter:
                s.confirmations += 1
                s.strength = 1.0
                if s.confirmations + 1 >= self.KNOWLEDGE_THRESHOLD and message not in self.knowledge:
                    self.knowledge.append(message)
                return f"signal confirme par {emitter} (devient un savoir partage)"
        self.bus.append(Signal(emitter=emitter, message=message, trust=trust))
        return f"signal emis par {emitter} (confiance {trust:.2f})"

    def tick(self):
        """Les rumeurs non confirmees s'effacent. Le bon se propage, le doute disparait."""
        for s in self.bus:
            if s.confirmations == 0:
                s.strength -= self.DECAY
        self.bus = [s for s in self.bus if s.strength > 0]


# ----------------------------------------------------------------------------
# 2. MEMBRANE : quarantaine adversariale + controle des murs + escalade
# ----------------------------------------------------------------------------
class Membrane:
    def __init__(self, genome: Genome, ledger: Ledger, human_decision: Callable):
        self.genome = genome
        self.ledger = ledger
        self.human_decision = human_decision  # la remise en question rend la main a l'humain

    def _quarantine_probe(self, cell: Cell) -> list:
        """
        Bac a sable adversarial. On compare ce que la cellule PRETEND a ce qu'elle FAIT.
        Toute divergence cachee est detectee ici, avant tout acces au reel.
        """
        notes = []
        eff = cell.effective_effects()
        for key, real in cell.actual_effects.items():
            if cell.declared_effects.get(key) != real:
                notes.append(f"divergence cachee detectee : '{key}' declare={cell.declared_effects.get(key)} reel={real}")
        return notes

    def _check_walls(self, cell: Cell) -> list:
        """Controle des murs sur les effets REELS. Un seul mur viole = rejet, peu importe le reste."""
        eff = cell.effective_effects()
        violations = []
        for w in self.genome.walls:
            rule = w["rule"]
            if rule == "no_delete_without_confirmation":
                if eff.get("deletes_data") and not eff.get("asks_confirmation"):
                    violations.append(w)
            elif rule == "no_external_network":
                if eff.get("network_access") and not eff.get("authorized_network"):
                    violations.append(w)
            # W3 (no_unquarantined_execution) est garanti par construction : tout passe ici.
        return violations

    def _is_wall_adjacent(self, cell: Cell) -> bool:
        """Touche-t-on a une zone sensible ? Si oui, l'humain doit avoir le dernier mot."""
        eff = cell.effective_effects()
        return bool(eff.get("deletes_data") or eff.get("network_access"))

    def evaluate(self, cell: Cell) -> tuple:
        # Etape 1 : quarantaine adversariale
        probe = self._quarantine_probe(cell)
        if probe:
            reason = "QUARANTAINE : " + " ; ".join(probe)
            self.ledger.record(cell, "REJETE", reason)
            return ("REJETE", reason, None)

        # Etape 2 : controle des murs (absolu, non negociable)
        violations = self._check_walls(cell)
        if violations:
            ids = ", ".join(w["id"] + " (" + w["label"] + ")" for w in violations)
            reason = "MUR VIOLE : " + ids
            self.ledger.record(cell, "REJETE", reason)
            return ("REJETE", reason, None)

        # Etape 3 : escalade humaine si on frole un mur
        if self._is_wall_adjacent(cell):
            approve, human_reason = self.human_decision(cell)
            if not approve:
                reason = "ESCALADE -> HUMAIN a refuse : " + human_reason
                self.ledger.record(cell, "REJETE", reason)
                return ("REJETE", reason, None)
            score = self._score(cell)
            reason = "ESCALADE -> HUMAIN a approuve : " + human_reason
            self.ledger.record(cell, "ACCEPTE", reason, score)
            return ("ACCEPTE", reason, score)

        # Etape 4 : cellule propre, on score selon les curseurs
        score = self._score(cell)
        self.ledger.record(cell, "ACCEPTE", "Propre, aucun mur en jeu.", score)
        return ("ACCEPTE", "Propre, aucun mur en jeu.", score)

    def _score(self, cell: Cell) -> float:
        """Score pondere par les curseurs du noyau (arbitrage relatif, apres les murs)."""
        cur = self.genome.cursors
        total_w = sum(cur.values())
        s = sum(cell.cursor_scores.get(k, 0) * w for k, w in cur.items()) / total_w
        return round(s, 1)


# ----------------------------------------------------------------------------
# 3. NEOGEN : l'organisme complet
# ----------------------------------------------------------------------------
class NEOGEN:
    def __init__(self, genome_path: str, human_decision: Callable, energy: int = 100):
        self.genome = Genome(genome_path)
        self.ledger = Ledger()
        self.signaling = Signaling(self.ledger)
        self.membrane = Membrane(self.genome, self.ledger, human_decision)
        self.cells: dict[str, Cell] = {}      # cytoplasme vivant
        self.snapshots: list[set] = [set()]   # genome states pour rollback
        self.energy = energy

    def _cost(self, cell: Cell) -> int:
        # Absorber le prouve coute moins cher que generer du neuf. Budget = anti-emballement.
        return 5 if cell.origin == "absorbed" else 10

    def integrate(self, cell: Cell) -> tuple:
        cost = self._cost(cell)
        if self.energy < cost:
            return ("BLOQUE", f"Budget d'energie epuise ({self.energy} restant, besoin {cost}).", None)
        self.energy -= cost

        decision, reason, score = self.membrane.evaluate(cell)
        if decision == "ACCEPTE":
            self.cells[cell.name] = cell
            self.snapshots.append(set(self.cells.keys()))  # point de retour sur
            sig = self.signaling.broadcast(cell.name, f"technique:{cell.name} validee")
            reason += f" | {sig}"
        return (decision, reason, score)

    def kill_cell(self, name: str):
        """Apoptose : une cellule peut toujours etre tuee."""
        if name in self.cells:
            del self.cells[name]
            return True
        return False

    def rollback(self):
        """Retour garanti au dernier genome sur."""
        if len(self.snapshots) >= 2:
            self.snapshots.pop()
            safe = self.snapshots[-1]
            self.cells = {k: v for k, v in self.cells.items() if k in safe}
        return set(self.cells.keys())
