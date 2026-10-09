# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "ortools",
#     "pandas==3.0.6",
# ]
# ///

import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium")


# ──────────────────────────────────────────────────────────────────────────────
# 1. IMPORTS E CONFIGURAÇÃO
# ──────────────────────────────────────────────────────────────────────────────
@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import copy
    import dataclasses
    import html
    import sys
    from pathlib import Path

    import pandas as pd

    # O notebook vive em notebook/, o pacote src/ está um nível acima.
    # O caminho é calculado a partir deste ficheiro, por isso não depende
    # da pasta a partir da qual o Marimo foi iniciado.
    ROOT = Path(__file__).resolve().parent.parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from src.incremental import comparar_abordagens, resolver_do_zero, resolver_incremental
    from src.loader import DATA_DIR, carregar_dados
    from src.metrics import comparar_horarios, contar_buracos
    from src.models import DIAS, NORMAL, Indisponibilidade, gerar_sessoes
    from src.scheduler import Scheduler
    from src.validator import REGRAS, validar_horario

    return (
        DATA_DIR,
        DIAS,
        Indisponibilidade,
        NORMAL,
        REGRAS,
        Scheduler,
        carregar_dados,
        comparar_abordagens,
        comparar_horarios,
        contar_buracos,
        copy,
        dataclasses,
        gerar_sessoes,
        html,
        pd,
        resolver_do_zero,
        resolver_incremental,
        validar_horario,
    )


@app.cell
def _(mo):
    mo.md(r"""
    # Gerador de Horário Escolar

    Notebook de **interface e orquestração**: toda a lógica (modelo CP-SAT, validação,
    métricas, construção incremental) vive em `src/` e é apenas reutilizada aqui.

    | Passo | Módulo |
    |---|---|
    | Ler CSV (R8) | `src/loader.py` |
    | Sessões a marcar | `src/models.py` |
    | Modelo CP-SAT, R1–R7 e objetivo O1 | `src/scheduler.py`, `constraints.py`, `objective.py` |
    | Verificação independente do solver | `src/validator.py` |
    | Buracos e comparação de horários | `src/metrics.py` |
    | Construção incremental (R9) | `src/incremental.py` |

    **Técnica:** programação por restrições com **CP-SAT (OR-Tools)**. Cada sessão tem uma variável
    booleana `comeca[sessão, dia, período]`; R4 e R6 ficam garantidas na criação das variáveis e as
    restantes regras são restrições lineares sobre essas variáveis. O objetivo O1 minimiza os buracos
    (tempos livres entre a primeira e a última aula do dia).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Enquadramento e abordagem geral

    Este notebook é o **relatório** do trabalho: explica as decisões, mostra o resultado e prova (com
    testes) que cumpre as regras.

    ### O problema

    Marcar, numa semana de `dias × tempos`, todas as aulas de todas as turmas, respeitando recursos
    limitados (professores, salas) e preferências (poucos tempos livres). Depois, quando os recursos
    mudam, **adaptar** o horário alterando o mínimo possível.

    ### Como o modelámos (CSP com CP-SAT)

    - **Sessão.** A unidade a marcar é a *sessão*: 1 tempo, ou 1 bloco de 2 tempos nas disciplinas de
      duplo período. Cada turma tem tantas sessões de cada disciplina quantas a carga semanal exige.
    - **Variáveis.** Uma variável booleana `comeca[sessão, dia, período]` (1 se a sessão começa nesse
      tempo). Só se criam variáveis para posições possíveis, por isso **R4** (blocos duplos não saem
      do fim do dia) e **R6** (indisponibilidades dos professores) ficam garantidas *por construção*.
    - **Restrições.** As restantes regras são restrições lineares sobre essas variáveis.
    - **Objetivo (O1).** Minimizar os **buracos**: tempos livres entre a primeira e a última aula do
      dia, de professores e de turmas, numa soma ponderada (os pesos escolhem-se nos parâmetros).

    ### As regras

    | Regra | O que exige |
    |---|---|
    | R1 | Uma turma não tem duas aulas no mesmo tempo |
    | R2 | A carga semanal de cada disciplina é cumprida |
    | R3 | A mesma disciplina não se repete no mesmo dia, para a mesma turma |
    | R4 | Os blocos de duplo período cabem no dia (não saem do fim) |
    | R5 | Um professor não dá duas aulas no mesmo tempo |
    | R6 | Nenhuma aula cai num tempo em que o professor está indisponível |
    | R7 | Cada aula tem uma sala do tipo certo, dentro das salas existentes |
    | R8 | Todos os dados vêm de ficheiros CSV, nada fica no código |
    | R9 | Construção incremental: H1 a partir de H0 com poucas alterações |

    ### Porque esta técnica

    As regras são combinatórias e muitas são "no máximo um" ou "exatamente k", que o CP-SAT trata bem.
    Em vez de escrevermos uma heurística de pesquisa, descrevemos o problema e deixamos o solver
    procurar, e ainda ganhamos a possibilidade de **otimizar** (O1) e de **provar** que não há solução.

    ### Estrutura do relatório

    1. Parâmetros e dados → 2. Gerar H0 → 3. Validar (R1–R7) → 4. Métricas → 5. Incremental (H0 → H1, R9)
    → 6. Benchmark → 7. Conclusões e uso de IA.
    """)
    return


