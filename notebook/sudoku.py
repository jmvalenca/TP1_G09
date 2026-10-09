# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "marimo>=0.25.1",
# ]
# ///

import marimo
 
__generated_with = "0.24.2"
app = marimo.App(width="medium")
 
 
# ──────────────────────────────────────────────────────────────────────────────
# 0. IMPORTS E INTRODUÇÃO
# ──────────────────────────────────────────────────────────────────────────────
@app.cell
def _():
    import marimo as mo
 
    return (mo,)
 
 
@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
 
    ## Ideia central
 
    No Sudoku a regra é sempre a mesma: *um conjunto de células tem de ter valores todos
    diferentes*. Linhas, colunas e blocos só diferem em **que células** pertencem ao conjunto.
    Por isso toda a solução assenta numa única abstração, o grupo de células (`box`), a partir da
    qual tudo o resto se constrói:
 
    | Elemento | Papel | Requisito |
    |---|---|---|
    | `box` | grupo genérico de células, algumas possivelmente fixas | R1 |
    | `cube` | `box` que representa um bloco $n \times n$ | R2 |
    | `path` | `box` que representa um troço reto (linha ou coluna) | R3 |
    | `gerar_pistas_aleatorias` | devolve um `box` com $k$ células fixas | R4 |
    | `SudokuCSP` | modelo CP-SAT; recebe grupos sem saber a sua origem | R5 |
    | `resolver_sudoku` | monta linhas + colunas + blocos + pistas e resolve | R6 |
    | `validar_solucao` | verificação independente do solver | testes |
 
    O modelo CSP **não sabe o que é uma linha, uma coluna ou um bloco**: só recebe grupos. É isto
    que permite acrescentar variantes (diagonais, regiões irregulares) sem tocar no modelo.
    """)
    return
 
 
@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Decisões de modelação e justificação
 
    **Solver: CP-SAT do OR-Tools.** A regra "células todas diferentes" corresponde diretamente à
    restrição global `AllDifferent`, que o CP-SAT trata com propagação mais forte do que um conjunto
    de desigualdades `!=` par a par. O código limita-se a *descrever* o problema e o solver faz a
    pesquisa, o que é mais curto, mais legível e escala melhor do que um backtracking escrito à mão.
 
    **Estrutura interna do `box`: dicionário.** Guardamos `{(linha, coluna): valor ou None}`. Só
    ocupa espaço para as células que pertencem ao grupo (uma linha tem $n^2$ entradas e não $n^4$)
    e a matriz $n^2 \times n^2$ só é construída quando é pedida (`as_matrix`).
 
    **Apresentação: texto simples.** A grelha é impressa com `.` nas células vazias. É suficiente
    para ler o resultado e não acrescenta dependências.
 
    **Pistas como grupo próprio, mas sem `AllDifferent`.** Um grupo de pistas é um `box` como os
    outros e chega ao modelo como tal (R6: "linhas, colunas, blocos e pistas"). Há porém um detalhe
    importante: as pistas são $k$ células espalhadas pela grelha, escolhidas ao acaso, e **não
    têm de ser diferentes entre si** (o mesmo dígito pode aparecer em duas linhas, colunas e blocos
    diferentes). Se o modelo lhes impusesse `AllDifferent`, exigiria-se algo que o Sudoku não exige e
    puzzles perfeitamente válidos passariam a ser impossíveis. Por isso `add_group` tem o parâmetro
    `todos_diferentes` e `add_clues` fixa os valores **sem** impor a diferença. Um dos testes mais
    abaixo mostra um caso concreto em que as duas leituras dão resultados diferentes.
 
    **Pistas sem solução.** Os valores das pistas são aleatórios em $[1, n^2]$ e $k = n$ por omissão,
    por isso duas pistas podem contradizer-se (por exemplo, o mesmo dígito duas vezes na mesma linha).
    Decidimos **tentar novas pistas** até um máximo de tentativas; se nenhuma tiver solução,
    devolve-se `None` em vez de entrar num ciclo infinito. Escolhemos tentar de novo porque o
    objetivo é obter um puzzle resolvido, e o limite garante que o programa termina sempre.
 
    **Aleatoriedade controlável.** As funções que sorteiam recebem opcionalmente um gerador
    `random.Random`. Assim os testes usam uma semente fixa e dão sempre o mesmo resultado, sem
    mexer no estado global do módulo `random`.
    """)
    return
 
 
