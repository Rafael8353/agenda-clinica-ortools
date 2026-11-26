"""Segundo modelo CP-SAT: intervalos opcionais + NoOverlap (forma "clássica" de escalonamento).

Diferença para o modelo da grade (`cpsat_solver.py`)
----------------------------------------------------
Em vez de uma variável booleana para cada (consulta, dia, slot, sala), cada consulta tem:

* `presente[a]`  - booleana: a consulta foi agendada?
* `inicio[a]`    - inteiro: instante de início (dia * slots_por_dia + slot), com domínio
                   restrito aos inícios válidos (dentista disponível, cabe no dia).
* `sala[a, r]`   - booleanas: em qual sala (exatamente uma se estiver presente).

e as restrições de conflito viram `NoOverlap` sobre intervalos opcionais de duração fixa:
um NoOverlap por dentista e um por sala. O modelo fica bem menor e o solver propaga melhor.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List, Optional

from ortools.sat.python import cp_model

from .cpsat_solver import CpSatResult
from .models import BASE_PRIORITY, Instance, Placement, Solution, score, valid_placements


def solve_cpsat_intervals(
    inst: Instance,
    time_limit: float = 10.0,
    workers: int = 0,
    seed: int = 0,
    log: bool = False,
    placements: Optional[Dict[int, List[Placement]]] = None,
) -> CpSatResult:
    placements = placements if placements is not None else valid_placements(inst)
    S = inst.slots_per_day
    horizon = len(inst.days) * S
    model = cp_model.CpModel()

    present: Dict[int, cp_model.IntVar] = {}
    start: Dict[int, cp_model.IntVar] = {}
    room_lit: Dict[int, Dict[int, cp_model.IntVar]] = {}
    dentist_intervals = defaultdict(list)
    room_intervals = defaultdict(list)
    objective = []

    for a in inst.appointments:
        options = placements[a.id]
        if not options:
            continue                                     # nunca cabe: fica sem horário
        starts = sorted({d * S + s for (d, s, _r) in options})
        rooms = sorted({r for (_d, _s, r) in options})

        p = model.new_bool_var(f"presente_{a.id}")
        st = model.new_int_var_from_domain(cp_model.Domain.from_values(starts), f"inicio_{a.id}")
        present[a.id], start[a.id] = p, st

        dentist_intervals[a.dentist].append(
            model.new_optional_fixed_size_interval_var(st, a.duration, p, f"int_dent_{a.id}")
        )

        lits = {r: model.new_bool_var(f"sala_{a.id}_{r}") for r in rooms}
        room_lit[a.id] = lits
        model.add(sum(lits.values()) == p)               # presente => exatamente uma sala
        for r, lit in lits.items():
            room_intervals[r].append(
                model.new_optional_fixed_size_interval_var(st, a.duration, lit, f"int_sala_{a.id}_{r}")
            )

        # custo de começar tarde só conta se a consulta estiver presente
        effective = model.new_int_var(0, horizon, f"inicio_efetivo_{a.id}")
        model.add(effective == st).only_enforce_if(p)
        model.add(effective == 0).only_enforce_if(p.Not())
        objective.append(BASE_PRIORITY * a.priority * p - effective)

    for intervals in dentist_intervals.values():
        model.add_no_overlap(intervals)
    for intervals in room_intervals.values():
        model.add_no_overlap(intervals)
    model.maximize(sum(objective))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers
    solver.parameters.random_seed = seed
    solver.parameters.log_search_progress = log

    t0 = time.perf_counter()
    status = solver.solve(model)
    elapsed = time.perf_counter() - t0

    solution: Solution = {}
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for aid, p in present.items():
            if solver.boolean_value(p):
                day, slot = divmod(solver.value(start[aid]), S)
                room = next(r for r, lit in room_lit[aid].items() if solver.boolean_value(lit))
                solution[aid] = (day, slot, room)

    return CpSatResult(
        solution=solution,
        score=score(inst, solution),
        status=solver.status_name(status),
        optimal=(status == cp_model.OPTIMAL),
        best_bound=solver.best_objective_bound if solution else 0.0,
        elapsed=elapsed,
        n_variables=len(present) * 2 + sum(len(v) for v in room_lit.values()),
    )
