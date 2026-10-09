"""Funções auxiliares dos testes: criar variantes dos CSV sem mexer nos originais."""
import shutil

from src.loader import DATA_DIR, carregar_dados


def variante(tmp_path, editar, origem="dados", **kw):
    """Copia data/<origem> para uma pasta temporária, aplica `editar(pasta)` e carrega."""
    pasta = tmp_path / "variante"
    shutil.copytree(DATA_DIR / origem, pasta)
    editar(pasta)
    return carregar_dados(pasta, **kw)


def anexar(ficheiro, texto):
    with open(ficheiro, "a", encoding="utf-8") as f:
        f.write(texto)


def substituir(ficheiro, antigo, novo):
    conteudo = ficheiro.read_text(encoding="utf-8")
    assert antigo in conteudo, f"{antigo!r} não existe em {ficheiro.name}"
    ficheiro.write_text(conteudo.replace(antigo, novo), encoding="utf-8")


def encontrar(horario, **criterios):
    """Primeira aula que satisfaz todos os critérios (ex.: turma='7ºA', disciplina='Matemática')."""
    return next(h for h in horario if all(h[k] == v for k, v in criterios.items()))
