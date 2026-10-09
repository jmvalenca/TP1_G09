import pytest

from src.loader import carregar_dados
from src.models import DIAS, gerar_sessoes
from tests.helpers import anexar, substituir, variante


def test_conta_entidades(dados0):
    assert dados0.turmas == ["7ºA", "7ºB"]
    assert len(dados0.disciplinas) == 6
    assert dados0.capacidades() == {"normal": 6, "Laboratório": 1, "Ginásio": 1}


def test_sala_especial_vazia_e_None_e_nao_a_string_None(dados0):
    """Regressão: str(None) == 'None' fazia o R7 dar capacidade 0 e o modelo INFEASIBLE."""
    mat = next(d for d in dados0.disciplinas if d.nome == "Matemática")
    assert mat.sala_especial is None
    assert {sessao.tipo_sala for sessao in gerar_sessoes(dados0)} == {"normal", "Laboratório", "Ginásio"}


def test_duplo_periodo_e_bool(dados0):
    ef = next(d for d in dados0.disciplinas if d.nome == "Educação Física")
    mat = next(d for d in dados0.disciplinas if d.nome == "Matemática")
    assert ef.duplo_periodo is True and mat.duplo_periodo is False   # "nao" não pode ser truthy


def test_dias_sao_ordenados():
    """Regressão: DIAS era um set (ordem aleatória entre execuções)."""
    assert DIAS == ("Seg", "Ter", "Qua", "Qui", "Sex")


def test_excecoes_sao_0_based(dados1):
    ana = {(i.dia, i.periodo) for i in dados1.indisponibilidades if i.professor == "Prof. Ana"}
    assert ana == {(4, 3), (4, 4)}          # Sex, 4.º e 5.º tempos


def test_dados_v2_so_difere_nas_excecoes(dados0, dados1):
    assert dados0.turmas == dados1.turmas and dados0.disciplinas == dados1.disciplinas
    assert len(dados1.indisponibilidades) == len(dados0.indisponibilidades) + 2


def test_sessoes_tem_ids_estaveis(dados0):
    assert [s.id for s in gerar_sessoes(dados0)] == [s.id for s in gerar_sessoes(dados0)]


def test_sessoes_respeitam_carga_e_duplo(dados0):
    sessoes = gerar_sessoes(dados0)
    ef = [s for s in sessoes if s.turma == "7ºA" and s.disciplina == "Educação Física"]
    assert len(ef) == 1 and ef[0].duracao == 2        # carga 2 duplo = 1 bloco de 2 tempos
    mat = [s for s in sessoes if s.turma == "7ºA" and s.disciplina == "Matemática"]
    assert len(mat) == 4 and all(s.duracao == 1 for s in mat)


def test_carga_impar_com_duplo_e_rejeitada(tmp_path):
    d = variante(tmp_path, lambda p: substituir(p / "disciplinas.csv", "Educação Física,Prof. Eduardo,2", "Educação Física,Prof. Eduardo,3"))
    with pytest.raises(ValueError):
        gerar_sessoes(d)


def test_sim_nao_invalido(tmp_path):
    with pytest.raises(ValueError):
        variante(tmp_path, lambda p: substituir(p / "disciplinas.csv", ",nao,", ",talvez,"))


def test_sala_especial_inexistente(tmp_path):
    with pytest.raises(ValueError):
        variante(tmp_path, lambda p: substituir(p / "disciplinas.csv", "Laboratório", "Piscina"))


def test_excecao_com_dia_invalido(tmp_path):
    with pytest.raises(ValueError):
        variante(tmp_path, lambda p: anexar(p / "disponibilidade_excecoes.csv", "Prof. Ana,Dom,1\n"))


def test_excecao_com_periodo_fora_do_intervalo(tmp_path):
    with pytest.raises(ValueError):
        variante(tmp_path, lambda p: anexar(p / "disponibilidade_excecoes.csv", "Prof. Ana,Seg,99\n"))


def test_ficheiro_em_falta(tmp_path):
    with pytest.raises(FileNotFoundError):
        carregar_dados(tmp_path)


def test_num_periodos_configuravel(tmp_path):
    d = variante(tmp_path, lambda p: None, num_periodos=6)
    assert d.num_periodos == 6
