"""Testes automaticos. Rodar na raiz do projeto:  python -m unittest -v"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agenda import (  # noqa: E402
    Appointment,
    Instance,
    generate_instance,
    hill_climbing,
    load_instance,
    save_instance,
    score,
    simulated_annealing,
    solve_cpsat,
    solve_cpsat_intervals,
    validate,
)


def mini_clinic(appointments, rooms=1, equipped=(True,), slots=2, available=None):
    """1 dentista, 1 dia. `available` = slots em que o dentista atende (padrao: todos)."""
    available = range(slots) if available is None else available
    return Instance(
        dentists=["Dra. Teste"],
        rooms=[f"Sala {i + 1}" for i in range(rooms)],
        room_has_equipment=list(equipped),
        days=["Seg"],
        slots_per_day=slots,
        availability={0: {(0, s) for s in available}},
        appointments=appointments,
    )


class TestModelo(unittest.TestCase):
    def test_validate_detecta_conflito_de_dentista(self):
        inst = mini_clinic([Appointment(0, "A", 0), Appointment(1, "B", 0)], rooms=2, equipped=(True, True))
        errors = validate(inst, {0: (0, 0, 0), 1: (0, 0, 1)})   # mesmo dentista, mesmo horario
        self.assertTrue(any("Dentista" in e for e in errors))

    def test_validate_detecta_conflito_de_sala(self):
        inst = Instance(
            dentists=["D1", "D2"], rooms=["Sala 1"], room_has_equipment=[True], days=["Seg"],
            slots_per_day=2, availability={0: {(0, 0), (0, 1)}, 1: {(0, 0), (0, 1)}},
            appointments=[Appointment(0, "A", 0), Appointment(1, "B", 1)],
        )
        errors = validate(inst, {0: (0, 0, 0), 1: (0, 0, 0)})   # mesma sala, mesmo horario
        self.assertTrue(any("Sala" in e for e in errors))

    def test_validate_aceita_solucao_correta(self):
        inst = mini_clinic([Appointment(0, "A", 0), Appointment(1, "B", 0)])
        self.assertEqual(validate(inst, {0: (0, 0, 0), 1: (0, 1, 0)}), [])


class TestSolvers(unittest.TestCase):
    ALL = {
        "cpsat": lambda i: solve_cpsat(i, time_limit=5).solution,
        "cpsat-int": lambda i: solve_cpsat_intervals(i, time_limit=5).solution,
        "hc": lambda i: hill_climbing(i, time_limit=1).solution,
        "sa": lambda i: simulated_annealing(i, time_limit=1).solution,
    }

    def test_otimo_conhecido_escolhe_as_de_maior_prioridade(self):
        # So cabem 2 consultas de 1 slot; devem ser as de prioridade 3 e 2.
        inst = mini_clinic([
            Appointment(0, "baixa", 0, priority=1),
            Appointment(1, "alta", 0, priority=3),
            Appointment(2, "media", 0, priority=2),
        ])
        for name, run in self.ALL.items():
            with self.subTest(solver=name):
                sol = run(inst)
                self.assertEqual(validate(inst, sol), [])
                self.assertEqual(set(sol), {1, 2})

    def test_sala_com_equipamento(self):
        inst = mini_clinic([Appointment(0, "A", 0, needs_equipment=True)],
                           rooms=2, equipped=(False, True))
        for name, run in self.ALL.items():
            with self.subTest(solver=name):
                sol = run(inst)
                self.assertEqual(sol[0][2], 1)          # tem que ser a sala 2 (indice 1)

    def test_consulta_que_nao_cabe_fica_sem_horario(self):
        # Dentista so atende no slot 0 e a consulta dura 2 slots: impossivel.
        inst = mini_clinic([Appointment(0, "A", 0, duration=2)], available=[0])
        for name, run in self.ALL.items():
            with self.subTest(solver=name):
                self.assertEqual(run(inst), {})

    def test_instancia_gerada_solucoes_validas_e_cpsat_nao_perde(self):
        inst = generate_instance(3, 2, 5, 8, 30, seed=3)
        cp = solve_cpsat(inst, time_limit=20)
        self.assertTrue(cp.optimal)
        results = {name: run(inst) for name, run in self.ALL.items()}
        for name, sol in results.items():
            with self.subTest(solver=name):
                self.assertEqual(validate(inst, sol), [])
                self.assertLessEqual(score(inst, sol), cp.score)


class TestJson(unittest.TestCase):
    def test_salvar_e_carregar_preserva_a_instancia(self):
        inst = generate_instance(3, 2, 5, 8, 20, seed=5)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "clinica.json")
            save_instance(inst, path)
            again = load_instance(path)
        self.assertEqual(inst.dentists, again.dentists)
        self.assertEqual(inst.availability, again.availability)
        self.assertEqual(inst.appointments, again.appointments)
        self.assertEqual(solve_cpsat(inst, time_limit=10).score, solve_cpsat(again, time_limit=10).score)


if __name__ == "__main__":
    unittest.main()