@app.cell
def _():
    import random
    import time
 
    from ortools.sat.python import cp_model
 
    return cp_model, random, time
 
 
# ──────────────────────────────────────────────────────────────────────────────
# 1. R1 — GRUPO GENÉRICO
# ──────────────────────────────────────────────────────────────────────────────
@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## R1 — `box`: grupo genérico de células
 
    O `box` representa **qualquer** conjunto de células ao qual se aplica "todos diferentes", com
    algumas células possivelmente já fixas. Não sabe nada de linhas, colunas, blocos ou Sudoku.
 
    - `add(linha, coluna, valor=None)` acrescenta uma célula e **rejeita** (`ValueError`) coordenadas
      fora da grelha, valores fora de $[1, n^2]$ e argumentos que não sejam inteiros.
    - O construtor aceita opcionalmente um dicionário inicial e reutiliza `add`, por isso a validação
      é a mesma e não há maneira de criar um `box` inválido.
    - `n` é obrigatório porque é ele que define os limites da grelha usados na validação.
    - `as_matrix()` devolve a matriz $n^2 \times n^2$ com o valor das células fixas e `0` nas restantes.
    """)
    return
 
 
@app.cell
def _():
    class box:
        """Conjunto de células com a restrição 'todos diferentes'.
 
        Guarda {(linha, coluna): valor ou None}; None significa célula livre.
        """
 
        def __init__(self, n, cells=None):
            self.n = n
            self.cells = {}
            for (linha, coluna), valor in (cells or {}).items():
                self.add(linha, coluna, valor)
 
        @staticmethod
        def _inteiro(x):
            return isinstance(x, int) and not isinstance(x, bool)
 
        def add(self, linha, coluna, valor=None):
            """Adiciona uma célula; levanta ValueError se for inválida."""
            dim = self.n ** 2
            if not (self._inteiro(linha) and self._inteiro(coluna)):
                raise ValueError(f"Coordenadas têm de ser inteiros: ({linha!r}, {coluna!r})")
            if not (0 <= linha < dim and 0 <= coluna < dim):
                raise ValueError(f"Coordenadas fora da grelha: ({linha}, {coluna})")
            if valor is not None:
                if not self._inteiro(valor):
                    raise ValueError(f"O valor tem de ser inteiro ou None: {valor!r}")
                if not (1 <= valor <= dim):
                    raise ValueError(f"Valor fora de 1..{dim}: {valor}")
            self.cells[(linha, coluna)] = valor
 
        def as_matrix(self):
            """Matriz n² × n² com o valor das células fixas e 0 nas restantes."""
            dim = self.n ** 2
            matriz = [[0] * dim for _ in range(dim)]
            for (linha, coluna), valor in self.cells.items():
                if valor is not None:
                    matriz[linha][coluna] = valor
            return matriz
 
    return (box,)
 
 
# ──────────────────────────────────────────────────────────────────────────────
# 2. R2, R3 — CUBE E PATH
# ──────────────────────────────────────────────────────────────────────────────
@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## R2 e R3 — `cube` e `path`: duas formas concretas de grupo
 
    Ambas são subclasses de `box` e **só acrescentam o modo de construção**: o cálculo de que
    células pertencem ao grupo. A restrição em si continua a ser a do `box`.
 
    - **`cube(n, i, j)`** é o bloco $n \times n$ com canto superior esquerdo em $(i \cdot n,\ j \cdot n)$,
      com $0 \le i, j < n$. Rejeita índices de bloco fora do intervalo.
    - **`path(n, inicio, fim)`** é o troço reto, horizontal ou vertical, entre duas coordenadas
      inclusivas. Usa `min` e `max` para funcionar em qualquer sentido (`fim` antes ou depois de
      `inicio`). Uma linha completa é `path(n, (i, 0), (i, n²−1))` e uma coluna completa é
      `path(n, (0, j), (n²−1, j))`. Rejeita troços em diagonal.
    """)
    return
 
 
