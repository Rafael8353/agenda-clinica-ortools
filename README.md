# Agenda de profissionais e salas com Google OR-Tools (CP-SAT)

Trabalho final de Inteligência Artificial (IFSUL). O programa monta a agenda de uma clínica
odontológica: decide **quando** e **em qual sala** cada consulta acontece, sem conflitos,
e compara o solver **CP-SAT do OR-Tools** com dois algoritmos de busca local vistos em aula:
**Hill-Climbing** e **Simulated Annealing**.

## 1. Como rodar (VS Code)

Requer Python 3.9 ou mais novo. Na pasta do projeto, no terminal do VS Code:

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate        Linux/Mac:  source .venv/bin/activate
pip install -r requirements.txt

python main.py                       # demo: gera uma clínica e resolve com CP-SAT
python main.py --solver all          # compara os 4 algoritmos na mesma clínica
python main.py --json dados/exemplo.json
python benchmark.py                  # experimentos do relatório (leva alguns minutos)
python benchmark.py --rapido         # versão curta, só para testar
python -m unittest -v                # testes automáticos
```

Opções úteis do `main.py`: `--dentistas 6 --salas 4 --dias 5 --slots 8 --consultas 60 --tempo 10 --seed 1`.
A agenda gerada é salva em `resultados/agenda.csv` (abre no Excel).

## 2. O problema

* O tempo é dividido em **slots** (1 slot = 1 hora). Um dia tem `slots_per_day` slots.
* Cada **consulta** tem: um dentista, uma duração (1 ou 2 slots), uma prioridade (1 a 3) e,
  às vezes, precisa de uma sala com equipamento (ex.: raio-X).
* Cada **dentista** só atende em certos dias/horários (manhã, tarde, dia todo ou folga).
* A **clínica** tem várias salas; só algumas têm equipamento.

**Regras (restrições):**

1. Um dentista não atende duas consultas ao mesmo tempo.
2. Uma sala não recebe duas consultas ao mesmo tempo.
3. A consulta precisa caber dentro do dia e dentro da disponibilidade do dentista.
4. Consulta que exige equipamento só vai para sala equipada.

**Objetivo:** maximizar `soma(10000 × prioridade − posição_no_tempo)` das consultas agendadas.
Na prática: primeiro agendar o maior número de consultas (as de maior prioridade primeiro) e,
como desempate, deixar a agenda o mais "cedo" possível (sem buracos no fim da semana).
Consultas que não cabem ficam sem horário e são listadas no final.

## 3. Os algoritmos

### CP-SAT, modelo "grade" (`agenda/cpsat_solver.py`)
Uma variável booleana `x[consulta, dia, slot, sala]` para cada colocação possível
(1 = "a consulta começa aí, nessa sala"). Restrições:
* cada consulta tem no máximo uma colocação;
* para cada (dentista, dia, slot) no máximo uma consulta ocupando aquele slot;
* para cada (sala, dia, slot) no máximo uma consulta ocupando aquele slot.

As restrições 3 e 4 do problema são resolvidas **antes**, criando só as variáveis válidas.
É um modelo fácil de explicar e, no benchmark, foi o que mais chegou ao **ótimo provado** (cenários pequeno e grande; no médio ficou muito perto, sem provar).

### CP-SAT, modelo "intervalos" (`agenda/cpsat_intervals.py`)
Forma clássica de escalonamento no OR-Tools: cada consulta tem uma variável de início, uma
booleana "foi agendada" e booleanas de sala; os conflitos viram `NoOverlap` sobre intervalos
opcionais (um por dentista e um por sala). Serve para mostrar que **a formulação do modelo
muda o desempenho** (compare os dois nos experimentos).

### Hill-Climbing e Simulated Annealing (`agenda/local_search.py`)
* Estado: agenda sempre válida, começando de uma solução gulosa (prioridade maior primeiro).
* Vizinhança: sorteia uma consulta e um horário/sala possível; se houver conflito, as consultas
  em conflito são "expulsas" (ficam sem horário).
* Hill-Climbing: aceita só movimentos que não pioram; para quando fica `patience` tentativas sem melhorar.
* Simulated Annealing: aceita piora com probabilidade `exp(Δ/T)`; a temperatura cai
  geometricamente de `t_start=2000` a `t_end=1` durante o tempo disponível.

## 4. Estrutura do projeto

```
main.py                  demonstração (linha de comando)
benchmark.py             experimentos: 3 cenários x 4 algoritmos, CSV e gráficos
agenda/
  models.py              dados do problema, pontuação (função objetivo), validação
  generator.py           gerador de clínicas aleatórias (com semente)
  cpsat_solver.py        CP-SAT - modelo grade
  cpsat_intervals.py     CP-SAT - modelo intervalos + NoOverlap
  local_search.py        Hill-Climbing e Simulated Annealing
  report.py              grade de horários em texto e exportação CSV
  io.py                  ler/gravar a clínica em JSON
dados/exemplo.json       exemplo de clínica em JSON
resultados/              saídas do benchmark (CSV e PNG)
tests/test_agenda.py     testes automáticos
```

## 5. Usando os dados da clínica real

Copie `dados/exemplo.json`, edite dias, salas, dentistas (com a disponibilidade) e consultas
e rode `python main.py --json minha_clinica.json --solver all`.
Em `disponibilidade`, `[0, 4]` significa os slots 0, 1, 2 e 3 (as 4 primeiras horas do dia).
Use apenas dados **anonimizados** (por exemplo "Paciente 001"), por causa da LGPD.

## 6. Experimentos (`benchmark.py`)

Três cenários (pequeno, médio e grande, definidos em `SCENARIOS`). Para cada um roda os dois
modelos CP-SAT uma vez e cada busca local com 5 sementes diferentes, e mede: consultas
agendadas, pontuação, tempo e a pontuação como % do melhor CP-SAT. Gera `resultados/benchmark.csv`,
`benchmark_resumo.csv` e gráficos (`benchmark_pontuacao.png`, `convergencia_*.png`).

Os arquivos que já estão em `resultados/` foram gerados numa máquina de apenas 2 núcleos; refaça no seu PC.

Observações para o relatório:
* Os números dependem do computador (núcleos/velocidade) e do tempo de cada execução; rode no seu
  PC e cite a configuração. O CP-SAT usa todos os núcleos (`--workers 0`).
* "OPTIMAL" significa que o CP-SAT **provou** que não existe agenda melhor; "FEASIBLE" significa que
  achou uma boa agenda, mas não provou que é a melhor dentro do tempo.
* A busca local não dá garantia de otimalidade, mas costuma chegar perto muito rápido.

## 7. Roteiro sugerido para o relatório

1. **Problema:** agenda da clínica, regras e objetivo (seção 2).
2. **Revisão:** busca local (hill-climbing, simulated annealing), programação por restrições
   e o OR-Tools / CP-SAT; ferramentas alternativas.
3. **Modelagem:** variáveis, restrições e função objetivo dos dois modelos CP-SAT; representação e
   vizinhança da busca local; gerador de cenários e método de avaliação (seção 6).
4. **Resultados:** tabela e gráficos do `benchmark.py`, exemplo de agenda do `main.py`,
   dificuldades (escolher a formulação, calibrar a temperatura do SA, impacto dos núcleos).
