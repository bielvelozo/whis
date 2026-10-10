"""O vocabulário da caçada: a oportunidade, o veredito, o pacote e o perfil.

Uma **oportunidade** é uma vaga de emprego ou um freela achado numa fonte, com o
link de onde veio — sem link, não existe. A **triagem** dá a cada uma um
**veredito**: *chance boa* (vai para ele mastigada, num **pacote**), *tentar a
sorte* (vai com uma mensagem curta pronta) ou *descartada* (vai só para a
lista, com o motivo). Nada aqui conversa com rede nem com o Claude: são os
dados que as etapas trocam e que o checkpoint guarda em JSON.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

VAGA = "vaga"
FREELA = "freela"
TIPOS = (VAGA, FREELA)

CHANCE_BOA = "chance_boa"
TENTAR_A_SORTE = "tentar_a_sorte"
DESCARTADA = "descartada"
CLASSES = (CHANCE_BOA, TENTAR_A_SORTE, DESCARTADA)

#: O quanto da descrição viaja até a triagem: o bastante para julgar, sem pagar o texto inteiro.
TAMANHO_DA_DESCRICAO = 1500

_PARAMETROS_DE_RASTREIO = re.compile(r"^(utm_|ref$|refid$|trk|trackingid$|fs$|src$|jobboardsource$)", re.I)


@dataclass(frozen=True)
class Oportunidade:
    """Uma vaga ou um freela como a fonte mostrou.

    `id` é estável entre corridas (o hash do link sem rastreio): é o que faz a
    mesma vaga, achada em duas fontes ou em duas caçadas, ser uma só.
    `detalhes` leva o que só algumas fontes têm — número de propostas, prazo,
    país do cliente — em texto, para a triagem ler.
    """

    id: str
    tipo: str
    fonte: str
    titulo: str
    link: str
    empresa: str = ""
    local: str = ""
    regime: str = ""
    faixa: str = ""
    publicada: str = ""
    descricao: str = ""
    detalhes: str = ""

    @classmethod
    def nova(
        cls,
        *,
        tipo: str,
        fonte: str,
        titulo: str,
        link: str,
        empresa: str = "",
        local: str = "",
        regime: str = "",
        faixa: str = "",
        publicada: datetime | str | None = None,
        descricao: str = "",
        detalhes: str = "",
    ) -> "Oportunidade":
        link_limpo = link_canonico(link)
        quando = publicada.isoformat(timespec="minutes") if isinstance(publicada, datetime) else (publicada or "")
        return cls(
            id=id_do_link(link_limpo),
            tipo=tipo if tipo in TIPOS else VAGA,
            fonte=_linha(fonte),
            titulo=_linha(titulo)[:200],
            link=link_limpo,
            empresa=_linha(empresa)[:120],
            local=_linha(local)[:160],
            regime=_linha(regime)[:80],
            faixa=_linha(faixa)[:160],
            publicada=quando,
            descricao=texto_limpo(descricao)[:TAMANHO_DA_DESCRICAO],
            detalhes=_linha(detalhes)[:400],
        )

    def para_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def de_json(cls, dados: dict[str, Any]) -> "Oportunidade":
        nomes = {campo.name for campo in fields(cls)}
        return cls(**{chave: str(valor) for chave, valor in dados.items() if chave in nomes})


@dataclass(frozen=True)
class Veredito:
    """O que a triagem disse de uma oportunidade: a classe, o porquê e o encaixe de 0 a 100."""

    id: str
    classe: str
    motivo: str
    encaixe: int = 0
    golpe: bool = False

    def para_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def de_json(cls, dados: dict[str, Any]) -> "Veredito":
        return cls(
            id=str(dados.get("id", "")),
            classe=str(dados.get("classe", DESCARTADA)),
            motivo=str(dados.get("motivo", "")),
            encaixe=int(dados.get("encaixe", 0) or 0),
            golpe=bool(dados.get("golpe", False)),
        )


@dataclass(frozen=True)
class Pacote:
    """Tudo mastigado para uma chance boa: ele lê, ajusta e envia.

    `proposta` sai no idioma da oportunidade. `amostra_html`, quando há, é a
    página de conceito para o cliente de um freela web; o resto do pacote vale
    sem ela. `como_enviar` diz o caminho no site e a regra do link (a Workana
    suspende proposta com link externo). `formulario` traz, uma por item no
    formato "Pergunta: resposta", as respostas que os formulários de candidatura
    costumam pedir (pretensão no formato do campo, data de início, fuso, inglês).
    """

    id: str
    resumo: str
    por_que_casa: str
    o_que_estica: str = ""
    alertas: tuple[str, ...] = ()
    preco: str = ""
    prazo: str = ""
    proposta: str = ""
    plano: tuple[str, ...] = ()
    perguntas: tuple[str, ...] = ()
    como_enviar: str = ""
    amostra_html: str = ""
    amostra_titulo: str = ""
    formulario: tuple[str, ...] = ()

    def para_json(self) -> dict[str, Any]:
        dados = asdict(self)
        dados["alertas"] = list(self.alertas)
        dados["plano"] = list(self.plano)
        dados["perguntas"] = list(self.perguntas)
        dados["formulario"] = list(self.formulario)
        return dados

    @classmethod
    def de_json(cls, dados: dict[str, Any]) -> "Pacote":
        def lista(chave: str) -> tuple[str, ...]:
            valor = dados.get(chave) or ()
            return tuple(str(item) for item in valor) if isinstance(valor, (list, tuple)) else ()

        return cls(
            id=str(dados.get("id", "")),
            resumo=str(dados.get("resumo", "")),
            por_que_casa=str(dados.get("por_que_casa", "")),
            o_que_estica=str(dados.get("o_que_estica", "")),
            alertas=lista("alertas"),
            preco=str(dados.get("preco", "")),
            prazo=str(dados.get("prazo", "")),
            proposta=str(dados.get("proposta", "")),
            plano=lista("plano"),
            perguntas=lista("perguntas"),
            como_enviar=str(dados.get("como_enviar", "")),
            amostra_html=str(dados.get("amostra_html", "")),
            amostra_titulo=str(dados.get("amostra_titulo", "")),
            formulario=lista("formulario"),
        )


@dataclass(frozen=True)
class Aposta:
    """O que vai junto de uma oportunidade de tentar a sorte: a mensagem curta, pronta."""

    id: str
    mensagem: str
    como_enviar: str = ""

    def para_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def de_json(cls, dados: dict[str, Any]) -> "Aposta":
        return cls(
            id=str(dados.get("id", "")),
            mensagem=str(dados.get("mensagem", "")),
            como_enviar=str(dados.get("como_enviar", "")),
        )


@dataclass(frozen=True)
class Perfil:
    """O que o Whis sabe dele para julgar e escrever, e o que falta ele dizer.

    `resumo` é o texto que vai em toda chamada da caçada — abstrai o
    empregador: nada de nome de empresa, cliente, colega ou projeto interno.
    `perguntas` é o que só ele sabe e ainda não está em *Sobre mim*.
    """

    resumo: str
    stack: tuple[str, ...] = ()
    senioridade: str = ""
    perguntas: tuple[str, ...] = ()

    def para_json(self) -> dict[str, Any]:
        return {
            "resumo": self.resumo,
            "stack": list(self.stack),
            "senioridade": self.senioridade,
            "perguntas": list(self.perguntas),
        }

    @classmethod
    def de_json(cls, dados: dict[str, Any]) -> "Perfil":
        return cls(
            resumo=str(dados.get("resumo", "")),
            stack=tuple(str(item) for item in dados.get("stack") or ()),
            senioridade=str(dados.get("senioridade", "")),
            perguntas=tuple(str(item) for item in dados.get("perguntas") or ()),
        )


@dataclass
class Medicao:
    """O peso acumulado da caçada na assinatura: custo equivalente, chamadas e o plano."""

    custo_usd: float = 0.0
    chamadas: int = 0
    plano_antes: tuple[int | None, int | None] | None = None
    plano_depois: tuple[int | None, int | None] | None = None
    pausas: list[str] = field(default_factory=list)


def link_canonico(link: str) -> str:
    """O link sem fragmento e sem parâmetro de rastreio — o mesmo anúncio vira o mesmo link."""
    texto = (link or "").strip()
    try:
        partes = urlsplit(texto)
    except ValueError:
        return texto
    if partes.scheme not in ("http", "https") or not partes.netloc:
        return texto
    consulta = "&".join(
        par
        for par in partes.query.split("&")
        if par and not _PARAMETROS_DE_RASTREIO.match(par.split("=", 1)[0])
    )
    host = partes.netloc.lower()
    return urlunsplit((partes.scheme.lower(), host, partes.path.rstrip("/") or "/", consulta, ""))


def id_do_link(link: str) -> str:
    return hashlib.sha1(link_canonico(link).encode("utf-8")).hexdigest()[:12]


def texto_limpo(texto: str) -> str:
    """Tira HTML e espaço sobrando: a descrição chega como texto corrido."""
    import html as _html

    sem_tags = re.sub(r"<(script|style)\b.*?</\1>", " ", texto or "", flags=re.S | re.I)
    sem_tags = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>", "\n", sem_tags, flags=re.I)
    sem_tags = re.sub(r"<[^>]+>", " ", sem_tags)
    sem_tags = _html.unescape(sem_tags)
    linhas = (" ".join(linha.split()) for linha in sem_tags.splitlines())
    return "\n".join(linha for linha in linhas if linha)


def _linha(texto: object) -> str:
    return " ".join(texto_limpo(str(texto or "")).split())