@app.cell
def _(box):
    class cube(box):
        """Bloco n × n com canto superior esquerdo em (i·n, j·n)."""
 
        def __init__(self, n, bloco_linha, bloco_coluna):
            super().__init__(n)
            if not (box._inteiro(bloco_linha) and box._inteiro(bloco_coluna)):
                raise ValueError("Índices de bloco têm de ser inteiros")
            if not (0 <= bloco_linha < n and 0 <= bloco_coluna < n):
                raise ValueError("Índice de bloco fora do intervalo 0..n-1")
            for i in range(n):
                for j in range(n):
                    self.add(bloco_linha * n + i, bloco_coluna * n + j)
 
    class path(box):
        """Linha ou coluna entre duas coordenadas (inclusivas), em qualquer sentido."""
 
        def __init__(self, n, inicio, fim):
            super().__init__(n)
            (l1, c1), (l2, c2) = inicio, fim
            if l1 == l2:
                for c in range(min(c1, c2), max(c1, c2) + 1):
                    self.add(l1, c)
            elif c1 == c2:
                for l in range(min(l1, l2), max(l1, l2) + 1):
                    self.add(l, c1)
            else:
                raise ValueError("O caminho tem de ser horizontal ou vertical")
 
    return cube, path
 
 
# ──────────────────────────────────────────────────────────────────────────────
# 3. R4 — PISTAS ALEATÓRIAS
# ──────────────────────────────────────────────────────────────────────────────
@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## R4 — Geração aleatória de pistas
 
    `gerar_pistas_aleatorias(n, k)` devolve **um `box`**, sem nenhuma classe nova: $k$ posições
    distintas escolhidas ao acaso (`random.sample`, que não repete posições), cada uma fixada a um
    valor aleatório em $[1, n^2]$. Por omissão $k = n$ (3 pistas no $9 \times 9$, 2 no $4 \times 4$),
    um valor pequeno que deixa quase sempre o puzzle possivel. Se $k$ for maior do que o número de
    células, é limitado a $n^4$.
 
    O parâmetro opcional `rng` recebe um `random.Random` para tornar a geração reprodutível.
    """)
    return
 
 
@app.cell
def _(box, random):
    def gerar_pistas_aleatorias(n, k=None, rng=None):
        """box com k posições distintas fixadas a valores aleatórios em 1..n² (k=n por omissão)."""
        rng = rng or random
        dim = n ** 2
        if k is None:
            k = n
        k = max(0, min(k, dim * dim))
        pistas = box(n)
        todas = [(l, c) for l in range(dim) for c in range(dim)]
        for linha, coluna in rng.sample(todas, k):
            pistas.add(linha, coluna, rng.randint(1, dim))
        return pistas
 
    return (gerar_pistas_aleatorias,)
 
 
# ──────────────────────────────────────────────────────────────────────────────
# 4. ESTRUTURA DO SUDOKU
# ──────────────────────────────────────────────────────────────────────────────
@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Estrutura do Sudoku: linhas, colunas e blocos
 
    `criar_grupos_sudoku(n)` constrói os $3 n^2$ grupos do Sudoku clássico: $n^2$ linhas, $n^2$
    colunas e $n^2$ blocos, todos como `path` ou `cube`. Esta função **não conhece as pistas**: elas
    são um grupo à parte que o modelo recebe separadamente.
    """)
    return
 
 
@app.cell
def _(cube, path):
    def criar_grupos_sudoku(n):
        """Linhas, colunas e blocos (3·n² grupos), sem pistas."""
        dim = n ** 2
        grupos = [path(n, (i, 0), (i, dim - 1)) for i in range(dim)]
        grupos += [path(n, (0, i), (dim - 1, i)) for i in range(dim)]
        grupos += [cube(n, i, j) for i in range(n) for j in range(n)]
        return grupos
 
    return (criar_grupos_sudoku,)
 
 
