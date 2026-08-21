"""Escrita no vault: estrutura de pastas, nota de reunião e transcrição.

A zona de propriedade é uma invariante deste módulo, não só dos testes:
`escrever` recusa qualquer caminho fora de `reunioes/` e `transcricoes/`.
`notas/` (a zona do usuário) e `diario/` (de um coletor futuro) são criadas
na primeira execução e nunca mais tocadas por este pipeline.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .portas import Resumo, Transcricao

_log = logging.getLogger("second_brain.vault")

PASTA_REUNIOES = "reunioes"
PASTA_TRANSCRICOES = "transcricoes"
PASTA_DIARIO = "diario"
PASTA_NOTAS = "notas"

#: Todas as pastas criadas na primeira execução.
ESTRUTURA = (PASTA_REUNIOES, PASTA_TRANSCRICOES, PASTA_DIARIO, PASTA_NOTAS)

#: As únicas pastas em que o coletor de reunião pode escrever.
ZONAS_DE_ESCRITA = (PASTA_REUNIOES, PASTA_TRANSCRICOES)

#: Valor do campo `tipo` no frontmatter de cada artefato.
TIPO_REUNIAO = "reuniao"
TIPO_TRANSCRICAO = "transcricao"


class ForaDaZonaDePropriedade(RuntimeError):
    """Tentativa de escrever fora de `reunioes/` ou `transcricoes/`."""


def preparar(vault: Path) -> Path:
    """Cria o vault e sua estrutura se ainda não existirem. Idempotente."""
    vault = Path(vault)
    if not vault.exists():
        _log.info("Criando o vault em %s", vault)
    vault.mkdir(parents=True, exist_ok=True)
    for pasta in ESTRUTURA:
        alvo = vault / pasta
        if not alvo.exists():
            _log.info("Criando a pasta %s/ no vault", pasta)
        alvo.mkdir(exist_ok=True)
    return vault


def escrever(vault: Path, relativo: str, conteudo: str) -> Path:
    """Escreve um arquivo no vault, recusando caminhos fora da zona de escrita.

    A checagem é feita no caminho **resolvido**: não basta começar com o nome
    de uma zona, o arquivo precisa terminar dentro dela. Assim `..` no meio do
    caminho não escapa para `notas/` nem para fora do vault.
    """
    raiz = Path(vault)
    caminho_relativo = Path(relativo)
    if not relativo or caminho_relativo.is_absolute() or not caminho_relativo.parts:
        raise ForaDaZonaDePropriedade(_recusa(relativo))

    zona = caminho_relativo.parts[0]
    if zona not in ZONAS_DE_ESCRITA:
        raise ForaDaZonaDePropriedade(_recusa(relativo))

    pasta_da_zona = (raiz / zona).resolve()
    alvo = (raiz / caminho_relativo).resolve()
    if alvo == pasta_da_zona or not alvo.is_relative_to(pasta_da_zona):
        raise ForaDaZonaDePropriedade(_recusa(relativo))

    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(conteudo, encoding="utf-8")
    _log.info("Escrito no vault: %s", relativo)
    return alvo


def _recusa(relativo: str) -> str:
    zonas = ", ".join(f"{zona}/" for zona in ZONAS_DE_ESCRITA)
    return (
        f"O coletor de reunião só escreve em {zonas} — recusado: {relativo!r}"
    )


def caminho_da_nota(basename: str) -> str:
    """Caminho relativo da nota de reunião, no formato do contrato."""
    return f"{PASTA_REUNIOES}/{basename}.md"


def caminho_da_transcricao(basename: str) -> str:
    """Caminho relativo da transcrição, com o mesmo basename da nota."""
    return f"{PASTA_TRANSCRICOES}/{basename}.md"


def wikilink(caminho_relativo: str) -> str:
    """Wikilink do Obsidian para um caminho do vault, sem a extensão.

    Usa o caminho e não só o nome porque nota e transcrição compartilham o
    basename — o link curto seria ambíguo dentro do vault.
    """
    return f"[[{caminho_relativo.removesuffix('.md')}]]"


def montar_nota(
    *,
    basename: str,
    data: str,
    titulo: str,
    participantes: tuple[str, ...],
    resumo: Resumo,
) -> str:
    """Monta o markdown da nota de reunião: frontmatter mínimo + resumo."""
    frontmatter = _frontmatter(
        {
            "data": data,
            "tipo": TIPO_REUNIAO,
            "participantes": list(participantes),
            "transcricao": wikilink(caminho_da_transcricao(basename)),
        }
    )
    corpo = [
        f"# {titulo}",
        "",
        "## Decisões",
        "",
        _lista(resumo.decisoes),
        "",
        "## Ações e pendências",
        "",
        _lista(resumo.acoes),
        "",
        "## Tópicos",
        "",
        _lista(resumo.topicos),
        "",
        "---",
        "",
        f"Transcrição completa: {wikilink(caminho_da_transcricao(basename))}",
        "",
    ]
    return frontmatter + "\n".join(corpo)


def montar_transcricao(
    *,
    basename: str,
    data: str,
    titulo: str,
    transcricao: Transcricao,
) -> str:
    """Monta o markdown da transcrição bruta, uma fala por parágrafo."""
    frontmatter = _frontmatter(
        {
            "data": data,
            "tipo": TIPO_TRANSCRICAO,
            "idioma": transcricao.idioma,
            "reuniao": wikilink(caminho_da_nota(basename)),
        }
    )
    corpo = [f"# Transcrição — {titulo}", ""]
    for fala in transcricao.falas:
        corpo.append(f"**{fala.falante}:** {fala.texto}")
        corpo.append("")
    return frontmatter + "\n".join(corpo)


def _frontmatter(campos: dict[str, object]) -> str:
    linhas = ["---"]
    for chave, valor in campos.items():
        linhas.append(f"{chave}: {_valor_yaml(valor)}")
    linhas.extend(["---", ""])
    return "\n".join(linhas) + "\n"


def _valor_yaml(valor: object) -> str:
    if isinstance(valor, list):
        return "[" + ", ".join(_texto_yaml(str(item)) for item in valor) + "]"
    return _texto_yaml(str(valor))


def _texto_yaml(texto: str) -> str:
    """Datas simples ficam sem aspas; o resto é sempre citado.

    Wikilinks precisam de aspas: `[[x]]` sem elas seria lista aninhada em YAML.
    """
    if texto and all(c.isalnum() or c in "-_" for c in texto) and not texto[0].isdigit():
        return texto
    if _parece_data(texto):
        return texto
    return '"' + texto.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _parece_data(texto: str) -> bool:
    partes = texto.split("-")
    return len(partes) == 3 and all(parte.isdigit() for parte in partes)


def _lista(itens: tuple[str, ...]) -> str:
    if not itens:
        return "_(nada registrado)_"
    return "\n".join(f"- {item}" for item in itens)
