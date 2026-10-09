# TP1 — Gerador de Horário Escolar e Sudoku Genérico (CSP)

Trabalho prático de Lógica Computacional, com dois problemas modelados como **problemas de satisfação e otimização de restrições (CSP/CP)** e resolvidos com o **CP-SAT do OR-Tools**:

1. **Gerador de Horário Escolar**, com construção incremental (R9).
2. **Sudoku Genérico**, assente numa abstração única de "grupo de células todas diferentes".

## Autores

| Nome | Nº |
|---|---|
| Luis Miguel Torres Martins | Aº110241 |
| Lucas Gabriel Rodrigues Ferreira | Aº111724 |

---

## Estrutura do projeto

```
TP1/
├── src/                        # Biblioteca do gerador de horários
│   ├── models.py               # Dataclasses (Disciplina, Sala, Sessao, Dados) e geração de sessões
│   ├── loader.py               # Leitura e validação dos CSV (R8)
│   ├── scheduler.py            # Modelo CP-SAT, extração do horário e atribuição de salas
│   ├── constraints.py          # Restrições R1, R2, R3, R5, R7 (+ quebra de simetria)
│   ├── objective.py            # Objetivo O1: minimizar buracos
│   ├── incremental.py          # R9: construção incremental de H1 a partir de H0
│   ├── metrics.py              # Contagem de buracos e comparação entre horários
│   └── validator.py            # Validação independente do solver (R1–R7)
├── tests/                      # Testes automáticos (pytest)
├── data/
│   ├── dados/                  # Conjunto base (H0)
│   ├── dados_v2/               # Alteração de recursos (H1)
│   └── dados_v3/               # Conjunto maior (8 turmas, mais disciplinas e salas)
├── notebook/
│   ├── horario.py              # Notebook Marimo do horário escolar (relatório)
│   └── sudoku.py               # Notebook Marimo do Sudoku
├── horario_enunciado.py        # Enunciado do horário (notebook Marimo)
├── sudoku_enunciado.py         # Enunciado do Sudoku (notebook Marimo)
├── pytest.ini
└── README.MD
```

---

## Requisitos e instalação

- Python 3.11 ou superior (o notebook do Sudoku declara `>=3.14`)
- Bibliotecas: `ortools`, `pandas`, `marimo`, `pytest`

```bash
pip install ortools pandas marimo pytest
```

---

## Como executar

Todos os comandos devem ser corridos a partir da pasta `TP1/`.

### Notebooks (relatórios)

```bash
marimo run notebook/horario.py     # Horário escolar
marimo run notebook/sudoku.py      # Sudoku genérico
```

Para correr em modo aplicação (só leitura): `marimo run notebook/horario.py`.

### Linha de comandos

```bash
python -m src.scheduler      # Gera H0 com data/dados e imprime a grelha de cada turma
python -m src.incremental    # Compara abordagens H0 -> H1 (dados -> dados_v2) e imprime a tabela
```

### Testes

```bash
pytest
```

---

## 1. Gerador de Horário Escolar

### Dados de entrada (R8)

Os dados são sempre lidos de ficheiros CSV, nunca escritos no código. Qualquer pasta em `data/` com o mesmo formato pode ser usada.

| Ficheiro | Colunas | Descrição |
|---|---|---|
| `turmas.csv` | `turma` | Uma turma por linha |
| `disciplinas.csv` | `disciplina, professor, carga_semanal, duplo_periodo, sala_especial` | Currículo; `duplo_periodo` é `sim`/`nao`; `sala_especial` vazio = sala normal |
| `salas.csv` | `sala, tipo, quantidade` | `tipo` é `normal` ou `especial`; quantidade = nº de aulas em simultâneo |
| `disponibilidade_excecoes.csv` | `professor, dia, periodo` | Opcional; lista só os tempos em que o professor **não** está disponível |

O `loader.py` valida os dados e rejeita, com `ValueError`, valores inválidos: tipo de sala desconhecido, `sim`/`nao` incorreto, sala especial inexistente, dia ou período fora do intervalo e carga ímpar em disciplinas de duplo período. O número de dias e de tempos por dia é configurável em `carregar_dados(pasta, num_dias, num_periodos)`.

### Restrições obrigatórias

| Regra | Descrição | Onde é garantida |
|---|---|---|
| R1 | Uma turma não tem duas aulas em simultâneo | `constraints.py` |
| R2 | Cada disciplina cumpre exatamente a carga semanal | `constraints.py` |
| R3 | No máximo uma aula (ou bloco) da mesma disciplina por dia e turma | `constraints.py` |
| R4 | Duplo período = bloco de 2 tempos consecutivos no mesmo dia | Por construção das variáveis (`scheduler.py`) |
| R5 | Um professor não dá duas aulas em simultâneo | `constraints.py` |
| R6 | Professor só dá aulas quando está disponível | Por construção: não existem variáveis nos tempos indisponíveis |
| R7 | Salas do tipo certo e dentro da capacidade | `constraints.py` + atribuição de salas físicas |
| R8 | Dados lidos de CSV | `loader.py` |

### Modelação

- Cada aula a colocar é uma **sessão** (`Sessao`) com id estável `turma|disciplina|indice`. Uma disciplina de duplo período com carga `c` gera `c/2` sessões de duração 2.
- A variável de decisão é `comeca[(sessao, dia, periodo)]`, que vale 1 se a sessão começa nesse dia e período.
- R4 e R6 são garantidas **por construção**: só se criam variáveis para blocos que cabem no dia e em que o professor está disponível.
- R7 limita, por tipo de sala, o número de aulas em simultâneo. Depois da resolução, `_atribuir_salas` dá um nome de sala física a cada aula, mantendo a sala de H0 quando possível.
- Como as sessões da mesma disciplina são intermutáveis, o modelo aplica uma **quebra de simetria** (dias crescentes) para acelerar a resolução de H0. Está desligada no modo incremental.

