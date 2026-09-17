"""A nota viva `daily/atual.md`: o texto que agente e usuário mantêm juntos.

Este módulo só conhece texto. Ele lê a nota como uma sequência de linhas,
acha as quatro seções e os itens de lista dentro delas, e faz as três únicas
coisas que o agente pode fazer ali: **acrescentar** um item, **mover** um item
de *O que estou fazendo* para *O que eu fiz* e **arquivar** *O que eu fiz*
quando a janela da daily muda. Quem decide o quê é a costura (`daily.py`);
quem lê e grava o arquivo é `vault.py`.

A regra que governa tudo aqui é a da entrega: cada linha que já está na nota
sai **byte a byte** igual ao que entrou — inclusive os espaços à direita, as
linhas em branco dentro de uma seção e a indentação por tab. Por isso a nota é
guardada como linhas cruas e nunca é "normalizada": toda edição é uma inserção
ou uma remoção de linhas inteiras, nunca a reescrita de uma.
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .portas import Daily

_log = logging.getLogger("whis.nota_viva")

#: Valor do campo `tipo` no frontmatter da nota viva.
TIPO_NOTA_VIVA = "daily-atual"

SECAO_FIZ = "O que eu fiz"
SECAO_FAZENDO = "O que estou fazendo"
SECAO_DUVIDAS = "Dúvidas"
SECAO_PONTOS = "Pontos"
SECAO_FALAR = "Falar"

#: As cinco seções, na ordem em que a nota as tem.
SECOES = (SECAO_FIZ, SECAO_FAZENDO, SECAO_DUVIDAS, SECAO_PONTOS, SECAO_FALAR)

#: As seções que o agente mantém — as únicas em que ele escreve sozinho.
SECOES_DO_AGENTE = (SECAO_FIZ, SECAO_FAZENDO)

#: As seções do usuário em que `anotar` pode acrescentar, a pedido dele.
SECOES_ANOTAVEIS = (SECAO_PONTOS, SECAO_DUVIDAS)

#: O arquivo que nasce quando ainda não há nota viva no vault: só o
#: frontmatter e os títulos. O usuário sabe o que cada seção é (ticket 13).
MODELO_DA_NOTA_VIVA = f"""\
---
tipo: {TIPO_NOTA_VIVA}
---

## O que eu fiz

## O que estou fazendo

## Dúvidas

## Pontos

