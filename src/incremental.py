"""incremental.py — R9: produzir H1 a partir de H0 quando os recursos mudam ligeiramente.

Técnica (combina as duas sugeridas no enunciado):
  1. HINT: H0 é dado ao solver como ponto de partida.
  2. MINIMIZAR MUDANÇAS: o objetivo é o nº de aulas de H0 que deixam de estar no mesmo tempo.
  3. FIXAÇÃO PROGRESSIVA (modo "fixar"): fixam-se as aulas não afetadas e resolve-se só o subproblema
     afetado. Se for impossível, alarga-se a vizinhança por níveis até, no limite, soltar tudo:
        nível 0 — só se mexe nas aulas "quebradas" (slot já inválido, aulas novas, salas sobrelotadas);
        nível 1 — + todas as aulas dos professores e turmas afetados;
        nível 2 — nada fixo (equivale ao modo "hint").
  As sessões da mesma disciplina são intermutáveis, por isso a mudança mede-se por TEMPO ocupado
  (turma, disciplina, dia, período) e não pelo id da sessão; a quebra de simetria fica desligada.
"""
import time
from pathlib import Path

from .metrics import comparar_horarios, contar_buracos
from .objective import criar_termos_buracos
from .scheduler import Scheduler

PESO_PROF, PESO_TURMA = 10, 1


def _agrupar_sessoes(sessoes):
    """{(turma, disciplina): [sessões]}"""
    grupos = {}
    for sessao in sessoes:
        grupos.setdefault((sessao.turma, sessao.disciplina), []).append(sessao)
    return grupos


def _indexar_h0(h0):
    """{(turma, disciplina): {(dia, periodo): aula}}"""
    h0_por_grupo = {}
    for aula in h0:
        h0_por_grupo.setdefault((aula["turma"], aula["disciplina"]), {})[(aula["dia"], aula["periodo"])] = aula
    return h0_por_grupo


def _analisar(agendador, h0, grupos, h0_por_grupo):
    """Descobre o que a alteração dos dados afeta.
    Devolve (validos, quebrados, profs_afetados, turmas_afetadas)."""
    validos, quebrados, profs_afetados, turmas_afetadas = {}, set(), set(), set()
    for grupo, sessoes_do_grupo in grupos.items():
        primeira_sessao = sessoes_do_grupo[0]
        aulas_h0 = h0_por_grupo.get(grupo, {})
        # slot de H0 ainda possível? (mesma duração e a variável existe: prof disponível, dentro do dia)
        validos[grupo] = sorted(slot for slot, aula in aulas_h0.items()
                                if aula["duracao"] == primeira_sessao.duracao
                                and (primeira_sessao.id, *slot) in agendador.comeca)
        if len(validos[grupo]) < len(sessoes_do_grupo):      # precisa de pelo menos um slot novo
            quebrados.add(grupo)
            profs_afetados.add(primeira_sessao.professor)
            turmas_afetadas.add(primeira_sessao.turma)
        for aula in aulas_h0.values():                       # professor substituído
            if aula["professor"] != primeira_sessao.professor:
                profs_afetados.update((aula["professor"], primeira_sessao.professor))
    # salas sobrelotadas em H0 com a capacidade nova (ex.: sala avariada)
    capacidade_por_tipo = agendador.dados.capacidades()
    uso_por_tipo = {}
    for aula in h0:
        for tempo in range(aula["periodo"], aula["periodo"] + aula["duracao"]):
            uso_por_tipo.setdefault((aula["tipo_sala"], aula["dia"], tempo), []).append(aula)
    for (tipo_sala, _, _), aulas_no_slot in uso_por_tipo.items():
        if len(aulas_no_slot) > capacidade_por_tipo.get(tipo_sala, 0):
            for aula in aulas_no_slot:
                grupo = (aula["turma"], aula["disciplina"])
                if grupo in grupos:
                    quebrados.add(grupo)
                    profs_afetados.add(aula["professor"])
                    turmas_afetadas.add(aula["turma"])
    return validos, quebrados, profs_afetados, turmas_afetadas


def _construir(dados, grupos_fixados, validos, otimizar_buracos):
    """Cria um Scheduler com hint de H0, aulas dos `grupos_fixados` fixas e objetivo = minimizar mudanças."""
    agendador = Scheduler(dados)
    agendador.criar_variaveis()
    agendador.aplicar_restricoes(ignorar=("SIMETRIA",))
    mudancas = []
    for grupo, sessoes_do_grupo in _agrupar_sessoes(agendador.sessoes).items():
        slots_a_manter = validos[grupo][:len(sessoes_do_grupo)]
        for dia, periodo in slots_a_manter:
            aula_mantida = sum(agendador.comeca[sessao.id, dia, periodo] for sessao in sessoes_do_grupo)  # 0/1 (R3)
            if grupo in grupos_fixados:
                agendador.model.add(aula_mantida == 1)
            else:
                mudancas.append(1 - aula_mantida)
        for sessao, slot_h0 in zip(sessoes_do_grupo, slots_a_manter):    # hint: sessão i -> i-ésimo slot de H0
            for dia in range(dados.num_dias):
                for periodo in range(dados.num_periodos):
                    if (sessao.id, dia, periodo) in agendador.comeca:
                        agendador.model.add_hint(agendador.comeca[sessao.id, dia, periodo], int((dia, periodo) == slot_h0))
    termos, majorante = criar_termos_buracos(agendador, PESO_PROF, PESO_TURMA) if otimizar_buracos else ([], 0)
    if mudancas or termos:
        # lexicográfico: uma mudança pesa sempre mais do que qualquer quantidade de buracos
        agendador.model.minimize((majorante + 1) * sum(mudancas) + sum(termos))
    return agendador


