from dataclasses import dataclass

DIAS = ("Seg", "Ter", "Qua", "Qui", "Sex")  # tuplo: a ordem importa (um set é desordenado)
NORMAL = "normal"  # Nome do tipo de sala para aulas sem sala especial


@dataclass(frozen=True)
class Disciplina:
    nome: str
    professor: str
    carga_semanal: int
    duplo_periodo: bool
    sala_especial: str | None  # None => sala normal


@dataclass(frozen=True)
class Sala:
    nome: str
    tipo: str  # "normal" | "especial"
    quantidade: int


@dataclass(frozen=True)
class Indisponibilidade:
    professor: str
    dia: int      # 0-based (0 = Seg)
    periodo: int  # 0-based (0 = 1.º tempo)


@dataclass(frozen=True)
class Sessao:
    """Uma unidade a marcar no horário: 1 tempo, ou 1 bloco de 2 tempos (duplo)."""
    id: str          # estável entre execuções: "turma|disciplina|indice"
    turma: str
    disciplina: str
    professor: str
    duracao: int     # 1 ou 2
    tipo_sala: str   # NORMAL ou o nome da sala especial


@dataclass
class Dados:
    turmas: list[str]
    disciplinas: list[Disciplina]
    salas: list[Sala]
    indisponibilidades: list[Indisponibilidade]
    num_dias: int = 5
    num_periodos: int = 5

    def capacidades(self) -> dict[str, int]:
        """Nº máximo de aulas em simultâneo por tipo de sala (R7)."""
        capacidade_por_tipo: dict[str, int] = {}
        for sala in self.salas:
            tipo = NORMAL if sala.tipo == "normal" else sala.nome
            capacidade_por_tipo[tipo] = capacidade_por_tipo.get(tipo, 0) + sala.quantidade
        return capacidade_por_tipo

    def nomes_salas(self, tipo_sala: str) -> list[str]:
        """Salas físicas de um tipo (ex.: 'Sala Normal 1'..'Sala Normal 6')."""
        nomes = []
        for sala in self.salas:
            if (tipo_sala == NORMAL and sala.tipo == "normal") or (tipo_sala != NORMAL and sala.nome == tipo_sala):
                nomes += [sala.nome] if sala.quantidade == 1 else [f"{sala.nome} {i + 1}" for i in range(sala.quantidade)]
        return nomes


def gerar_sessoes(dados: Dados) -> list[Sessao]:
    """Turmas × disciplinas -> sessões. Duplo período: carga/2 blocos de 2 tempos."""
    sessoes = []
    for turma in dados.turmas:
        for disciplina in dados.disciplinas:
            if disciplina.duplo_periodo:
                if disciplina.carga_semanal % 2:
                    raise ValueError(f"{disciplina.nome}: duplo_periodo exige carga par (tem {disciplina.carga_semanal})")
                n_sessoes, duracao = disciplina.carga_semanal // 2, 2
            else:
                n_sessoes, duracao = disciplina.carga_semanal, 1
            for indice in range(n_sessoes):
                sessoes.append(Sessao(f"{turma}|{disciplina.nome}|{indice}", turma, disciplina.nome,
                                      disciplina.professor, duracao, disciplina.sala_especial or NORMAL))
    return sessoes
