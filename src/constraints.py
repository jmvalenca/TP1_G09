"""constraints.py — restrições R1–R7 sobre as variáveis comeca[(sessao_id, dia, periodo)].

Modelo: comeca[sessao, dia, periodo] = 1 se a sessão COMEÇA nesse dia e período
(ocupa periodo .. periodo+duracao-1).
Por construção (em Scheduler.criar_variaveis):
  R4 — sessões duplas são um bloco de 2 tempos consecutivos e não passam do fim do dia;
  R6 — não existe variável nos slots em que o professor está indisponível.
"""


def _limitar_por_slot(agendador, agrupar_por, limite):
    """Para cada (grupo, dia, tempo): soma das sessões que ocupam esse tempo <= limite(grupo)."""
    grupos = {}
    for sessao in agendador.sessoes:
        for dia in range(agendador.dados.num_dias):
            for tempo in range(agendador.dados.num_periodos):
                variaveis = agendador.ocupa_tempo.get((sessao.id, dia, tempo))
                if variaveis:
                    grupos.setdefault((agrupar_por(sessao), dia, tempo), []).extend(variaveis)
    for (grupo, _, _), variaveis in grupos.items():
        max_aulas = limite(grupo)
        if len(variaveis) > max_aulas:
            agendador.model.add(sum(variaveis) <= max_aulas)


def restricao_r1_turma(agendador):
    """R1 — uma turma não tem duas aulas em simultâneo."""
    _limitar_por_slot(agendador, lambda sessao: sessao.turma, lambda grupo: 1)


def restricao_r2_carga_semanal(agendador):
    """R2 — cada sessão é colocada exatamente uma vez (o nº de sessões = carga semanal)."""
    for sessao in agendador.sessoes:
        opcoes = agendador.opcoes_da_sessao[sessao.id]
        if not opcoes:
            raise ValueError(f"Sessão {sessao.id} não tem nenhum slot possível (disponibilidade?)")
        agendador.model.add_exactly_one(opcoes)


def _agrupar_sessoes(agendador):
    """{(turma, disciplina): [sessões]} — as sessões do mesmo grupo são intermutáveis."""
    grupos = {}
    for sessao in agendador.sessoes:
        grupos.setdefault((sessao.turma, sessao.disciplina), []).append(sessao)
    return grupos


def restricao_r3_uma_por_dia(agendador):
    """R3 — no máx. uma sessão da mesma disciplina por dia, por turma (bloco duplo conta como uma)."""
    for sessoes_do_grupo in _agrupar_sessoes(agendador).values():
        for dia in range(agendador.dados.num_dias):
            variaveis = [variavel for sessao in sessoes_do_grupo
                         for periodo in range(agendador.dados.num_periodos)
                         if (variavel := agendador.comeca.get((sessao.id, dia, periodo))) is not None]
            if len(variaveis) > 1:
                agendador.model.add(sum(variaveis) <= 1)


def quebrar_simetria(agendador):
    """Não é uma regra do enunciado: sessões do mesmo grupo são intermutáveis, logo impomos
    dia crescente (válido porque R3 já obriga a dias distintos). Acelera o H0, mas é DESLIGADA
    no incremental (senão forçaria mudanças desnecessárias em relação a H0)."""
    for sessoes_do_grupo in _agrupar_sessoes(agendador).values():
        dia_de_cada_sessao = [
            sum(dia * variavel for (sessao_id, dia, periodo), variavel in agendador.comeca.items()
                if sessao_id == sessao.id)
            for sessao in sessoes_do_grupo]
        for dia_anterior, dia_seguinte in zip(dia_de_cada_sessao, dia_de_cada_sessao[1:]):
            agendador.model.add(dia_anterior < dia_seguinte)


def restricao_r5_professor(agendador):
    """R5 — um professor não dá duas aulas em simultâneo."""
    _limitar_por_slot(agendador, lambda sessao: sessao.professor, lambda grupo: 1)


def restricao_r7_salas(agendador):
    """R7 — por tipo de sala, nº de aulas em simultâneo <= quantidade."""
    capacidade_por_tipo = agendador.dados.capacidades()
    _limitar_por_slot(agendador, lambda sessao: sessao.tipo_sala,
                      lambda tipo_sala: capacidade_por_tipo.get(tipo_sala, 0))