### Objetivo (O1)

Minimizar o número de **buracos** dos professores (tempos livres entre a primeira e a última aula do dia). Como desempate opcional, também se podem compactar os horários das turmas (`peso_prof=10`, `peso_turma=1` por omissão).

### Construção incremental (R9)

Dado um horário `H0` e uma pequena alteração aos recursos (`dados` → `dados_v2`), `incremental.py` produz um `H1` válido, mais rápido e com menos mudanças do que resolver do zero. A técnica combina:

1. **Hint**: H0 é dado ao solver como ponto de partida.
2. **Minimizar mudanças**: o objetivo é o número de aulas de H0 que deixam de estar no mesmo tempo.
3. **Fixação progressiva** (modo `fixar`): fixam-se as aulas não afetadas e resolve-se só o subproblema afetado. Se for impossível, alarga-se a vizinhança por níveis:
   - nível 0: só se mexe nas aulas "quebradas" (slot já inválido, aulas novas, salas sobrelotadas);
   - nível 1: mais todas as aulas dos professores e turmas afetados;
   - nível 2: nada fixo (equivale ao modo `hint`).

A mudança mede-se por **tempo ocupado** `(turma, disciplina, dia, período)` e não pelo id da sessão, porque as sessões da mesma disciplina são intermutáveis.

Funções principais:

| Função | Descrição |
|---|---|
| `resolver_do_zero(dados)` | Base de comparação: resolve tudo com O1, sem usar H0 |
| `resolver_incremental(dados, h0, modo, otimizar_buracos)` | H1 a partir de H0; `modo` é `"fixar"` ou `"hint"` |
| `comparar_abordagens(dados0, dados1)` | Tabela com a mediana do tempo, aulas alteradas e buracos de cada variante |

Cenários de alteração tratados (testados em `tests/test_incremental.py`): professor com disponibilidade alterada, sala avariada, turma nova, professor substituído e instância impossível (devolve `INFEASIBLE` sem rebentar).

Compromisso: o H1 incremental pode ter mais buracos do que um H1 feito do zero; a variante `fixar + O1` recupera qualidade com algum custo de tempo.

### Validação independente

O `validator.py` verifica R1–R7 **sem usar o solver**, por isso apanha erros do próprio modelo. Cada regra devolve uma lista de `Violacao` (vazia = regra cumprida) e `validar_horario(dados, horario)` corre todas.

### Exemplo de uso em Python

```python
from src.loader import DATA_DIR, carregar_dados
from src.scheduler import Scheduler, imprimir_horario
from src.validator import validar_horario
from src.incremental import resolver_incremental

dados0 = carregar_dados(DATA_DIR / "dados")
agendador = Scheduler(dados0)
agendador.criar_variaveis()
agendador.aplicar_restricoes()
agendador.aplicar_objetivo(peso_prof=10, peso_turma=1)
agendador.resolver(tempo_limite=30)
h0 = agendador.extrair_solucao()

assert validar_horario(dados0, h0) == []
imprimir_horario(h0, dados0)

dados1 = carregar_dados(DATA_DIR / "dados_v2")
resultado = resolver_incremental(dados1, h0, modo="fixar")
print(resultado["estado"], resultado["alteradas"], f'{resultado["tempo"]:.2f}s')
```

---

## 2. Sudoku Genérico

O notebook `notebook/sudoku.py` resolve Sudokus de dimensão $n^2 \times n^2$ com uma única abstração: um **grupo de células** que têm de ter valores todos diferentes. O modelo CSP não sabe o que é uma linha, uma coluna ou um bloco; só recebe grupos, o que permite acrescentar variantes (diagonais, regiões irregulares) sem alterar o modelo.

| Elemento | Papel |
|---|---|
| `box` | Grupo genérico de células, algumas possivelmente fixas |
| `cube` | `box` que representa um bloco $n \times n$ |
| `path` | `box` que representa um troço reto (linha ou coluna) |
| `gerar_pistas_aleatorias` | Devolve um `box` com $k$ células fixas |
| `SudokuCSP` | Modelo CP-SAT (restrição global `AllDifferent`) |
| `resolver_sudoku` | Monta linhas, colunas, blocos e pistas e resolve |
| `validar_solucao` | Verificação independente do solver |

O `box` guarda um dicionário `{(linha, coluna): valor ou None}`, que só ocupa espaço para as células do grupo.

---

## Testes

A suite (`pytest`) está em `tests/` e cobre:

| Ficheiro | O que testa |
|---|---|
| `test_loader.py` | Leitura dos CSV, tipos, ids estáveis das sessões e rejeição de dados inválidos |
| `test_scheduler.py` | H0 válido e ótimo, dataset diferente sem alterar código, mais tempos por dia, instância impossível |
| `test_validator.py` | Injeção de violações: o validator tem de apanhar cada regra R1–R7 |
| `test_incremental.py` | Validade de H1 em todos os modos, mínimo teórico de mudanças, turma nova, professor substituído, sala avariada, métricas |

---

## Uso de IA

Foram usados GitHub Copilot, Claude e ChatGPT como apoio (texto do relatório, sugestões e melhorias de código). A lógica e a implementação base foram desenvolvidas pelos dois elementos do grupo, que assumem a responsabilidade por todo o conteúdo. O detalhe completo e as ligações de referência estão na secção "Uso de IA" de `notebook/horario.py` e `notebook/sudoku.py`.