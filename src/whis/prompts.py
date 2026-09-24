"""Os prompts guardados: `prompts/` no vault, um `.md` por prompt.

O título é o nome do arquivo; o corpo é o prompt; `tags` e `favorito` são
propriedades do Obsidian no frontmatter. Um prompt criado à mão no Obsidian
vale igual a um guardado pela palheta — é por isso que o frontmatter é lido
nos dois formatos de lista que o Obsidian escreve.

`prompts/` é zona do usuário: o agente só escreve a pedido (um arquivo novo,
ou a linha `favorito:`), e nunca reescreve o corpo de um prompt que existe.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from . import vault as _vault

_log = logging.getLogger("whis.prompts")

PASTA_PROMPTS = "prompts"
ZONAS_DOS_PROMPTS = (PASTA_PROMPTS,)

MARCA_DE_FAVORITO = "*"

#: Quanto da primeira linha vira título quando `stash` vem sem título.
TAMANHO_DO_TITULO_PADRAO = 60

_PROIBIDOS_NO_NOME = re.compile(r'[<>:"/\\|?*\x00-\x1f#^\[\]]')


class PromptRecusado(ValueError):
    """Não há o que guardar, ou o título já é de outro prompt."""


@dataclass(frozen=True)
class Prompt:
    titulo: str
    conteudo: str
    caminho: str
    tags: tuple[str, ...] = ()
    favorito: bool = False

    def primeira_linha(self) -> str:
        return next((linha.strip() for linha in self.conteudo.splitlines() if linha.strip()), "")


@dataclass(frozen=True)
class Pedido:
    """O que `stash <título> #tag *` pediu."""

    titulo: str
    tags: tuple[str, ...]
    favorito: bool


def interpretar_pedido(texto: str) -> Pedido:
    tags: list[str] = []
    favorito = False
    palavras: list[str] = []
    for palavra in texto.split():
        if palavra == MARCA_DE_FAVORITO:
            favorito = True
        elif palavra.startswith("#") and len(palavra) > 1:
            tag = palavra[1:]
            if tag not in tags:
                tags.append(tag)
        else:
            palavras.append(palavra)
    return Pedido(" ".join(palavras), tuple(tags), favorito)


# -- ler ------------------------------------------------------------------------


def listar(vault: Path) -> list[Prompt]:
    pasta = Path(vault) / PASTA_PROMPTS
    if not pasta.is_dir():
        return []
    prompts = []
    for arquivo in pasta.rglob("*.md"):
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as erro:
            _log.warning("Prompt ilegível em %s: %s", arquivo, erro)
            continue
        campos, corpo = separar_frontmatter(texto)
        prompts.append(
            Prompt(
                titulo=arquivo.stem,
                conteudo=corpo.strip("\n"),
                caminho=arquivo.relative_to(vault).as_posix(),
                tags=_tags(campos.get("tags")),
                favorito=str(campos.get("favorito", "")).strip().casefold() == "true",
            )
        )
    return ordenar(prompts)


def ordenar(prompts: Sequence[Prompt]) -> list[Prompt]:
    return sorted(prompts, key=lambda prompt: (not prompt.favorito, prompt.titulo.casefold()))


def separar_frontmatter(texto: str) -> tuple[dict[str, object], str]:
    """Os campos do frontmatter e o corpo. Só o que os prompts usam: chaves
    simples, listas em `[a, b]` ou em linhas `- a`."""
    linhas = texto.splitlines()
    if not linhas or linhas[0].strip() != "---":
        return {}, texto
    try:
        fim = next(indice for indice in range(1, len(linhas)) if linhas[indice].strip() == "---")
    except StopIteration:
        return {}, texto
    campos: dict[str, object] = {}
    chave_da_lista: str | None = None
    for linha in linhas[1:fim]:
        item = re.match(r"^\s+-\s*(.*)$", linha)
        if item and chave_da_lista is not None:
            lista = campos.setdefault(chave_da_lista, [])
            if isinstance(lista, list):
                lista.append(_sem_aspas(item[1]))
            continue
        par = re.match(r"^([\w-]+):\s*(.*)$", linha)
        if par is None:
            chave_da_lista = None
            continue
        chave, valor = par[1], par[2].strip()
        chave_da_lista = chave if not valor else None
        if valor.startswith("[") and valor.endswith("]"):
            campos[chave] = [_sem_aspas(parte) for parte in valor[1:-1].split(",") if parte.strip()]
        else:
            campos[chave] = _sem_aspas(valor) if valor else []
    return campos, "\n".join(linhas[fim + 1 :])


def _sem_aspas(texto: str) -> str:
    texto = texto.strip()
    if len(texto) >= 2 and texto[0] == texto[-1] and texto[0] in "\"'":
        return texto[1:-1]
    return texto


def _tags(valor: object) -> tuple[str, ...]:
    if isinstance(valor, str):
        valor = [valor] if valor else []
    if not isinstance(valor, list):
        return ()
    return tuple(str(tag).strip().lstrip("#") for tag in valor if str(tag).strip().lstrip("#"))


# -- filtrar --------------------------------------------------------------------


def filtrar(prompts: Sequence[Prompt], consulta: str) -> list[Prompt]:
    """`#tag` casa pelo começo de uma tag, `*` só favoritos, o resto em título, corpo ou tags.

    Favoritos primeiro; depois quem casa tudo no título; o resto por último.
    """
    tags: list[str] = []
    so_favoritos = False
    palavras: list[str] = []
    for palavra in consulta.casefold().split():
        if palavra == MARCA_DE_FAVORITO:
            so_favoritos = True
        elif palavra.startswith("#") and len(palavra) > 1:
            tags.append(palavra[1:])
        else:
            palavras.append(palavra)

    achados: list[tuple[bool, bool, str, Prompt]] = []
    for prompt in prompts:
        if so_favoritos and not prompt.favorito:
            continue
        minhas = [tag.casefold() for tag in prompt.tags]
        if not all(any(tag.startswith(procurada) for tag in minhas) for procurada in tags):
            continue
        titulo = prompt.titulo.casefold()
        tudo = " ".join((titulo, prompt.conteudo.casefold(), *minhas))
        if not all(palavra in tudo for palavra in palavras):
            continue
        no_titulo = all(palavra in titulo for palavra in palavras)
        achados.append((not prompt.favorito, not no_titulo, titulo, prompt))
    return [prompt for *_ordem, prompt in sorted(achados, key=lambda achado: achado[:3])]


# -- escrever -------------------------------------------------------------------


def nome_de_arquivo(titulo: str) -> str:
    """O título como o Windows e o Obsidian aceitam num nome de arquivo."""
    limpo = _PROIBIDOS_NO_NOME.sub(" ", titulo)
    limpo = " ".join(limpo.split()).strip(" .")
    return limpo


def guardar(vault: Path, pedido: Pedido, conteudo: str) -> Prompt:
    """Um arquivo novo em `prompts/`. Nunca sobrescreve: título repetido é recusa."""
    corpo = conteudo.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not corpo.strip():
        raise PromptRecusado("O clipboard está vazio — copie o prompt e rode de novo.")
    titulo = pedido.titulo.strip() or _titulo_da_primeira_linha(corpo)
    nome = nome_de_arquivo(titulo)
    if not nome:
        raise PromptRecusado(f"'{titulo}' não serve de nome de arquivo — escolha outro título.")
    relativo = f"{PASTA_PROMPTS}/{nome}.md"
    existente = _existente(Path(vault), nome)
    if existente is not None:
        raise PromptJaExiste(nome, existente)

    frontmatter = ["---"]
    if pedido.tags:
        frontmatter += ["tags:", *(f"  - {tag}" for tag in pedido.tags)]
    else:
        frontmatter.append("tags: []")
    frontmatter += [f"favorito: {'true' if pedido.favorito else 'false'}", "---", ""]
    _vault.escrever(
        Path(vault),
        relativo,
        "\n".join(frontmatter) + corpo + "\n",
        zonas=ZONAS_DOS_PROMPTS,
        literal=True,
    )
    return Prompt(nome, corpo, relativo, pedido.tags, pedido.favorito)


class PromptJaExiste(PromptRecusado):
    def __init__(self, titulo: str, caminho: str) -> None:
        super().__init__(f"Já existe um prompt '{titulo}' — escolha outro título ou edite o que existe.")
        self.caminho = caminho


def _existente(vault: Path, nome: str) -> str | None:
    pasta = vault / PASTA_PROMPTS
    if not pasta.is_dir():
        return None
    procurado = nome.casefold()
    for arquivo in pasta.rglob("*.md"):
        if arquivo.stem.casefold() == procurado:
            return arquivo.relative_to(vault).as_posix()
    return None


def _titulo_da_primeira_linha(corpo: str) -> str:
    linha = next((linha.strip() for linha in corpo.splitlines() if linha.strip()), "")
    linha = linha.lstrip("#").strip()
    if len(linha) <= TAMANHO_DO_TITULO_PADRAO:
        return linha
    return linha[:TAMANHO_DO_TITULO_PADRAO].rsplit(" ", 1)[0] or linha[:TAMANHO_DO_TITULO_PADRAO]


def alternar_favorito(vault: Path, prompt: Prompt) -> Prompt:
    """Troca só a linha `favorito:`; o resto do arquivo volta byte a byte."""
    arquivo = Path(vault) / prompt.caminho
    with arquivo.open(encoding="utf-8", newline="") as leitura:
        texto = leitura.read()
    novo = not prompt.favorito
    valor = "true" if novo else "false"
    quebra = "\r\n" if "\r\n" in texto else "\n"
    linhas = texto.split(quebra)

    if linhas and linhas[0].strip() == "---":
        fim = next((i for i in range(1, len(linhas)) if linhas[i].strip() == "---"), None)
        if fim is not None:
            for indice in range(1, fim):
                if re.match(r"^favorito:", linhas[indice]):
                    linhas[indice] = f"favorito: {valor}"
                    break
            else:
                linhas.insert(fim, f"favorito: {valor}")
            texto_novo = quebra.join(linhas)
        else:
            texto_novo = quebra.join(["---", f"favorito: {valor}", "---", ""]) + texto
    else:
        texto_novo = quebra.join(["---", f"favorito: {valor}", "---", ""]) + texto

    _vault.escrever(Path(vault), prompt.caminho, texto_novo, zonas=ZONAS_DOS_PROMPTS, literal=True)
    return Prompt(prompt.titulo, prompt.conteudo, prompt.caminho, prompt.tags, novo)
