"""Demonstração: monta a agenda de uma clínica e mostra o resultado.

Exemplos:
    python main.py                       # clínica pequena gerada, resolve com CP-SAT
    python main.py --solver all          # compara CP-SAT, Hill-Climbing e Simulated Annealing
    python main.py --json dados/exemplo.json
    python main.py --dentistas 6 --salas 4 --consultas 60 --solver all
"""
from __future__ import annotations

import argparse
import sys

from agenda import (
    generate_instance,
    hill_climbing,
    load_instance,
    score,
    simulated_annealing,
    solve_cpsat,
    solve_cpsat_intervals,
    validate,
)
from agenda.report import export_csv, format_schedule, format_unscheduled


def main() -> None:
    try:  # evita erro de acentuação no terminal do Windows
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Agenda de dentistas e salas com OR-Tools (CP-SAT)")
    ap.add_argument("--json", help="arquivo JSON com a clínica (ver dados/exemplo.json)")
    ap.add_argument("--dentistas", type=int, default=3)
    ap.add_argument("--salas", type=int, default=2)
    ap.add_argument("--dias", type=int, default=5)
    ap.add_argument("--slots", type=int, default=8, help="horários por dia (1 slot = 1 hora)")
    ap.add_argument("--consultas", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--solver", choices=["cpsat", "cpsat-int", "hc", "sa", "all"], default="cpsat")
    ap.add_argument("--tempo", type=float, default=5.0, help="segundos por algoritmo")
    ap.add_argument("--csv", default="resultados/agenda.csv", help="onde salvar a agenda (CSV)")
    args = ap.parse_args()

    if args.json:
        inst = load_instance(args.json)
    else:
        inst = generate_instance(
            args.dentistas, args.salas, args.dias, args.slots, args.consultas, seed=args.seed
        )
    print(
        f"Clinica: {len(inst.dentists)} dentistas, {len(inst.rooms)} salas, "
        f"{len(inst.days)} dias x {inst.slots_per_day} horarios, "
        f"{len(inst.appointments)} consultas pedidas."
    )

    runs = {}
    if args.solver in ("cpsat", "all"):
        r = solve_cpsat(inst, time_limit=args.tempo)
        runs["CP-SAT (grade)"] = (r.solution, r.elapsed, f"status={r.status}, limite superior={r.best_bound:.0f}")
    if args.solver in ("cpsat-int", "all"):
        r = solve_cpsat_intervals(inst, time_limit=args.tempo)
        runs["CP-SAT (intervalos)"] = (r.solution, r.elapsed, f"status={r.status}, limite superior={r.best_bound:.0f}")
    if args.solver in ("hc", "all"):
        r = hill_climbing(inst, time_limit=args.tempo)
        runs["Hill-Climbing"] = (r.solution, r.elapsed, f"{r.iterations} iteracoes")
    if args.solver in ("sa", "all"):
        r = simulated_annealing(inst, time_limit=args.tempo)
        runs["Simulated Annealing"] = (r.solution, r.elapsed, f"{r.iterations} iteracoes")

    print("\n" + "=" * 70)
    for name, (sol, elapsed, extra) in runs.items():
        errors = validate(inst, sol)
        status = "valida" if not errors else f"INVALIDA ({len(errors)} erros)"
        print(
            f"{name:<22} agendadas={len(sol):>3}/{len(inst.appointments)}  "
            f"pontuacao={score(inst, sol):>8}  tempo={elapsed:5.2f}s  [{status}]  {extra}"
        )

    # Mostra a agenda do primeiro algoritmo executado e salva em CSV
    first_name, (first_sol, _, _) = next(iter(runs.items()))
    print(f"\n########## Agenda gerada por: {first_name} ##########")
    print(format_schedule(inst, first_sol))
    print("\n" + format_unscheduled(inst, first_sol))
    export_csv(inst, first_sol, args.csv)
    print(f"\nAgenda salva em: {args.csv}")


if __name__ == "__main__":
    main()