# ──────────────────────────────────────────────────────────────────────────────
# 5. R5 — MODELO CSP
# ──────────────────────────────────────────────────────────────────────────────
@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## R5 — Modelo CSP
 
    **Variáveis:** uma variável inteira por célula, com domínio $[1, n^2]$.
 
    **Restrições:** vêm todas dos grupos que o modelo recebe.
 
    - `add_group(grupo, todos_diferentes=True)` impõe `AllDifferent` nas células do grupo (se
      `todos_diferentes`) e fixa as que tenham valor atribuído. É o comportamento pedido em R5.
    - `add_groups(*grupos)` aceita **um número arbitrário de grupos**, de qualquer tipo.
    - `add_clues(pistas)` é o caso particular de um grupo de pistas: só fixa valores, sem impor que
      sejam diferentes entre si (ver a justificação na secção de decisões).
 
    **Resolução:** `solve()` devolve a grelha preenchida ou `None` se não houver solução. O motivo
    fica em `estado` (`"OPTIMAL"`/`"FEASIBLE"`, `"INFEASIBLE"`, `"UNKNOWN"`…), por isso "sem
    solução" é distinguível de "o solver não chegou a uma conclusão" (por exemplo, por limite de
    tempo).
    """)
    return
 
 
@app.cell
def _(cp_model):
    class SudokuCSP:
        """Modelo CSP: uma variável 1..n² por célula."""
 
        def __init__(self, n):
            self.n = n
            dim = n ** 2
            self.model = cp_model.CpModel()
            self.vars = [
                [self.model.new_int_var(1, dim, f"x_{l}_{c}") for c in range(dim)]
                for l in range(dim)
            ]
            self.estado = None
 
        def add_group(self, grupo, todos_diferentes=True):
            """Fixa as células com valor e, se pedido, impõe valores distintos no grupo."""
            if grupo.n != self.n:
                raise ValueError(f"Grupo com n={grupo.n} num modelo com n={self.n}")
            if todos_diferentes:
                self.model.add_all_different([self.vars[l][c] for (l, c) in grupo.cells])
            for (l, c), valor in grupo.cells.items():
                if valor is not None:
                    self.model.add(self.vars[l][c] == valor)
 
        def add_groups(self, *grupos):
            """Aceita um número arbitrário de grupos (box, cube, path, ...)."""
            for grupo in grupos:
                self.add_group(grupo)
 
        def add_clues(self, pistas):
            """Grupo de pistas: fixa os valores sem exigir que sejam todos diferentes."""
            self.add_group(pistas, todos_diferentes=False)
 
        def solve(self, tempo_limite=None):
            """Grelha resolvida, ou None se não houver solução (motivo em self.estado)."""
            solver = cp_model.CpSolver()
            if tempo_limite is not None:
                solver.parameters.max_time_in_seconds = tempo_limite
            estado = solver.solve(self.model)
            self.estado = solver.status_name(estado)
            if estado not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                return None
            return [[solver.value(x) for x in linha] for linha in self.vars]
 
    return (SudokuCSP,)
 
 
# ──────────────────────────────────────────────────────────────────────────────
# 6. R6 — SUDOKU COMPLETO
# ──────────────────────────────────────────────────────────────────────────────
@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## R6 — Sudoku completo
 
    `resolver_sudoku(n, k, max_tentativas)` junta tudo:
 
    1. gera um grupo de pistas aleatórias (R4);
    2. cria um modelo novo e entrega-lhe linhas, colunas e blocos (`add_groups`) e as pistas
       (`add_clues`);
    3. resolve; se o puzzle for impossível, volta ao passo 1 até `max_tentativas`.
 
    Devolve `(pistas, grupos, grelha, tentativas)`; `grelha` é `None` se todas as tentativas falharem.
    Como cada tentativa cria um modelo novo, uma tentativa falhada não deixa restrições para trás.
    """)
    return
 
 
@app.cell
def _(SudokuCSP, criar_grupos_sudoku, gerar_pistas_aleatorias):
    def resolver_sudoku(n, k=None, max_tentativas=50, rng=None):
        """Devolve (pistas, grupos, grelha, tentativas); grelha é None se falhar sempre."""
        pistas = grupos = None
        for tentativa in range(1, max_tentativas + 1):
            pistas = gerar_pistas_aleatorias(n, k, rng)
            grupos = criar_grupos_sudoku(n)
            csp = SudokuCSP(n)
            csp.add_groups(*grupos)
            csp.add_clues(pistas)
            grelha = csp.solve()
            if grelha is not None:
                return pistas, grupos, grelha, tentativa
        return pistas, grupos, None, max_tentativas
 
    return (resolver_sudoku,)
 
 