# ──────────────────────────────────────────────────────────────────────────────
# 2. FUNÇÕES AUXILIARES DO NOTEBOOK (apenas apresentação / cenários)
# ──────────────────────────────────────────────────────────────────────────────
@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Funções auxiliares do notebook

    As funções desta secção servem **apenas a apresentação e a criação de cenários**; nenhuma resolve nem
    valida horários.

    - `grelha_html` desenha a grelha semanal (tempos × dias) de uma turma ou de um professor. Uma célula
      a vermelho significa duas aulas no mesmo tempo, o que nunca deveria aparecer num horário válido.
    - `diferencas` compara H0 e H1 e identifica cada aula alterada (mudou de tempo, de sala, nova ou removida).
      As sessões da mesma disciplina são intermutáveis, por isso a comparação é por **tempo ocupado** e não
      por "número da sessão".
    - `aplicar_cenario` aplica uma alteração de recursos (outro CSV, indisponibilidade, sala avariada,
      turma nova, professor substituído) criando uma **cópia** dos dados; H0 e os dados originais não
      são tocados.
    - `corromper` estraga de propósito um horário para violar uma regra concreta. Serve para
      **testar o validador** (ver a secção de validação).
    """)
    return


@app.cell
def _(
    DIAS,
    Indisponibilidade,
    NORMAL,
    copy,
    dataclasses,
    carregar_dados,
    DATA_DIR,
    html,
    mo,
    pd,
):
    PALETA = ["#cfe8ff", "#ffd9c2", "#d6f5d6", "#f5d6f0", "#fff3b0", "#d9d2f7", "#c9f2ee", "#ffd1d9"]

    def listar_pastas_dados():
        """Pastas em data/ que têm um conjunto de CSV válido."""
        return sorted(p.name for p in DATA_DIR.iterdir() if p.is_dir() and (p / "turmas.csv").exists())

    def aulas_para_df(horario):
        """Horário (lista de dicts) -> DataFrame legível."""
        return pd.DataFrame(
            [
                {
                    "turma": a["turma"],
                    "disciplina": a["disciplina"],
                    "professor": a["professor"],
                    "dia": DIAS[a["dia"]],
                    "período": a["periodo"] + 1,
                    "duração": a["duracao"],
                    "sala": a["sala"],
                }
                for a in sorted(horario, key=lambda a: (a["turma"], a["dia"], a["periodo"]))
            ]
        )

    def grelha_html(horario, dados, chave, valor, destacar=frozenset()):
        """Grelha semanal (tempos × dias) de uma turma ou de um professor (chave='turma'|'professor')."""
        cor = {d.nome: PALETA[i % len(PALETA)] for i, d in enumerate(dados.disciplinas)}
        celulas = {}
        for aula in horario:
            if aula[chave] == valor:
                for tempo in range(aula["periodo"], aula["periodo"] + aula["duracao"]):
                    celulas.setdefault((aula["dia"], tempo), []).append(aula)
        base = "border:1px solid rgba(128,128,128,.45);padding:6px 8px;text-align:center;vertical-align:middle;min-width:115px;"
        linhas = ["<tr><th></th>" + "".join(f'<th style="{base}">{DIAS[d]}</th>' for d in range(dados.num_dias)) + "</tr>"]
        for tempo in range(dados.num_periodos):
            tds = [f'<th style="{base}">{tempo + 1}º</th>']
            for dia in range(dados.num_dias):
                aulas = celulas.get((dia, tempo), [])
                if not aulas:
                    tds.append(f'<td style="{base}opacity:.45">–</td>')
                    continue
                aula = aulas[0]
                extra = aula["turma"] if chave == "professor" else aula["professor"]
                fundo = "#ff9aa2" if len(aulas) > 1 else cor.get(aula["disciplina"], "#eee")
                chave_aula = (aula["turma"], aula["disciplina"], aula["dia"], aula["periodo"])
                realce = "outline:3px solid #d9480f;outline-offset:-3px;" if chave_aula in destacar else ""
                tds.append(
                    f'<td style="{base}background:{fundo};color:#1a1a1a;{realce}">'
                    f'<b>{html.escape(aula["disciplina"])}</b><br>'
                    f'<small>{html.escape(extra)} · {html.escape(str(aula["sala"]))}</small></td>'
                )
            linhas.append("<tr>" + "".join(tds) + "</tr>")
        return mo.Html(
            '<div style="overflow-x:auto"><table style="border-collapse:collapse;font-size:.85rem">'
            + "".join(linhas)
            + "</table></div>"
        )

    def grelhas_em_tabs(horario, dados, destacar=frozenset()):
        professores = sorted({d.professor for d in dados.disciplinas})
        return mo.ui.tabs(
            {
                "Turmas": mo.ui.tabs({t: grelha_html(horario, dados, "turma", t, destacar) for t in dados.turmas}),
                "Professores": mo.ui.tabs(
                    {p: grelha_html(horario, dados, "professor", p, destacar) for p in professores}
                ),
            }
        )

    def diferencas(h0, h1):
        """Tabela das aulas que mudaram entre H0 e H1 + conjunto das aulas de H1 a destacar."""

        def indexar(horario):
            indice = {}
            for aula in horario:
                indice.setdefault((aula["turma"], aula["disciplina"]), {})[(aula["dia"], aula["periodo"])] = aula
            return indice

        def fmt(aula):
            return f'{DIAS[aula["dia"]]} {aula["periodo"] + 1}º ({aula["sala"]})'

        i0, i1 = indexar(h0), indexar(h1)
        linhas, destaque = [], set()
        for (turma, disciplina) in sorted(set(i0) | set(i1)):
            a0, a1 = i0.get((turma, disciplina), {}), i1.get((turma, disciplina), {})
            comuns = set(a0) & set(a1)
            for slot in sorted(comuns):
                if a0[slot]["sala"] != a1[slot]["sala"]:
                    linhas.append({"turma": turma, "disciplina": disciplina, "alteração": "mudou de sala",
                                   "antes": fmt(a0[slot]), "depois": fmt(a1[slot])})
                    destaque.add((turma, disciplina, *slot))
            so0 = [a0[s] for s in sorted(set(a0) - comuns)]
            so1 = [a1[s] for s in sorted(set(a1) - comuns)]
            for k in range(max(len(so0), len(so1))):
                antes = so0[k] if k < len(so0) else None
                depois = so1[k] if k < len(so1) else None
                tipo = "mudou de tempo" if antes and depois else ("aula nova" if depois else "aula removida")
                linhas.append({"turma": turma, "disciplina": disciplina, "alteração": tipo,
                               "antes": fmt(antes) if antes else "—", "depois": fmt(depois) if depois else "—"})
                if depois:
                    destaque.add((turma, disciplina, depois["dia"], depois["periodo"]))
        return pd.DataFrame(linhas, columns=["turma", "disciplina", "alteração", "antes", "depois"]), frozenset(destaque)

    def corromper(horario, dados, regra):
        """Devolve (horário_estragado, descrição) que viola de propósito `regra`, ou (None, motivo)."""
        h = copy.deepcopy(horario)
        if regra == "R1":
            a, b = [x for x in h if x["turma"] == dados.turmas[0]][:2]
            b["dia"], b["periodo"] = a["dia"], a["periodo"]
            return h, f"duas aulas de {a['turma']} no mesmo tempo"
        if regra == "R2":
            h.pop(0)
            return h, "removida uma aula (carga semanal incompleta)"
        if regra == "R3":
            a = dict(h[0])
            novo = a["periodo"] + a["duracao"]
            a["periodo"] = novo if novo + a["duracao"] <= dados.num_periodos else max(0, a["periodo"] - a["duracao"])
            h.append(a)
            return h, "mesma disciplina duas vezes no mesmo dia"
        if regra == "R4":
            a = next((x for x in h if x["duracao"] == 2), h[0])
            if a["duracao"] == 2:
                a["periodo"] = dados.num_periodos - 1
                return h, "bloco duplo a sair do fim do dia"
            a["duracao"] = 2
            return h, "disciplina simples dada como bloco duplo"
        if regra == "R5":
            for i, a in enumerate(h):
                b = next((x for x in h[i + 1:] if x["professor"] == a["professor"]), None)
                if b:
                    b["dia"], b["periodo"] = a["dia"], a["periodo"]
                    return h, f"{a['professor']} com duas aulas no mesmo tempo"
            return None, "só existe uma aula por professor"
        if regra == "R6":
            if not dados.indisponibilidades:
                return None, "os dados não têm indisponibilidades"
            ind = dados.indisponibilidades[0]
            a = next((x for x in h if x["professor"] == ind.professor), None)
            if a is None:
                return None, "o professor indisponível não dá aulas"
            a["dia"], a["periodo"] = ind.dia, ind.periodo
            return h, f"aula de {ind.professor} num tempo em que está indisponível"
        if regra == "R7":
            a = h[0]
            todas = {n for tipo in dados.capacidades() for n in dados.nomes_salas(tipo)}
            erradas = sorted(todas - set(dados.nomes_salas(a["tipo_sala"])))
            a["sala"] = erradas[0] if erradas else "Sala inexistente"
            return h, "aula atribuída a uma sala do tipo errado"
        return None, "regra desconhecida"

    def aplicar_cenario(dados, cenario, p):
        """Aplica uma alteração de recursos a `dados` e devolve (novos_dados, descrição)."""
        if cenario == "Outro conjunto de CSV":
            return carregar_dados(DATA_DIR / p["pasta"]), f"dados lidos de `data/{p['pasta']}/`"
        if cenario == "Disponibilidade de um professor":
            dia = list(DIAS).index(p["dia"])
            tempos = {Indisponibilidade(p["professor"], dia, per - 1) for per in range(p["per_ini"], p["per_fim"] + 1)}
            atuais = set(dados.indisponibilidades)
            if p["modo"] == "Fica indisponível":
                novas = sorted(atuais | tempos, key=lambda i: (i.professor, i.dia, i.periodo))
                texto = f"{p['professor']} fica indisponível: {p['dia']}, períodos {p['per_ini']}–{p['per_fim']}"
            else:
                novas = sorted(atuais - tempos, key=lambda i: (i.professor, i.dia, i.periodo))
                texto = f"{p['professor']} fica disponível: {p['dia']}, períodos {p['per_ini']}–{p['per_fim']}"
            return dataclasses.replace(dados, indisponibilidades=novas), texto
        if cenario == "Sala avariada":
            salas = [dataclasses.replace(s, quantidade=int(p["quantidade"])) if s.nome == p["sala"] else s
                     for s in dados.salas]
            return dataclasses.replace(dados, salas=salas), f"`{p['sala']}` passa a ter {int(p['quantidade'])} sala(s)"
        if cenario == "Turma nova":
            if p["turma"] in dados.turmas:
                raise ValueError(f"A turma {p['turma']!r} já existe")
            return dataclasses.replace(dados, turmas=[*dados.turmas, p["turma"]]), f"nova turma {p['turma']}"
        if cenario == "Professor substituído":
            disciplinas = [dataclasses.replace(d, professor=p["professor_novo"]) if d.professor == p["professor_antigo"] else d
                           for d in dados.disciplinas]
            return dataclasses.replace(dados, disciplinas=disciplinas), f"{p['professor_antigo']} → {p['professor_novo']}"
        raise ValueError(f"Cenário desconhecido: {cenario}")

    return (
        aplicar_cenario,
        aulas_para_df,
        corromper,
        diferencas,
        grelhas_em_tabs,
        listar_pastas_dados,
    )


# ──────────────────────────────────────────────────────────────────────────────
# 3. PARÂMETROS
# ──────────────────────────────────────────────────────────────────────────────
@app.cell
def _(listar_pastas_dados, mo):
    _pastas = listar_pastas_dados()
    pasta = mo.ui.dropdown(_pastas, value="dados" if "dados" in _pastas else _pastas[0], label="Conjunto de dados")
    tempo_limite = mo.ui.slider(5, 120, value=30, step=5, label="Tempo limite do solver (s)")
    workers = mo.ui.slider(1, 16, value=8, step=1, label="Workers")
    peso_prof = mo.ui.slider(0, 20, value=10, step=1, label="Peso buracos de professores")
    peso_turma = mo.ui.slider(0, 20, value=1, step=1, label="Peso buracos de turmas")
    mo.vstack(
        [
            mo.md("## Parâmetros"),
            pasta,
            mo.hstack([tempo_limite, workers], justify="start", gap=2),
            mo.hstack([peso_prof, peso_turma], justify="start", gap=2),
        ]
    )
    return pasta, peso_prof, peso_turma, tempo_limite, workers


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Notas sobre os parâmetros

    Os parâmetros controlam o solver e o objetivo, e podem mudar-se sem tocar no código:

    - **Conjunto de dados:** pasta de `data/` com os CSV (R8).
    - **Tempo limite:** o solver devolve a melhor solução encontrada até esse momento. Se parar por tempo,
      o estado é `FEASIBLE` (solução válida, não provada ótima); com `OPTIMAL` há prova de otimalidade.
    - **Workers:** número de *threads* de pesquisa em paralelo do CP-SAT.
    - **Pesos dos buracos:** o objetivo é `peso_prof × buracos de professores + peso_turma × buracos de turmas`.
      Por omissão os buracos dos professores pesam 10× mais, por isso o solver prefere tirar tempos livres
      aos professores antes de os tirar às turmas. Pôr um peso a 0 desliga essa parcela.
    """)
    return


