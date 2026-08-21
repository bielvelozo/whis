"""Leitura do que o pipeline escreveu — o lado 'comportamento externo' dos testes."""

from __future__ import annotations

from pathlib import Path


def ler_frontmatter(arquivo: Path) -> dict[str, object]:
    """Extrai o frontmatter YAML de uma nota como dicionário simples.

    Só entende o que o vault escreve: escalares citados ou não e listas
    inline. Não é um parser de YAML — é um leitor de asserção.
    """
    linhas = arquivo.read_text(encoding="utf-8").splitlines()
    if not linhas or linhas[0] != "---":
        raise AssertionError(f"{arquivo} não começa com frontmatter")
    campos: dict[str, object] = {}
    for linha in linhas[1:]:
        if linha == "---":
            return campos
        chave, _, valor = linha.partition(":")
        campos[chave.strip()] = _valor(valor.strip())
    raise AssertionError(f"Frontmatter de {arquivo} não foi fechado")


def corpo(arquivo: Path) -> str:
    """O markdown depois do frontmatter."""
    texto = arquivo.read_text(encoding="utf-8")
    partes = texto.split("---\n", 2)
    return partes[2] if len(partes) == 3 else texto


def arquivos_do_vault(vault: Path) -> set[str]:
    """Todos os arquivos do vault, como caminhos relativos com barra normal."""
    return {
        caminho.relative_to(vault).as_posix()
        for caminho in Path(vault).rglob("*")
        if caminho.is_file()
    }


def _valor(bruto: str) -> object:
    if bruto.startswith("[") and bruto.endswith("]") and not bruto.startswith("[["):
        interior = bruto[1:-1].strip()
        if not interior:
            return []
        return [_sem_aspas(item.strip()) for item in interior.split(",")]
    return _sem_aspas(bruto)


def _sem_aspas(texto: str) -> str:
    if len(texto) >= 2 and texto[0] == texto[-1] and texto[0] in "\"'":
        return texto[1:-1]
    return texto
