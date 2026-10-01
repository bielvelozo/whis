"""Fixtures das costuras do repositório.

Um vault em `tmp_path` e uma configuração local apontada por `WHIS_CONFIG`. A
do diário — `gerar_diario(data) → nota em diario/` — ganha uma configuração
própria, porque a janela do dia e o filtro de exclusão mudam de teste para
teste.

Trocar um fake por um adaptador é injetar outro objeto.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from whis import avisos
from whis.configuracao import VARIAVEL_DE_AMBIENTE, Configuracao, carregar


@pytest.fixture
def caminho_do_vault(tmp_path: Path) -> Path:
    """Onde o vault deve nascer — de propósito, ainda não existe."""
    return tmp_path / "vault"


@pytest.fixture
def arquivo_de_configuracao(
    tmp_path: Path,
    caminho_do_vault: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Escreve um `config.toml` de teste e aponta `WHIS_CONFIG` para ele."""
    arquivo = tmp_path / "config.toml"
    arquivo.write_text(f'vault = "{caminho_do_vault.as_posix()}"\n', encoding="utf-8")
    monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(arquivo))
    return arquivo


@pytest.fixture
def configuracao(arquivo_de_configuracao: Path) -> Configuracao:
    """A configuração como o comando a lê: do disco, pela variável de ambiente."""
    return carregar()


@pytest.fixture
def configuracao_do_diario(
    tmp_path: Path,
    caminho_do_vault: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Fábrica da configuração do diário: `configuracao_do_diario(...)`.

    Escreve um `config.toml` com a janela e o filtro que o teste precisa e
    aponta `WHIS_CONFIG` para ele — assim o mesmo cenário serve à
    costura e ao subcomando.
    """

    def montar(
        *, inicio_do_dia: str = "04:00", excluir: tuple[str, ...] = ()
    ) -> Configuracao:
        linhas = [
            f'vault = "{caminho_do_vault.as_posix()}"',
            "",
            "[diario]",
            f'inicio_do_dia = "{inicio_do_dia}"',
            "",
            "[privacidade]",
            "excluir = [" + ", ".join(f'"{padrao}"' for padrao in excluir) + "]",
            "",
        ]
        arquivo = tmp_path / "config-do-diario.toml"
        arquivo.write_text("\n".join(linhas), encoding="utf-8")
        monkeypatch.setenv(VARIAVEL_DE_AMBIENTE, str(arquivo))
        return carregar(arquivo)

    return montar


#: O `avisar` de verdade, guardado antes de a fixture autouse abaixo trocá-lo:
#: quem testa o disparo em si (com `subprocess.run` espionado) chama por aqui.
AVISAR_DE_VERDADE = avisos.avisar


@pytest.fixture(autouse=True)
def toasts(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, tuple[str, str] | None]]:
    """Nenhum teste mostra um toast de verdade na máquina de quem roda a suíte.

    `main(["daily"])` e a bandeja chamam `avisos.avisar`, que dispara o
    PowerShell e deixa uma notificação na central do Windows. Com dezenas de
    testes nesse caminho, uma execução da suíte enchia a central do usuário —
    e as notificações ficam três dias lá. Quem quer observar o toast troca esta
    função pela sua (`AvisoEspiao`), e o `avisar` de verdade continua testado
    com o executor injetado.
    """
    mostrados: list[tuple[str, str, tuple[str, str] | None]] = []

    def fingir(titulo: str, texto: str, *, botao=None, executar=None) -> bool:
        if executar is not None:
            return AVISAR_DE_VERDADE(titulo, texto, botao=botao, executar=executar)
        mostrados.append((titulo, texto, botao))
        return True

    monkeypatch.setattr(avisos, "avisar", fingir)
    return mostrados


@pytest.fixture(autouse=True)
def area_de_transferencia_trancada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum teste lê, troca ou cola no clipboard de quem roda a suíte.

    Colar um prompt manda Ctrl+V para a janela que estiver ativa — numa
    execução da suíte, a do usuário. Quem testa a lista de prompts injeta uma
    área fake; chegar na de verdade é erro do teste.
    """
    from whis import area_de_transferencia

    def recusar(*_argumentos, **_nomeados):
        raise AssertionError("teste chegou no clipboard de verdade — injete uma área fake")

    monkeypatch.setattr(area_de_transferencia, "lembrar_janela_anterior", lambda: None)
    for nome in ("ler", "copiar", "colar"):
        monkeypatch.setattr(area_de_transferencia, nome, recusar)


@pytest.fixture(autouse=True)
def navegador_trancado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum teste abre o Chrome com a conta do X de quem roda a suíte.

    O modelo de `fontes.md` tem linhas `x:`; quem chega no leitor de verdade
    abriria o perfil do Whis e navegaria no X. Quem testa o jornal injeta um
    `LeitorDoXFake`.
    """
    from whis import fonte_x

    def recusar():
        raise AssertionError("teste chegou no navegador de verdade — injete um LeitorDoXFake")

    monkeypatch.setattr(fonte_x, "_playwright", recusar)
