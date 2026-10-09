"""validator.py — verifica um horário contra R1–R7, SEM usar o solver.

É deliberadamente independente do modelo CP-SAT: se o modelo tiver um erro, o validator apanha-o.
Cada função devolve uma lista de Violacao (vazia = regra cumprida).
"""
from collections import Counter
from dataclasses import dataclass

from .models import DIAS


@dataclass(frozen=True)
class Violacao:
    regra: str
    mensagem: str


def _tempos(h):
    """Períodos (0-based) ocupados por uma aula: 1 tempo, ou 2 se for bloco duplo."""
    return range(h["periodo"], h["periodo"] + h["duracao"])


def _nome_slot(dia, tempo):
    return f"{DIAS[dia]} {tempo + 1}º tempo"


def _contar_por_slot(horario, chave):
    c = Counter()
    for h in horario:
        for t in _tempos(h):
            c[h[chave], h["dia"], t] += 1
    return c


def verificar_r1_turma(dados, horario):
    """R1 — uma turma não tem duas aulas em simultâneo."""
    return [Violacao("R1", f"{k[0]} tem {n} aulas em {_nome_slot(k[1], k[2])}")
            for k, n in _contar_por_slot(horario, "turma").items() if n > 1]


def verificar_r2_carga(dados, horario):
    """R2 — cada turma tem, de cada disciplina, exatamente a carga semanal."""
    v = []
    for turma in dados.turmas:
        for d in dados.disciplinas:
            tempos = sum(h["duracao"] for h in horario
                         if h["turma"] == turma and h["disciplina"] == d.nome)
            if tempos != d.carga_semanal:
                v.append(Violacao("R2", f"{turma}/{d.nome}: {tempos} tempos em vez de {d.carga_semanal}"))
    conhecidas = {(t, d.nome) for t in dados.turmas for d in dados.disciplinas}
    for h in horario:
        if (h["turma"], h["disciplina"]) not in conhecidas:
            v.append(Violacao("R2", f"aula de {h['turma']}/{h['disciplina']} que não existe nos dados"))
    return v


def verificar_r3_uma_por_dia(dados, horario):
    """R3 — no máximo uma aula (ou um bloco) da mesma disciplina por dia, por turma."""
    c = Counter((h["turma"], h["disciplina"], h["dia"]) for h in horario)
    return [Violacao("R3", f"{k[0]}/{k[1]} tem {n} ocorrências em {DIAS[k[2]]}")
            for k, n in c.items() if n > 1]


def verificar_r4_duplo_periodo(dados, horario):
    """R4 — duplo período = 1 bloco de 2 tempos consecutivos no mesmo dia, sem sair do dia."""
    duplo = {d.nome: d.duplo_periodo for d in dados.disciplinas}
    v = []
    for h in horario:
        esperado = 2 if duplo.get(h["disciplina"]) else 1
        if h["duracao"] != esperado:
            v.append(Violacao("R4", f"{h['turma']}/{h['disciplina']}: duração {h['duracao']}, esperado {esperado}"))
        if h["periodo"] < 0 or h["periodo"] + h["duracao"] > dados.num_periodos:
            v.append(Violacao("R4", f"{h['turma']}/{h['disciplina']} sai do dia (período {h['periodo'] + 1}, duração {h['duracao']})"))
    return v


def verificar_r5_professor(dados, horario):
    """R5 — um professor não dá duas aulas em simultâneo (e é o professor da disciplina)."""
    v = [Violacao("R5", f"{k[0]} tem {n} aulas em {_nome_slot(k[1], k[2])}")
         for k, n in _contar_por_slot(horario, "professor").items() if n > 1]
    prof = {d.nome: d.professor for d in dados.disciplinas}
    for h in horario:
        if prof.get(h["disciplina"]) != h["professor"]:
            v.append(Violacao("R5", f"{h['disciplina']} dada por {h['professor']}, mas o professor é {prof.get(h['disciplina'])}"))
    return v


def verificar_r6_disponibilidade(dados, horario):
    """R6 — nenhuma aula num (professor, dia, período) indisponível."""
    indisp = {(i.professor, i.dia, i.periodo) for i in dados.indisponibilidades}
    return [Violacao("R6", f"{h['professor']} indisponível em {_nome_slot(h['dia'], t)} ({h['turma']}/{h['disciplina']})")
            for h in horario for t in _tempos(h) if (h["professor"], h["dia"], t) in indisp]


def verificar_r7_salas(dados, horario):
    """R7 — a sala é do tipo exigido, existe, e não é usada por duas aulas ao mesmo tempo;
    e o nº de aulas em simultâneo por tipo respeita a quantidade."""
    v = []
    exigido = {d.nome: (d.sala_especial or "normal") for d in dados.disciplinas}
    for h in horario:
        rec = exigido.get(h["disciplina"], "normal")
        if h["sala"] not in dados.nomes_salas(rec):
            v.append(Violacao("R7", f"{h['turma']}/{h['disciplina']} na sala {h['sala']!r}, que não é do tipo {rec!r}"))
    v += [Violacao("R7", f"sala {k[0]} usada {n}× em {_nome_slot(k[1], k[2])}")
          for k, n in _contar_por_slot(horario, "sala").items() if n > 1]
    cap = dados.capacidades()
    v += [Violacao("R7", f"'{k[0]}': {n} aulas em {_nome_slot(k[1], k[2])}, capacidade {cap.get(k[0], 0)}")
          for k, n in _contar_por_slot([{**h, "recurso": exigido.get(h["disciplina"], "normal")} for h in horario],
                                       "recurso").items() if n > cap.get(k[0], 0)]
    return v


REGRAS = (verificar_r1_turma, verificar_r2_carga, verificar_r3_uma_por_dia, verificar_r4_duplo_periodo,
          verificar_r5_professor, verificar_r6_disponibilidade, verificar_r7_salas)


def validar_horario(dados, horario):
    """Corre todas as regras. Devolve a lista de violações (vazia = horário válido)."""
    return [v for regra in REGRAS for v in regra(dados, horario)]