# ──────────────────────────────────────────────────────────────────────────────
# 4. DADOS
# ──────────────────────────────────────────────────────────────────────────────
@app.cell
def _(DATA_DIR, DIAS, carregar_dados, mo, pasta, pd):
    try:
        dados0 = carregar_dados(DATA_DIR / pasta.value)
        _erro = None
    except Exception as e:  # ficheiro em falta, valor inválido, etc.
        dados0, _erro = None, e
    mo.stop(_erro is not None, mo.callout(mo.md(f"**Erro ao carregar `{pasta.value}`:** {_erro}"), kind="danger"))
    assert dados0 is not None

    _t_disciplinas = pd.DataFrame(
        [{"disciplina": d.nome, "professor": d.professor, "carga": d.carga_semanal,
          "duplo": "sim" if d.duplo_periodo else "não", "sala especial": d.sala_especial or "—"}
         for d in dados0.disciplinas]
    )
    _t_salas = pd.DataFrame([{"sala": s.nome, "tipo": s.tipo, "quantidade": s.quantidade} for s in dados0.salas])
    _t_indisp = pd.DataFrame(
        [{"professor": i.professor, "dia": DIAS[i.dia], "período": i.periodo + 1} for i in dados0.indisponibilidades],
        columns=["professor", "dia", "período"],
    )
    mo.vstack(
        [
            mo.md(f"## Dados de entrada — `data/{pasta.value}/`"),
            mo.hstack(
                [
                    mo.stat(len(dados0.turmas), label="Turmas"),
                    mo.stat(len(dados0.disciplinas), label="Disciplinas"),
                    mo.stat(len({d.professor for d in dados0.disciplinas}), label="Professores"),
                    mo.stat(f"{dados0.num_dias} × {dados0.num_periodos}", label="Dias × tempos"),
                ],
                justify="start",
                gap=2,
            ),
            mo.ui.tabs(
                {
                    "Turmas": mo.ui.table(pd.DataFrame({"turma": dados0.turmas}), selection=None),
                    "Disciplinas": mo.ui.table(_t_disciplinas, selection=None),
                    "Salas": mo.ui.table(_t_salas, selection=None),
                    "Indisponibilidades": mo.ui.table(_t_indisp, selection=None),
                }
            ),
        ]
    )
    return (dados0,)


