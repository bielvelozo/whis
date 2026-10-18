r"""A proposta automática na 99Freelas: o projeto novo que ele entrega ganha proposta na mesma hora.

Em 13/10, seis propostas baratas e específicas na 99Freelas trouxeram um cliente.
A caçada chega tarde, então a proposta sai da vigia de freelas (`whis
vigia-freelas`, de hora em hora): da listagem que ela já leu ficam os projetos
que abriram há pouco para quem não assina (na 99Freelas todo projeto novo
fica 24 h só para assinante) e não muito disputados; a página e o
formulário de proposta conferem de novo; o Claude decide se ele entrega e
escreve a proposta daquele projeto; o Whis envia pelo Chrome da caçada e confere
pelo botão "Melhorar proposta".

`[cacada].propostas_auto` diz o modo: `ensaio` faz tudo menos o clique (a nota
nasce com `status: ensaio`, que o *Funil* não conta) e `ligado` envia. O preço
é a oferta mínima do formulário, de propósito: foi o que deu cliente.

Nada aqui é enviado duas vezes. O que aconteceu com cada projeto fica em
`%LOCALAPPDATA%\whis\cacada\propostas-auto.json`; um clique sem confirmação
vira `incerta`, ele confere no site, e o projeto nunca volta.

Só na 99Freelas: o User Agreement do Freelancer.com (seção 33) proíbe enviar
por meio automático, e lá a vigia só avisa no celular.
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import time
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Protocol

from . import navegador_logado as _logado
from . import vault as _vault
from .cacada_claude import ErroDaCacada, LimiteDoPlano
from .criterios_da_cacada import PASTA_CACADA, PecaDoPortfolio, ler_criterios
from .fontes_da_cacada import e_da_99freelas
from .freelas_rapidos import do_nicho
from .oportunidades import FREELA, Oportunidade, link_canonico

_log = logging.getLogger("whis.propostas_auto")

DESLIGADO = "desligado"
ENSAIO = "ensaio"
LIGADO = "ligado"

ENVIADA = "enviada"
NO_ENSAIO = "ensaio"
INCERTA = "incerta"
NAO_ENTREGA = "nao_entrega"
PULADA = "pulada"
CONTAM_NA_COTA = {ENSAIO: (NO_ENSAIO, INCERTA), LIGADO: (ENVIADA, INCERTA)}

PASTA_DAS_NOTAS = f"{PASTA_CACADA}/propostas-auto"
CAMINHO_DO_RESUMO = f"{PASTA_CACADA}/propostas-auto.md"
NOME_DO_ESTADO = "propostas-auto.json"
OFERTA_SEM_MINIMO = 50
LIMITE_DO_TEXTO = 3000
CHAMADAS_ALEM_DA_COTA = 2
GUARDA_POR = timedelta(days=30)
DIAS_NO_RESUMO = 14
PAUSA_ENTRE_PAGINAS_S = (2.0, 5.0)
#: Quanto o projeto novo fica só para assinante: a idade das travas conta daqui, para quem não assina.
JANELA_DO_EXCLUSIVO = timedelta(hours=24)
_DIAS_DA_SEMANA = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


@dataclass(frozen=True)
class Travas:
    """As travas de `[cacada]`: idade e propostas do projeto, exclusivo, cota do dia e reserva de conexões.

    `horas` conta da hora em que o projeto abre para ele: 24 h depois de publicado, quando ele não
    assina (`exclusivos` falso), ou da publicação, quando assina.
    """

    horas: int = 24
    max_propostas: int = 80
    por_dia: int = 3
    reserva: int = 3
    exclusivos: bool = False

    @classmethod
    def da_configuracao(cls, configuracao) -> Travas:
        return cls(
            horas=configuracao.cacada_propostas_auto_horas,
            max_propostas=configuracao.cacada_propostas_auto_max_propostas,
            por_dia=configuracao.cacada_propostas_auto_por_dia,
            reserva=configuracao.cacada_propostas_auto_reserva,
            exclusivos=configuracao.cacada_propostas_auto_exclusivos,
        )


@dataclass(frozen=True)
class Contexto:
    """O que o Claude lê sobre ele: as regras, *Sobre mim*, o perfil, o portfólio e as propostas que deram certo."""

    procuro: str
    sobre_mim: str
    perfil: str
    portfolio: tuple[PecaDoPortfolio, ...]
    exemplos: tuple[str, ...]
    nicho: str = ""


@dataclass(frozen=True)
class Escrita:
    """A resposta do Claude: se ele entrega, por quê, a proposta e o prazo."""

    entrega: bool
    motivo: str
    texto: str = ""
    prazo_dias: int = 0


class Escritor(Protocol):
    def escrever(self, oportunidade: Oportunidade, pagina: str, contexto: Contexto, *, corrigir: str = "") -> Escrita: ...


@dataclass(frozen=True)
class Resultado:
    link: str
    titulo: str
    situacao: str
    motivo: str = ""
    preco: int = 0
    prazo_dias: int = 0
    propostas: int | None = None
    orcamento: str = ""
    texto: str = ""
    nota: str = ""
    quando: str = ""


@dataclass(frozen=True)
class Rodada:
    resultados: tuple[Resultado, ...] = ()
    parou: str = ""


def caminho_do_estado() -> Path:
    from .corrida import pasta_da_cacada

    return pasta_da_cacada() / NOME_DO_ESTADO


def pasta_das_fotos() -> Path:
    from .corrida import pasta_da_cacada

    return pasta_da_cacada() / "propostas-auto"


def pagina_publica(url: str) -> str:
    """A página do projeto sem login, para o ensaio com o Chrome da caçada deslogado."""
    import httpx

    from .fontes_da_cacada import CABECALHOS, TEMPO_LIMITE_S

    with httpx.Client(timeout=TEMPO_LIMITE_S, follow_redirects=True, headers=CABECALHOS) as cliente:
        resposta = cliente.get(url)
        resposta.raise_for_status()
        return resposta.text


# -- a rodada -------------------------------------------------------------------------------------


@dataclass
class _Estado:
    arquivo: Path
    projetos: dict[str, dict] = field(default_factory=dict)
    avisos: dict[str, str] = field(default_factory=dict)

    @classmethod
    def ler(cls, arquivo: Path) -> _Estado:
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.is_file() else {}
        except (OSError, ValueError) as erro:
            _log.warning("Propostas automáticas: o estado %s não abriu (%s); começando sem nada.", arquivo, erro)
            dados = {}
        projetos = dados.get("projetos") if isinstance(dados, dict) else None
        avisos = dados.get("avisos") if isinstance(dados, dict) else None
        return cls(
            arquivo,
            {str(k): v for k, v in (projetos or {}).items() if isinstance(v, dict)},
            {str(k): str(v) for k, v in (avisos or {}).items()},
        )

    def guardar(self, agora: datetime) -> None:
        limite = (agora - GUARDA_POR).isoformat()
        projetos = {link: dados for link, dados in self.projetos.items() if str(dados.get("quando", "")) >= limite}
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = self.arquivo.with_name(self.arquivo.name + ".tmp")
        temporario.write_text(
            json.dumps({"projetos": projetos, "avisos": self.avisos}, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        os.replace(temporario, self.arquivo)

    def usados(self, modo: str, dia: date) -> int:
        contam = CONTAM_NA_COTA.get(modo, ())
        return sum(
            1 for dados in self.projetos.values() if dados.get("situacao") in contam and str(dados.get("quando", ""))[:10] == dia.isoformat()
        )

    def avisar_uma_vez(self, chave: str, dia: date) -> bool:
        if self.avisos.get(chave) == dia.isoformat():
            return False
        self.avisos[chave] = dia.isoformat()
        return True


def rodar(
    oportunidades: Sequence[Oportunidade],
    *,
    modo: str,
    travas: Travas,
    vault: Path,
    escritor: Escritor,
    contexto: Contexto,
    sessao: _logado.SessaoLogada | None,
    estado: Path,
    celular: Callable[[str], bool],
    agora: datetime | None = None,
    publica: Callable[[str], str] = pagina_publica,
    fotos: Path | None = None,
    dormir: Callable[[float], None] = time.sleep,
) -> Rodada:
    """Uma rodada: as travas, a página, o Claude, o envio (ou o ensaio), a nota, o celular e o resumo."""
    if modo not in (ENSAIO, LIGADO):
        return Rodada()
    agora = (agora or datetime.now()).astimezone()
    hoje = agora.date()
    memoria = _Estado.ler(estado)
    if memoria.usados(modo, hoje) >= travas.por_dia:
        return Rodada(parou=f"cota do dia ({travas.por_dia})")
    candidatos = _candidatos(oportunidades, travas, memoria, vault, agora, contexto.nicho)
    if not candidatos:
        return Rodada()

    logada = sessao is not None and not sessao.motivo and sessao.logado(_logado.NOVENTA_E_NOVE)
    if modo == LIGADO and not logada:
        motivo = sessao.motivo if sessao is not None and sessao.motivo else "o Chrome da caçada está deslogado da 99Freelas"
        if memoria.avisar_uma_vez("deslogado", hoje):
            celular(f"O envio automático da 99Freelas parou: {motivo}. Entre de novo pelo whis navegador (e feche o Chrome depois).")
            memoria.guardar(agora)
        return Rodada(parou=f"deslogado: {motivo}")

    resultados: list[Resultado] = []
    parou = ""
    chamadas = 0
    limite_de_chamadas = travas.por_dia - memoria.usados(modo, hoje) + CHAMADAS_ALEM_DA_COTA
    abertas = 0
    for oportunidade in candidatos:
        usados = memoria.usados(modo, hoje)
        if usados >= travas.por_dia:
            parou = f"cota do dia ({travas.por_dia})"
            break
        if chamadas >= limite_de_chamadas:
            break
        if abertas:
            dormir(random.uniform(*PAUSA_ENTRE_PAGINAS_S))
        abertas += 1
        try:
            html = sessao.html(oportunidade.link) if logada else publica(oportunidade.link)
        except Exception as erro:  # noqa: BLE001 — sem a página, fica para a próxima hora
            _log.info("Propostas automáticas: %s não abriu (%s).", oportunidade.link, erro)
            continue
        pagina = _logado.ler_99freelas(html)
        if pagina.situacao == _logado.JA_PROPOS:
            resultados.append(_registrar(memoria, oportunidade, PULADA, agora, motivo="você já propôs"))
            continue
        if pagina.situacao != _logado.ABERTO:
            resultados.append(_registrar(memoria, oportunidade, PULADA, agora, motivo=f"o projeto não está aberto ({pagina.situacao})"))
            continue
        if pagina.propostas is not None and pagina.propostas >= travas.max_propostas:
            continue
        if pagina.publicada is not None and _velho(pagina.publicada.replace(tzinfo=agora.tzinfo), travas, agora):
            continue
        # Logado, o cabeçalho lista os projetos novos de outros clientes com a bandeira deles; quem
        # diz se este é exclusivo é o formulário, logo abaixo.
        if not logada and not travas.exclusivos and "flat_project_exclusive" in html:
            continue
        oferta = pagina.valor_minimo or OFERTA_SEM_MINIMO
        formulario = formulario_da_proposta(oportunidade.link)
        if logada:
            try:
                proposta = _logado.ler_proposta_da_99freelas(sessao.html(formulario))
            except _logado.SemNavegador as erro:
                _log.info("Propostas automáticas: o formulário de %s não abriu (%s).", oportunidade.link, erro)
                continue
            if proposta.exclusivo and not travas.exclusivos:
                continue
            if proposta.restantes is not None and proposta.restantes < travas.reserva:
                parou = f"conexões: sobrariam {proposta.restantes}, a reserva é {travas.reserva}"
                if memoria.avisar_uma_vez("conexoes", hoje):
                    celular(
                        f"O envio automático da 99Freelas parou: a próxima proposta deixaria {proposta.restantes} "
                        f"conexões, e a reserva é {travas.reserva}."
                    )
                break
            oferta = proposta.oferta_minima or oferta
        texto_da_pagina = _texto_para_o_claude(html, pagina)
        try:
            escrita, chamadas_feitas = _escrever(escritor, oportunidade, texto_da_pagina, contexto, limite_de_chamadas - chamadas)
        except LimiteDoPlano as erro:
            parou = f"plano do Claude: {erro}"
            break
        chamadas += chamadas_feitas
        if escrita is None:
            continue
        if not escrita.entrega:
            resultados.append(_registrar(memoria, oportunidade, NAO_ENTREGA, agora, motivo=escrita.motivo))
            continue
        problemas = problemas_do_texto(escrita.texto, oportunidade, texto_da_pagina, contexto.portfolio)
        if problemas:
            resultados.append(_registrar(memoria, oportunidade, PULADA, agora, motivo=f"texto reprovado: {'; '.join(problemas)}"))
            continue
        prazo = max(1, min(60, escrita.prazo_dias or 7))
        situacao, observacao = _enviar_ou_ensaiar(modo, logada, sessao, oportunidade, formulario, oferta, prazo, escrita.texto, fotos)
        resultado = _registrar(
            memoria,
            oportunidade,
            situacao,
            agora,
            motivo=observacao,
            preco=oferta,
            prazo_dias=prazo,
            propostas=pagina.propostas,
            orcamento=pagina.orcamento,
            texto=escrita.texto,
            nota=_nota_relativa(oportunidade.link),
        )
        _escrever_nota(vault, resultado, agora)
        resultados.append(resultado)
        celular(_mensagem(resultado, memoria.usados(modo, hoje), travas.por_dia))
    memoria.guardar(agora)
    escrever_resumo(vault, memoria, modo, agora)
    return Rodada(tuple(resultados), parou)


def formulario_da_proposta(link: str) -> str:
    return link.replace("/project/", "/project/bid/", 1)


def _candidatos(
    oportunidades: Sequence[Oportunidade], travas: Travas, memoria: _Estado, vault: Path, agora: datetime, nicho: str
) -> list[Oportunidade]:
    from .funil import ler_mandadas

    mandadas = {link_canonico(m.link) for m in ler_mandadas(vault)}
    vistos: set[str] = set()
    ficam = []
    for oportunidade in oportunidades:
        link = link_canonico(oportunidade.link)
        if not e_da_99freelas(link) or link in vistos or link in memoria.projetos or link in mandadas:
            continue
        vistos.add(link)
        if not travas.exclusivos and "exclusivo para assinantes" in oportunidade.detalhes.casefold():
            continue
        propostas = _propostas(oportunidade)
        if propostas is not None and propostas >= travas.max_propostas:
            continue
        publicada = _publicada(oportunidade, agora)
        if publicada is not None and _velho(publicada, travas, agora):
            continue
        ficam.append(oportunidade)
    return sorted(
        ficam,
        key=lambda o: (
            not (nicho and do_nicho(o, nicho)),
            _propostas(o) if _propostas(o) is not None else 0,
            -(_publicada(o, agora) or agora).timestamp(),
        ),
    )


def _propostas(oportunidade: Oportunidade) -> int | None:
    casou = re.search(r"Propostas:\s*(\d+)", oportunidade.detalhes)
    return int(casou.group(1)) if casou else None


def _velho(publicada: datetime, travas: Travas, agora: datetime) -> bool:
    abriu = publicada if travas.exclusivos else publicada + JANELA_DO_EXCLUSIVO
    return agora - abriu > timedelta(hours=travas.horas)


def _publicada(oportunidade: Oportunidade, agora: datetime) -> datetime | None:
    try:
        publicada = datetime.fromisoformat(oportunidade.publicada)
    except ValueError:
        return None
    return publicada if publicada.tzinfo else publicada.replace(tzinfo=agora.tzinfo)


def _texto_para_o_claude(html: str, pagina: _logado.PaginaDa99Freelas) -> str:
    texto = _logado.texto_da_pagina(html)
    inicio = texto.find("Descrição do Projeto")
    corpo = texto[inicio:] if inicio >= 0 else texto
    cabecalho = [f"Cliente: {pagina.cliente}" if pagina.cliente else "", f"Orçamento: {pagina.orcamento}" if pagina.orcamento else ""]
    return "\n".join([*(c for c in cabecalho if c), corpo[:6000]])


def _escrever(
    escritor: Escritor, oportunidade: Oportunidade, pagina: str, contexto: Contexto, chamadas_que_restam: int
) -> tuple[Escrita | None, int]:
    """A proposta, e uma segunda vez com o motivo quando o texto falha na conferência."""
    feitas = 0
    corrigir = ""
    escrita: Escrita | None = None
    for _tentativa in range(2):
        if feitas >= chamadas_que_restam:
            break
        try:
            escrita = escritor.escrever(oportunidade, pagina, contexto, corrigir=corrigir)
        except ErroDaCacada as erro:
            _log.warning("Propostas automáticas: o Claude não escreveu a de %s (%s).", oportunidade.link, erro)
            return None, feitas + 1
        feitas += 1
        if not escrita.entrega:
            break
        problemas = problemas_do_texto(escrita.texto, oportunidade, pagina, contexto.portfolio)
        if not problemas:
            break
        corrigir = "; ".join(problemas)
    return escrita, feitas


def _enviar_ou_ensaiar(
    modo: str,
    logada: bool,
    sessao: _logado.SessaoLogada | None,
    oportunidade: Oportunidade,
    formulario: str,
    oferta: int,
    prazo: int,
    texto: str,
    fotos: Path | None,
) -> tuple[str, str]:
    if modo == ENSAIO:
        if not logada:
            return NO_ENSAIO, "sem login: o formulário não foi aberto"
        try:
            lidos = sessao.preencher_proposta_da_99freelas(
                formulario, oferta=oferta, dias=prazo, texto=texto, enviar=False, pasta_das_fotos=fotos
            )
        except _logado.SemNavegador as erro:
            return NO_ENSAIO, f"o formulário não aceitou: {erro}"
        return NO_ENSAIO, f"formulário preenchido e conferido sem clicar (oferta {lidos.oferta}, {lidos.dias} dias)"
    try:
        sessao.preencher_proposta_da_99freelas(formulario, oferta=oferta, dias=prazo, texto=texto, enviar=True, pasta_das_fotos=fotos)
    except _logado.SemNavegador as erro:
        return PULADA, f"o formulário não aceitou, nada foi enviado: {erro}"
    try:
        confirmada = _logado.ler_99freelas(sessao.html(oportunidade.link)).situacao == _logado.JA_PROPOS
    except _logado.SemNavegador:
        confirmada = False
    if confirmada:
        return ENVIADA, ""
    return INCERTA, "o Whis clicou em enviar, mas a página do projeto não mostrou \"Melhorar proposta\""


def _registrar(memoria: _Estado, oportunidade: Oportunidade, situacao: str, agora: datetime, **campos) -> Resultado:
    resultado = Resultado(
        link=link_canonico(oportunidade.link),
        titulo=oportunidade.titulo,
        situacao=situacao,
        quando=agora.isoformat(timespec="minutes"),
        **campos,
    )
    memoria.projetos[resultado.link] = {
        "quando": resultado.quando,
        "situacao": situacao,
        "titulo": resultado.titulo,
        "motivo": resultado.motivo,
        "preco": resultado.preco,
        "prazo_dias": resultado.prazo_dias,
        "propostas": resultado.propostas,
        "nota": resultado.nota,
    }
    return resultado


# -- a conferência do texto -------------------------------------------------------------------------

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_TELEFONE = re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}[-\s]?\d{4}\b")
_CONTATO = re.compile(r"me chama|meu (?:whats|zap|telefone|celular|e-?mail|insta)|fora da plataforma|por fora", re.I)
_LINK = re.compile(r"https?://[^\s)>\]]+|www\.[^\s)>\]]+", re.I)
_PRECO = re.compile(r"R\$\s*\d")
_IA_SIGLA = re.compile(r"\b(?:IA|I\.A\.|AI|GPT|LLMs?)\b")
_IA_NOME = re.compile(r"intelig[êe]ncia artificial|chatgpt|claude|copilot|openai|gemini", re.I)


def problemas_do_texto(texto: str, oportunidade: Oportunidade, pagina: str, portfolio: Sequence[PecaDoPortfolio]) -> list[str]:
    """O que impede a proposta de sair: contato, link fora do portfólio, preço, IA sem o projeto pedir, tamanho."""
    problemas = []
    if len(texto) > LIMITE_DO_TEXTO:
        problemas.append(f"passa de {LIMITE_DO_TEXTO} caracteres, o limite do campo")
    if len(texto.strip()) < 150:
        problemas.append("curta demais para ser específica do projeto")
    if _EMAIL.search(texto):
        problemas.append("tem e-mail (contato é proibido na 99Freelas)")
    if _TELEFONE.search(texto):
        problemas.append("tem telefone (contato é proibido na 99Freelas)")
    if _CONTATO.search(texto):
        problemas.append("chama para contato fora da plataforma")
    links = _LINK.findall(texto)
    permitidos = [peca.link.rstrip("/") for peca in portfolio]
    fora = [link for link in links if not any(link.rstrip(".,;").startswith(p) for p in permitidos)]
    if fora:
        problemas.append(f"link fora do portfólio: {fora[0]}")
    elif len(links) > 1:
        problemas.append("mais de um link")
    if _PRECO.search(texto):
        problemas.append("preço no texto (o preço vai no campo)")
    projeto = f"{oportunidade.titulo} {oportunidade.descricao} {pagina}"
    if (_IA_SIGLA.search(texto) and not _IA_SIGLA.search(projeto)) or (_IA_NOME.search(texto) and not _IA_NOME.search(projeto)):
        problemas.append("cita IA sem o projeto falar de IA")
    return problemas


# -- a nota, a mensagem e o resumo ------------------------------------------------------------------


def _slug(link: str) -> str:
    final = link.rstrip("/").rsplit("/", 1)[-1]
    sem_acento = "".join(c for c in unicodedata.normalize("NFKD", final) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9-]+", "-", sem_acento.casefold()).strip("-")[:120] or "projeto"


def _nota_relativa(link: str) -> str:
    return f"{PASTA_DAS_NOTAS}/{_slug(link)}.md"


def _status(resultado: Resultado, dia: date) -> str:
    preco = f"R$ {resultado.preco}, {resultado.prazo_dias} {'dia' if resultado.prazo_dias == 1 else 'dias'}"
    if resultado.situacao == ENVIADA:
        return f"enviada em {dia.isoformat()} ({preco})"
    if resultado.situacao == INCERTA:
        return f"incerta em {dia.isoformat()} ({preco}): confira no site e troque por enviada ou pulada"
    if resultado.situacao == PULADA:
        return f"pulada em {dia.isoformat()}: {resultado.motivo}"
    return f"ensaio em {dia.isoformat()} ({preco}), não enviada"


def _escrever_nota(vault: Path, resultado: Resultado, agora: datetime) -> None:
    linhas = [
        "---",
        f"titulo: {json.dumps(resultado.titulo, ensure_ascii=False)}",
        "plataforma: 99Freelas",
        f"link: {resultado.link}",
        "lingua: pt",
        f'preco: "R$ {resultado.preco}"',
        f"prazo_dias: {resultado.prazo_dias}",
        f"propostas_antes: {resultado.propostas if resultado.propostas is not None else '?'}",
        f"orcamento: {json.dumps(resultado.orcamento, ensure_ascii=False)}",
        f"status: {_status(resultado, agora.date())}",
        f"{'enviada' if resultado.situacao == ENVIADA else 'escrita'}: {agora:%Y-%m-%d %H:%M}",
        "origem: propostas automáticas (whis vigia-freelas)",
        "---",
        "",
        resultado.texto.strip(),
        "",
    ]
    if resultado.motivo:
        linhas += [f"> {resultado.motivo}", ""]
    _vault.escrever(vault, resultado.nota, "\n".join(linhas), zonas=(PASTA_CACADA,))


def _mensagem(resultado: Resultado, usados: int, por_dia: int) -> str:
    if resultado.situacao == INCERTA:
        return (
            "Cliquei em enviar na 99Freelas, mas a página não confirmou: confira se a proposta saiu.\n"
            f"{resultado.titulo}\n{resultado.link}"
        )
    if resultado.situacao == PULADA:
        return f"A proposta não saiu: {resultado.motivo}\n{resultado.titulo}\n{resultado.link}"
    comeco = (
        f"Proposta enviada na 99Freelas ({usados} de {por_dia} hoje)"
        if resultado.situacao == ENVIADA
        else f"Ensaio: esta proposta sairia agora na 99Freelas ({usados} de {por_dia} hoje)"
    )
    dados = " · ".join(
        parte
        for parte in (
            f"Orçamento: {resultado.orcamento}" if resultado.orcamento else "",
            f"{resultado.propostas} propostas até agora" if resultado.propostas is not None else "",
        )
        if parte
    )
    dias = "dia" if resultado.prazo_dias == 1 else "dias"
    preco = f"R$ {resultado.preco} em {resultado.prazo_dias} {dias}"
    if resultado.situacao == NO_ENSAIO and resultado.motivo:
        preco += f" ({resultado.motivo})"
    linhas = [comeco, resultado.titulo, dados, preco, resultado.link, "", resultado.texto]
    return "\n".join(linha for indice, linha in enumerate(linhas) if linha or indice == 5)


_ROTULOS = {ENVIADA: "enviada", NO_ENSAIO: "ensaio", INCERTA: "incerta", NAO_ENTREGA: "não entrega", PULADA: "pulada"}


def escrever_resumo(vault: Path, memoria: _Estado, modo: str, agora: datetime) -> Path:
    """`cacada/propostas-auto.md`: por dia, o que saiu, o que teria saído e o que ficou de fora."""
    explicacao = {
        ENSAIO: "**ensaio**: escreve, preenche o formulário sem clicar e avisa no celular, mas não envia",
        LIGADO: "**ligado**: envia pela 99Freelas e confere pelo botão \"Melhorar proposta\"",
    }.get(modo, f"**{modo}**")
    linhas = [
        "# Propostas automáticas da 99Freelas",
        "",
        f"O Whis reescreve esta nota a cada rodada da vigia de freelas. Modo agora: {explicacao}. "
        "Cada proposta tem a nota dela em `cacada/propostas-auto/`.",
    ]
    por_dia: dict[str, list[dict]] = {}
    for link, dados in memoria.projetos.items():
        por_dia.setdefault(str(dados.get("quando", ""))[:10], []).append({**dados, "link": link})
    for dia in sorted(por_dia, reverse=True)[:DIAS_NO_RESUMO]:
        try:
            data = date.fromisoformat(dia)
        except ValueError:
            continue
        itens = sorted(por_dia[dia], key=lambda d: str(d.get("quando", "")))
        saiu = sum(1 for d in itens if d.get("situacao") == ENVIADA)
        ensaio = sum(1 for d in itens if d.get("situacao") == NO_ENSAIO)
        linhas += ["", f"## {data:%d/%m/%Y} ({_DIAS_DA_SEMANA[data.weekday()]})", "", f"Enviadas: {saiu} · no ensaio: {ensaio}", ""]
        for dados in itens:
            hora = str(dados.get("quando", ""))[11:16]
            partes = [hora, _ROTULOS.get(str(dados.get("situacao")), str(dados.get("situacao"))), f"[{dados.get('titulo', '')}]({dados['link']})"]
            if dados.get("preco"):
                dias = dados.get("prazo_dias") or 0
                partes.append(f"R$ {dados['preco']} em {dias} {'dia' if dias == 1 else 'dias'}")
            if dados.get("propostas") is not None:
                partes.append(f"{dados['propostas']} propostas antes")
            if dados.get("nota"):
                partes.append(f"[[{str(dados['nota']).removesuffix('.md')}|nota]]")
            linha = "- " + " · ".join(partes)
            if dados.get("motivo") and dados.get("situacao") in (NAO_ENTREGA, PULADA, INCERTA):
                linha += f" — {dados['motivo']}"
            linhas.append(linha)
    return _vault.escrever(vault, CAMINHO_DO_RESUMO, "\n".join(linhas) + "\n", zonas=(PASTA_CACADA,))


# -- o contexto do vault ----------------------------------------------------------------------------

_FRONTMATTER = re.compile(r"\A---\r?\n(?P<campos>.*?)\r?\n---\r?\n?(?P<corpo>.*)\Z", re.S)
EXEMPLOS = 3


def contexto_do_vault(vault: Path, nicho: str = "") -> Contexto:
    """Critérios, perfil e as propostas da 99Freelas que ele mandou (as respondidas primeiro) como exemplo."""
    from .cacada import CAMINHO_DO_PERFIL, CAMINHO_DO_PERFIL_DE_FREELAS

    criterios = ler_criterios(vault)
    perfis = []
    for relativo in (CAMINHO_DO_PERFIL_DE_FREELAS, CAMINHO_DO_PERFIL):
        arquivo = Path(vault) / relativo
        if arquivo.is_file():
            casou = _FRONTMATTER.match(arquivo.read_text(encoding="utf-8", errors="replace"))
            perfis.append((casou["corpo"] if casou else arquivo.read_text(encoding="utf-8", errors="replace")).strip()[:4000])
    return Contexto(
        procuro=criterios.procuro,
        sobre_mim=criterios.sobre_mim,
        perfil="\n\n".join(perfis),
        portfolio=criterios.portfolio,
        exemplos=_exemplos(vault),
        nicho=nicho,
    )


def _exemplos(vault: Path) -> tuple[str, ...]:
    pasta = Path(vault) / PASTA_CACADA
    respondidas, enviadas = [], []
    for arquivo in sorted(pasta.glob("*/*.md")) if pasta.is_dir() else ():
        casou = _FRONTMATTER.match(arquivo.read_text(encoding="utf-8", errors="replace"))
        if casou is None:
            continue
        campos = dict(linha.partition(":")[::2] for linha in casou["campos"].splitlines())
        campos = {chave.strip(): valor.strip().strip('"') for chave, valor in campos.items()}
        if "99freelas" not in campos.get("link", "") and campos.get("plataforma", "").casefold() != "99freelas":
            continue
        status = campos.get("status", "").casefold()
        corpo = casou["corpo"].strip()
        if not corpo:
            continue
        if status.startswith(("respondida", "fechada")):
            respondidas.append(corpo)
        elif status.startswith("enviada") and arquivo.parent.name != "propostas-auto":
            enviadas.append(corpo)
    return tuple((respondidas + enviadas)[:EXEMPLOS])


# -- o modo de teste (`whis vigia-freelas --fakes`) ---------------------------------------------------

LINK_DE_TESTE = "https://www.99freelas.com.br/project/ajuste-no-tema-da-loja-shopify-teste-1"
PAGINA_DE_TESTE = (
    '<a href="/project/bid/ajuste-no-tema-da-loja-shopify-teste-1" class="btn blue clickable">Enviar proposta</a>'
    "<table><tr><th>Orçamento:</th><td>Aberto</td></tr><tr><th>Propostas:</th><td>2</td></tr>"
    '<tr><th>Valor Mínimo:</th><td class="valor-minimo">R$ 50,00</td></tr></table>'
)


class EscritorDeTeste:
    """Sem Claude: devolve sempre a mesma proposta, para ver o caminho inteiro e a mensagem no celular."""

    def escrever(self, oportunidade: Oportunidade, pagina: str, contexto: Contexto, *, corrigir: str = "") -> Escrita:
        return Escrita(
            entrega=True,
            motivo="modo de teste",
            texto=(
                "Olá! Proposta de teste do Whis: é assim que a proposta automática chega no seu celular. Nada foi "
                "enviado para a 99Freelas, e o projeto não existe; a de verdade cita um detalhe do pedido e diz como "
                "você começaria.\n\nGabriel"
            ),
            prazo_dias=2,
        )


def projeto_de_teste(agora: datetime | None = None) -> Oportunidade:
    agora = (agora or datetime.now()).astimezone()
    return Oportunidade.nova(
        tipo=FREELA,
        fonte="99Freelas",
        titulo="Ajuste no tema da loja Shopify (teste)",
        link=LINK_DE_TESTE,
        publicada=agora - timedelta(minutes=20),
        descricao="Projeto falso da proposta automática.",
        detalhes="Propostas: 2",
    )
