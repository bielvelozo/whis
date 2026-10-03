"""As contas nos sites (entrega 2): criar, confirmar pelo Gmail e completar o perfil, com ele no PC.

`whis contas` (ou `accounts` na palheta) percorre *Contas* de
`cacada/criterios.md` e, para cada site, faz só o passo que falta:

1. **criar** — senha forte sorteada e guardada no cofre *antes* de o agente do
   navegador começar (se o processo cair no meio, a senha não se perde), a
   intenção no registro, o agente, o desfecho;
2. **confirmar** — lê o Gmail dedicado e segue só o link de confirmação de um
   site onde o próprio Whis registrou a intenção de criar conta (`caixa`);
3. **completar o perfil** — título, resumo e habilidades a partir do perfil
   da caçada, com as regras de discrição.

Roda com ele no PC de propósito: CAPTCHA, telefone e documento são dele, e o
agente espera alguns minutos na tela antes de devolver `precisa_de_voce`. O que
ficou pendente vai para `cacada/contas.md`, sem senha nenhuma; a senha de um
site sai só no terminal, com `whis contas --senha <site>`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from . import vault as _vault
from .acoes import CONFIRMACAO, CONTA, FEITO, INTENCAO, PERFIL, PRECISA_DE_VOCE, Registro
from .cofre import Cofre, senha_nova
from .configuracao import Configuracao
from .criterios_da_cacada import PASTA_CACADA, Conta, Criterios
from .navegador_agente import DadosDele, Desfecho
from .politica import dominio

_log = logging.getLogger("whis.contas")

CAMINHO_DAS_CONTAS = f"{PASTA_CACADA}/contas.md"


def chave_no_cofre(conta: Conta | str) -> str:
    nome = conta.nome if isinstance(conta, Conta) else conta
    return f"conta:{nome.strip().casefold()}"


def dados_dele(configuracao: Configuracao, criterios: Criterios) -> DadosDele:
    """O que o agente pode digitar: o config (o sensível fica fora do vault) e *Sobre mim*."""
    return DadosDele(
        nome=configuracao.cacada_nome,
        email=configuracao.cacada_email,
        telefone=configuracao.cacada_telefone,
        cidade=configuracao.cacada_cidade,
        cpf=configuracao.cacada_cpf,
        nascimento=configuracao.cacada_nascimento,
        linkedin=criterios.em_sobre_mim("LinkedIn"),
        github=criterios.em_sobre_mim("GitHub"),
        portfolio=criterios.em_sobre_mim("Portfólio"),
        curriculo=criterios.em_sobre_mim("Currículo"),
    )


@dataclass
class SituacaoDaConta:
    conta: Conta
    conta_feita: bool = False
    confirmada: bool = False
    perfil_feito: bool = False
    pendente: str = ""


@dataclass
class ResultadoDasContas:
    situacoes: list[SituacaoDaConta] = field(default_factory=list)
    falhas: list[str] = field(default_factory=list)
    nota: str = CAMINHO_DAS_CONTAS

    @property
    def pendentes(self) -> list[SituacaoDaConta]:
        return [s for s in self.situacoes if s.pendente]


def cuidar_das_contas(
    configuracao: Configuracao,
    criterios: Criterios,
    *,
    agente: Any,
    cofre: Cofre,
    registro: Registro,
    perfil_texto: str,
    ler_caixa: Callable[[], Sequence[Any]] | None = None,
    seguir: Callable[[str], bool] | None = None,
    so: str = "",
) -> ResultadoDasContas:
    """Um passo por site, o que faltar; nunca repete uma conta que já tem desfecho de feito."""
    if not configuracao.cacada_email:
        raise ValueError("preencha [cacada].email com o Gmail dedicado antes de criar contas")
    dados = dados_dele(configuracao, criterios)
    resultado = ResultadoDasContas()
    contas = [c for c in criterios.contas if not so or c.nome.casefold().startswith(so.casefold())]
    acoes = registro.acoes()

    def estado(tipo: str, conta: Conta) -> str:
        do_site = [a for a in acoes if a.tipo == tipo and a.alvo == conta.nome.strip().casefold()]
        return do_site[-1].estado if do_site else ""

    # 1. criar
    for conta in contas:
        situacao = SituacaoDaConta(conta)
        resultado.situacoes.append(situacao)
        atual = estado(CONTA, conta)
        if atual == FEITO:
            situacao.conta_feita = True
            continue
        if atual == INTENCAO:
            situacao.pendente = "a criação começou e não terminou: confira no site (a senha está no cofre) antes de tentar de novo"
            continue
        guardada = cofre.obter(chave_no_cofre(conta)) or {}
        senha = guardada.get("senha") or senha_nova()
        cofre.guardar(chave_no_cofre(conta), {"site": conta.nome, "endereco": conta.endereco, "email": dados.email, "senha": senha})
        id_ = registro.intencao(CONTA, conta.nome, detalhe=conta.endereco)
        desfecho = _com_rede(lambda: agente.criar_conta(conta.nome, conta.endereco, senha, dados), resultado, conta)
        registro.concluir(id_, desfecho.status if desfecho.status != "nao_feito" else "falhou", desfecho.motivo)
        if desfecho.status == FEITO:
            situacao.conta_feita = True
            if desfecho.o_que_falta:
                situacao.pendente = desfecho.o_que_falta
        else:
            situacao.pendente = desfecho.o_que_falta or desfecho.motivo

    # 2. confirmar pelo Gmail
    if ler_caixa is not None and any(s.conta_feita for s in resultado.situacoes):
        from .caixa import confirmacoes_seguras
        from .caixa import seguir as _seguir

        try:
            mensagens = ler_caixa()
        except Exception as erro:  # noqa: BLE001 — sem caixa, a confirmação fica com ele
            resultado.falhas.append(f"Gmail: {erro}")
            mensagens = ()
        dominios = {dominio(s.conta.endereco): s for s in resultado.situacoes if s.conta_feita}
        for mensagem, link in confirmacoes_seguras(mensagens, dominios):
            if registro.ja_tentado(CONFIRMACAO, link):
                continue
            situacao = next((s for d, s in dominios.items() if mensagem.dominio == d or mensagem.dominio.endswith("." + d)), None)
            id_ = registro.intencao(CONFIRMACAO, link, detalhe=mensagem.assunto)
            ok = (seguir or _seguir)(link)
            registro.concluir(id_, FEITO if ok else "falhou", mensagem.assunto)
            if ok and situacao is not None:
                situacao.confirmada = True
                if "confirm" in situacao.pendente.casefold():
                    situacao.pendente = ""

    # 3. completar o perfil
    for situacao in resultado.situacoes:
        if not situacao.conta_feita or estado(PERFIL, situacao.conta) == FEITO or situacao.pendente:
            situacao.perfil_feito = estado(PERFIL, situacao.conta) == FEITO
            continue
        id_ = registro.intencao(PERFIL, situacao.conta.nome)
        desfecho = _com_rede(
            lambda s=situacao: agente.completar_perfil(s.conta.nome, s.conta.endereco, perfil_texto, dados), resultado, situacao.conta
        )
        registro.concluir(id_, desfecho.status if desfecho.status != "nao_feito" else "falhou", desfecho.motivo)
        situacao.perfil_feito = desfecho.status == FEITO
        if desfecho.status != FEITO:
            situacao.pendente = desfecho.o_que_falta or desfecho.motivo

    return resultado


def _com_rede(funcao: Callable[[], Desfecho], resultado: ResultadoDasContas, conta: Conta) -> Desfecho:
    try:
        return funcao()
    except Exception as erro:  # noqa: BLE001 — um site não derruba os outros
        _log.warning("Contas: %s falhou: %s", conta.nome, erro)
        resultado.falhas.append(f"{conta.nome}: {erro}")
        return Desfecho(status=PRECISA_DE_VOCE, motivo=str(erro)[:200], o_que_falta="rode 'whis contas' de novo")


def montar_nota_das_contas(resultado: ResultadoDasContas, email: str, quando: datetime) -> str:
    linhas = [
        "---",
        "tipo: contas",
        f"atualizada: {quando.isoformat(timespec='minutes')}",
        "---",
        "",
        "# As suas contas nos sites",
        "",
        f"Criadas pelo Whis com {email or 'o Gmail dedicado'}. As senhas ficam no cofre do Whis, nunca aqui: "
        "`python -m whis contas --senha <site>` mostra a de um site no terminal.",
        "",
        "| Site | Conta | E-mail confirmado | Perfil | O que falta você fazer |",
        "|---|---|---|---|---|",
    ]
    for s in resultado.situacoes:
        linhas.append(
            f"| [{s.conta.nome}]({s.conta.endereco}) | {'✓' if s.conta_feita else '—'} | {'✓' if s.confirmada else '—'} "
            f"| {'✓' if s.perfil_feito else '—'} | {s.pendente.replace('|', '/') or '—'} |"
        )
    if resultado.falhas:
        linhas += ["", "## Falhas", "", *(f"- {f}" for f in resultado.falhas)]
    linhas.append("")
    return "\n".join(linhas)


def escrever_nota(vault: Path, resultado: ResultadoDasContas, email: str, quando: datetime) -> str:
    _vault.escrever(Path(vault), CAMINHO_DAS_CONTAS, montar_nota_das_contas(resultado, email, quando), zonas=(PASTA_CACADA,))
    return CAMINHO_DAS_CONTAS