# ──────────────────────────────────────────────────────────────────────────────
# 7. VALIDAÇÃO E APRESENTAÇÃO
# ──────────────────────────────────────────────────────────────────────────────
@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Validação independente
 
    `validar_solucao(grelha, n, pistas)` verifica uma grelha **sem usar `box`, `cube`, `path` nem o
    modelo**, para que o teste não seja circular (se a construção dos grupos tivesse um erro, um
    validador que a reutilizasse repetiria o erro e passaria):
 
    - a grelha tem dimensão $n^2 \times n^2$;
    - cada linha, cada coluna e cada bloco, calculados com índices diretos, contém exatamente
      $1 \ldots n^2$ (compara-se `sorted(...)` com `range`);
    - cada pista mantém o valor com que foi fixada, comparando diretamente com `pistas.cells`.
 
    Devolve a **lista de problemas** encontrados (vazia se a grelha for válida), o que torna as falhas
    legíveis. `formatar_grelha` limita-se a imprimir a matriz em texto.
    """)
    return
 
 
@app.cell
def _():
    def validar_solucao(grelha, n, pistas=None):
        """Lista de problemas da grelha (vazia = válida), sem reutilizar os grupos do modelo."""
        dim = n ** 2
        if grelha is None:
            return ["não há grelha"]
        if len(grelha) != dim or any(len(linha) != dim for linha in grelha):
            return [f"a grelha não é {dim}×{dim}"]
        alvo = list(range(1, dim + 1))
        problemas = []
        for i in range(dim):
            if sorted(grelha[i]) != alvo:
                problemas.append(f"linha {i} inválida: {grelha[i]}")
            coluna = [grelha[l][i] for l in range(dim)]
            if sorted(coluna) != alvo:
                problemas.append(f"coluna {i} inválida: {coluna}")
        for bi in range(n):
            for bj in range(n):
                bloco = [grelha[bi * n + a][bj * n + b] for a in range(n) for b in range(n)]
                if sorted(bloco) != alvo:
                    problemas.append(f"bloco ({bi},{bj}) inválido: {bloco}")
        if pistas is not None:
            for (l, c), valor in pistas.cells.items():
                if valor is not None and grelha[l][c] != valor:
                    problemas.append(f"pista ({l},{c})={valor} não respeitada (há {grelha[l][c]})")
        return problemas
 
    def formatar_grelha(matriz):
        return "\n".join(" ".join(str(v) if v else "." for v in linha) for linha in matriz)
 
    return formatar_grelha, validar_solucao
 
 
# ──────────────────────────────────────────────────────────────────────────────
# 8. TESTES
# ──────────────────────────────────────────────────────────────────────────────
@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Testes
 
    Cada linha abaixo é uma verificação automática. Os testes cobrem:
 
    - **R1** — rejeição de coordenadas e valores inválidos, construtor com células iniciais, `as_matrix`;
    - **R2 e R3** — `cube` em várias posições (e os 4 blocos de $n=2$ a cobrirem a grelha sem sobreposição),
      `path` horizontal e vertical nos dois sentidos, e rejeição de argumentos inválidos;
    - **R4** — número e distinção das pistas, domínio dos valores, valor por omissão de $k$ e reprodutibilidade;
    - **R5** — um puzzle **impossível** devolve `None` com estado `INFEASIBLE`, e a diferença entre
      `add_clues` e `AllDifferent` nas pistas;
    - **R6** — fluxo completo para $n = 2, 3, 4$, validado de forma independente;
    - **o próprio validador** — apanha uma grelha estragada de propósito (um teste que nunca falha não prova nada).
 
    Os testes que sorteiam usam `random.Random(semente)`, por isso dão sempre o mesmo resultado.
    """)
    return
 
 
