"""Saída legível da agenda (texto no terminal e CSV)."""
from __future__ import annotations

import csv
from typing import List

from .models import Instance, Solution

COL_WIDTH = 24


def format_schedule(inst: Instance, sol: Solution) -> str:
    """Uma grade por dia: linhas = horários, colunas = salas."""
    grid = {}
    for aid, (day, slot, room) in sol.items():
        a = inst.appointment(aid)
        for k in range(a.duration):
            text = f"{inst.dentists[a.dentist]}: {a.patient}" if k == 0 else "   (continua)"
            grid[(day, slot + k, room)] = text[:COL_WIDTH]

    lines: List[str] = []
    for d, day_name in enumerate(inst.days):
        if not any(key[0] == d for key in grid):
            continue
        lines.append(f"\n=== {day_name} (dia {d + 1}) ===")
        header = "Horario | " + " | ".join(r.center(COL_WIDTH) for r in inst.rooms)
        lines.append(header)
        lines.append("-" * len(header))
        for s in range(inst.slots_per_day):
            cells = [grid.get((d, s, r), "").ljust(COL_WIDTH) for r in range(len(inst.rooms))]
            lines.append(f"{inst.slot_label(s)}   | " + " | ".join(cells))
    return "\n".join(lines)


def format_unscheduled(inst: Instance, sol: Solution) -> str:
    missing = [a for a in inst.appointments if a.id not in sol]
    if not missing:
        return "Todas as consultas foram agendadas."
    rows = [
        f"  - {a.patient} ({inst.dentists[a.dentist]}, {a.duration}h, prioridade {a.priority})"
        for a in missing
    ]
    return f"{len(missing)} consulta(s) sem horario:\n" + "\n".join(rows)


def export_csv(inst: Instance, sol: Solution, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig: Excel abre com acentos
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "paciente", "dentista", "dia", "inicio", "fim", "sala",
                    "prioridade", "precisa_equipamento"])
        for aid, (day, slot, room) in sorted(sol.items(), key=lambda kv: (kv[1][0], kv[1][1], kv[1][2])):
            a = inst.appointment(aid)
            w.writerow([
                a.id, a.patient, inst.dentists[a.dentist], inst.days[day],
                inst.slot_label(slot), inst.slot_label(slot + a.duration),
                inst.rooms[room], a.priority, "sim" if a.needs_equipment else "nao",
            ])