@app.cell
def _(dados0, gerar_sessoes, mo, pd):
    sessoes = gerar_sessoes(dados0)
    _resumo = (
        pd.DataFrame([{"turma": s.turma, "disciplina": s.disciplina, "duração": s.duracao, "tipo de sala": s.tipo_sala}
                      for s in sessoes])
        .groupby(["disciplina", "duração", "tipo de sala"])
        .size()
        .reset_index(name="sessões (todas as turmas)")
    )
    mo.vstack(
        [
            mo.md(f"### Sessões a marcar: **{len(sessoes)}**\n\n"
                  "Cada sessão é 1 tempo ou 1 bloco de 2 tempos (disciplinas de duplo período)."),
            mo.ui.table(_resumo, selection=None),
        ]
    )
    return (sessoes,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Notas sobre os dados e as sessões

    Tudo o que o problema precisa (turmas, disciplinas, professores, salas, indisponibilidades, número de
    dias e de tempos) é lido de CSV por `carregar_dados` (**R8**). O código nunca contém dados do problema,
    e por isso trocar de conjunto, ou acrescentar uma turma, não exige alterar código.

    A tabela de **sessões** mostra o tamanho do problema que o solver vai resolver: para cada turma e
    disciplina, a carga semanal decompõe-se em sessões de 1 tempo ou de 2 (blocos duplos).
    """)
    return


# ──────────────────────────────────────────────────────────────────────────────
# 5. GERAR H0
# ──────────────────────────────────────────────────────────────────────────────
@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Como H0 é gerado

    H0 é o horário gerado **de raiz**, em quatro passos (todos em `Scheduler`):

    1. `criar_variaveis` cria as variáveis `comeca[sessão, dia, período]` (R4 e R6 ficam garantidas aqui);
    2. `aplicar_restricoes` acrescenta R1, R2, R3, R5 e R7;
    3. `aplicar_objetivo` define O1 com os pesos escolhidos;
    4. `resolver` corre o CP-SAT com o tempo limite e os workers escolhidos.

    Se não houver solução, o notebook **pára** com uma mensagem (`mo.stop`) e mostra o estado do solver,
    em vez de tentar desenhar um horário que não existe. Depois mostra-se o horário em grelhas por turma
    e por professor, e a lista completa de aulas.
    """)
    return


