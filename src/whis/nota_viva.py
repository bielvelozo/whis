"""A nota viva `daily/atual.md`: o texto que ele escreve e de onde sai a daily.

Este módulo só conhece texto. Ele lê a nota como uma sequência de linhas, acha
as cinco seções e as linhas dentro delas, e faz as escritas do agente ali, todas
a pedido dele: **anotar** uma linha (`did`, `doing`, `note`, `doubt`, `do`),
**concluir** um item de *O que estou fazendo*, que vai para *O que eu fiz*
(`done`), e **abrir** o título de uma seção que falte. O resto da nota é dele;
quem a lê para o deck é `deck.py`, e quem lê e grava o arquivo é `vault.py`.

A regra que governa tudo aqui: cada linha que já está na nota sai **byte a
byte** igual — inclusive os espaços à direita, as linhas em branco dentro de
uma seção e a indentação por tab. Por isso a nota é guardada como linhas cruas
e toda edição insere ou remove linhas inteiras, nunca reescreve uma.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

TIPO_NOTA_VIVA = "daily-atual"

SECAO_FIZ = "O que eu fiz"
SECAO_FAZENDO = "O que estou fazendo"
SECAO_FAZER = "Fazer"
SECAO_DUVIDAS = "Dúvidas"
SECAO_PONTOS = "Pontos"

SECOES = (
    SECAO_FIZ,
    SECAO_FAZENDO,
    SECAO_FAZER,
    SECAO_DUVIDAS,
    SECAO_PONTOS,
)

SECOES_ANOTAVEIS = (SECAO_FIZ, SECAO_FAZENDO, SECAO_FAZER, SECAO_DUVIDAS, SECAO_PONTOS)

SECOES_COM_CAIXA = (SECAO_FAZER,)

CAIXA = "[ ] "

#: Só o frontmatter e os títulos: ele sabe o que cada seção é (ticket 13).
MODELO_DA_NOTA_VIVA = f"""\
---
tipo: {TIPO_NOTA_VIVA}
---

## O que eu fiz

## O que estou fazendo

## Fazer

## Dúvidas

