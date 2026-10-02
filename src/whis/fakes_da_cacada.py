"""As portas fake da caçada: o mesmo caminho inteiro, sem rede e sem gastar a assinatura.

`whis hunt --fakes` e os testes montam a corrida com isto: uma coleta de
mentira com vagas e freelas plausíveis, um perfil fixo, uma triagem por
palavra-chave, mensagens e pacotes de modelo. O fake pode também simular o
limite do plano (`limite_em`), que é como se prova a pausa e a parada sem
esperar cinco horas.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from .cacada import PortasDaCacada
from .cacada_claude import LimiteDoPlano, Plano
from .fontes_da_cacada import ColetaDaCacada
from .oportunidades import (
    CHANCE_BOA,
    DESCARTADA,
    FREELA,
    TENTAR_A_SORTE,
    VAGA,
    Aposta,
    Oportunidade,
    Pacote,
    Perfil,
    Veredito,
)


def oportunidades_de_exemplo() -> tuple[Oportunidade, ...]:
    return (
        Oportunidade.nova(
            tipo=VAGA, fonte="Himalayas · full stack", titulo="Senior Full Stack Engineer (React/Node)",
            link="https://example.com/vagas/full-stack-react", empresa="Acme Remote", local="Remoto (LatAm)",
            faixa="USD 48.000 – 60.000 por ano", descricao="React, Node, TypeScript, PostgreSQL. LatAm welcome.",
        ),
        Oportunidade.nova(
            tipo=FREELA, fonte="Workana · TI e programação", titulo="Landing page para clínica odontológica",
            link="https://example.com/freelas/landing-clinica", faixa="R$ 500 - 1.000",
            descricao="Preciso de uma landing page responsiva com agendamento por WhatsApp.",
            detalhes="Propostas: 4",
        ),
        Oportunidade.nova(
            tipo=VAGA, fonte="LinkedIn · games", titulo="Game Developer (Unity)", link="https://example.com/vagas/unity",
            empresa="Estúdio Indie", local="Remoto — Brasil",
        ),
        Oportunidade.nova(
            tipo=VAGA, fonte="Gupy · desenvolvedor", titulo="Desenvolvedor Java presencial", link="https://example.com/vagas/java-curitiba",
            empresa="Banco Exemplo", local="Presencial — Curitiba, PR",
        ),
        Oportunidade.nova(
            tipo=FREELA, fonte="99Freelas · web, mobile e software", titulo="Transferir R$ 200 para liberar o projeto",
            link="https://example.com/freelas/golpe", descricao="Pague a taxa de cadastro por fora para receber o projeto.",
        ),
    )


def coleta_fake(fontes, agora, **_ignorados) -> ColetaDaCacada:
    coleta = ColetaDaCacada()
    for oportunidade in oportunidades_de_exemplo():
        coleta.por_fonte.setdefault(oportunidade.fonte, ())
        coleta.por_fonte[oportunidade.fonte] += (oportunidade,)
    return coleta


class _Fake:
    def __init__(self, *, plano: Plano | None = None) -> None:
        self.ultimo_plano = plano or Plano(cinco_horas=20, sete_dias=40, vira_sete_dias=datetime.now(UTC) + timedelta(hours=20))
        self.custo_usd = 0.0
        self.chamadas = 0

    def _contar(self) -> None:
        self.chamadas += 1
        self.custo_usd += 0.01


class PerfilFake(_Fake):
    def montar(self, evidencias: str, procuro: str, sobre_mim: str) -> Perfil:
        self._contar()
        return Perfil(
            resumo="Desenvolvedor web full-stack (perfil de exemplo).",
            stack=("TypeScript", "React", "Node.js", "Python"),
            senioridade="pleno (exemplo)",
            perguntas=("Qual o seu nível de inglês?",),
        )


class ExploradorFake(_Fake):
    def explorar(self, pedido, perfil, procuro, sobre_mim, ja_vistas, nome) -> tuple[Oportunidade, ...]:
        self._contar()
        return (
            Oportunidade.nova(
                tipo=FREELA, fonte=f"{nome} (exemplo)", titulo="Site institucional para escritório de advocacia",
                link="https://example.com/freelas/site-advocacia", faixa="R$ 1.500",
                descricao="Site de 5 páginas, responsivo.",
            ),
        )


class TriagemFake(_Fake):
    """Por palavra: golpe e presencial fora descartam; games é tentar a sorte; o resto é chance boa."""

    def __init__(self, *, limite_em: int | None = None, semanal: bool = False, **opcoes) -> None:
        super().__init__(**opcoes)
        self._limite_em = limite_em
        self._semanal = semanal

    def triar(self, oportunidades: Sequence[Oportunidade], perfil, procuro, sobre_mim) -> tuple[Veredito, ...]:
        self._contar()
        if self._limite_em is not None and self.chamadas == self._limite_em:
            raise LimiteDoPlano(
                "limite de exemplo",
                tipo="seven_day" if self._semanal else "five_hour",
                retoma_em=datetime.now(UTC) + timedelta(minutes=10),
            )
        saida = []
        for oportunidade in oportunidades:
            texto = f"{oportunidade.titulo} {oportunidade.descricao} {oportunidade.local}".lower()
            if "pague" in texto or "transferir" in texto:
                saida.append(Veredito(oportunidade.id, DESCARTADA, "sinal de golpe: pede dinheiro", 0, True))
            elif "presencial" in texto and "ribeirão" not in texto and "são paulo" not in texto:
                saida.append(Veredito(oportunidade.id, DESCARTADA, "presencial fora da região", 10))
            elif "game" in texto or "unity" in texto:
                saida.append(Veredito(oportunidade.id, TENTAR_A_SORTE, "games: ele quer tentar", 40))
            else:
                saida.append(Veredito(oportunidade.id, CHANCE_BOA, "web, remoto, casa com a stack", 85))
        return tuple(saida)


class ApostasFake(_Fake):
    def escrever(self, oportunidades, perfil, procuro, sobre_mim) -> tuple[Aposta, ...]:
        self._contar()
        return tuple(Aposta(o.id, f"Olá! Vi a vaga {o.titulo} e quero participar.", "Pelo site.") for o, _ in oportunidades)


class PreparoFake(_Fake):
    def preparar(self, oportunidade, veredito, pagina, perfil, procuro, sobre_mim) -> Pacote:
        self._contar()
        amostra = ""
        if oportunidade.tipo == FREELA:
            amostra = "<!doctype html><html><head><title>Conceito</title></head><body><h1>Conceito</h1></body></html>"
        return Pacote(
            id=oportunidade.id,
            resumo=f"Pedem: {oportunidade.titulo}.",
            por_que_casa="Casa com a stack web (exemplo).",
            alertas=("Exemplo: confira o prazo.",),
            preco="R$ 700" if oportunidade.tipo == FREELA else "R$ 9.000",
            prazo="7 dias" if oportunidade.tipo == FREELA else "",
            proposta="Olá! Proposta de exemplo.",
            plano=("Entender o pedido", "Entregar"),
            como_enviar="Pelo site.",
            amostra_html=amostra,
            amostra_titulo="Conceito" if amostra else "",
        )


def portas_fake(**opcoes_da_triagem) -> PortasDaCacada:
    return PortasDaCacada(
        perfil=PerfilFake(),
        explorador=ExploradorFake(),
        triagem=TriagemFake(**opcoes_da_triagem),
        apostas=ApostasFake(),
        preparo=PreparoFake(),
        coletar=coleta_fake,
        ler_detalhe=lambda _oportunidade: "",
        evidencias=lambda _configuracao: "(evidências de exemplo)",
        amostras=False,
    )