@app.cell
def _(Scheduler, dados0, mo, peso_prof, peso_turma, sessoes, tempo_limite, workers):
    agendador0 = Scheduler(dados0, sessoes)
    agendador0.criar_variaveis()
    agendador0.aplicar_restricoes()
    agendador0.aplicar_objetivo(peso_prof=peso_prof.value, peso_turma=peso_turma.value)
    agendador0.resolver(tempo_limite=tempo_limite.value, workers=workers.value)

    estado0 = agendador0.solver.status_name(agendador0.status)
    mo.stop(
        not agendador0.solucao_encontrada(),
        mo.callout(mo.md(f"**Sem solução** (estado: `{estado0}`). Verifica os dados ou aumenta o tempo limite."), kind="danger"),
    )
    h0 = agendador0.extrair_solucao()
    mo.vstack(
        [
            mo.md("## Horário H0 (gerado de raiz)"),
            mo.hstack(
                [
                    mo.stat(estado0, label="Estado do solver"),
                    mo.stat(f"{agendador0.tempo:.2f} s", label="Tempo"),
                    mo.stat(len(h0), label="Aulas marcadas"),
                ],
                justify="start",
                gap=2,
            ),
        ]
    )
    return agendador0, estado0, h0


@app.cell
def _(aulas_para_df, dados0, grelhas_em_tabs, h0, mo):
    mo.vstack(
        [
            mo.md("### Visualização de H0"),
            grelhas_em_tabs(h0, dados0),
            mo.accordion({"Lista completa de aulas": mo.ui.table(aulas_para_df(h0), selection=None)}),
        ]
    )
    return


# ──────────────────────────────────────────────────────────────────────────────
# 6. VALIDAÇÃO (R1–R7) E TESTES DAS REGRAS
# ──────────────────────────────────────────────────────────────────────────────
@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Como funciona a validação (R1–R7)

    `validar_horario` verifica o horário **sem usar o solver**: percorre as aulas e confirma cada regra
    diretamente. Isto importa porque, se validássemos com o mesmo modelo que gerou o horário, um erro
    no modelo passaria despercebido (a verificação seria circular).

    Cada regra é uma função em `REGRAS`; a tabela mostra quantas violações cada uma encontrou em H0.

    **Teste do próprio validador.** Um validador que nunca encontra erros não prova nada. Por isso,
    para cada regra, estraga-se H0 de propósito (`corromper`) e confirma-se que o validador apanha
    essa violação. Quando o cenário não permite injetar o erro (por exemplo, não há indisponibilidades
    nos dados), a regra aparece como `n/a` em vez de passar em falso.
    """)
    return


@app.cell
def _(REGRAS, dados0, h0, mo, pd, validar_horario):
    violacoes0 = validar_horario(dados0, h0)
    _descricoes = {f.__name__.split("_")[1].upper(): (f.__doc__ or "").strip().splitlines()[0] for f in REGRAS}
    _contagem = {r: 0 for r in _descricoes}
    for _v in violacoes0:
        _contagem[_v.regra] = _contagem.get(_v.regra, 0) + 1
    _tabela = pd.DataFrame(
        [{"regra": r, "descrição": _descricoes.get(r, ""), "violações": n, "estado": "✅" if n == 0 else "❌"}
         for r, n in _contagem.items()]
    )
    mo.vstack(
        [
            mo.md("## Validação de H0 (R1–R7, sem usar o solver)"),
            mo.callout(
                mo.md("**H0 cumpre todas as regras.**" if not violacoes0 else f"**{len(violacoes0)} violações encontradas.**"),
                kind="success" if not violacoes0 else "danger",
            ),
            mo.ui.table(_tabela, selection=None),
            mo.accordion({"Detalhe das violações": mo.ui.table(
                pd.DataFrame([{"regra": v.regra, "mensagem": v.mensagem} for v in violacoes0],
                             columns=["regra", "mensagem"]), selection=None)}),
            mo.md("*R8 (dados só em CSV) cumpre-se por construção: tudo vem de `carregar_dados`.*"),
        ]
    )
    return (violacoes0,)


@app.cell
def _(corromper, dados0, h0, mo, pd, validar_horario):
    _linhas = []
    for _regra in ("R1", "R2", "R3", "R4", "R5", "R6", "R7"):
        _estragado, _desc = corromper(h0, dados0, _regra)
        if _estragado is None:
            _linhas.append({"regra": _regra, "violação injetada": _desc, "detetadas": None, "resultado": "n/a"})
            continue
        _n = sum(v.regra == _regra for v in validar_horario(dados0, _estragado))
        _linhas.append({"regra": _regra, "violação injetada": _desc, "detetadas": _n,
                        "resultado": "✅ apanhada" if _n else "❌ NÃO apanhada"})
    mo.vstack(
        [
            mo.md("### Teste do validador\n\n"
                  "Para cada regra, estraga-se H0 de propósito e confirma-se que o validador a apanha."),
            mo.ui.table(pd.DataFrame(_linhas), selection=None),
        ]
    )
    return


# ──────────────────────────────────────────────────────────────────────────────
# 7. MÉTRICAS
# ──────────────────────────────────────────────────────────────────────────────
@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Como se medem os buracos

    Mede-se a qualidade de H0 com os **buracos** (O1): para cada professor e para cada turma, o número de
    tempos livres entre a primeira e a última aula do mesmo dia. Estas contagens são calculadas por
    `contar_buracos` sobre o horário final e **não** lidas do solver, e por isso são comparáveis entre
    H0 e as várias versões de H1.

    O "valor do objetivo" é o que o solver reporta; o **limite inferior** indica o melhor valor que
    ainda poderia existir. Quando coincidem, H0 é ótimo. Quando há uma diferença, o solver parou por
    tempo e H0 pode ser melhorado.
    """)
    return


