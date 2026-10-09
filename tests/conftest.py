import copy
import pytest

from src.incremental import resolver_do_zero
from src.loader import DATA_DIR, carregar_dados


@pytest.fixture(scope="session")
def dados0():
    return carregar_dados(DATA_DIR / "dados")


@pytest.fixture(scope="session")
def dados1():
    return carregar_dados(DATA_DIR / "dados_v2")


@pytest.fixture(scope="session")
def h0(dados0):
    return resolver_do_zero(dados0)["horario"]


@pytest.fixture
def horario(h0):
    """Cópia de H0 que cada teste pode estragar à vontade."""
    return copy.deepcopy(h0)
