"""Leitura/gravação de uma clínica em JSON (para usar dados reais, sem mexer no código).

Formato (ver dados/exemplo.json):
{
  "dias": ["Seg", "Ter"], "slots_por_dia": 8, "hora_inicio": 8, "minutos_por_slot": 60,
  "salas": [{"nome": "Sala 1", "equipamento": true}],
  "dentistas": [{"nome": "Dra. Ana", "disponibilidade": {"Seg": [[0, 4]], "Ter": [[0, 8]]}}],
  "consultas": [{"paciente": "Fulano", "dentista": "Dra. Ana", "duracao": 1,
                 "prioridade": 2, "precisa_equipamento": false}]
}
Em "disponibilidade", [ini, fim) são slots: [0, 4] = slots 0,1,2,3 (4 primeiras horas).
"""
from __future__ import annotations

import json
import re
from typing import List

from .models import Appointment, Instance


def _to_ranges(slots: List[int]) -> List[List[int]]:
    ranges: List[List[int]] = []
    for s in sorted(slots):
        if ranges and ranges[-1][1] == s:
            ranges[-1][1] = s + 1
        else:
            ranges.append([s, s + 1])
    return ranges


def save_instance(inst: Instance, path: str) -> None:
    data = {
        "dias": inst.days,
        "slots_por_dia": inst.slots_per_day,
        "hora_inicio": inst.start_hour,
        "minutos_por_slot": inst.slot_minutes,
        "salas": [
            {"nome": n, "equipamento": e} for n, e in zip(inst.rooms, inst.room_has_equipment)
        ],
        "dentistas": [],
        "consultas": [],
    }
    for i, name in enumerate(inst.dentists):
        avail = {}
        for d, day in enumerate(inst.days):
            slots = [s for (dd, s) in inst.availability[i] if dd == d]
            if slots:
                avail[day] = _to_ranges(slots)
        data["dentistas"].append({"nome": name, "disponibilidade": avail})
    for a in inst.appointments:
        data["consultas"].append({
            "paciente": a.patient,
            "dentista": inst.dentists[a.dentist],
            "duracao": a.duration,
            "prioridade": a.priority,
            "precisa_equipamento": a.needs_equipment,
        })
    text = json.dumps(data, ensure_ascii=False, indent=2)
    # deixa listas numericas curtas em uma linha só (arquivo mais legivel)
    text = re.sub(r"\[\s+(\d+),\s+(\d+)\s+\]", r"[\1, \2]", text)
    text = re.sub(r"\[\s+((?:\[\d+, \d+\],?\s*)+)\]",
                  lambda m: "[" + re.sub(r"\s+", " ", m.group(1)).strip() + "]", text)
    text = re.sub(r'\[\s+("(?:[^"\n]+)"(?:,\s*"[^"\n]+")*)\s+\]',
                  lambda m: "[" + re.sub(r"\s+", " ", m.group(1)) + "]", text)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")


def load_instance(path: str) -> Instance:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    days = data["dias"]
    if len(set(days)) != len(days):
        raise ValueError("Os nomes em 'dias' precisam ser unicos (ex.: Seg, Ter, Qua...).")
    day_index = {name: i for i, name in enumerate(days)}
    dentists = [d["nome"] for d in data["dentistas"]]
    dentist_index = {name: i for i, name in enumerate(dentists)}

    availability = {}
    for i, d in enumerate(data["dentistas"]):
        slots = set()
        for day_name, ranges in d["disponibilidade"].items():
            for ini, fim in ranges:
                slots.update((day_index[day_name], s) for s in range(ini, fim))
        availability[i] = slots

    appointments = [
        Appointment(
            id=i,
            patient=c["paciente"],
            dentist=dentist_index[c["dentista"]],
            duration=c.get("duracao", 1),
            priority=c.get("prioridade", 1),
            needs_equipment=c.get("precisa_equipamento", False),
        )
        for i, c in enumerate(data["consultas"])
    ]
    return Instance(
        dentists=dentists,
        rooms=[s["nome"] for s in data["salas"]],
        room_has_equipment=[s.get("equipamento", False) for s in data["salas"]],
        days=days,
        slots_per_day=data["slots_por_dia"],
        availability=availability,
        appointments=appointments,
        start_hour=data.get("hora_inicio", 8),
        slot_minutes=data.get("minutos_por_slot", 60),
    )