@app.cell
def _(
    SudokuCSP,
    box,
    criar_grupos_sudoku,
    cube,
    gerar_pistas_aleatorias,
    mo,
    path,
    random,
    resolver_sudoku,
    validar_solucao,
):
    def _rejeita(fn, *args):
        try:
            fn(*args)
        except ValueError:
            return True
        return False
 
    def _resolve(n, pistas, todos_diferentes_pistas=False):
        csp = SudokuCSP(n)
        csp.add_groups(*criar_grupos_sudoku(n))
        if todos_diferentes_pistas:
            csp.add_group(pistas)
        else:
            csp.add_clues(pistas)
        return csp, csp.solve()
 
    _t = []  # (secção, descrição, passou)
 
    # ---- R1 ----
    _b3 = box(3)
    _t += [
        ("R1", "add rejeita linha fora da grelha", _rejeita(_b3.add, 9, 0, 1)),
        ("R1", "add rejeita coluna negativa", _rejeita(_b3.add, 0, -1, 1)),
        ("R1", "add rejeita valor 0", _rejeita(_b3.add, 0, 0, 0)),
        ("R1", "add rejeita valor n²+1", _rejeita(_b3.add, 0, 0, 10)),
        ("R1", "add rejeita coordenada não inteira", _rejeita(_b3.add, 0.5, 0, 1)),
        ("R1", "add rejeita valor que não é inteiro", _rejeita(_b3.add, 0, 0, "5")),
        ("R1", "add aceita um valor válido", not _rejeita(box(3).add, 0, 0, 9)),
        ("R1", "add sem valor deixa a célula livre", (lambda b: (b.add(1, 1), b.cells[(1, 1)] is None)[1])(box(3))),
        ("R1", "construtor aceita células iniciais", box(2, {(0, 0): 3, (1, 1): None}).cells == {(0, 0): 3, (1, 1): None}),
        ("R1", "construtor rejeita células iniciais inválidas", _rejeita(box, 2, {(0, 4): 1})),
        (
            "R1",
            "as_matrix: valores fixos e zeros",
            box(2, {(0, 0): 3, (1, 2): None, (3, 3): 4}).as_matrix()
            == [[3, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 4]],
        ),
    ]
 
    # ---- R2 ----
    _blocos2 = [cube(2, i, j) for i in range(2) for j in range(2)]
    _uniao = set().union(*(b.cells for b in _blocos2))
    _t += [
        ("R2", "cube(2,0,1) tem as 4 células certas", set(cube(2, 0, 1).cells) == {(0, 2), (0, 3), (1, 2), (1, 3)}),
        ("R2", "cube(3,2,1) começa em (6,3) e tem 9 células",
         len(cube(3, 2, 1).cells) == 9 and min(cube(3, 2, 1).cells) == (6, 3) and max(cube(3, 2, 1).cells) == (8, 5)),
        ("R2", "os 4 blocos de n=2 cobrem a grelha sem sobreposição",
         len(_uniao) == 16 and sum(len(b.cells) for b in _blocos2) == 16),
        ("R2", "cube rejeita índice de bloco n", _rejeita(cube, 2, 0, 2)),
        ("R2", "cube rejeita índice de bloco negativo", _rejeita(cube, 2, -1, 0)),
    ]
 
    # ---- R3 ----
    _t += [
        ("R3", "path horizontal funciona nos dois sentidos",
         set(path(2, (0, 0), (0, 3)).cells) == set(path(2, (0, 3), (0, 0)).cells) == {(0, c) for c in range(4)}),
        ("R3", "path vertical funciona nos dois sentidos",
         set(path(2, (0, 1), (3, 1)).cells) == set(path(2, (3, 1), (0, 1)).cells) == {(l, 1) for l in range(4)}),
        ("R3", "path com troço parcial (não só linhas completas)",
         set(path(3, (4, 2), (4, 5)).cells) == {(4, 2), (4, 3), (4, 4), (4, 5)}),
        ("R3", "path rejeita diagonal", _rejeita(path, 2, (0, 0), (1, 1))),
        ("R3", "path rejeita coordenadas fora da grelha", _rejeita(path, 3, (0, 0), (0, 9))),
    ]
 
    # ---- R4 ----
    _p = gerar_pistas_aleatorias(3, 10, random.Random(1))
    _t += [
        ("R4", "k pistas em posições distintas", len(_p.cells) == 10),
        ("R4", "valores das pistas em 1..n²", all(1 <= v <= 9 for v in _p.cells.values())),
        ("R4", "k por omissão é n", len(gerar_pistas_aleatorias(3, rng=random.Random(2)).cells) == 3
         and len(gerar_pistas_aleatorias(2, rng=random.Random(2)).cells) == 2),
        ("R4", "k acima do máximo é limitado a n⁴", len(gerar_pistas_aleatorias(2, 999, random.Random(3)).cells) == 16),
        ("R4", "mesma semente, mesmas pistas",
         gerar_pistas_aleatorias(3, 8, random.Random(7)).cells == gerar_pistas_aleatorias(3, 8, random.Random(7)).cells),
    ]
 
    # ---- R5 ----
    _imp = box(2, {(0, 0): 1, (0, 1): 1})  # o mesmo valor duas vezes na linha 0
    _csp_imp, _g_imp = _resolve(2, _imp)
    _dif = box(2, {(0, 0): 1, (3, 3): 1})  # mesmo valor, mas linha, coluna e bloco diferentes
    _csp_ok, _g_ok = _resolve(2, _dif)
    _csp_estrito, _g_estrito = _resolve(2, _dif, todos_diferentes_pistas=True)
    _csp_vazio, _g_vazio = _resolve(3, box(3))
    _t += [
        ("R5", "puzzle impossível devolve None", _g_imp is None),
        ("R5", "e o estado distingue-o: INFEASIBLE", _csp_imp.estado == "INFEASIBLE"),
        ("R5", "add_clues aceita pistas repetidas em zonas diferentes",
         _g_ok is not None and validar_solucao(_g_ok, 2, _dif) == []),
        ("R5", "AllDifferent nas pistas seria demasiado estrito (mesmo puzzle, sem solução)", _g_estrito is None),
        ("R5", "sem pistas o modelo resolve um Sudoku vazio 9×9",
         _g_vazio is not None and validar_solucao(_g_vazio, 3) == []),
        ("R5", "add_group rejeita grupo com n diferente", _rejeita(SudokuCSP(3).add_group, box(2))),
    ]
 
    # ---- R6: fluxo completo ----
    for _n in (2, 3, 4):
        _rng = random.Random(100 + _n)
        _pistas, _grupos, _grelha, _tent = resolver_sudoku(_n, rng=_rng)
        _problemas = validar_solucao(_grelha, _n, _pistas)
        _t.append(("R6", f"fluxo completo n={_n} ({_n**2}×{_n**2}): resolvido e válido", _grelha is not None and not _problemas))
        _t.append(("R6", f"n={_n}: pistas preservadas na solução",
                   _grelha is not None and all(_grelha[l][c] == v for (l, c), v in _pistas.cells.items())))
    _t.append(("R6", "número de grupos é 3·n² (n=3 → 27)", len(criar_grupos_sudoku(3)) == 27))
 
    # ---- o próprio validador ----
    _base_pistas, _, _base, _ = resolver_sudoku(3, rng=random.Random(5))
    _lin, _col = next(iter(_base_pistas.cells))
    _estragada1 = [linha[:] for linha in _base]
    _estragada1[0][0], _estragada1[0][1] = _estragada1[0][1], _estragada1[0][0]  # troca → duplica coluna/bloco
    _estragada2 = [linha[:] for linha in _base]
    _estragada2[_lin][_col] = _base_pistas.cells[(_lin, _col)] % 9 + 1  # altera uma pista
    _estragada3 = [linha[:] for linha in _base]
    _estragada3[4][4] = _estragada3[4][3]  # repete um valor na linha
    _t += [
        ("validador", "aceita uma solução correta", validar_solucao(_base, 3, _base_pistas) == []),
        ("validador", "apanha duas células trocadas", validar_solucao(_estragada1, 3) != []),
        ("validador", "apanha uma pista alterada", any("pista" in p for p in validar_solucao(_estragada2, 3, _base_pistas))),
        ("validador", "apanha um valor repetido na linha", validar_solucao(_estragada3, 3) != []),
        ("validador", "apanha dimensão errada", validar_solucao(_base[:-1], 3) != []),
        ("validador", "apanha ausência de grelha", validar_solucao(None, 3) != []),
    ]
 
    _falhas = [t for t in _t if not t[2]]
    _linhas = "\n".join(f"{'OK  ' if ok else 'ERRO'}  [{sec}] {nome}" for sec, nome, ok in _t)
    mo.vstack(
        [
            mo.callout(
                mo.md(f"**{len(_t) - len(_falhas)}/{len(_t)} testes passam.**" if not _falhas
                      else f"**{len(_falhas)} de {len(_t)} testes falham.**"),
                kind="success" if not _falhas else "danger",
            ),
            mo.md(f"```\n{_linhas}\n```"),
        ]
    )
    return
 
 
