"""metrics.py — métricas calculadas sobre o horário final (independentes do solver)."""


def contar_buracos(horario, chave):
    """Nº total de buracos por `chave` ("professor" ou "turma"): tempos livres entre a 1.ª e a última aula."""
    tempos_por_dia = {}
    for aula in horario:
        for tempo in range(aula["periodo"], aula["periodo"] + aula["duracao"]):
            tempos_por_dia.setdefault((aula[chave], aula["dia"]), set()).add(tempo)
    return sum(max(tempos) - min(tempos) + 1 - len(tempos) for tempos in tempos_por_dia.values())


def comparar_horarios(h0, h1):
    """Compara dois horários. Uma aula (turma, disciplina) é identificada pelo seu tempo, porque
    as sessões da mesma disciplina são intermutáveis. Conta:
      moveram_tempo — aulas de H0 que já não estão no mesmo (dia, período)
      moveram_sala  — aulas que ficaram no mesmo tempo mas mudaram de sala
      novas/removidas — aulas que só existem em H1 / só em H0 (turma nova, carga alterada...)
    alteradas = moveram_tempo + moveram_sala (é o que o enunciado pede para minimizar)."""
    def indexar(horario):
        """{(turma, disciplina): {(dia, periodo): sala}}"""
        indice = {}
        for aula in horario:
            indice.setdefault((aula["turma"], aula["disciplina"]), {})[(aula["dia"], aula["periodo"])] = aula["sala"]
        return indice

    indice_h0, indice_h1 = indexar(h0), indexar(h1)
    moveram_tempo = moveram_sala = novas = removidas = 0
    for grupo in set(indice_h0) | set(indice_h1):
        salas_h0, salas_h1 = indice_h0.get(grupo, {}), indice_h1.get(grupo, {})
        slots_comuns = set(salas_h0) & set(salas_h1)
        moveram_sala += sum(salas_h0[slot] != salas_h1[slot] for slot in slots_comuns)
        moveram_tempo += min(len(salas_h0), len(salas_h1)) - len(slots_comuns)
        novas += max(0, len(salas_h1) - len(salas_h0))
        removidas += max(0, len(salas_h0) - len(salas_h1))
    return {"moveram_tempo": moveram_tempo, "moveram_sala": moveram_sala,
            "alteradas": moveram_tempo + moveram_sala, "novas": novas, "removidas": removidas}
