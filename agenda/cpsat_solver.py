"""Solução exata/otimizada com Google OR-Tools (CP-SAT).

Modelo
------
Variável de decisão (booleana), uma para cada colocação possível:

    x[a, dia, slot, sala] = 1  se a consulta `a` começa em (dia, slot) na `sala`.

Restrições
----------
1. Cada consulta é agendada no máximo uma vez (ou fica sem horário).
2. Um dentista atende no máximo uma consulta por slot.
3. Uma sala recebe no máximo uma consulta por slot.
(Disponibilidade do dentista, consulta caber no dia e sala com equipamento já são
tratadas ao criar só as variáveis válidas, ver `valid_placements`.)

Objetivo
--------
Maximizar a soma de [10000 * prioridade - posição_no_tempo] das consultas agendadas:
primeiro agendar o maior número (ponderado pela prioridade), depois deixar a agenda
o mais "cedo" possível.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ortools.sat.python import cp_model

from .models import (
    BASE_PRIORITY,
    Instance,
    Placement,
    Solution,
    score,
    valid_placements,
)


@dataclass
class CpSatResult:
    solution: Solution
    score: int
    status: str            # "OPTIMAL", "FEASIBLE", "INFEASIBLE", ...
    optimal: bool
    best_bound: float      # limite superior provado pelo solver
    elapsed: float
    n_variables: int


def solve_cpsat(
    inst: Instance,
    time_limit: float = 10.0,
    workers: int = 0,
    seed: int = 0,
    log: bool = False,
    placements: Optional[Dict[int, List[Placement]]] = None,
) -> CpSatResult:
    placements = placements if placements is not None else valid_placements(inst)
    model = cp_model.CpModel()

    # --- variáveis -------------------------------------------------------------
    x: Dict[Tuple[int, int, int, int], cp_model.IntVar] = {}
    per_appointment = defaultdict(list)
    for a in inst.appointments:
        for (d, s, r) in placements[a.id]:
            var = model.new_bool_var(f"x_a{a.id}_d{d}_s{s}_r{r}")
            x[(a.id, d, s, r)] = var
            per_appointment[a.id].append(var)

    # --- restrição 1: no máximo um horário por consulta -------------------------
    for variables in per_appointment.values():
        model.add_at_most_one(variables)

    # --- restrições 2 e 3: conflito de dentista e de sala -----------------------
    dentist_slot = defaultdict(list)   # (dentista, dia, slot) -> variáveis que o ocupam
    room_slot = defaultdict(list)      # (sala, dia, slot) -> variáveis que a ocupam
    for (aid, d, s, r), var in x.items():
        a = inst.appointment(aid)
        for t in range(s, s + a.duration):
            dentist_slot[(a.dentist, d, t)].append(var)
            room_slot[(r, d, t)].append(var)
    for variables in dentist_slot.values():
        model.add_at_most_one(variables)
    for variables in room_slot.values():
        model.add_at_most_one(variables)

    # --- objetivo ---------------------------------------------------------------
    terms = []
    for (aid, d, s, r), var in x.items():
        a = inst.appointment(aid)
        terms.append((BASE_PRIORITY * a.priority - (d * inst.slots_per_day + s)) * var)
    model.maximize(sum(terms))

    # --- resolver ---------------------------------------------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers
    solver.parameters.random_seed = seed
    solver.parameters.log_search_progress = log

    start = time.perf_counter()
    status = solver.solve(model)
    elapsed = time.perf_counter() - start

    solution: Solution = {}
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for (aid, d, s, r), var in x.items():
            if solver.boolean_value(var):
                solution[aid] = (d, s, r)

    return CpSatResult(
        solution=solution,
        score=score(inst, solution),
        status=solver.status_name(status),
        optimal=(status == cp_model.OPTIMAL),
        best_bound=solver.best_objective_bound if solution else 0.0,
        elapsed=elapsed,
        n_variables=len(x),
    )
