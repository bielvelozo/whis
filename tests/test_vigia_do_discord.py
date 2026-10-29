"""A vigia do Discord: o leitor do canal, as travas dos rascunhos, a primeira rodada calada e o envio no toque."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from whis import vigia_do_discord
from whis.configuracao import carregar_texto
from whis.navegador_logado import DISCORD, PAGINAS_DE_CONFERENCIA, SemNavegador, SessaoLogada, logado_no_html
from whis.propostas_auto import Contexto
from whis.vigia_do_discord import (
    CONVERSA,
    ENVIADA,
    INCERTA,
    NAO_ACHEI,
    PEDIDOS,
    PROPOSTA,
    RESPOSTA,
    Canal,
    Mensagem,
    Rascunho,
    chave_do_toque,
    ler_canais,
    ler_mensagens,
    problemas,
    rodar,
    tocou_enviar,
)
from whis.vigia_do_discord_claude import interpretar

FIXTURE = Path(__file__).parent / "fixtures" / "discord" / "canal.html"
AGORA = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)
CANAL = Canal("Devs For Hire · paid-jobs", "880546729349488741", "927703276487606302", PEDIDOS)
CHAT = Canal("Mavenport · free-chat", "986590128346660944", "986653790755233882", CONVERSA)
JOB = "1564297452176023694"
COLADA = "1564297999999999999"
PROPOSTA_BOA = (
    "Hi Pragnesh! A live React and TypeScript product on Cloudflare Workers is close to what I build every day. "
    "I'd start by reading the D1 schema and picking one open ticket to ship in the first week.\n\n"
    "Is the role open to someone working from Brazil (UTC-3)?\n\nGabriel"
)
CONTEXTO = Contexto(procuro="Freela por projeto.", sobre_mim="- Inglês: intermediário", perfil="Full stack.", portfolio=(), exemplos=())


def _pagina() -> str:
    return FIXTURE.read_text(encoding="utf-8")


class SessaoFake(SessaoLogada):
    def __init__(self, paginas: dict[str, str], *, logado: bool = True, confirma: bool = True, falha: str = "") -> None:
        super().__init__()
        self.paginas = paginas
        self._logado[DISCORD] = logado
        self.confirma = confirma
        self.falha = falha
        self.postados: list[tuple[str, str, str, bool]] = []

    def html_do_discord(self, url: str) -> str:
        if url not in self.paginas:
            raise SemNavegador(f"fora do fake: {url}")
        return self.paginas[url]

    def postar_no_discord(self, canal, mensagem, texto, *, privado):
        if self.falha:
            raise SemNavegador(self.falha)
        self.postados.append((canal, mensagem, texto, privado))
        return self.confirma


@dataclass
class EscritorFake:
    rascunhos: list[Rascunho] = field(default_factory=lambda: [Rascunho(JOB, PROPOSTA, PROPOSTA_BOA, "vaga full stack remota")])
    pedidos: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)

    def escrever(self, canal, mensagens, contexto):
        self.pedidos.append((canal.id, tuple(m.id for m in mensagens)))
        return self.rascunhos


class CelularFake(list):
    def __init__(self) -> None:
        super().__init__()
        self.botoes: list[tuple] = []

    def __call__(self, texto: str, *, botoes=()) -> bool:
        self.append(texto)
        self.botoes.append(tuple(botoes))
        return True


def _rodar(tmp_path: Path, *, sessao=None, escritor=None, por_dia: int = 5, agora: datetime = AGORA, canais=(CANAL,)):
    celular = CelularFake()
    escritor = escritor or EscritorFake()
    rodada = rodar(
        canais,
        sessao=sessao or SessaoFake({CANAL.url: _pagina()}),
        escritor=escritor,
        contexto=CONTEXTO,
        estado=tmp_path / "discord.json",
        celular=celular,
        por_dia=por_dia,
        agora=agora,
        dormir=lambda _s: None,
    )
    return rodada, celular, escritor


def _ja_visto(tmp_path: Path, *ids: str, canal: Canal = CANAL) -> None:
    (tmp_path / "discord.json").write_text(
        json.dumps({"canais": {canal.id: "2026-10-20T00:00:00+00:00"}, "vistas": {i: "2026-10-26T00:00:00+00:00" for i in ids}}),
        encoding="utf-8",
    )


# -- o leitor do canal -------------------------------------------------------------------------------


def test_le_as_mensagens_do_canal_com_autor_hora_e_texto() -> None:
    job, colada, bot = ler_mensagens(_pagina())

    assert (job.id, job.canal, job.autor) == (JOB, CANAL.id, "Pragnesh")
    assert job.quando == datetime(2026, 10, 26, 15, 19, 35, 840000, tzinfo=timezone.utc)
    assert job.texto.startswith("[Project Type]: Junior Full-Stack Developer (Remote, Full-time)\n[Budget]:")
    assert "real product problems & not just tickets." in job.texto
    assert not job.bot
    assert bot.bot and bot.autor == "StickyBot"
    assert "⁠" not in bot.texto


def test_a_mensagem_colada_na_anterior_herda_o_autor_e_quebra_a_linha_no_br() -> None:
    colada = ler_mensagens(_pagina())[1]

    assert colada.autor == "Pragnesh"
    assert colada.texto == "Also need someone for a Shopify theme fix\nDM me"


def test_o_texto_para_no_fim_da_div_da_mensagem() -> None:
    pagina = (
        '<li id="chat-messages-1-2"><h3><span id="message-username-2"><span data-text="Ana">Ana</span></span></h3>'
        '<div id="message-content-2"><div><span>that guy</span></div><span> is new</span></div>'
        '<div><span>Sou novo aqui</span></div></li>'
    )

    assert ler_mensagens(pagina)[0].texto == "that guy is new"


def test_logado_no_discord_e_a_barra_de_servidores_do_app() -> None:
    assert logado_no_html(DISCORD, _pagina())
    assert not logado_no_html(DISCORD, "<html><form>Bem-vindo(a) de volta!</form></html>")
    assert PAGINAS_DE_CONFERENCIA[DISCORD] == "https://discord.com/channels/@me"


def test_os_canais_saem_da_nota_com_link_e_tipo(tmp_path: Path) -> None:
    nota = tmp_path / vigia_do_discord.CAMINHO_DOS_CANAIS
    nota.parent.mkdir(parents=True)
    nota.write_text(
        "# Canais\n\n"
        f"- Devs For Hire · paid-jobs: {CANAL.url} pedidos\n"
        f"- Mavenport · free-chat: {CHAT.url}/ conversa\n"
        "- Sem tipo: https://discord.com/channels/1/2\n"
        "- Tipo errado: https://discord.com/channels/1/2 outros\n",
        encoding="utf-8",
    )

    assert ler_canais(tmp_path) == (CANAL, CHAT)
    assert ler_canais(tmp_path / "vazio") == ()


# -- a rodada ----------------------------------------------------------------------------------------


def test_a_primeira_leitura_do_canal_guarda_tudo_como_visto_e_nao_escreve(tmp_path: Path) -> None:
    rodada, celular, escritor = _rodar(tmp_path)

    assert rodada.novos_canais == (CANAL.nome,)
    assert escritor.pedidos == [] and celular == []
    vistas = json.loads((tmp_path / "discord.json").read_text(encoding="utf-8"))["vistas"]
    assert set(vistas) == {JOB, COLADA, "1565141758097105028"}


def test_mensagem_nova_vira_rascunho_no_celular_com_o_botao(tmp_path: Path) -> None:
    _ja_visto(tmp_path)

    rodada, celular, escritor = _rodar(tmp_path)

    assert escritor.pedidos == [(CANAL.id, (JOB, COLADA))]
    assert len(rodada.rascunhos) == 1
    assert celular[0].startswith("Discord · Devs For Hire · paid-jobs · proposta por mensagem privada a Pragnesh")
    assert PROPOSTA_BOA in celular[0]
    assert f"{CANAL.url}/{JOB}" in celular[0]
    assert celular.botoes == [(("Enviar no Discord", chave_do_toque(JOB)),)]


def test_mensagem_ja_vista_velha_curta_ou_de_bot_nao_vai_ao_claude(tmp_path: Path) -> None:
    _ja_visto(tmp_path, JOB)

    _rodada, _celular, escritor = _rodar(tmp_path, agora=AGORA + timedelta(days=3))

    assert escritor.pedidos == []


def test_a_cota_do_dia_para_os_rascunhos(tmp_path: Path) -> None:
    _ja_visto(tmp_path)
    escritor = EscritorFake([Rascunho(JOB, PROPOSTA, PROPOSTA_BOA), Rascunho(COLADA, PROPOSTA, PROPOSTA_BOA)])

    rodada, celular, _ = _rodar(tmp_path, escritor=escritor, por_dia=1)

    assert len(rodada.rascunhos) == len(celular) == 1


def test_canal_de_pedidos_nao_aceita_resposta_no_canal(tmp_path: Path) -> None:
    _ja_visto(tmp_path)
    escritor = EscritorFake([Rascunho(JOB, RESPOSTA, "Use the D1 binding in wrangler.toml and restart the worker.")])

    rodada, celular, _ = _rodar(tmp_path, escritor=escritor)

    assert rodada.rascunhos == () and celular == []


def test_deslogado_para_a_vigia_e_avisa_uma_vez_por_dia(tmp_path: Path) -> None:
    sessao = SessaoFake({}, logado=False)

    rodada, celular, escritor = _rodar(tmp_path, sessao=sessao)
    _rodar(tmp_path, sessao=SessaoFake({}, logado=False))

    assert rodada.parou == "Discord deslogado"
    assert len(celular) == 1 and "whis navegador" in celular[0]
    assert escritor.pedidos == []


def test_problemas_barram_ia_link_na_resposta_e_contato() -> None:
    mensagem = Mensagem(JOB, CHAT.id, "Ana", AGORA, "My Shopify theme is slow on mobile, any tips?")

    assert problemas(Rascunho(JOB, RESPOSTA, "Compress the hero image in theme settings."), CHAT, mensagem) == []
    assert problemas(Rascunho(JOB, RESPOSTA, "I used ChatGPT and fixed it."), CHAT, mensagem) == ["cita IA sem o pedido falar de IA"]
    assert "resposta no canal com link (os servidores tratam como autopromoção)" in problemas(
        Rascunho(JOB, RESPOSTA, "See velozo.dev for an example."), CHAT, mensagem
    )
    assert problemas(Rascunho(JOB, PROPOSTA, "Portfolio at velozo.dev.\n\nGabriel"), CHAT, mensagem) == []
    assert problemas(Rascunho(JOB, PROPOSTA, "Mail me at gabriel@example.com"), CHAT, mensagem) == ["e-mail ou telefone no texto"]
    pede_ia = Mensagem(JOB, CHAT.id, "Ana", AGORA, "Need an AI chatbot on my Shopify store")
    assert problemas(Rascunho(JOB, PROPOSTA, "I'd wire the AI chatbot into the theme.\n\nGabriel"), CHAT, pede_ia) == []


def test_o_claude_devolve_so_o_que_tem_forma() -> None:
    assert interpretar(None) == []
    assert interpretar([{"mensagem": " 1 ", "tipo": "proposta", "texto": " Oi ", "motivo": "x"}, "lixo"]) == [
        Rascunho("1", "proposta", "Oi", "x")
    ]


# -- o toque -------------------------------------------------------------------------------------------


def _com_rascunho(tmp_path: Path) -> Path:
    _ja_visto(tmp_path)
    _rodar(tmp_path)
    return tmp_path / "discord.json"


def test_o_toque_manda_a_proposta_por_mensagem_privada_e_nao_repete(tmp_path: Path) -> None:
    estado = _com_rascunho(tmp_path)
    sessao = SessaoFake({})

    resposta = tocou_enviar(chave_do_toque(JOB), abrir_sessao=lambda: sessao, estado=estado, agora=AGORA)
    de_novo = tocou_enviar(chave_do_toque(JOB), abrir_sessao=lambda: sessao, estado=estado, agora=AGORA)

    assert sessao.postados == [(CANAL.url, JOB, PROPOSTA_BOA, True)]
    assert resposta.texto == "Mandei por mensagem privada a Pragnesh." and resposta.tirar_botao
    assert "já foi" in de_novo.texto
    assert json.loads(estado.read_text(encoding="utf-8"))["rascunhos"][JOB]["situacao"] == ENVIADA


def test_envio_sem_confirmacao_vira_incerta(tmp_path: Path) -> None:
    estado = _com_rascunho(tmp_path)

    resposta = tocou_enviar(chave_do_toque(JOB), abrir_sessao=lambda: SessaoFake({}, confirma=False), estado=estado, agora=AGORA)

    assert "confira no Discord" in resposta.texto
    assert json.loads(estado.read_text(encoding="utf-8"))["rascunhos"][JOB]["situacao"] == INCERTA


def test_falha_antes_do_enter_nao_marca_nada_e_deixa_tocar_de_novo(tmp_path: Path) -> None:
    estado = _com_rascunho(tmp_path)

    resposta = tocou_enviar(chave_do_toque(JOB), abrir_sessao=lambda: SessaoFake({}, falha="caixa sumiu"), estado=estado, agora=AGORA)

    assert resposta.texto.startswith("Não mandei: caixa sumiu.") and not resposta.tirar_botao
    assert json.loads(estado.read_text(encoding="utf-8"))["rascunhos"][JOB]["situacao"] == vigia_do_discord.ESPERANDO


def test_toque_desconhecido_ou_deslogado(tmp_path: Path) -> None:
    estado = _com_rascunho(tmp_path)

    assert tocou_enviar("discord:nada", abrir_sessao=lambda: SessaoFake({}), estado=estado).texto == NAO_ACHEI
    deslogado = tocou_enviar(chave_do_toque(JOB), abrir_sessao=lambda: SessaoFake({}, logado=False), estado=estado)
    assert deslogado.texto.startswith("Não mandei: Discord: deslogado")


def test_a_configuracao_le_o_discord(tmp_path: Path) -> None:
    vault = f'vault = "{(tmp_path / "vault").as_posix()}"\n'
    configuracao = carregar_texto(vault + "[cacada]\ndiscord = true\ndiscord_por_dia = 2\n", origem=tmp_path / "config.toml")

    assert configuracao.cacada_discord is True
    assert configuracao.cacada_discord_por_dia == 2
    assert carregar_texto(vault, origem=tmp_path / "config.toml").cacada_discord is False
