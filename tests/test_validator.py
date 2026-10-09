"""Cada teste estraga um horário válido de propósito e confirma que o validator apanha a regra certa.
(Sem isto, um validator que dissesse sempre 'ok' passaria em todos os outros testes.)"""
from src.validator import validar_horario
from tests.helpers import encontrar


def regras(dados, horario):
    return {v.regra for v in validar_horario(dados, horario)}


def test_h0_e_valido(dados0, horario):
    assert validar_horario(dados0, horario) == []


def test_r1_turma_com_duas_aulas_em_simultaneo(dados0, horario):
    a = encontrar(horario, turma="7ºA", disciplina="Matemática")
    b = encontrar(horario, turma="7ºA", disciplina="Português")
    b["dia"], b["periodo"] = a["dia"], a["periodo"]
    assert "R1" in regras(dados0, horario)


def test_r2_carga_em_falta(dados0, horario):
    horario.remove(encontrar(horario, turma="7ºA", disciplina="Matemática"))
    assert "R2" in regras(dados0, horario)


def test_r2_carga_a_mais(dados0, horario):
    extra = dict(encontrar(horario, turma="7ºA", disciplina="História"))
    horario.append(extra)
    assert "R2" in regras(dados0, horario)


def test_r3_duas_aulas_da_mesma_disciplina_no_mesmo_dia(dados0, horario):
    aulas = [h for h in horario if h["turma"] == "7ºA" and h["disciplina"] == "Matemática"]
    aulas[1]["dia"] = aulas[0]["dia"]
    assert "R3" in regras(dados0, horario)


def test_r4_bloco_duplo_partido(dados0, horario):
    encontrar(horario, turma="7ºA", disciplina="Educação Física")["duracao"] = 1
    assert "R4" in regras(dados0, horario)


def test_r4_bloco_duplo_sai_do_dia(dados0, horario):
    encontrar(horario, turma="7ºA", disciplina="Educação Física")["periodo"] = dados0.num_periodos - 1
    assert "R4" in regras(dados0, horario)


def test_r4_disciplina_simples_em_bloco_duplo(dados0, horario):
    encontrar(horario, turma="7ºA", disciplina="Matemática")["duracao"] = 2
    assert "R4" in regras(dados0, horario)


def test_r5_professor_em_duas_turmas_ao_mesmo_tempo(dados0, horario):
    a = encontrar(horario, turma="7ºA", disciplina="Matemática")
    b = encontrar(horario, turma="7ºB", disciplina="Matemática")
    b["dia"], b["periodo"] = a["dia"], a["periodo"]
    assert "R5" in regras(dados0, horario)


def test_r6_professor_indisponivel(dados1, h0):
    import copy
    h = copy.deepcopy(h0)
    encontrar(h, turma="7ºA", disciplina="Matemática").update(dia=4, periodo=3)   # Ana, Sex 4.º tempo (v2)
    assert "R6" in regras(dados1, h)


def test_r6_bloco_duplo_que_entra_num_slot_indisponivel(dados0, horario):
    encontrar(horario, turma="7ºA", disciplina="Educação Física").update(dia=0, periodo=1)  # Eduardo só a partir do 4.º
    assert "R6" in regras(dados0, horario)


def test_r7_sala_do_tipo_errado(dados0, horario):
    encontrar(horario, turma="7ºA", disciplina="Matemática")["sala"] = "Ginásio"
    assert "R7" in regras(dados0, horario)


def test_r7_duas_aulas_no_laboratorio_ao_mesmo_tempo(dados0, horario):
    a = encontrar(horario, turma="7ºA", disciplina="Ciências")
    b = encontrar(horario, turma="7ºB", disciplina="Ciências")
    b["dia"], b["periodo"] = a["dia"], a["periodo"]
    assert "R7" in regras(dados0, horario)
