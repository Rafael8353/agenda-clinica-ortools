"""Experimentos: CP-SAT x Hill-Climbing x Simulated Annealing em cenarios de tamanhos diferentes.

Uso:
    python benchmark.py                 # padrao: CP-SAT 20s, busca local 5s, 5 sementes
    python benchmark.py --rapido        # teste rapido (poucos segundos)
    python benchmark.py --tempo 10 --sementes 10

Saidas (pasta resultados/):
    benchmark.csv            uma linha por execucao
    benchmark_resumo.csv     medias por cenario e algoritmo
    benchmark_pontuacao.png  grafico de barras (pontuacao relativa ao CP-SAT)
    convergencia_<cenario>.png  evolucao da melhor pontuacao ao longo do tempo
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics
import sys

from agenda import (
    generate_instance,
    solve_cpsat_intervals,
    hill_climbing,
    score,
    simulated_annealing,
    solve_cpsat,
    validate,
    valid_placements,
)

ALGOS = ["CP-SAT (grade)", "CP-SAT (intervalos)", "Hill-Climbing", "Simulated Annealing"]

# nome: (dentistas, salas, dias, slots/dia, consultas)
SCENARIOS = {
    "pequeno": (3, 2, 5, 8, 30),
    "medio": (6, 4, 5, 8, 120),
    "grande": (10, 6, 5, 10, 300),
}


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("--tempo", type=float, default=5.0, help="segundos da busca local")
    ap.add_argument("--tempo-cpsat", type=float, default=20.0, help="segundos do CP-SAT")
    ap.add_argument("--sementes", type=int, default=5, help="execucoes da busca local por cenario")
    ap.add_argument("--workers", type=int, default=0, help="threads do CP-SAT (0 = todos os nucleos)")
    ap.add_argument("--rapido", action="store_true", help="versao curta para testar")
    ap.add_argument("--saida", default="resultados")
    args = ap.parse_args()
    if args.rapido:
        args.tempo, args.tempo_cpsat, args.sementes = 1.0, 2.0, 2

    os.makedirs(args.saida, exist_ok=True)
    rows = []
    histories = {}   # cenario -> {algoritmo: historico da 1a semente}
    cpsat_score = {}

    for name, (nd, nr, ndias, nslots, nc) in SCENARIOS.items():
        inst = generate_instance(nd, nr, ndias, nslots, nc, seed=7)
        options = valid_placements(inst)
        print(f"\n[{name}] {nd} dentistas, {nr} salas, {ndias}x{nslots} horarios, {nc} consultas")

        best_cpsat = 0
        for label, fn in (("CP-SAT (grade)", solve_cpsat), ("CP-SAT (intervalos)", solve_cpsat_intervals)):
            r = fn(inst, time_limit=args.tempo_cpsat, workers=args.workers, placements=options)
            assert not validate(inst, r.solution)
            best_cpsat = max(best_cpsat, r.score)
            rows.append(dict(cenario=name, algoritmo=label, semente=0, agendadas=len(r.solution),
                             pontuacao=r.score, tempo=round(r.elapsed, 2),
                             otimo=r.optimal, limite_superior=round(r.best_bound)))
            print(f"  {label:<20} agendadas={len(r.solution)} pontuacao={r.score} "
                  f"tempo={r.elapsed:.1f}s status={r.status}")
        cpsat_score[name] = best_cpsat

        histories[name] = {}
        for label, fn in (("Hill-Climbing", hill_climbing), ("Simulated Annealing", simulated_annealing)):
            for seed in range(args.sementes):
                res = fn(inst, time_limit=args.tempo, seed=seed, placements=options)
                assert not validate(inst, res.solution)
                rows.append(dict(cenario=name, algoritmo=label, semente=seed,
                                 agendadas=len(res.solution), pontuacao=res.score,
                                 tempo=round(res.elapsed, 2), otimo="", limite_superior=""))
                if seed == 0:
                    histories[name][label] = res.history
            sub = [x for x in rows if x["cenario"] == name and x["algoritmo"] == label]
            print(f"  {label:<20} agendadas(media)={statistics.mean(x['agendadas'] for x in sub):.1f} "
                  f"pontuacao(media)={statistics.mean(x['pontuacao'] for x in sub):.0f}")

    # ---- CSVs ----------------------------------------------------------------
    path = os.path.join(args.saida, "benchmark.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
        w.writeheader()
        w.writerows(rows)

    summary = []
    for name in SCENARIOS:
        for algo in ALGOS:
            sub = [x for x in rows if x["cenario"] == name and x["algoritmo"] == algo]
            mean_score = statistics.mean(x["pontuacao"] for x in sub)
            summary.append(dict(
                cenario=name, algoritmo=algo,
                agendadas_media=round(statistics.mean(x["agendadas"] for x in sub), 1),
                pontuacao_media=round(mean_score),
                pontuacao_dp=round(statistics.pstdev(x["pontuacao"] for x in sub)) if len(sub) > 1 else 0,
                pct_do_cpsat=round(100 * mean_score / max(1, cpsat_score[name]), 2),
                tempo_medio=round(statistics.mean(x["tempo"] for x in sub), 2),
            ))
    with open(os.path.join(args.saida, "benchmark_resumo.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]), delimiter=";")
        w.writeheader()
        w.writerows(summary)

    print("\n" + "=" * 80)
    print(f"{'cenario':<10}{'algoritmo':<24}{'agendadas':>10}{'pontuacao':>12}{'% CP-SAT':>10}{'tempo(s)':>10}")
    for s in summary:
        print(f"{s['cenario']:<10}{s['algoritmo']:<24}{s['agendadas_media']:>10}"
              f"{s['pontuacao_media']:>12}{s['pct_do_cpsat']:>10}{s['tempo_medio']:>10}")

    _plots(summary, histories, cpsat_score, args.saida)
    print(f"\nArquivos salvos em: {args.saida}/")


def _plots(summary, histories, cpsat_score, out_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("(matplotlib nao instalado: graficos ignorados. pip install matplotlib)")
        return

    algos = ALGOS
    names = list(SCENARIOS)
    width = 0.2
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, algo in enumerate(algos):
        vals = [next(s["pct_do_cpsat"] for s in summary if s["cenario"] == n and s["algoritmo"] == algo)
                for n in names]
        ax.bar([k + (i - 1.5) * width for k in range(len(names))], vals, width, label=algo)
    lo = min(s["pct_do_cpsat"] for s in summary)
    ax.set_ylim(max(0, lo - 2), 100.5)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names)
    ax.set_ylabel("pontuacao media (% do melhor CP-SAT)")
    ax.set_title("Qualidade da agenda por algoritmo e cenario")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "benchmark_pontuacao.png"), dpi=150)
    plt.close(fig)

    for name, hs in histories.items():
        fig, ax = plt.subplots(figsize=(8, 4.5))
        for algo, hist in hs.items():
            ax.step([t for t, _ in hist], [s for _, s in hist], where="post", label=algo)
        ax.axhline(cpsat_score[name], color="k", linestyle="--", label="melhor CP-SAT (final)")
        top = cpsat_score[name]
        ax.set_ylim(top * 0.9, top * 1.005)
        ax.set_xlabel("tempo (s)")
        ax.set_ylabel("melhor pontuacao")
        ax.set_title(f"Convergencia - cenario {name}")
        ax.legend()
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, f"convergencia_{name}.png"), dpi=150)
        plt.close(fig)


if __name__ == "__main__":
    main()
