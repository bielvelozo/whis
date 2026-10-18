r"""Os lances do Freelancer.com: a vigia olha uma vez por dia e avisa no celular quando eles voltam.

Em 18/10 ele estava com 0 de 6 lances do plano grátis, e sem lance o
Freelancer.com nem mostra o formulário de proposta. A vigia de freelas abre,
logada, a página de um projeto ativo que ela acabou de ler, tira do quadro
"Suas Ofertas" o "N/6 restantes" e guarda em
`%LOCALAPPDATA%\whis\cacada\lances-do-freelancer.json`. Quando sai do zero,
manda no celular e guarda a página (já com o formulário) em
`%LOCALAPPDATA%\whis\cacada\freelancer-formulario\`: é o que falta para o
envio automático lá (ticket 06 de `.scratch/propostas-auto`).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from . import navegador_logado as _logado

_log = logging.getLogger("whis.lances_do_freelancer")

NOME_DO_ESTADO = "lances-do-freelancer.json"
NOME_DA_PASTA_DO_FORMULARIO = "freelancer-formulario"


def caminho_do_estado() -> Path:
    from .corrida import pasta_da_cacada

    return pasta_da_cacada() / NOME_DO_ESTADO


def pasta_do_formulario() -> Path:
    from .corrida import pasta_da_cacada

    return pasta_da_cacada() / NOME_DA_PASTA_DO_FORMULARIO


def conferir(
    *,
    abrir_sessao: Callable[[], _logado.SessaoLogada],
    estado: Path,
    celular: Callable[..., bool],
    projeto: str,
    pasta_do_formulario: Path,
    agora: datetime | None = None,
) -> tuple[int, int] | None:
    """Os lances que sobram e o total, uma vez por dia; None quando hoje já foi olhado ou não deu para olhar."""
    agora = (agora or datetime.now()).astimezone()
    hoje = agora.date().isoformat()
    memoria = _ler(estado)
    if memoria.get("dia") == hoje or not projeto:
        return None
    with abrir_sessao() as sessao:
        if sessao.motivo:
            _log.info("Lances do Freelancer.com: o Chrome da caçada não abriu (%s); fica para a próxima rodada.", sessao.motivo)
            return None
        if not sessao.logado(_logado.FREELANCER):
            if memoria.get("deslogado") != hoje:
                celular(
                    "O Chrome da caçada saiu do Freelancer.com, e o Whis não consegue ver os seus lances. Entre de novo "
                    "pelo whis navegador, marque \"Remember me\" antes de entrar e feche a janela depois."
                )
            _guardar(estado, {**memoria, "dia": hoje, "deslogado": hoje})
            return None
        try:
            pagina = sessao.html(projeto)
        except _logado.SemNavegador as erro:
            _log.info("Lances do Freelancer.com: %s não abriu (%s).", projeto, erro)
            return None
    lances = _logado.ler_lances_do_freelancer(pagina)
    if lances is None:
        _log.warning("Lances do Freelancer.com: a página de %s não mostrou o quadro de lances.", projeto)
        _guardar(estado, {**memoria, "dia": hoje})
        return None
    restantes, total = lances
    if restantes > 0 and not memoria.get("restantes"):
        pasta_do_formulario.mkdir(parents=True, exist_ok=True)
        (pasta_do_formulario / "projeto.html").write_text(pagina, encoding="utf-8")
        celular(
            f"Seus lances do Freelancer.com voltaram: {restantes} de {total}. Peça ao Claude o envio automático lá "
            f"(ticket 06): a página do formulário ficou guardada em {pasta_do_formulario}.\n{projeto}"
        )
    _guardar(estado, {"dia": hoje, "restantes": restantes, "total": total, "visto": agora.isoformat(timespec="minutes")})
    _log.info("Lances do Freelancer.com: %d de %d.", restantes, total)
    return lances


def _ler(estado: Path) -> dict:
    try:
        dados = json.loads(estado.read_text(encoding="utf-8")) if estado.is_file() else {}
    except (OSError, ValueError):
        dados = {}
    return dados if isinstance(dados, dict) else {}


def _guardar(estado: Path, dados: dict) -> None:
    estado.parent.mkdir(parents=True, exist_ok=True)
    temporario = estado.with_name(estado.name + ".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(temporario, estado)
