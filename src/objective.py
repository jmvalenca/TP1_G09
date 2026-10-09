"""objective.py — O1: minimizar buracos (tempos livres entre a 1.ª e a última aula do dia)."""


def _ocupacao(agendador, agrupar_por):
    """tem_aula[(entidade, dia, tempo)] = BoolVar (1 se a entidade tem aula nesse tempo).
    Só é válido com R1/R5 ativas (<=1 aula por tempo), que é o caso normal."""
    num_dias, num_periodos = agendador.dados.num_dias, agendador.dados.num_periodos
    grupos = {}
    for sessao in agendador.sessoes:
        for dia in range(num_dias):
            for tempo in range(num_periodos):
                variaveis = agendador.ocupa_tempo.get((sessao.id, dia, tempo))
                if variaveis:
                    grupos.setdefault((agrupar_por(sessao), dia, tempo), []).extend(variaveis)
    tem_aula = {}
    for chave, variaveis in grupos.items():
        variavel = agendador.model.new_bool_var(f"tem_aula|{chave}")
        agendador.model.add(sum(variaveis) == variavel)
        tem_aula[chave] = variavel
    return tem_aula


def _buracos(agendador, agrupar_por, entidades):
    """Devolve a lista de IntVars buracos_do_dia[entidade, dia] = nº de buracos nesse dia."""
    modelo = agendador.model
    num_dias, num_periodos = agendador.dados.num_dias, agendador.dados.num_periodos
    tem_aula = _ocupacao(agendador, agrupar_por)
    lista_buracos = []
    for entidade in entidades:
        for dia in range(num_dias):
            tempos_possiveis = [(tempo, tem_aula[entidade, dia, tempo]) for tempo in range(num_periodos)
                                if (entidade, dia, tempo) in tem_aula]
            if len(tempos_possiveis) < 2:      # com 0 ou 1 slot possível não há buraco possível
                continue
            trabalha = modelo.new_bool_var(f"trabalha|{entidade}|{dia}")
            primeiro = modelo.new_int_var(0, num_periodos - 1, f"primeiro|{entidade}|{dia}")
            ultimo = modelo.new_int_var(0, num_periodos - 1, f"ultimo|{entidade}|{dia}")
            buracos_do_dia = modelo.new_int_var(0, num_periodos, f"buracos|{entidade}|{dia}")
            n_aulas = sum(variavel for _, variavel in tempos_possiveis)
            for tempo, variavel in tempos_possiveis:
                modelo.add(variavel <= trabalha)
                modelo.add(primeiro <= tempo).only_enforce_if(variavel)   # primeiro <= qualquer tempo ocupado
                modelo.add(ultimo >= tempo).only_enforce_if(variavel)     # último  >= qualquer tempo ocupado
            modelo.add(trabalha <= n_aulas)
            # buracos = (janela do 1.º ao último tempo) - (tempos ocupados)
            modelo.add(buracos_do_dia >= ultimo - primeiro + 1 - n_aulas).only_enforce_if(trabalha)
            lista_buracos.append(buracos_do_dia)
    return lista_buracos


def criar_termos_buracos(agendador, peso_prof=10, peso_turma=0):
    """Devolve (termos, majorante): termos a somar no objetivo e um limite superior do seu valor."""
    num_periodos = agendador.dados.num_periodos
    professores = sorted({sessao.professor for sessao in agendador.sessoes})
    agendador.buracos_prof = _buracos(agendador, lambda sessao: sessao.professor, professores)
    termos = [peso_prof * buracos for buracos in agendador.buracos_prof]
    majorante = peso_prof * len(agendador.buracos_prof) * num_periodos
    if peso_turma:
        agendador.buracos_turma = _buracos(agendador, lambda sessao: sessao.turma, agendador.dados.turmas)
        termos += [peso_turma * buracos for buracos in agendador.buracos_turma]
        majorante += peso_turma * len(agendador.buracos_turma) * num_periodos
    return termos, majorante


def aplicar_objetivo(agendador, peso_prof=10, peso_turma=0):
    """Minimiza peso_prof × buracos de professores (+ peso_turma × buracos de turmas, opcional)."""
    termos, _ = criar_termos_buracos(agendador, peso_prof, peso_turma)
    if termos:
        agendador.model.minimize(sum(termos))