@app.cell
def _(agendador0, contar_buracos, dados0, h0, mo, pd):
    _professores = sorted({d.professor for d in dados0.disciplinas})
    _t_prof = pd.DataFrame(
        [{"professor": p,
          "tempos de aula": sum(a["duracao"] for a in h0 if a["professor"] == p),
          "buracos": contar_buracos([a for a in h0 if a["professor"] == p], "professor")}
         for p in _professores]
    )
    _t_turma = pd.DataFrame(
        [{"turma": t,
          "tempos de aula": sum(a["duracao"] for a in h0 if a["turma"] == t),
          "buracos": contar_buracos([a for a in h0 if a["turma"] == t], "turma")}
         for t in dados0.turmas]
    )
    try:
        _obj = f"{agendador0.solver.objective_value:.0f} (limite inferior: {agendador0.solver.best_objective_bound:.0f})"
    except Exception:
        _obj = "—"
    mo.vstack(
        [
            mo.md("## Métricas de H0"),
            mo.hstack(
                [
                    mo.stat(contar_buracos(h0, "professor"), label="Buracos de professores (O1)"),
                    mo.stat(contar_buracos(h0, "turma"), label="Buracos de turmas"),
                    mo.stat(_obj, label="Valor do objetivo"),
                ],
                justify="start",
                gap=2,
            ),
            mo.hstack([mo.ui.table(_t_prof, selection=None), mo.ui.table(_t_turma, selection=None)], justify="start", gap=2),
        ]
    )
    return


# ──────────────────────────────────────────────────────────────────────────────
# 8. CONSTRUÇÃO INCREMENTAL (R9)
# ──────────────────────────────────────────────────────────────────────────────
@app.cell
def _(mo):
    mo.md(r"""
    ## Construção incremental (R9): de H0 para H1

    Escolhe uma alteração de recursos. O cenário `Outro conjunto de CSV` com `dados_v2` é o do enunciado
    (Prof. Ana indisponível às sextas nos 2 últimos tempos); os restantes cobrem as outras alterações pedidas.

    **Abordagem (`src/incremental.py`):**

    1. **Hint** — H0 é dado ao solver como ponto de partida.
    2. **Minimizar mudanças** — o objetivo é o nº de aulas de H0 que deixam de estar no mesmo tempo (as sessões
       da mesma disciplina são intermutáveis, por isso a mudança mede-se por tempo ocupado).
    3. **Fixação progressiva** — fixam-se as aulas não afetadas e resolve-se só o subproblema afetado; se for
       impossível, a vizinhança alarga-se (nível 0 → 1 → 2, sendo 2 = nada fixo).
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Porque um horário incremental

    Num horário em uso, uma alteração de recursos (um professor fica indisponível, uma sala avaria)
    obriga a refazê-lo. Um horário gerado de raiz pode ser **muito diferente** de H0, e isso tem custo
    real (alunos e professores teriam de reorganizar a semana). O objetivo de R9 é, por isso, trocar
    "qualidade ótima" por **estabilidade**: manter o máximo de aulas onde estavam.

    Neste relatório compara-se, para o mesmo cenário, quatro formas de obter H1: do zero e três
    variantes incrementais (`hint`, `fixar`, `fixar + O1`), medindo o tempo e o número de aulas alteradas.
    """)
    return


@app.cell
def _(DIAS, dados0, listar_pastas_dados, mo):
    _pastas = listar_pastas_dados()
    _professores = sorted({d.professor for d in dados0.disciplinas})
    _np = dados0.num_periodos

    cenario = mo.ui.dropdown(
        ["Outro conjunto de CSV", "Disponibilidade de um professor", "Sala avariada", "Turma nova", "Professor substituído"],
        value="Outro conjunto de CSV",
        label="Cenário",
    )
    # parâmetros de cada cenário
    ctl_pasta = mo.ui.dropdown(_pastas, value="dados_v2" if "dados_v2" in _pastas else _pastas[-1], label="Pasta")
    ctl_prof = mo.ui.dropdown(_professores, value=_professores[0], label="Professor")
    ctl_modo = mo.ui.radio(["Fica indisponível", "Fica disponível"], value="Fica indisponível", label="Alteração")
    ctl_dia = mo.ui.dropdown(list(DIAS[: dados0.num_dias]), value=DIAS[dados0.num_dias - 1], label="Dia")
    ctl_periodos = mo.ui.range_slider(1, _np, value=[max(1, _np - 1), _np], step=1, label="Períodos")
    ctl_sala = mo.ui.dropdown([s.nome for s in dados0.salas], value=dados0.salas[0].nome, label="Sala")
    ctl_qtd = mo.ui.number(0, 100, value=1, label="Nova quantidade")
    ctl_turma = mo.ui.text(value="Nova turma", label="Nome da turma")
    ctl_prof_antigo = mo.ui.dropdown(_professores, value=_professores[0], label="Professor a substituir")
    ctl_prof_novo = mo.ui.text(value="Prof. Substituto", label="Novo professor")
    botao_incremental = mo.ui.run_button(label="Gerar H1")
    return (
        botao_incremental,
        cenario,
        ctl_dia,
        ctl_modo,
        ctl_pasta,
        ctl_periodos,
        ctl_prof,
        ctl_prof_antigo,
        ctl_prof_novo,
        ctl_qtd,
        ctl_sala,
        ctl_turma,
    )


@app.cell
def _(
    botao_incremental,
    cenario,
    ctl_dia,
    ctl_modo,
    ctl_pasta,
    ctl_periodos,
    ctl_prof,
    ctl_prof_antigo,
    ctl_prof_novo,
    ctl_qtd,
    ctl_sala,
    ctl_turma,
    mo,
):
    _por_cenario = {
        "Outro conjunto de CSV": [ctl_pasta],
        "Disponibilidade de um professor": [ctl_prof, ctl_modo, ctl_dia, ctl_periodos],
        "Sala avariada": [ctl_sala, ctl_qtd],
        "Turma nova": [ctl_turma],
        "Professor substituído": [ctl_prof_antigo, ctl_prof_novo],
    }
    mo.vstack([cenario, *_por_cenario[cenario.value], botao_incremental])
    return


