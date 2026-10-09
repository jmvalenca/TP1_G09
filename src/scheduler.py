"""scheduler.py — constrói o modelo CP-SAT e gera o horário (H0)."""
import time
from ortools.sat.python import cp_model
from pathlib import Path


from .constraints import (restricao_r1_turma, restricao_r2_carga_semanal, restricao_r3_uma_por_dia,
                          restricao_r5_professor, restricao_r7_salas, quebrar_simetria)
from .loader import DATA_DIR, carregar_dados
from .metrics import contar_buracos
from .models import DIAS, Dados, gerar_sessoes
from .objective import aplicar_objetivo


class Scheduler:
    def __init__(self, dados: Dados, sessoes=None):
        self.dados = dados
        self.sessoes = sessoes if sessoes is not None else gerar_sessoes(dados)
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.status = None
        self.comeca = {}            # (sessao_id, dia, periodo_inicial) -> BoolVar
        self.ocupa_tempo = {}       # (sessao_id, dia, tempo) -> [BoolVar] que ocupam esse tempo
        self.opcoes_da_sessao = {}  # sessao_id -> [BoolVar] (todas as posições possíveis)

    def criar_variaveis(self):
        num_dias, num_periodos = self.dados.num_dias, self.dados.num_periodos
        indisponiveis = {(i.professor, i.dia, i.periodo) for i in self.dados.indisponibilidades}
        for sessao in self.sessoes:
            self.opcoes_da_sessao[sessao.id] = []
            for dia in range(num_dias):
                for periodo in range(num_periodos - sessao.duracao + 1):  # R4: bloco não sai do dia
                    tempos_do_bloco = range(periodo, periodo + sessao.duracao)
                    if any((sessao.professor, dia, tempo) in indisponiveis for tempo in tempos_do_bloco):  # R6
                        continue
                    variavel = self.model.new_bool_var(f"comeca|{sessao.id}|{dia}|{periodo}")
                    self.comeca[sessao.id, dia, periodo] = variavel
                    self.opcoes_da_sessao[sessao.id].append(variavel)
                    for tempo in tempos_do_bloco:
                        self.ocupa_tempo.setdefault((sessao.id, dia, tempo), []).append(variavel)

    def aplicar_restricoes(self, ignorar=()):
        """`ignorar` permite desligar partes (ex.: {"SIMETRIA"} no incremental). R2 é sempre aplicada."""
        restricao_r2_carga_semanal(self)
        for nome, restricao in (("R1", restricao_r1_turma), ("R3", restricao_r3_uma_por_dia),
                                ("R5", restricao_r5_professor), ("R7", restricao_r7_salas),
                                ("SIMETRIA", quebrar_simetria)):
            if nome not in ignorar:
                restricao(self)

    def aplicar_objetivo(self, peso_prof=10, peso_turma=0):
        aplicar_objetivo(self, peso_prof, peso_turma)

    def resolver(self, tempo_limite=30, workers=8):
        self.solver.parameters.max_time_in_seconds = tempo_limite
        self.solver.parameters.num_workers = workers
        inicio = time.perf_counter()
        self.status = self.solver.solve(self.model)
        self.tempo = time.perf_counter() - inicio
        return self.status

    def solucao_encontrada(self):
        return self.status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    def extrair_solucao(self, preferencias_sala=None):
        """Lista de dicts (uma por sessão), com salas físicas atribuídas.
        `preferencias_sala`: {(turma, disciplina, dia, periodo): sala} de um horário anterior."""
        if not self.solucao_encontrada():
            return None
        sessao_por_id = {sessao.id: sessao for sessao in self.sessoes}
        horario = []
        for (sessao_id, dia, periodo), variavel in self.comeca.items():
            if self.solver.value(variavel):
                sessao = sessao_por_id[sessao_id]
                horario.append({"sessao_id": sessao_id, "turma": sessao.turma, "disciplina": sessao.disciplina,
                                "professor": sessao.professor, "dia": dia, "periodo": periodo,
                                "duracao": sessao.duracao, "tipo_sala": sessao.tipo_sala, "sala": None})
        self._atribuir_salas(horario, preferencias_sala or {})
        return sorted(horario, key=lambda aula: (aula["turma"], aula["dia"], aula["periodo"]))

    def _atribuir_salas(self, horario, salas_antigas):
        """R7 garante a capacidade por tipo; aqui damos um nome de sala físico. Quando havia uma sala
        em H0 para a mesma aula, tenta mantê-la. Há sempre sala livre (nº em uso < capacidade)."""
        identificar = lambda aula: (aula["turma"], aula["disciplina"], aula["dia"], aula["periodo"])
        for tipo_sala in {aula["tipo_sala"] for aula in horario}:
            nomes = self.dados.nomes_salas(tipo_sala)
            for dia in range(self.dados.num_dias):
                aulas_do_dia = sorted((aula for aula in horario if aula["tipo_sala"] == tipo_sala and aula["dia"] == dia),
                                      key=lambda aula: aula["periodo"])
                livre_ate = {nome: 0 for nome in nomes}   # 1.º período em que a sala fica livre
                for i, aula in enumerate(aulas_do_dia):
                    # salas que aulas posteriores querem manter (para não as ocupar sem necessidade)
                    reservadas = {salas_antigas.get(identificar(outra)) for outra in aulas_do_dia[i + 1:]}
                    sala_desejada = salas_antigas.get(identificar(aula))
                    if sala_desejada in livre_ate and livre_ate[sala_desejada] <= aula["periodo"]:
                        sala = sala_desejada
                    else:
                        livres = [nome for nome in nomes if livre_ate[nome] <= aula["periodo"]]
                        sala = next((nome for nome in livres if nome not in reservadas), livres[0])
                    aula["sala"], livre_ate[sala] = sala, aula["periodo"] + aula["duracao"]


def imprimir_horario(horario, dados: Dados):
    for turma in dados.turmas:
        print(f"\n=== {turma} ===")
        grelha = {}
        for aula in horario:
            if aula["turma"] == turma:
                for tempo in range(aula["periodo"], aula["periodo"] + aula["duracao"]):
                    grelha[aula["dia"], tempo] = f'{aula["disciplina"][:9]}'
        print("     " + "".join(f"{DIAS[dia]:<11}" for dia in range(dados.num_dias)))
        for tempo in range(dados.num_periodos):
            print(f"{tempo + 1:<5}" + "".join(f'{grelha.get((dia, tempo), "-"):<11}' for dia in range(dados.num_dias)))

if __name__ == "__main__":
    import sys
    pasta = Path("data/dados")
    dados = carregar_dados(pasta)  
    agendador = Scheduler(dados)
    agendador.criar_variaveis()
    agendador.aplicar_restricoes()
    agendador.aplicar_objetivo(peso_prof=10, peso_turma=1)  # O1 (+ compactar turmas como desempate)
    agendador.resolver()
    print(f"{len(agendador.sessoes)} sessões | estado: {agendador.solver.status_name(agendador.status)} | {agendador.tempo:.2f}s")
    if agendador.solucao_encontrada():
        horario = agendador.extrair_solucao()
        print(f"buracos: professores={contar_buracos(horario, 'professor')} | turmas={contar_buracos(horario, 'turma')}")
        imprimir_horario(horario, dados)