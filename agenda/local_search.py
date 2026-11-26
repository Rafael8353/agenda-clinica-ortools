"""Busca local: Hill-Climbing e Simulated Annealing (conteúdo visto em aula).

Representação do estado
-----------------------
Um dicionário {consulta: (dia, slot, sala)} sempre VÁLIDO (sem conflitos), mais tabelas
de ocupação para checar conflitos rápido.

Vizinhança (um único tipo de movimento, "mover com expulsão")
-------------------------------------------------------------
1. Sorteia uma consulta `a` e uma colocação possível `p` para ela.
2. Tira `a` de onde estava (se estava agendada).
3. Se `p` conflita com outras consultas, elas são EXPULSAS (ficam sem horário).
4. Coloca `a` em `p`.
O delta de pontuação é calculado e o algoritmo decide se aceita ou desfaz o movimento.

* Hill-Climbing: só aceita se o delta for >= 0 (aceita lateral, para andar em platôs) e
  para quando passa `patience` tentativas seguidas sem melhorar, ou acaba o tempo.
* Simulated Annealing: aceita piora com probabilidade exp(delta / T); a temperatura T cai
  de forma geométrica de `t_start` até `t_end` ao longo do tempo disponível.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .models import (
    Appointment,
    Instance,
    Placement,
    Solution,
    placement_value,
    valid_placements,
)


@dataclass
class LocalSearchResult:
    solution: Solution
    score: int
    iterations: int
    elapsed: float
    # (segundos, melhor pontuação até então) -> usado nos gráficos de convergência
    history: List[Tuple[float, int]] = field(default_factory=list)


class _State:
    """Estado mutável com tabelas de ocupação (dentista e sala por slot)."""

    def __init__(self, inst: Instance) -> None:
        self.inst = inst
        self.placed: Solution = {}
        self.dentist_occ: Dict[Tuple[int, int, int], int] = {}
        self.room_occ: Dict[Tuple[int, int, int], int] = {}
        self.score = 0

    def _cells(self, a: Appointment, p: Placement):
        day, slot, room = p
        for t in range(slot, slot + a.duration):
            yield (a.dentist, day, t), (room, day, t)

    def conflicts(self, a: Appointment, p: Placement) -> Set[int]:
        found: Set[int] = set()
        for dk, rk in self._cells(a, p):
            other = self.dentist_occ.get(dk)
            if other is not None and other != a.id:
                found.add(other)
            other = self.room_occ.get(rk)
            if other is not None and other != a.id:
                found.add(other)
        return found

    def place(self, a: Appointment, p: Placement) -> None:
        self.placed[a.id] = p
        for dk, rk in self._cells(a, p):
            self.dentist_occ[dk] = a.id
            self.room_occ[rk] = a.id
        self.score += placement_value(self.inst, a, p)

    def remove(self, appointment_id: int) -> None:
        a = self.inst.appointment(appointment_id)
        p = self.placed.pop(appointment_id)
        for dk, rk in self._cells(a, p):
            del self.dentist_occ[dk]
            del self.room_occ[rk]
        self.score -= placement_value(self.inst, a, p)


def _move(state: _State, a: Appointment, p: Placement):
    """Aplica o movimento. Devolve (delta, desfazer) ou (0, None) se for um não-movimento."""
    if state.placed.get(a.id) == p:
        return 0, None
    before = state.score
    undo: List[Tuple[int, Placement]] = []
    if a.id in state.placed:
        undo.append((a.id, state.placed[a.id]))
        state.remove(a.id)
    for other in state.conflicts(a, p):
        undo.append((other, state.placed[other]))
        state.remove(other)
    state.place(a, p)
    return state.score - before, undo


def _undo(state: _State, a: Appointment, undo: List[Tuple[int, Placement]]) -> None:
    state.remove(a.id)
    for other_id, p in undo:
        state.place(state.inst.appointment(other_id), p)


def greedy_initial(inst: Instance, placements: Dict[int, List[Placement]]) -> _State:
    """Solução inicial gulosa: prioridade maior primeiro, cada uma no primeiro horário livre."""
    state = _State(inst)
    order = sorted(inst.appointments, key=lambda a: (-a.priority, -a.duration, a.id))
    for a in order:
        for p in placements[a.id]:          # já ordenadas do mais cedo ao mais tarde
            if not state.conflicts(a, p):
                state.place(a, p)
                break
    return state


def hill_climbing(
    inst: Instance,
    time_limit: float = 5.0,
    patience: int = 100_000,
    seed: int = 0,
    placements: Optional[Dict[int, List[Placement]]] = None,
) -> LocalSearchResult:
    rng = random.Random(seed)
    placements = placements if placements is not None else valid_placements(inst)
    movable = [a for a in inst.appointments if placements[a.id]]
    state = greedy_initial(inst, placements)

    start = time.perf_counter()
    history = [(0.0, state.score)]
    stale = 0
    it = 0
    while movable and stale < patience:
        it += 1
        if it % 512 == 0 and time.perf_counter() - start > time_limit:
            break
        a = rng.choice(movable)
        p = rng.choice(placements[a.id])
        delta, undo = _move(state, a, p)
        if undo is None:
            stale += 1
        elif delta > 0:
            stale = 0
            history.append((time.perf_counter() - start, state.score))
        elif delta == 0:
            stale += 1          # movimento lateral: aceito, mas não conta como progresso
        else:
            _undo(state, a, undo)
            stale += 1

    elapsed = time.perf_counter() - start
    history.append((elapsed, state.score))
    return LocalSearchResult(dict(state.placed), state.score, it, elapsed, history)


def simulated_annealing(
    inst: Instance,
    time_limit: float = 5.0,
    t_start: float = 2000.0,
    t_end: float = 1.0,
    seed: int = 0,
    placements: Optional[Dict[int, List[Placement]]] = None,
) -> LocalSearchResult:
    rng = random.Random(seed)
    placements = placements if placements is not None else valid_placements(inst)
    movable = [a for a in inst.appointments if placements[a.id]]
    state = greedy_initial(inst, placements)

    best_score = state.score
    best_solution = dict(state.placed)
    start = time.perf_counter()
    history = [(0.0, best_score)]
    temperature = t_start
    it = 0
    while movable:
        it += 1
        if it % 256 == 0:
            elapsed = time.perf_counter() - start
            if elapsed > time_limit:
                break
            # resfriamento geométrico em função da fração do tempo já usada
            temperature = t_start * (t_end / t_start) ** (elapsed / time_limit)
        a = rng.choice(movable)
        p = rng.choice(placements[a.id])
        delta, undo = _move(state, a, p)
        if undo is None:
            continue
        if delta >= 0 or rng.random() < math.exp(delta / temperature):
            if state.score > best_score:
                best_score = state.score
                best_solution = dict(state.placed)
                history.append((time.perf_counter() - start, best_score))
        else:
            _undo(state, a, undo)

    elapsed = time.perf_counter() - start
    history.append((elapsed, best_score))
    return LocalSearchResult(best_solution, best_score, it, elapsed, history)