@app.cell
def _(
    aplicar_cenario,
    botao_incremental,
    cenario,
    ctl_dia,
    ctl_modo,
    ctl_pasta,
    ctl_periodos,
    ctl_prof,
    ctl_prof_antigo,
    ctl_prof_novo,
    ctl_qtd,
    ctl_sala,
    ctl_turma,
    dados0,
    h0,
    mo,
    resolver_do_zero,
    resolver_incremental,
    tempo_limite,
    validar_horario,
    workers,
):
    mo.stop(not botao_incremental.value, mo.md("*Escolhe o cenário e carrega em **Gerar H1**.*"))

    _params = {
        "pasta": ctl_pasta.value,
        "professor": ctl_prof.value,
        "modo": ctl_modo.value,
        "dia": ctl_dia.value,
        "per_ini": ctl_periodos.value[0],
        "per_fim": ctl_periodos.value[1],
        "sala": ctl_sala.value,
        "quantidade": ctl_qtd.value,
        "turma": ctl_turma.value,
        "professor_antigo": ctl_prof_antigo.value,
        "professor_novo": ctl_prof_novo.value,
    }
    try:
        dados1, descricao_cenario = aplicar_cenario(dados0, cenario.value, _params)
    except Exception as e:
        mo.stop(True, mo.callout(mo.md(f"**Cenário inválido:** {e}"), kind="danger"))
        raise

    _tl, _w = tempo_limite.value, workers.value
    _variantes = {
        "H1 do zero (sem H0)": lambda: resolver_do_zero(dados1, _tl, _w),
        "incremental: hint": lambda: resolver_incremental(dados1, h0, modo="hint", tempo_limite=_tl, workers=_w),
        "incremental: fixar": lambda: resolver_incremental(dados1, h0, modo="fixar", tempo_limite=_tl, workers=_w),
        "incremental: fixar + O1": lambda: resolver_incremental(
            dados1, h0, modo="fixar", otimizar_buracos=True, tempo_limite=_tl, workers=_w
        ),
    }
    resultados1 = {}
    for _nome, _correr in _variantes.items():
        _r = _correr()
        _r["violacoes"] = len(validar_horario(dados1, _r["horario"])) if _r["horario"] else None
        resultados1[_nome] = _r
    return dados1, descricao_cenario, resultados1


@app.cell
def _(descricao_cenario, mo, pd, resultados1):
    _base = resultados1["H1 do zero (sem H0)"]["tempo"]
    _linhas = []
    for _nome, _r in resultados1.items():
        _linhas.append(
            {
                "abordagem": _nome,
                "estado": _r["estado"],
                "tempo (s)": round(_r["tempo"], 3),
                "speed-up vs do zero": round(_base / _r["tempo"], 2) if _r["tempo"] else None,
                "aulas alteradas": _r.get("alteradas"),
                "mudaram de tempo": _r.get("moveram_tempo"),
                "mudaram de sala": _r.get("moveram_sala"),
                "novas": _r.get("novas"),
                "buracos prof.": _r.get("buracos_prof"),
                "buracos turma": _r.get("buracos_turma"),
                "nível": _r.get("nivel"),
                "violações": _r.get("violacoes"),
            }
        )
    mo.vstack(
        [
            mo.md(f"### Resultado: {descricao_cenario}"),
            mo.ui.table(pd.DataFrame(_linhas), selection=None),
            mo.md("*Uma só execução por abordagem: com instâncias pequenas o tempo é ruidoso. "
                  "A secção seguinte repete as medições e usa a mediana.*"),
        ]
    )
    return


@app.cell
def _(mo, resultados1):
    _com_solucao = [n for n, r in resultados1.items() if r["horario"]]
    mo.stop(not _com_solucao, mo.callout(mo.md("**Nenhuma abordagem encontrou solução para H1.**"), kind="danger"))
    abordagem_vista = mo.ui.dropdown(
        _com_solucao,
        value="incremental: fixar" if "incremental: fixar" in _com_solucao else _com_solucao[0],
        label="Abordagem a visualizar",
    )
    abordagem_vista
    return (abordagem_vista,)


@app.cell
def _(
    abordagem_vista,
    comparar_horarios,
    dados1,
    diferencas,
    grelhas_em_tabs,
    h0,
    mo,
    pd,
    resultados1,
    validar_horario,
):
    _h1 = resultados1[abordagem_vista.value]["horario"]
    _tabela_dif, _destaque = diferencas(h0, _h1)
    _resumo = comparar_horarios(h0, _h1)
    _viol = validar_horario(dados1, _h1)
    mo.vstack(
        [
            mo.md(f"## Horário H1 — {abordagem_vista.value}"),
            mo.callout(
                mo.md("**H1 cumpre R1–R7 com os novos dados.**" if not _viol else f"**{len(_viol)} violações em H1.**"),
                kind="success" if not _viol else "danger",
            ),
            mo.hstack(
                [
                    mo.stat(_resumo["alteradas"], label="Aulas alteradas"),
                    mo.stat(_resumo["moveram_tempo"], label="Mudaram de tempo"),
                    mo.stat(_resumo["moveram_sala"], label="Mudaram de sala"),
                    mo.stat(_resumo["novas"], label="Aulas novas"),
                ],
                justify="start",
                gap=2,
            ),
            mo.md("Aulas alteradas em relação a H0 estão com contorno laranja."),
            grelhas_em_tabs(_h1, dados1, _destaque),
            mo.accordion({"Lista de alterações H0 → H1": mo.ui.table(_tabela_dif, selection=None)}),
            mo.accordion({"Violações (se existirem)": mo.ui.table(
                pd.DataFrame([{"regra": v.regra, "mensagem": v.mensagem} for v in _viol],
                             columns=["regra", "mensagem"]), selection=None)}),
        ]
    )
    return