## Pontos
"""

_ITEM = re.compile(r"^(?P<indentacao>[ \t]*)(?P<marcador>[-*+]|\d+[.)])[ \t]+(?P<texto>.*)$")

#: Um marcador sem texto (`-`, `1.`): o item vazio que o Obsidian deixa ao dar Enter.
_SO_MARCADOR = re.compile(r"^[ \t]*([-*+]|\d+[.)])[ \t]*$")

#: Só `#` e `##` delimitam seção; `###` fica dentro dela.
_TITULO = re.compile(r"^#{1,2}[ \t]+(?P<titulo>.*?)[ \t]*$")

_TAB = 4


@dataclass
class _Bloco:
    titulo: str | None
    linhas: list[str]


@dataclass(frozen=True)
class Item:
    """Um item de lista de uma seção, com a subárvore que viaja com ele.

    `linhas` são a linha do item e tudo o que está mais indentado embaixo dela,
    literais, sem as linhas em branco do fim. `inicio` é a posição da linha do
    item no corpo da seção (as linhas sem o título); `ancestrais` são os
    `inicio` dos itens que o contêm, de fora para dentro.
    """

    texto: str
    linhas: tuple[str, ...]
    inicio: int
    ancestrais: tuple[int, ...]

    @property
    def linha(self) -> str:
        return self.linhas[0]

    @property
    def fim(self) -> int:
        return self.inicio + len(self.linhas)


class NotaViva:
    """A nota viva como texto editável, guardada linha a linha.

    A quebra de linha do arquivo é detectada e devolvida como veio, para o
    Obsidian e o hash não verem diferença.
    """

    def __init__(self, linhas: Sequence[str], quebra: str = "\n") -> None:
        self._quebra = quebra
        self._blocos = _blocos(list(linhas))

    @classmethod
    def de_texto(cls, texto: str) -> NotaViva:
        quebra = "\r\n" if "\r\n" in texto else "\n"
        return cls(texto.replace("\r\n", "\n").split("\n"), quebra)

    @classmethod
    def do_modelo(cls) -> NotaViva:
        return cls.de_texto(MODELO_DA_NOTA_VIVA)

    def texto(self) -> str:
        return self._quebra.join(linha for bloco in self._blocos for linha in bloco.linhas)

    def tem_secao(self, titulo: str) -> bool:
        return self._bloco(titulo) is not None

    def conteudo(self, titulo: str) -> tuple[str, ...]:
        """As linhas de uma seção, sem as em branco das pontas. `()` se não existe."""
        bloco = self._bloco(titulo)
        return sem_brancos_nas_pontas(_corpo(bloco)) if bloco else ()

    def secoes(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        return tuple((secao, self.conteudo(secao)) for secao in SECOES)

    def acrescentar(self, titulo: str, texto: str) -> tuple[str, ...]:
        """`- texto` no fim de uma seção, aberta no lugar dela se faltar."""
        bloco = self._bloco(titulo) or self._abrir_secao(titulo)
        item_novo = f"- {texto.strip()}"
        bloco.linhas.insert(1 + _fim_do_conteudo(_corpo(bloco)), item_novo)
        return (item_novo,)

    def garantir_secao(self, titulo: str) -> bool:
        """Abre `## titulo` vazio no lugar dele, se faltar. `True` quando abriu."""
        if self._bloco(titulo) is not None:
            return False
        self._abrir_secao(titulo)
        return True

    def anotar(self, texto: str, secao: str = SECAO_PONTOS) -> str:
        """`- texto` no fim de uma seção que tem comando (`did`, `doing`, `note`, `doubt`, `do`), a pedido dele.

        Em *Fazer* o item nasce `- [ ] texto`: a caixa é dele, e marcá-la é o
        gesto que fecha a tarefa. O agente nunca mais volta nessa linha.
        """
        if _chave(secao) not in {_chave(anotavel) for anotavel in SECOES_ANOTAVEIS}:
            raise ValueError(f"Só se anota em {' ou '.join(SECOES_ANOTAVEIS)}; {secao!r} não tem comando.")
        com_caixa = _chave(secao) in {_chave(secao_marcavel) for secao_marcavel in SECOES_COM_CAIXA}
        return self.acrescentar(secao, f"{CAIXA}{texto.strip()}" if com_caixa else texto)[0]

    def itens(self, titulo: str) -> tuple[Item, ...]:
        """Os itens de lista de uma seção, os aninhados inclusive, na ordem da nota."""
        bloco = self._bloco(titulo)
        return _itens(_corpo(bloco)) if bloco else ()

    def concluir(self, posicao: int, linha: str) -> tuple[str, ...] | None:
        """Leva um item de *O que estou fazendo* para *O que eu fiz*, a pedido dele (`done`).

        O item é reencontrado pela linha literal na `posicao` do corpo, ou pela
        linha literal se ela for única na seção: ele pode ter mexido na nota
        desde que a lista foi lida. Sem item, `None` e nada muda. A subárvore
        sai inteira e literal; os pais ficam, e entram em *O que eu fiz* como
        cabeçalho, sem repetir um elo que já esteja lá. Devolve as linhas que
        entraram em *O que eu fiz*.
        """
        item = self._reencontrar(SECAO_FAZENDO, posicao, linha)
        if item is None:
            return None
        por_inicio = {candidato.inicio: candidato for candidato in self.itens(SECAO_FAZENDO)}
        cadeia = (*(por_inicio[inicio] for inicio in item.ancestrais), item)
        origem = self._bloco(SECAO_FAZENDO)
        assert origem is not None
        del origem.linhas[1 + item.inicio : 1 + item.fim]

        entraram, elo = self._garantir_cadeia(SECAO_FIZ, cadeia)
        destino = self._bloco(SECAO_FIZ)
        assert destino is not None
        filhos = list(item.linhas[1:])
        destino.linhas[1 + elo.fim : 1 + elo.fim] = filhos
        return (*entraram, *filhos)

    def _reencontrar(self, titulo: str, posicao: int, linha: str) -> Item | None:
        itens = self.itens(titulo)
        no_lugar = next((item for item in itens if item.inicio == posicao and item.linha == linha), None)
        if no_lugar is not None:
            return no_lugar
        iguais = [item for item in itens if item.linha == linha]
        return iguais[0] if len(iguais) == 1 else None

    def _garantir_cadeia(self, titulo: str, cadeia: Sequence[Item]) -> tuple[tuple[str, ...], Item]:
        """Cada elo em `titulo` como filho direto do anterior; o que falta entra com a linha literal.

        Devolve as linhas que entraram e o último elo como está na seção.
        """
        bloco = self._bloco(titulo) or self._abrir_secao(titulo)
        entraram: list[str] = []
        pai: Item | None = None
        for elo in cadeia:
            existente = self._filho(titulo, pai, elo.texto)
            if existente is None:
                posicao = pai.fim if pai else _fim_do_conteudo(_corpo(bloco))
                bloco.linhas.insert(1 + posicao, elo.linha)
                entraram.append(elo.linha)
                existente = next(item for item in self.itens(titulo) if item.inicio == posicao)
            pai = existente
        assert pai is not None
        return tuple(entraram), pai

    def _filho(self, titulo: str, pai: Item | None, texto: str) -> Item | None:
        """O item de `texto` filho direto de `pai`, ou de nível raiz sem pai."""
        esperado = (pai.inicio,) if pai else ()
        return next(
            (item for item in self.itens(titulo) if item.texto == texto and item.ancestrais[-1:] == esperado),
            None,
        )

    def _bloco(self, titulo: str) -> _Bloco | None:
        chave = _chave(titulo)
        for bloco in self._blocos:
            if bloco.titulo is not None and _chave(bloco.titulo) == chave:
                return bloco
        return None

    def _abrir_secao(self, titulo: str) -> _Bloco:
        """Uma seção nova no lugar dela na ordem das sete; no fim, se nenhuma vem depois.

        Só linhas inteiras entram: uma em branco antes do título, quando a seção
        anterior não a tem.
        """
        seguinte = self._bloco_seguinte(titulo)
        if seguinte is not None:
            posicao = self._blocos.index(seguinte)
            anterior = self._blocos[posicao - 1].linhas
            if anterior and anterior[-1] != "":
                anterior.append("")
            bloco = _Bloco(titulo, [f"## {titulo}", ""])
            self._blocos.insert(posicao, bloco)
            return bloco

        ultimo = self._blocos[-1].linhas
        termina_em_quebra = bool(ultimo) and ultimo[-1] == ""
        if termina_em_quebra:
            ultimo.pop()
        if ultimo and ultimo[-1] != "":
            ultimo.append("")
        bloco = _Bloco(titulo, [f"## {titulo}", ""] if termina_em_quebra else [f"## {titulo}"])
        self._blocos.append(bloco)
        return bloco

    def _bloco_seguinte(self, titulo: str) -> _Bloco | None:
        ordem = [_chave(secao) for secao in SECOES]
        if _chave(titulo) not in ordem:
            return None
        for secao in SECOES[ordem.index(_chave(titulo)) + 1 :]:
            bloco = self._bloco(secao)
            if bloco is not None:
                return bloco
        return None


def _blocos(linhas: list[str]) -> list[_Bloco]:
    blocos = [_Bloco(None, [])]
    for linha in linhas:
        titulo = _TITULO.match(linha)
        if titulo is not None:
            blocos.append(_Bloco(titulo["titulo"], []))
        blocos[-1].linhas.append(linha)
    return blocos


def _corpo(bloco: _Bloco) -> list[str]:
    return bloco.linhas[1:] if bloco.titulo is not None else bloco.linhas


def _fim_do_conteudo(corpo: Sequence[str]) -> int:
    for indice in range(len(corpo) - 1, -1, -1):
        if corpo[indice].strip():
            return indice + 1
    return 0


def _itens(corpo: Sequence[str]) -> tuple[Item, ...]:
    itens: list[Item] = []
    abertos: list[tuple[int, int]] = []
    for indice, linha in enumerate(corpo):
        if not linha.strip():
            continue
        nivel = _nivel(linha)
        while abertos and abertos[-1][0] >= nivel:
            abertos.pop()
        partes = _ITEM.match(linha)
        if partes is None or not partes["texto"].strip():
            continue
        fim = _fim_da_subarvore(corpo, indice, nivel)
        ancestrais = tuple(inicio for _, inicio in abertos)
        itens.append(Item(partes["texto"].strip(), tuple(corpo[indice:fim]), indice, ancestrais))
        abertos.append((nivel, indice))
    return tuple(itens)


def _fim_da_subarvore(corpo: Sequence[str], inicio: int, nivel: int) -> int:
    """Onde acaba o que pertence ao item: a última linha mais indentada que ele."""
    fim = inicio + 1
    for indice in range(inicio + 1, len(corpo)):
        linha = corpo[indice]
        if not linha.strip():
            continue
        if _nivel(linha) <= nivel:
            break
        fim = indice + 1
    return fim


def _nivel(linha: str) -> int:
    indentacao = linha[: len(linha) - len(linha.lstrip(" \t"))]
    return len(indentacao.expandtabs(_TAB))


def texto_e_profundidade(linhas: Sequence[str]) -> tuple[tuple[str, int], ...]:
    """Cada linha com texto como `(texto, profundidade)`, para quem só lê a seção.

    O texto vem sem o marcador de lista e sem o recuo; uma linha que não é item
    entra inteira. A profundidade conta as linhas abertas acima dela, pela
    mesma régua de recuo de `_nivel` (tab = 4 colunas).
    """
    resultado: list[tuple[str, int]] = []
    colunas: list[int] = []
    for linha in linhas:
        if _SO_MARCADOR.match(linha):
            continue
        partes = _ITEM.match(linha)
        texto = (partes["texto"] if partes else linha).strip()
        if not texto:
            continue
        coluna = _nivel(linha)
        while colunas and colunas[-1] >= coluna:
            colunas.pop()
        resultado.append((texto, len(colunas)))
        colunas.append(coluna)
    return tuple(resultado)


def sem_brancos_nas_pontas(linhas: Sequence[str]) -> tuple[str, ...]:
    inicio, fim = 0, len(linhas)
    while inicio < fim and not linhas[inicio].strip():
        inicio += 1
    while fim > inicio and not linhas[fim - 1].strip():
        fim -= 1
    return tuple(linhas[inicio:fim])


def contem(texto: str, busca: str) -> bool:
    """`busca` aparece em `texto`, sem diferenciar maiúscula nem acento."""
    return _chave(busca) in _chave(texto)


def _chave(titulo: str) -> str:
    """`O que eu fiz `, `o que eu FIZ` e `Duvidas`/`Dúvidas` são a mesma seção."""
    decomposto = unicodedata.normalize("NFKD", titulo)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())