# ──────────────────────────────────────────────────────────────────────────────
# 9. EXEMPLOS E ESCALA
# ──────────────────────────────────────────────────────────────────────────────
@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Exemplos de execução
 
    Fluxo completo (pistas aleatórias → linhas + colunas + blocos + pistas → resolver → validar) com
    $n = 3$ (Sudoku clássico $9 \times 9$) e $n = 2$ ($4 \times 4$). Os valores variam a cada execução
    porque aqui não fixamos a semente (nos testes fixamos); a linha "problemas" mostra o resultado
    do validador independente.
    """)
    return
 
 
@app.cell
def _(formatar_grelha, mo, resolver_sudoku, validar_solucao):
    _blocos = []
    for _n in (3, 2):
        _pistas, _grupos, _grelha, _t = resolver_sudoku(_n)
        _problemas = validar_solucao(_grelha, _n, _pistas)
        _blocos.append(
            f"### n={_n} ({_n**2}×{_n**2})\n\n"
            f"Pistas:\n\n```\n{formatar_grelha(_pistas.as_matrix())}\n```\n\n"
            f"Solução (tentativas: {_t}, problemas: {len(_problemas)}):\n\n"
            f"```\n{formatar_grelha(_grelha) if _grelha else 'sem solução'}\n```\n"
        )
    mo.md("\n".join(_blocos))
    return
 
 
@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Escala: o código não está fixo a $9 \times 9$
 
    Nada no código assume $n = 3$: o tamanho vem sempre de `n`. Para o confirmar, resolve-se o mesmo
    fluxo com $n = 2, 3, 4$ e mede-se o tempo (inclui a geração das pistas, a construção do modelo e
    todas as tentativas). Os tempos são de uma única execução e servem apenas de ordem de grandeza.
    """)
    return
 
 