# ──────────────────────────────────────────────────────────────────────────────
# 9. BENCHMARK (mediana de várias repetições)
# ──────────────────────────────────────────────────────────────────────────────
@app.cell
def _(mo):
    repeticoes = mo.ui.slider(1, 15, value=5, step=1, label="Repetições")
    botao_benchmark = mo.ui.run_button(label="Correr benchmark")
    mo.vstack(
        [
            mo.md("## Evidência: tempo e nº de aulas alteradas (mediana)\n\n"
                  "Compara H1 do zero com as três variantes incrementais, para o cenário escolhido acima."),
            mo.hstack([repeticoes, botao_benchmark], justify="start", gap=2),
        ]
    )
    return botao_benchmark, repeticoes


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Notas sobre o benchmark: porquê repetir e usar a mediana

    Estas instâncias são pequenas e os tempos do solver têm muito ruído (arranque, *threads*, variação
    da pesquisa). Uma só execução pode enganar, por isso o benchmark repete cada abordagem várias vezes
    e reporta a **mediana**, que é pouco sensível a execuções atípicas. Convém olhar para as duas
    métricas em conjunto: **tempo** e **aulas alteradas**. Uma abordagem mais rápida que altere muitas
    aulas não cumpre o espírito de R9.
    """)
    return


@app.cell
def _(botao_benchmark, comparar_abordagens, dados0, dados1, mo, pd, repeticoes):
    mo.stop(not botao_benchmark.value, mo.md("*Carrega em **Correr benchmark**.*"))
    with mo.status.spinner(title="A medir…"):
        _h0_bench, _linhas_bench = comparar_abordagens(dados0, dados1, repeticoes=repeticoes.value, verbose=False)
    _df = pd.DataFrame(_linhas_bench).rename(
        columns={"abordagem": "abordagem", "tempo_mediana_s": "tempo mediano (s)", "alteradas": "aulas alteradas",
                 "moveram_tempo": "mudaram de tempo", "moveram_sala": "mudaram de sala",
                 "buracos_prof": "buracos prof.", "buracos_turma": "buracos turma"}
    )
    _df["tempo mediano (s)"] = _df["tempo mediano (s)"].round(3)
    mo.ui.table(_df, selection=None)
    return


# ──────────────────────────────────────────────────────────────────────────────
# 10. CONCLUSÕES
# ──────────────────────────────────────────────────────────────────────────────
@app.cell
def _(mo):
    mo.md(r"""
    ## Notas finais
    - **Limitações na escala dos dados:** O nosso scheduler funciona com dados de grande escala. Contudo, a limitação principal é a carga horaria total(número de aulas) das turmas e dos professores podem impossibilitar a obtenção de uma solução. Por exemplo, se um professor tiver 10 aulas e só houver 5 tempos disponíveis, não há solução possível. Podendo se aumentar o numero de periodos no dia e o numero de dias de aulas por semana.
    - **Sem dados no código:** tudo é lido de `data/<pasta>/*.csv`; muda-se de conjunto no dropdown de parâmetros.
      Os cenários desta página (turma nova, sala avariada, professor substituído, disponibilidade) alteram os dados
      carregados e mostram que nada está *hardcoded*.
    - **Validação independente:** `validator.py` não usa o solver; o teste de injeção de violações mostra que apanha
      cada regra R1–R7.
    - **Incremental:** o ganho vem de (i) reaproveitar H0 como hint, (ii) minimizar mudanças em vez de otimizar buracos e
      (iii) fixar o que não é afetado. O compromisso é que H1 pode ter mais buracos do que um H1 feito do zero
      (ver coluna *buracos prof.*); a variante `fixar + O1` recupera qualidade com um custo de tempo.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Uso de IA


    | Pergunta | Resposta |
    |---|---|
    | Que ferramentas de IA foram usadas (nome e versão/modelo)? | *Usou se o Github Copilot, Claude e ChatGPT* |
    | Em que partes do trabalho (modelação, código, testes, texto do relatório, revisão)? | *O Github Copilot foi usado para gerar texto do relatório, na elaboraçao de prompts para uso no Claude e alguma sugestoes para resolução de problemas. o Claude ajudou na resoluçao de algumas funçoes nos ficheiros validator.py, incremental.py e objective.py. O ChatGPT ajudou na estrutura do codigo (FileTree, bibliotecas usadas, organizaçao das funçoes.) * |
    | Que *prompts* ou pedidos principais foram feitos? | *Solicitações para gerar código, sugestões de otimização e melhorias. Em si, nao foram prompts específicos mas outputs de bugs ou sugestoes diretas do modelo de IA. Para o resto ver links no relatorio.* |
    | Que partes do trabalho foram feitas sem IA? | *Em geral, o codigo e a logica por tras foi feita manualmente pelos dois elementos do grupo (scheduler, loader, models etc.)* |
    
    **Declaração de responsabilidade:** *Nos, Luis Martins e Lucas Ferreira, assumimos a responsabilidade por todo o conteúdo deste notebook. Consideramos que o uso da IA foi ético e respeitou os princípios de integridade académica.*
    
    **Links de referência:** 
    -    [ChatGPT/Project](https://chatgpt.com/g/g-p-6ab4f1a7e6f48191adf200fccb74fa95-lc-tp1/project), 
    -    [Claude/Objective](https://claude.ai/share/be1e179f-a851-4d45-85c3-9c51944bcf83),
    -    [Claude/Validator](https://claude.ai/share/c73e8a18-caf9-4b24-8784-08b14b3544ec),
    -    [Claude/Incremental](https://claude.ai/share/dbc083e0-d59f-4dea-acd9-caa5935f4cb7)
    """)
    return


if __name__ == "__main__":
    app.run()