def _finalizar(agendador, h0, inicio, tentativas, nivel):
    salas_antigas = {(aula["turma"], aula["disciplina"], aula["dia"], aula["periodo"]): aula["sala"] for aula in h0}
    h1 = agendador.extrair_solucao(salas_antigas) if agendador.solucao_encontrada() else None
    resultado = {"horario": h1, "estado": agendador.solver.status_name(agendador.status),
                 "tempo": time.perf_counter() - inicio, "nivel": nivel, "tentativas": tentativas,
                 "agendador": agendador}
    if h1:
        resultado.update(comparar_horarios(h0, h1))
        resultado["buracos_prof"] = contar_buracos(h1, "professor")
        resultado["buracos_turma"] = contar_buracos(h1, "turma")
    return resultado


def resolver_do_zero(dados, tempo_limite=30, workers=8):
    """Base de comparação: resolve o problema completo com O1, sem usar nenhum horário anterior.
    O tempo inclui construir o modelo."""
    inicio = time.perf_counter()
    agendador = Scheduler(dados)
    agendador.criar_variaveis()
    agendador.aplicar_restricoes()
    agendador.aplicar_objetivo(PESO_PROF, PESO_TURMA)
    agendador.resolver(tempo_limite, workers)
    horario = agendador.extrair_solucao() if agendador.solucao_encontrada() else None
    resultado = {"horario": horario, "estado": agendador.solver.status_name(agendador.status),
                 "tempo": time.perf_counter() - inicio, "nivel": None, "tentativas": 1, "agendador": agendador}
    if horario:
        resultado["buracos_prof"] = contar_buracos(horario, "professor")
        resultado["buracos_turma"] = contar_buracos(horario, "turma")
    return resultado


def resolver_incremental(dados, h0, modo="fixar", otimizar_buracos=False, tempo_limite=30, workers=8):
    """H1 a partir de H0.  modo: "fixar" (fixação progressiva) ou "hint" (só hint + minimizar mudanças).
    otimizar_buracos: se True, usa O1 como critério secundário (após minimizar mudanças)."""
    inicio = time.perf_counter()
    base = Scheduler(dados)
    base.criar_variaveis()
    grupos = _agrupar_sessoes(base.sessoes)
    validos, quebrados, profs_afetados, turmas_afetadas = _analisar(base, h0, grupos, _indexar_h0(h0))

    todos = set(grupos)
    niveis = [(0, todos - quebrados),
              (1, {grupo for grupo in todos if grupo not in quebrados
                   and grupos[grupo][0].professor not in profs_afetados
                   and grupos[grupo][0].turma not in turmas_afetadas}),
              (2, set())]
    if modo == "hint":
        niveis = [(2, set())]
    tentativas, fixados_anteriores = [], None
    agendador = None
    for nivel, grupos_fixados in niveis:
        if grupos_fixados == fixados_anteriores:      # este nível não muda nada face ao anterior
            continue
        fixados_anteriores = grupos_fixados
        agendador = _construir(dados, grupos_fixados, validos, otimizar_buracos)
        agendador.resolver(tempo_limite, workers)
        tentativas.append((nivel, agendador.solver.status_name(agendador.status)))
        if agendador.solucao_encontrada():
            return _finalizar(agendador, h0, inicio, tentativas, nivel)
    return _finalizar(agendador, h0, inicio, tentativas, None)


def comparar_abordagens(dados0, dados1, repeticoes=5, verbose=True):
    """Corre H0 -> H1 de várias formas e devolve uma tabela com a mediana do tempo."""
    import statistics
    h0 = resolver_do_zero(dados0)["horario"]
    variantes = {
        "H1 do zero (sem H0)":     lambda: resolver_do_zero(dados1),
        "incremental: hint":       lambda: resolver_incremental(dados1, h0, "hint"),
        "incremental: fixar":      lambda: resolver_incremental(dados1, h0, "fixar"),
        "incremental: fixar + O1": lambda: resolver_incremental(dados1, h0, "fixar", otimizar_buracos=True),
    }
    linhas = []
    for nome, correr in variantes.items():
        resultados = [correr() for _ in range(repeticoes)]
        resultado = resultados[0]
        alteracoes = comparar_horarios(h0, resultado["horario"]) if resultado["horario"] else {}
        linhas.append({"abordagem": nome, "estado": resultado["estado"],
                       "tempo_mediana_s": statistics.median(r["tempo"] for r in resultados),
                       "alteradas": alteracoes.get("alteradas"), "moveram_tempo": alteracoes.get("moveram_tempo"),
                       "moveram_sala": alteracoes.get("moveram_sala"), "novas": alteracoes.get("novas"),
                       "buracos_prof": resultado.get("buracos_prof"), "buracos_turma": resultado.get("buracos_turma"),
                       "nivel": resultado.get("nivel")})
    if verbose:
        print(f"{'abordagem':<26}{'estado':<9}{'tempo(s)':>9}{'alteradas':>10}{'tempo':>6}{'sala':>5}{'novas':>6}{'bur.prof':>9}{'bur.turma':>10}{'nível':>6}")
        for linha in linhas:
            print(f"{linha['abordagem']:<26}{linha['estado']:<9}{linha['tempo_mediana_s']:>9.3f}{str(linha['alteradas']):>10}"
                  f"{str(linha['moveram_tempo']):>6}{str(linha['moveram_sala']):>5}{str(linha['novas']):>6}"
                  f"{str(linha['buracos_prof']):>9}{str(linha['buracos_turma']):>10}{str(linha['nivel']):>6}")
    return h0, linhas

if __name__ == "__main__":
    import sys
    from .loader import DATA_DIR, carregar_dados
    p0 = Path("data/dados")
    p1 = Path("data/dados_v2")
    comparar_abordagens(carregar_dados(p0), carregar_dados(p1))