@app.cell
def _(mo, random, resolver_sudoku, time, validar_solucao):
    _linhas = ["n | grelha | tentativas | tempo (s) | válida", "--|--------|-----------|----------|-------"]
    for _n in (2, 3, 4):
        _t0 = time.perf_counter()
        _pistas, _, _grelha, _tent = resolver_sudoku(_n, rng=random.Random(_n))
        _dt = time.perf_counter() - _t0
        _ok = _grelha is not None and not validar_solucao(_grelha, _n, _pistas)
        _linhas.append(f"{_n} | {_n**2}×{_n**2} | {_tent} | {_dt:.3f} | {'sim' if _ok else 'não'}")
    mo.md("\n".join(_linhas))
    return
 
 
# ──────────────────────────────────────────────────────────────────────────────
# 10. CONCLUSÕES
# ──────────────────────────────────────────────────────────────────────────────
@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Conclusões
 
    - **Uma só abstração.** Linhas, colunas, blocos e pistas são todos `box`. O modelo CSP recebe uma
      lista de grupos e não distingue a sua origem, que é o objetivo de R5 e R6.
    - **Validação sem circularidade.** O validador recalcula linhas, colunas e blocos por índices e
      compara as pistas com o `box` original, sem reutilizar `path`, `cube` nem o modelo, e os testes
      mostram que ele apanha grelhas estragadas.
    - **Casos limite tratados.** Argumentos inválidos são rejeitados, puzzles impossíveis são
      sinalizados (`None` + `estado`) e a procura de pistas resolúveis tem um limite de tentativas.
    - **Pistas sem `AllDifferent`.** A decisão mais subtil do modelo: um grupo de pistas fixa valores
      mas não os obriga a ser diferentes, porque não formam uma região do Sudoku.
    - **Limitações.** As pistas aleatórias não garantem solução **única**: o resultado é uma solução
      possível, não *a* solução.
    """)
    return
 
 
# ──────────────────────────────────────────────────────────────────────────────
# 11. USO DE IA
# ──────────────────────────────────────────────────────────────────────────────
@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Uso de IA
 
    | Pergunta | Resposta |
    |---|---|
    | Que ferramentas de IA foram usadas (nome e versão/modelo)? | *Usou se o Github Copilot e ChatGPT.* |
    | Em que partes do trabalho (modelação, código, testes, texto do relatório, revisão)? | *O Github Copilot foi usado para gerar texto do relatório e alguma sugestoes para resolução de problemas. O ChatGPT ajudou na estrutura do codigo (FileTree, bibliotecas usadas, organizaçao das funçoes.* |
    | Que *prompts* ou pedidos principais foram feitos? | *Solicitações para gerar código, sugestões de otimização e melhorias. Em si, nao foram prompts específicos mas outputs de bugs ou sugestoes diretas do modelo de IA.* |
    | Como verificámos que o resultado estava correto (testes, leitura do código, execução)? | *Verificações realizadas manualmente durante o desenvolvimento.* |
    | Que partes do trabalho foram feitas sem IA? | *Em geral, o codigo e a logica por tras foi feita manualmente pelos dois elementos do grupo.* |
 
    **Declaração de responsabilidade:** *Nos, Luis Martins e Lucas Ferreira, assumimos a responsabilidade por todo o conteúdo deste notebook. Consideramos que o uso da IA foi ético e respeitou os princípios de integridade académica.*
    """)
    return
 
 
if __name__ == "__main__":
    app.run()