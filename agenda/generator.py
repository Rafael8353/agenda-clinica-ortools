"""Gerador de clínicas aleatórias (reprodutíveis pela semente `seed`)."""
from __future__ import annotations

import random

from .models import Appointment, Instance

DENTIST_NAMES = [
    "Dra. Ana", "Dr. Bruno", "Dra. Carla", "Dr. Daniel", "Dra. Elisa", "Dr. Felipe",
    "Dra. Gabriela", "Dr. Henrique", "Dra. Isabela", "Dr. Joao", "Dra. Karina", "Dr. Lucas",
]
DAY_NAMES = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab"]


def generate_instance(
    n_dentists: int,
    n_rooms: int,
    n_days: int,
    slots_per_day: int,
    n_appointments: int,
    seed: int = 0,
) -> Instance:
    rng = random.Random(seed)

    dentists = [
        DENTIST_NAMES[i % len(DENTIST_NAMES)] + ("" if i < len(DENTIST_NAMES) else f" {i}")
        for i in range(n_dentists)
    ]
    rooms = [f"Sala {i + 1}" for i in range(n_rooms)]
    # ~1/3 das salas têm equipamento (raio-X), no mínimo uma.
    n_equipped = max(1, n_rooms // 3)
    room_has_equipment = [i < n_equipped for i in range(n_rooms)]
    days = [DAY_NAMES[i % len(DAY_NAMES)] for i in range(n_days)]

    # Disponibilidade: cada dia o dentista está de folga, só de manhã, só à tarde ou o dia todo.
    half = slots_per_day // 2
    patterns = {
        "folga": [],
        "manha": list(range(0, half)),
        "tarde": list(range(half, slots_per_day)),
        "integral": list(range(slots_per_day)),
    }
    availability = {}
    for dent in range(n_dentists):
        slots = set()
        working_days = 0
        for d in range(n_days):
            kind = rng.choices(list(patterns), weights=[0.2, 0.25, 0.25, 0.3])[0]
            if kind != "folga":
                working_days += 1
            slots.update((d, s) for s in patterns[kind])
        if working_days < 2:  # evita dentista que nunca atende
            for d in range(min(2, n_days)):
                slots.update((d, s) for s in range(slots_per_day))
        availability[dent] = slots

    appointments = []
    for i in range(n_appointments):
        appointments.append(
            Appointment(
                id=i,
                patient=f"Paciente {i + 1:03d}",
                dentist=rng.randrange(n_dentists),
                duration=rng.choices([1, 2], weights=[0.7, 0.3])[0],
                priority=rng.choices([1, 2, 3], weights=[0.5, 0.3, 0.2])[0],
                needs_equipment=rng.random() < 0.25,
            )
        )

    return Instance(
        dentists=dentists,
        rooms=rooms,
        room_has_equipment=room_has_equipment,
        days=days,
        slots_per_day=slots_per_day,
        availability=availability,
        appointments=appointments,
    )
