import pytest

from src.incremental import resolver_do_zero, resolver_incremental
from src.metrics import comparar_horarios, contar_buracos
from src.validator import validar_horario
from tests.helpers import anexar, substituir, variante

MODOS = [("hint", {}), ("fixar", {}), ("fixar", {"otimizar_buracos": True})]


def test_h1_valido_em_todos_os_modos(dados0, dados1, h0):
    for modo, kw in MODOS:
        r = resolver_incremental(dados1, h0, modo, **kw)
        assert r["estado"] in ("OPTIMAL", "FEASIBLE")
        assert validar_horario(dados1, r["horario"]) == []


def test_mudancas_minimas_igual_ao_minimo_teorico(dados0, dados1, h0):
    """Só as aulas de H0 que caem em slots agora proibidos têm de mudar."""
    proibidos = {(i.professor, i.dia, i.periodo) for i in dados1.indisponibilidades}
    forcadas = [h for h in h0 if any((h["professor"], h["dia"], t) in proibidos
                                     for t in range(h["periodo"], h["periodo"] + h["duracao"]))]
    r = resolver_incremental(dados1, h0, "fixar")
    assert r["alteradas"] == len(forcadas)


def test_mudanca_forcada_muda_exatamente_uma_aula(dados0, h0, tmp_path):
    """Torna indisponível o slot onde a Ana dá uma aula de H0: só essa aula pode mudar."""
    from src.models import DIAS
    a = next(h for h in h0 if h["professor"] == "Prof. Ana")
    d = variante(tmp_path, lambda p: anexar(p / "disponibilidade_excecoes.csv",
                                            f"Prof. Ana,{DIAS[a['dia']]},{a['periodo'] + 1}\n"))
    for modo, kw in MODOS:
        r = resolver_incremental(d, h0, modo, **kw)
        assert validar_horario(d, r["horario"]) == []
        assert r["alteradas"] == 1 and r["moveram_tempo"] == 1


def test_incremental_altera_muito_menos_que_do_zero(dados0, dados1, h0):
    zero = resolver_do_zero(dados1)
    inc = resolver_incremental(dados1, h0, "fixar")
    assert inc["alteradas"] < comparar_horarios(h0, zero["horario"])["alteradas"] / 3


def test_hint_e_fixar_dao_o_mesmo_minimo(dados1, h0):
    assert resolver_incremental(dados1, h0, "hint")["alteradas"] == resolver_incremental(dados1, h0, "fixar")["alteradas"]


def test_sem_alteracao_nao_muda_nada(dados0, h0):
    r = resolver_incremental(dados0, h0, "fixar")
    assert r["alteradas"] == 0 and r["novas"] == 0


def test_turma_nova(tmp_path, h0):
    d = variante(tmp_path, lambda p: anexar(p / "turmas.csv", "7ºC\n"))
    for modo, kw in MODOS:
        r = resolver_incremental(d, h0, modo, **kw)
        assert validar_horario(d, r["horario"]) == []
        assert r["alteradas"] == 0 and r["novas"] == 16      # 16 sessões numa turma nova


def test_professor_substituido(tmp_path, h0):
    d = variante(tmp_path, lambda p: substituir(p / "disciplinas.csv", "Inglês,Prof. Diana", "Inglês,Prof. Filipa"))
    r = resolver_incremental(d, h0, "fixar")
    assert validar_horario(d, r["horario"]) == []
    assert all(h["professor"] == "Prof. Filipa" for h in r["horario"] if h["disciplina"] == "Inglês")


def test_sala_avariada(tmp_path, h0):
    d = variante(tmp_path, lambda p: substituir(p / "salas.csv", "Sala Normal,normal,6", "Sala Normal,normal,1"))
    for modo, kw in MODOS:
        r = resolver_incremental(d, h0, modo, **kw)
        assert validar_horario(d, r["horario"]) == []


def test_laboratorio_indisponivel_em_alguns_tempos_nao_quebra(tmp_path, h0):
    d = variante(tmp_path, lambda p: anexar(p / "disponibilidade_excecoes.csv", "".join(f"Prof. Bruno,Seg,{t}\n" for t in range(1, 6))))
    r = resolver_incremental(d, h0, "fixar")
    assert validar_horario(d, r["horario"]) == []


def test_salas_mantidas_quando_possivel(dados1, h0):
    r = resolver_incremental(dados1, h0, "fixar")
    assert r["moveram_sala"] == 0


def test_instancia_impossivel_devolve_infeasible_sem_rebentar(tmp_path, h0):
    d = variante(tmp_path, lambda p: anexar(p / "turmas.csv", "8ºA\n8ºB\n8ºC\n8ºD\n"))
    r = resolver_incremental(d, h0, "fixar", tempo_limite=10)
    assert r["estado"] == "INFEASIBLE" and r["horario"] is None


# ---- métricas ----
def aula(turma, disc, dia, per, sala="S", dur=1, prof="P"):
    return {"turma": turma, "disciplina": disc, "dia": dia, "periodo": per, "duracao": dur,
            "sala": sala, "professor": prof}


def test_contar_buracos():
    h = [aula("A", "x", 0, 0), aula("A", "y", 0, 3)]           # tempos 0 e 3 -> buracos nos tempos 1 e 2
    assert contar_buracos(h, "turma") == 2
    assert contar_buracos([aula("A", "x", 0, 0), aula("A", "y", 0, 1)], "turma") == 0
    assert contar_buracos([aula("A", "x", 0, 0, dur=2), aula("A", "y", 0, 3)], "turma") == 1   # bloco ocupa 0-1; falta o tempo 2


def test_comparar_horarios():
    a = [aula("A", "x", 0, 0, "S1"), aula("A", "x", 1, 0, "S1"), aula("A", "y", 2, 0, "S1")]
    b = [aula("A", "x", 0, 0, "S2"), aula("A", "x", 1, 3, "S1"), aula("A", "y", 2, 0, "S1"), aula("A", "z", 3, 0, "S1")]
    r = comparar_horarios(a, b)
    assert r == {"moveram_tempo": 1, "moveram_sala": 1, "alteradas": 2, "novas": 1, "removidas": 0}


def test_comparar_ignora_troca_de_sessoes_intermutaveis():
    a = [aula("A", "x", 0, 0), aula("A", "x", 1, 0)]
    b = [aula("A", "x", 1, 0), aula("A", "x", 0, 0)]           # mesma grelha, ordem diferente
    assert comparar_horarios(a, b)["alteradas"] == 0