## Falar
"""

#: Um item de lista markdown: `- `, `* `, `+ `, `1. ` ou `1) `, com qualquer indentação.
_ITEM = re.compile(r"^(?P<indentacao>[ \t]*)(?P<marcador>[-*+]|\d+[.)])[ \t]+(?P<texto>.*)$")

#: O título que abre uma seção: só `#` e `##` delimitam; `###` fica dentro.
_TITULO = re.compile(r"^#{1,2}[ \t]+(?P<titulo>.*?)[ \t]*$")

#: Quantas colunas um tab ocupa ao comparar níveis de indentação.
_TAB = 4

#: A indentação de um sub-item novo quando o pai ainda não tem filhos.
_UM_NIVEL = "\t"

_ID = re.compile(r"[0-9a-f]{6}")


@dataclass(frozen=True)
class Item:
    """Um item de lista de uma seção, com a subárvore que viaja com ele.

    `inicio` e `fim` delimitam a subárvore dentro das linhas da seção: a
    própria linha mais tudo que está indentado embaixo dela, sem as linhas em
    branco do fim. `ancestrais` são os `inicio` dos itens que o contêm, do mais
    externo ao mais próximo.
    """

    id: str
    texto: str
    linha: str
    indentacao: str
    nivel: int
    inicio: int
    fim: int
    ancestrais: tuple[int, ...]


@dataclass(frozen=True)
class Mudancas:
    """O que uma resposta do modelo fez na nota — para a nota datada e o log.

    `acrescentadas` e `movidas` são blocos de linhas literais, na ordem em que
    entraram. `ignorados` são as referências que apontavam para item nenhum;
    `repetidos`, os textos que o modelo devolveu e já estavam na nota.
    """

    acrescentadas: tuple[tuple[str, ...], ...] = ()
    movidas: tuple[tuple[str, ...], ...] = ()
    ignorados: tuple[str, ...] = ()
    repetidos: tuple[str, ...] = ()

    def vazia(self) -> bool:
        return not (self.acrescentadas or self.movidas)


@dataclass
class _Bloco:
    """Um trecho da nota: o que vem antes do primeiro título, ou um título e o corpo dele."""

    titulo: str | None
    linhas: list[str]


class NotaViva:
    """A nota viva como texto editável, guardada linha a linha.

    `de_texto` lê qualquer markdown — inclusive a nota datada, que compartilha
    a mesma gramática de seções. A quebra de linha do arquivo é detectada e
    devolvida como veio, para o Obsidian e o hash não verem diferença.
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

    # -- leitura -----------------------------------------------------------

    def tem_secao(self, titulo: str) -> bool:
        return self._bloco(titulo) is not None

    def conteudo(self, titulo: str) -> tuple[str, ...]:
        """As linhas de uma seção, sem as em branco das pontas. `()` se não existe."""
        bloco = self._bloco(titulo)
        return sem_brancos_nas_pontas(_corpo(bloco)) if bloco else ()

    def secoes(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """As quatro seções da nota, na ordem de falar, com o conteúdo de cada uma."""
        return tuple((secao, self.conteudo(secao)) for secao in SECOES)

    def itens(self, titulo: str) -> tuple[Item, ...]:
        """Os itens de uma seção do agente, com identificadores estáveis.

        O identificador é um hash curto do texto do item, o mesmo em toda
        execução enquanto o texto não mudar; dois itens de texto igual ganham
        ids diferentes, decididos pela posição. Os ids são um espaço só para
        as duas seções do agente — o modelo aponta sem dizer de qual lista.
        """
        return self._itens_do_agente().get(_chave(titulo), ())

    def com_ids(self, titulo: str) -> tuple[str, ...]:
        """As linhas de uma seção como o modelo as vê: cada item com `(id ...)` no fim.

        Numa seção do usuário não há item com id, e as linhas saem como estão.
        """
        bloco = self._bloco(titulo)
        if bloco is None:
            return ()
        ids = {item.inicio: item.id for item in self.itens(titulo)}
        marcadas = [
            f"{linha.rstrip()} (id {ids[posicao]})" if posicao in ids else linha
            for posicao, linha in enumerate(_corpo(bloco))
        ]
        return sem_brancos_nas_pontas(marcadas)

    def id_de(self, texto: str) -> str | None:
        """O id do primeiro item das seções do agente com exatamente este texto."""
        alvo = texto.strip()
        for itens in self._itens_do_agente().values():
            for item in itens:
                if item.texto == alvo:
                    return item.id
        return None

    # -- escrita -----------------------------------------------------------

    def aplicar(self, resposta: Daily) -> Mudancas:
        """Faz na nota o que a resposta do modelo pede, na ordem que preserva os ids.

        Primeiro os movidos, para que um item novo possa entrar sob um grupo
        que acabou de chegar em *O que eu fiz*; depois os novos de cada lista.
        Um texto que já está em alguma seção do agente não entra de novo — é o
        que faz duas execuções na mesma janela não duplicarem nada, mesmo que
        o modelo repita.
        """
        movidas: list[tuple[str, ...]] = []
        acrescentadas: list[tuple[str, ...]] = []
        ignorados: list[str] = []
        repetidos: list[str] = []

        for referencia in resposta.mover:
            bloco = self.mover(referencia)
            if bloco is None:
                ignorados.append(referencia)
            else:
                movidas.append(bloco)

        # Texto de item novo desta resposta → id dele, para o modelo montar um
        # grupo com sub-itens numa resposta só, sem conhecer o hash.
        novos: dict[str, str] = {}
        for secao, itens in ((SECAO_FIZ, resposta.fiz), (SECAO_FAZENDO, resposta.fazendo)):
            for item in itens:
                texto = item.texto.strip()
                if not texto:
                    continue
                existente = self.id_de(texto)
                if existente is not None:
                    _log.info("Item já está na nota viva, não entra de novo: %r", texto)
                    repetidos.append(texto)
                    novos[texto] = existente
                    continue
                sob = novos.get(item.sob.strip(), item.sob) if item.sob else None
                if sob is not None and self._item_por_id(sob) is None:
                    _log.warning(
                        "O modelo apontou %r como pai de %r, mas não há item com esse id "
                        "na nota viva — o item entra no fim de '%s'.",
                        sob,
                        texto,
                        secao,
                    )
                    ignorados.append(sob)
                    sob = None
                acrescentadas.append(self.acrescentar(secao, texto, sob=sob))
                novos[texto] = self.id_de(texto) or ""

        return Mudancas(
            acrescentadas=tuple(acrescentadas),
            movidas=tuple(movidas),
            ignorados=tuple(ignorados),
            repetidos=tuple(repetidos),
        )

    def acrescentar(self, titulo: str, texto: str, *, sob: str | None = None) -> tuple[str, ...]:
        """Acrescenta `- texto` numa seção e devolve as linhas que entraram.

        Sem `sob`, no fim da seção (criada no fim da nota se não existir). Com
        `sob`, como último sub-item do item apontado, indentado como os irmãos
        dele ou um nível a mais. Se o item apontado está na outra seção do
        agente, a linha dele e as dos ancestrais vêm antes como cabeçalhos de
        grupo, sem repetir um que já esteja aqui.
        """
        bloco = self._bloco(titulo) or self._abrir_secao(titulo)
        item_novo = f"- {texto.strip()}"

        alvo = self._item_por_id(sob) if sob else None
        if alvo is None:
            bloco.linhas.insert(1 + _fim_do_conteudo(_corpo(bloco)), item_novo)
            return (item_novo,)

        secao_do_alvo, pai = alvo
        cabecalhos: tuple[str, ...] = ()
        if _chave(secao_do_alvo) != _chave(titulo):
            cadeia = (*self._ancestrais(secao_do_alvo, pai), pai)
            cabecalhos, copiado = self._garantir_cabecalhos(titulo, cadeia)
            assert copiado is not None
            pai = copiado
        linha = f"{_indentacao_dos_filhos(_corpo(bloco), pai)}{item_novo}"
        bloco.linhas.insert(1 + pai.fim, linha)
        return (*cabecalhos, linha)

    def mover(self, referencia: str) -> tuple[str, ...] | None:
        """Leva um item de *O que estou fazendo* para *O que eu fiz*, literalmente.

        A linha e tudo que está embaixo dela mudam de seção como estão. Se o
        item é aninhado, os ancestrais vêm junto como cabeçalhos de grupo — a
        linha literal deles —, sem duplicar um que já exista no destino. Um id
        que não existe, ou que já está em *O que eu fiz*, é ignorado com log:
        nada é inventado nem casado por aproximação.
        """
        encontrado = self._item_por_id(referencia)
        if encontrado is None:
            _log.warning("O modelo pediu para mover o id %r, que não está na nota viva.", referencia)
            return None
        secao, item = encontrado
        if _chave(secao) != _chave(SECAO_FAZENDO):
            _log.warning("O modelo pediu para mover o id %r, que já está em '%s'.", referencia, secao)
            return None

        origem = self._bloco(SECAO_FAZENDO)
        assert origem is not None
        ancestrais = self._ancestrais(SECAO_FAZENDO, item)
        subarvore = tuple(origem.linhas[1 + item.inicio : 1 + item.fim])
        del origem.linhas[1 + item.inicio : 1 + item.fim]

        cabecalhos, pai = self._garantir_cabecalhos(SECAO_FIZ, ancestrais)
        destino = self._bloco(SECAO_FIZ)
        assert destino is not None
        posicao = 1 + (pai.fim if pai else _fim_do_conteudo(_corpo(destino)))
        destino.linhas[posicao:posicao] = list(subarvore)
        return (*cabecalhos, *subarvore)

    def arquivar_fiz(self) -> tuple[str, ...]:
        """Esvazia *O que eu fiz* e devolve o bloco inteiro que estava lá.

        É a única remoção que o agente faz na nota, e ela nunca toca as outras
        seções. Quem guarda o bloco devolvido é a nota datada.
        """
        bloco = self._bloco(SECAO_FIZ)
        if bloco is None:
            return ()
        arquivado = sem_brancos_nas_pontas(_corpo(bloco))
        bloco.linhas[1:] = [""]
        return arquivado

    def anotar(self, texto: str, secao: str = SECAO_PONTOS) -> str:
        """`- texto` no fim de *Pontos* (ou *Dúvidas*) — o único gesto do agente numa seção do usuário."""
        if _chave(secao) not in {_chave(anotavel) for anotavel in SECOES_ANOTAVEIS}:
            raise ValueError(
                f"Só se anota em {' ou '.join(SECOES_ANOTAVEIS)}; {secao!r} é seção do agente ou de fala."
            )
        return self.acrescentar(secao, texto)[0]

    # -- bastidores --------------------------------------------------------

    def _bloco(self, titulo: str) -> _Bloco | None:
        chave = _chave(titulo)
        for bloco in self._blocos:
            if bloco.titulo is not None and _chave(bloco.titulo) == chave:
                return bloco
        return None

    def _abrir_secao(self, titulo: str) -> _Bloco:
        """Uma seção nova no lugar dela na ordem das cinco; no fim, se nenhuma vem depois.

        Uma nota antiga sem `## Pontos` ganha a seção **antes de `## Falar`**,
        e não no fim: a ordem de falar é a da nota. Só linhas inteiras entram
        — uma em branco antes do título, quando a seção anterior não a tem.
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
        """O primeiro bloco existente que, na ordem das seções, vem depois de `titulo`."""
        ordem = [_chave(secao) for secao in SECOES]
        if _chave(titulo) not in ordem:
            return None
        for secao in SECOES[ordem.index(_chave(titulo)) + 1 :]:
            bloco = self._bloco(secao)
            if bloco is not None:
                return bloco
        return None

    def _itens_do_agente(self) -> dict[str, tuple[Item, ...]]:
        usados: set[str] = set()
        por_secao: dict[str, tuple[Item, ...]] = {}
        for titulo in SECOES_DO_AGENTE:
            bloco = self._bloco(titulo)
            por_secao[_chave(titulo)] = _itens(_corpo(bloco), usados) if bloco else ()
        return por_secao

    def _item_por_id(self, referencia: str) -> tuple[str, Item] | None:
        procurado = _id_limpo(referencia)
        for titulo in SECOES_DO_AGENTE:
            for item in self.itens(titulo):
                if item.id == procurado:
                    return titulo, item
        return None

    def _ancestrais(self, titulo: str, item: Item) -> tuple[Item, ...]:
        por_inicio = {candidato.inicio: candidato for candidato in self.itens(titulo)}
        return tuple(por_inicio[inicio] for inicio in item.ancestrais)

    def _garantir_cabecalhos(
        self, titulo: str, cadeia: Sequence[Item]
    ) -> tuple[tuple[str, ...], Item | None]:
        """Garante que a cadeia de itens existe na seção, como cabeçalhos literais.

        Devolve as linhas que precisaram entrar e o item mais interno da
        cadeia como está na seção de destino — é abaixo dele que o que vem a
        seguir se aninha. `cadeia` vazia devolve `None`: o destino é o fim.
        """
        bloco = self._bloco(titulo) or self._abrir_secao(titulo)
        entraram: list[str] = []
        pai: Item | None = None
        for elo in cadeia:
            existente = self._descendente_com_texto(titulo, pai, elo.texto)
            if existente is None:
                posicao = 1 + (pai.fim if pai else _fim_do_conteudo(_corpo(bloco)))
                bloco.linhas.insert(posicao, elo.linha)
                entraram.append(elo.linha)
                existente = self._descendente_com_texto(titulo, pai, elo.texto)
                assert existente is not None
            pai = existente
        return tuple(entraram), pai

    def _descendente_com_texto(self, titulo: str, pai: Item | None, texto: str) -> Item | None:
        for item in self.itens(titulo):
            if item.texto != texto:
                continue
            if pai is None or pai.inicio in item.ancestrais:
                return item
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
    """As linhas de uma seção sem o título — índice 0 é a linha logo abaixo dele."""
    return bloco.linhas[1:] if bloco.titulo is not None else bloco.linhas


def _fim_do_conteudo(corpo: Sequence[str]) -> int:
    """Onde um item novo entra: logo depois da última linha não vazia."""
    for indice in range(len(corpo) - 1, -1, -1):
        if corpo[indice].strip():
            return indice + 1
    return 0


def _itens(corpo: Sequence[str], usados: set[str]) -> tuple[Item, ...]:
    itens: list[Item] = []
    abertos: list[Item] = []
    for indice, linha in enumerate(corpo):
        if not linha.strip():
            continue
        nivel = _nivel(linha)
        while abertos and abertos[-1].nivel >= nivel:
            abertos.pop()
        partes = _ITEM.match(linha)
        if partes is None:
            continue
        texto = partes["texto"].strip()
        item = Item(
            id=_id(texto, usados),
            texto=texto,
            linha=linha,
            indentacao=partes["indentacao"],
            nivel=nivel,
            inicio=indice,
            fim=_fim_da_subarvore(corpo, indice, nivel),
            ancestrais=tuple(aberto.inicio for aberto in abertos),
        )
        itens.append(item)
        abertos.append(item)
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


def _indentacao_dos_filhos(corpo: Sequence[str], pai: Item) -> str:
    for indice in range(pai.inicio + 1, pai.fim):
        partes = _ITEM.match(corpo[indice])
        if partes is not None:
            return partes["indentacao"]
    return pai.indentacao + _UM_NIVEL


def id_do_item(texto: str) -> str:
    """O id que um item com este texto ganha quando é o primeiro com ele na nota."""
    return _hash(texto.strip())


def _id(texto: str, usados: set[str]) -> str:
    candidato = _hash(texto)
    desempate = 1
    while candidato in usados:
        desempate += 1
        candidato = _hash(f"{texto}\x00{desempate}")
    usados.add(candidato)
    return candidato


def _hash(texto: str) -> str:
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:6]


def _nivel(linha: str) -> int:
    indentacao = linha[: len(linha) - len(linha.lstrip(" \t"))]
    return len(indentacao.expandtabs(_TAB))


def sem_brancos_nas_pontas(linhas: Sequence[str]) -> tuple[str, ...]:
    """As linhas sem as vazias (ou só de espaço) do começo e do fim."""
    inicio, fim = 0, len(linhas)
    while inicio < fim and not linhas[inicio].strip():
        inicio += 1
    while fim > inicio and not linhas[fim - 1].strip():
        fim -= 1
    return tuple(linhas[inicio:fim])


def _chave(titulo: str) -> str:
    """`O que eu fiz `, `o que eu FIZ` e `Duvidas`/`Dúvidas` são a mesma seção."""
    decomposto = unicodedata.normalize("NFKD", titulo)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())


def _id_limpo(referencia: str) -> str:
    """`abc123` de `(id abc123)` — o modelo às vezes copia a marca inteira da pergunta."""
    texto = referencia.strip().casefold()
    encontrado = _ID.search(texto)
    if encontrado is not None and len(texto) <= len("(id abc123)"):
        return encontrado.group(0)
    return texto
