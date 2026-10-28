r"""O lembrete às agências: 7 dias depois do primeiro e-mail, um aviso no celular com o texto curto pronto.

As fontes dizem que um lembrete depois de uma semana, na mesma conversa, vale a pena, e que
depois dele não se insiste. Os e-mails vêm de dois lugares: a tabela "Dia | Agências" de
`cacada/emails-agencias.md` (os 10 programados no Gmail para 19 a 21/10) e o estado de
`agencias_email` (os que ele mandou pelo botão no Telegram). O Whis não lê a caixa dele, então
quem vê se a agência respondeu é ele: a mensagem traz o texto e diz para ignorar se já responderam.

Cada agência recebe um lembrete só, guardado em `%LOCALAPPDATA%\whis\cacada\lembretes-agencias.json`
quando o celular aceita a mensagem. Passadas duas semanas do e-mail, o lembrete não chega mais.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from .agencias_email import CAMINHO_DOS_JA_ESCRITOS, ENVIADO, _ler

_log = logging.getLogger("whis.lembrete_das_agencias")

NOME_DO_ESTADO = "lembretes-agencias.json"
DIAS_ATE_O_LEMBRETE = 7
ATRASADO_DEMAIS = timedelta(days=14)

_ANO = re.compile(r"^criado:\s*(\d{4})-", re.M)
_LINHA_DA_TABELA = re.compile(r"^\|[^|]*?\b(\d{1,2})/(\d{1,2})\b[^|]*\|\s*([^|]+?)\s*\|\s*$")
_SECAO = re.compile(r"^##\s*\d+\.\s*(?P<nome>[^(·\n]+?)\s*(?:\(|·|$)")
_PARA = re.compile(r"^\*\*Para:\*\*\s*([\w.+-]+@[\w-]+(?:\.[\w-]+)+)", re.M)
_ASSUNTO = re.compile(r"^\*\*Assunto:\*\*\s*(.+?)\s*$", re.M)


@dataclass(frozen=True)
class Enviado:
    nome: str
    email: str
    assunto: str
    dia: date


def caminho_do_estado() -> Path:
    from .corrida import pasta_da_cacada

    return pasta_da_cacada() / NOME_DO_ESTADO


def lembrar(
    vault: Path,
    *,
    estado: Path,
    estado_dos_emails: Path,
    celular: Callable[[str], bool],
    agora: datetime | None = None,
) -> list[Enviado]:
    """Manda ao celular o lembrete de cada e-mail que fez 7 dias hoje (ou há pouco) e ainda não teve lembrete."""
    agora = (agora or datetime.now()).astimezone()
    hoje = agora.date()
    lembrados = _ler_estado(estado)
    feitos: list[Enviado] = []
    for enviado in [*_programados(vault, hoje.year), *_pelo_botao(estado_dos_emails)]:
        if enviado.email in lembrados:
            continue
        if hoje < enviado.dia + timedelta(days=DIAS_ATE_O_LEMBRETE) or hoje - enviado.dia > ATRASADO_DEMAIS:
            continue
        if not celular(mensagem(enviado)):
            _log.info("Lembrete às agências: o celular não aceitou o de %s; tento na próxima rodada.", enviado.nome)
            continue
        lembrados[enviado.email] = hoje.isoformat()
        _guardar_estado(estado, lembrados)
        feitos.append(enviado)
    return feitos


def texto_do_lembrete(nome: str) -> str:
    return (
        f"Oi, pessoal da {nome}, tudo certo? Só pra saber se o meu e-mail chegou. Se não for o momento, tranquilo.\n\n"
        "Abraço,\nGabriel Velozo"
    )


def mensagem(enviado: Enviado) -> str:
    return "\n".join(
        [
            f"Lembrete de follow-up: faz {DIAS_ATE_O_LEMBRETE} dias do e-mail para a {enviado.nome}",
            f"Para: {enviado.email} · enviado em {enviado.dia:%d/%m}" + (f" · assunto \"{enviado.assunto}\"" if enviado.assunto else ""),
            "Se não responderam, abra esse e-mail em Enviados no Gmail e responda na mesma conversa com:",
            "",
            texto_do_lembrete(enviado.nome),
            "",
            "Se já responderam, ignore. Depois deste, não insista.",
        ]
    )


def _programados(vault: Path, ano_padrao: int) -> list[Enviado]:
    """A tabela "Dia | Agências" e, de cada agência, o "Para" e o "Assunto" da seção dela."""
    arquivo = Path(vault) / CAMINHO_DOS_JA_ESCRITOS
    if not arquivo.is_file():
        return []
    texto = arquivo.read_text(encoding="utf-8", errors="replace")
    casou = _ANO.search(texto)
    ano = int(casou.group(1)) if casou else ano_padrao
    secoes = _secoes(texto)
    enviados: list[Enviado] = []
    for linha in texto.splitlines():
        casou = _LINHA_DA_TABELA.match(linha.strip())
        if casou is None:
            continue
        try:
            dia = date(ano, int(casou.group(2)), int(casou.group(1)))
        except ValueError:
            continue
        for nome in (parte.strip() for parte in casou.group(3).split(",")):
            secao = next((s for s in secoes if _mesma_agencia(nome, s[0])), None)
            if secao is None:
                _log.info("Lembrete às agências: %s está na tabela, mas não achei a seção com o e-mail.", nome)
                continue
            enviados.append(Enviado(secao[0], secao[1], secao[2], dia))
    return enviados


def _secoes(texto: str) -> list[tuple[str, str, str]]:
    secoes: list[tuple[str, str, str]] = []
    partes = re.split(r"^(?=##\s*\d+\.)", texto, flags=re.M)
    for parte in partes:
        cabecalho = _SECAO.match(parte)
        para = _PARA.search(parte)
        if cabecalho is None or para is None:
            continue
        assunto = _ASSUNTO.search(parte)
        secoes.append((cabecalho["nome"].strip(), para.group(1).casefold(), assunto.group(1) if assunto else ""))
    return secoes


def _mesma_agencia(da_tabela: str, da_secao: str) -> bool:
    curto, longo = sorted((da_tabela.casefold(), da_secao.casefold()), key=len)
    return bool(curto) and (longo == curto or longo.startswith(curto + " "))


def _pelo_botao(estado_dos_emails: Path) -> list[Enviado]:
    enviados: list[Enviado] = []
    for email, dados in _ler(estado_dos_emails)["emails"].items():
        if dados.get("situacao") != ENVIADO:
            continue
        try:
            dia = datetime.fromisoformat(str(dados.get("enviado") or "")).date()
        except ValueError:
            continue
        enviados.append(Enviado(str(dados.get("nome") or email), email, str(dados.get("assunto") or ""), dia))
    return enviados


def _ler_estado(arquivo: Path) -> dict[str, str]:
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8")) if arquivo.is_file() else {}
    except (OSError, ValueError) as erro:
        _log.warning("Lembrete às agências: o estado %s não abriu (%s); começando sem nada.", arquivo, erro)
        return {}
    return {str(k): str(v) for k, v in dados.items()} if isinstance(dados, dict) else {}


def _guardar_estado(arquivo: Path, lembrados: dict[str, str]) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    temporario = arquivo.with_name(arquivo.name + ".tmp")
    temporario.write_text(json.dumps(lembrados, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temporario, arquivo)
