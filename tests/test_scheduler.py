import pytest

from src.incremental import resolver_do_zero
from src.metrics import contar_buracos
from src.scheduler import Scheduler
from src.validator import validar_horario
from tests.helpers import anexar, variante


def test_h0_valido_e_otimo(dados0):
    r = resolver_do_zero(dados0)
    assert r["estado"] == "OPTIMAL"
    assert validar_horario(dados0, r["horario"]) == []


def test_h0_com_dados_v2_valido(dados1):
    r = resolver_do_zero(dados1)
    assert validar_horario(dados1, r["horario"]) == []


def test_todas_as_sessoes_colocadas(dados0, h0):
    assert sum(h["duracao"] for h in h0) == sum(d.carga_semanal for d in dados0.disciplinas) * len(dados0.turmas)


def test_o1_reduz_buracos_de_professores(dados0):
    """O objetivo tem de melhorar face a uma solução qualquer."""
    sem = Scheduler(dados0); sem.criar_variaveis(); sem.aplicar_restricoes(); sem.resolver()
    com = resolver_do_zero(dados0)
    b_sem = contar_buracos(sem.extrair_solucao(), "professor")
    b_com = contar_buracos(com["horario"], "professor")
    assert b_com <= b_sem and b_com == 0


def test_dataset_diferente_sem_alterar_codigo(tmp_path):
    """R8: os dados vêm só dos CSV — mais turmas, nova disciplina, nova exceção."""
    def editar(p):
        anexar(p / "turmas.csv", "8ºA\n8ºB\n")
        anexar(p / "disciplinas.csv", "Música,Prof. Fátima,2,nao,\n")
        anexar(p / "disponibilidade_excecoes.csv", "Prof. Bruno,Qua,1\nProf. Bruno,Qua,2\n")
    d = variante(tmp_path, editar)
    r = resolver_do_zero(d)
    assert r["estado"] in ("OPTIMAL", "FEASIBLE")
    assert validar_horario(d, r["horario"]) == []


def test_mais_periodos_por_dia(tmp_path):
    d = variante(tmp_path, lambda p: None, num_periodos=8)
    r = resolver_do_zero(d)
    assert validar_horario(d, r["horario"]) == []


def test_instancia_impossivel_da_infeasible(tmp_path):
    """Com 6 turmas a Prof. Ana precisaria de 24 tempos e só tem 23 livres."""
    d = variante(tmp_path, lambda p: anexar(p / "turmas.csv", "8ºA\n8ºB\n8ºC\n8ºD\n"))
    assert resolver_do_zero(d, tempo_limite=10)["estado"] == "INFEASIBLE"


def test_ids_das_sessoes_estaveis_entre_execucoes(dados0):
    a = {h["sessao_id"] for h in resolver_do_zero(dados0)["horario"]}
    b = {h["sessao_id"] for h in resolver_do_zero(dados0)["horario"]}
    assert a == b
