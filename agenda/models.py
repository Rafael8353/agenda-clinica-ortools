"""Modelo do problema: dados da clínica, solução, pontuação e validação.

Conceitos
---------
* O tempo é dividido em *slots* (por padrão 1 hora). Um dia tem `slots_per_day` slots.
* Uma consulta (`Appointment`) pertence a UM dentista, ocupa `duration` slots seguidos,
  tem uma prioridade (1 = baixa ... 3 = alta) e pode exigir uma sala com equipamento
  (ex.: raio-X).
* Uma *colocação* (`Placement`) é a tupla (dia, slot_inicial, sala).
* Uma *solução* é um dicionário {id_da_consulta: colocação}. Consulta que não está no
  dicionário ficou sem horário (não agendada).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

# Colocação = (dia, slot inicial, sala)
Placement = Tuple[int, int, int]
Solution = Dict[int, Placement]

# Cada consulta agendada vale BASE_PRIORITY * prioridade. Como a penalização por horário
# tardio é bem menor (no máximo algumas dezenas), agendar mais consultas (e as mais
# prioritárias) SEMPRE vale mais do que "compactar" a agenda.
BASE_PRIORITY = 10_000


@dataclass(frozen=True)
class Appointment:
    id: int
    patient: str
    dentist: int            # índice em Instance.dentists
    duration: int = 1       # em slots
    priority: int = 1       # 1 (baixa) .. 3 (alta)
    needs_equipment: bool = False


@dataclass
class Instance:
    dentists: List[str]
    rooms: List[str]
    room_has_equipment: List[bool]
    days: List[str]
    slots_per_day: int
    # dentista -> conjunto de (dia, slot) em que ele está disponível
    availability: Dict[int, Set[Tuple[int, int]]]
    appointments: List[Appointment]
    start_hour: int = 8
    slot_minutes: int = 60

    def __post_init__(self) -> None:
        self._by_id = {a.id: a for a in self.appointments}

    def appointment(self, appointment_id: int) -> Appointment:
        return self._by_id[appointment_id]

    def slot_label(self, slot: int) -> str:
        minutes = self.start_hour * 60 + slot * self.slot_minutes
        return f"{minutes // 60:02d}:{minutes % 60:02d}"


def valid_placements(inst: Instance) -> Dict[int, List[Placement]]:
    """Para cada consulta, todas as colocações individualmente possíveis.

    Já elimina o que viola as restrições "unárias": consulta que não cabe no dia,
    dentista indisponível em algum slot e sala sem o equipamento necessário.
    A lista sai ordenada por (dia, slot, sala), ou seja, do mais cedo ao mais tarde.
    """
    result: Dict[int, List[Placement]] = {}
    for a in inst.appointments:
        avail = inst.availability[a.dentist]
        options: List[Placement] = []
        for d in range(len(inst.days)):
            for s in range(inst.slots_per_day - a.duration + 1):
                if not all((d, s + k) in avail for k in range(a.duration)):
                    continue
                for r in range(len(inst.rooms)):
                    if a.needs_equipment and not inst.room_has_equipment[r]:
                        continue
                    options.append((d, s, r))
        result[a.id] = options
    return result


def placement_value(inst: Instance, a: Appointment, p: Placement) -> int:
    """Quanto vale ter a consulta `a` na colocação `p` (maior é melhor)."""
    day, slot, _room = p
    return BASE_PRIORITY * a.priority - (day * inst.slots_per_day + slot)


def score(inst: Instance, sol: Solution) -> int:
    """Função objetivo (a MESMA para CP-SAT, hill-climbing e simulated annealing).

    soma de [10000 * prioridade - posição_no_tempo] das consultas agendadas.
    """
    return sum(placement_value(inst, inst.appointment(i), p) for i, p in sol.items())


def validate(inst: Instance, sol: Solution) -> List[str]:
    """Confere todas as regras. Devolve a lista de erros (vazia = solução válida)."""
    errors: List[str] = []
    options = valid_placements(inst)
    dentist_busy: Dict[Tuple[int, int, int], int] = {}
    room_busy: Dict[Tuple[int, int, int], int] = {}

    for aid, p in sol.items():
        a = inst.appointment(aid)
        if p not in options[aid]:
            errors.append(f"Consulta {aid}: colocação {p} inválida (disponibilidade/sala/duração).")
            continue
        day, slot, room = p
        for t in range(slot, slot + a.duration):
            dk, rk = (a.dentist, day, t), (room, day, t)
            if dk in dentist_busy:
                errors.append(
                    f"Dentista {inst.dentists[a.dentist]} em duas consultas "
                    f"({dentist_busy[dk]} e {aid}) no dia {day}, slot {t}."
                )
            if rk in room_busy:
                errors.append(
                    f"Sala {inst.rooms[room]} com duas consultas "
                    f"({room_busy[rk]} e {aid}) no dia {day}, slot {t}."
                )
            dentist_busy[dk] = aid
            room_busy[rk] = aid
    return errors
