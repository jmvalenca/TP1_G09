from pathlib import Path 
import pandas as pd 

from .models import DIAS, Dados, Disciplina, Indisponibilidade, Sala

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def ler_dados(pasta: Path, nome: str, obrigatorio: bool = True) -> pd.DataFrame:
    """Lê um ficheiro CSV e devolve um DataFrame. Se não existir, devolve None."""
    caminho = pasta / f"{nome}.csv"
    if not caminho.exists():
        if obrigatorio:
            raise FileNotFoundError(f"Ficheiro {caminho} não encontrado.")
        return pd.DataFrame()
    df = pd.read_csv(caminho, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]  # remove espaços dos nomes das colunas
    return df

def sim_nao(val: str, contexto: str) -> bool:
    """Converte 'sim'/'nao' em True/False. Lança ValueError se não for nenhum dos dois."""
    v = val.lower()
    if v not in ("sim", "nao", "não"):
        raise ValueError(f"{contexto}: esperado 'sim' ou 'nao', recebi {val!r}")
    return v == "sim"

def carregar_dados(pasta=DATA_DIR, num_dias: int = 5, num_periodos: int = 8) -> Dados:
    pasta = Path(pasta)
 
    turmas = ler_dados(pasta, "turmas")["turma"].tolist()
 
    salas = [Sala(str(r.sala), str(r.tipo), int(str(r.quantidade))) for r in ler_dados(pasta, "salas").itertuples()]
    for sala in salas:
        if sala.tipo not in ("normal", "especial"):
            raise ValueError(f"Sala {sala.nome}: tipo inválido {sala.tipo!r}")
    especiais = {sala.nome for sala in salas if sala.tipo == "especial"}
 
    disciplinas = []
    for r in ler_dados(pasta, "disciplinas").itertuples():
        sala_especial = str(r.sala_especial) if str(r.sala_especial) else None
        if sala_especial and sala_especial not in especiais:
            raise ValueError(f"{r.disciplina}: sala especial {sala_especial!r} não existe em salas.csv")
        disciplinas.append(Disciplina(str(r.disciplina), str(r.professor), int(str(r.carga_semanal)),
                                      sim_nao(str(r.duplo_periodo), str(r.disciplina)), sala_especial))
 
    dias = {nome: i for i, nome in enumerate(list(DIAS)[:num_dias])}
    indisponibilidades = []
    excecoes = ler_dados(pasta, "disponibilidade_excecoes", obrigatorio=False)
    for r in excecoes.itertuples():
        periodo = int(str(r.periodo))
        if r.dia not in dias or not 1 <= periodo <= num_periodos:
            raise ValueError(f"Exceção inválida: {r.professor}, {r.dia}, {r.periodo}")
        indisponibilidades.append(Indisponibilidade(str(r.professor), dias[str(r.dia)], periodo - 1))
 
    return Dados(turmas, disciplinas, salas, indisponibilidades, num_dias, num_periodos)