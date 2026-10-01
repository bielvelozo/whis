"""Comportamento do coletor do Slack, sem rede.

As respostas vêm de fixtures JSON no formato que a Web API devolve — `channels`
de `users.conversations`, `messages` de `conversations.history` e
`conversations.replies`, `user` de `users.info` —, montadas a partir dos
exemplos da documentação oficial
(https://docs.slack.dev/reference/methods/conversations.history/).

O HTTP é interceptado com `httpx.MockTransport`, então o código que monta a
requisição (URL, cabeçalhos, parâmetros e paginação) é exatamente o de
produção. A espera do `Retry-After` entra por `dormir`, injetado: o teste prova
que a espera aconteceu sem dormir de verdade.

A janela dos testes é declarada em **UTC** de propósito: assim as fixtures caem
sempre no mesmo lugar dela, rode a suíte na máquina que rodar. A conversão para
o fuso local — que o contrato exige de `momento` — tem teste próprio, e a
costura inteira reancora os `ts` na janela local do dia.

Nenhuma fixture contém segredo: o token dos testes é `xoxp-EXEMPLO`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from whis.__main__ import montar_fontes
from whis.configuracao import Configuracao, ConfiguracaoInvalida, carregar
from whis.diario import gerar_diario
from whis.fakes import ResumoDoDiaFake
from whis.fonte_slack import (
    BASE,
    ESPERA_MAXIMA_S,
    ESPERA_PADRAO_S,
    SCOPES_MINIMOS,
    TENTATIVAS_APOS_429,
    FonteSlack,
    de_configuracao,
)
from whis.fontes import ErroDeFonte, Evento, Janela, janela_do_dia

TOKEN_FALSO = "xoxp-EXEMPLO"
FIXTURES = Path(__file__).parent / "fixtures"

#: A janela dos testes: 3 de setembro de 2026, das 04:00 de Brasília às 04:00
#: do dia seguinte, escrita em UTC para não depender do relógio da máquina.
JANELA = Janela(
    data=date(2026, 9, 3),
    inicio=datetime(2026, 9, 3, 7, 0, tzinfo=UTC),
    fim=datetime(2026, 9, 4, 7, 0, tzinfo=UTC),
)

#: O endereço que o `auth.test` devolve, e de onde saem os permalinks.
WORKSPACE = "https://segundo-cerebro.slack.com/"

RESPOSTA_DO_AUTH = {
    "ok": True,
    "url": WORKSPACE,
    "team": "Segundo Cerebro",
    "user": "gabriel",
    "team_id": "T0SEGUNDOCEREBRO",
    "user_id": "U0GABRIEL",
}

CONVERSA_VAZIA = {"ok": True, "messages": [], "has_more": False}

#: O `ts` da mensagem que abre a thread em #plataforma.
THREAD = "1788440520.000100"

#: O instante da segunda mensagem de #plataforma. Os microssegundos vêm do
#: `ts` do Slack, que é epoch com fração — o coletor não os arredonda.
MOMENTO_DA_RESPOSTA = datetime(2026, 9, 3, 14, 20, 0, 200, tzinfo=UTC)


def carregar_fixture(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


CONVERSAS = [
    carregar_fixture("resposta_slack_conversas.json"),
    carregar_fixture("resposta_slack_conversas_pagina_2.json"),
]
USUARIOS = carregar_fixture("resposta_slack_usuarios.json")
HISTORICOS = {
    "C0PLATAFORMA": [
        carregar_fixture("resposta_slack_historico_plataforma.json"),
        carregar_fixture("resposta_slack_historico_plataforma_pagina_2.json"),
    ],
    "D0ANA": [carregar_fixture("resposta_slack_historico_dm.json")],
    "C0GRUPO": [carregar_fixture("resposta_slack_historico_grupo.json")],
}
THREADS = {("C0PLATAFORMA", THREAD): carregar_fixture("resposta_slack_thread.json")}

#: Os títulos e trechos que as fixtures produzem — é por eles que a nota é lida.
DA_ANA = "Ana Prado"
DO_GABRIEL = "Gabriel Velozo"
DO_BOT = "Deploy Bot"
EM_THREAD = "Gabriel Velozo (em thread)"


# -- O workspace falso ------------------------------------------------------


def responder_padrao(
    metodo: str, parametros: dict[str, str], historicos: dict[str, list]
) -> dict:
    """O que um workspace com as fixtures responderia a cada método."""
    if metodo == "auth.test":
        return RESPOSTA_DO_AUTH
    pagina = 1 if parametros.get("cursor") else 0
    if metodo == "users.conversations":
        return CONVERSAS[pagina]
    if metodo == "users.info":
        return USUARIOS.get(
            parametros.get("user", ""), {"ok": False, "error": "user_not_found"}
        )
    canal = parametros.get("channel", "")
    if metodo == "conversations.history":
        paginas = historicos.get(canal) or [CONVERSA_VAZIA]
        return paginas[min(pagina, len(paginas) - 1)]
    if metodo == "conversations.replies":
        return THREADS.get((canal, parametros.get("ts", "")), CONVERSA_VAZIA)
    return {"ok": False, "error": "unknown_method"}


def montar_resposta(valor: Any, requisicao: httpx.Request) -> httpx.Response:
    if callable(valor):
        return valor(requisicao)
    if isinstance(valor, httpx.Response):
        return valor
    return httpx.Response(200, json=valor)


def fonte(
    *,
    respostas: dict[str, Any] | None = None,
    registro: list[httpx.Request] | None = None,
    proibidos: Sequence[str] = (),
    historicos: dict[str, list] | None = None,
    esperas: list[float] | None = None,
    token: str = TOKEN_FALSO,
    excluidas: Sequence[str] = (),
    **extras,
) -> FonteSlack:
    """Coletor com transporte falso, apontado para um workspace de fixtures.

    `respostas` mapeia o nome de um método da Web API ao que responder no lugar
    do padrão: um dicionário, uma lista consumida na ordem das chamadas, um
    `httpx.Response` ou um callable. `proibidos` são conversas que o teste
    afirma que **nenhuma** requisição pode tocar — é assim que a blocklist é
    provada, e não pela ausência do resultado.
    """
    filas = {
        metodo: list(valor) if isinstance(valor, list) else [valor]
        for metodo, valor in (respostas or {}).items()
    }
    tabela = HISTORICOS if historicos is None else historicos

    def responder(requisicao: httpx.Request) -> httpx.Response:
        if registro is not None:
            registro.append(requisicao)
        metodo = requisicao.url.path.rsplit("/", 1)[-1]
        parametros = dict(requisicao.url.params)
        canal = parametros.get("channel", "")
        if canal and canal in proibidos:
            raise AssertionError(
                f"o coletor consultou {canal}, que está na blocklist do usuário"
            )

        fila = filas.get(metodo)
        if fila is not None:
            atual = fila.pop(0) if len(fila) > 1 else fila[0]
            return montar_resposta(atual, requisicao)
        return montar_resposta(responder_padrao(metodo, parametros, tabela), requisicao)

    return FonteSlack(
        token,
        conversas_excluidas=excluidas,
        cliente=httpx.Client(transport=httpx.MockTransport(responder)),
        dormir=(esperas.append if esperas is not None else lambda _: None),
        **extras,
    )


def coletar_o_dia_cheio(**extras) -> dict[str, Evento]:
    """Os eventos do dia cheio, indexados pelo detalhe — o que a nota mostra."""
    return {
        evento.detalhe: evento for evento in fonte(**extras).coletar(JANELA)
    }


def requisicoes_de(registro: list[httpx.Request], metodo: str) -> list[httpx.Request]:
    return [r for r in registro if r.url.path.endswith(f"/{metodo}")]


def parametros(requisicao: httpx.Request) -> dict[str, str]:
    return dict(requisicao.url.params)


# -- A requisição -----------------------------------------------------------


def test_fala_com_a_web_api_do_slack_autenticado_com_o_user_token():
    registro: list[httpx.Request] = []

    fonte(registro=registro).coletar(JANELA)

    assert registro, "alguma requisição foi feita"
    for requisicao in registro:
        assert str(requisicao.url).startswith(f"{BASE}/")
        assert requisicao.headers["authorization"] == f"Bearer {TOKEN_FALSO}"


def test_lista_as_conversas_do_usuario_inclusive_dms_e_group_dms():
    registro: list[httpx.Request] = []

    fonte(registro=registro).coletar(JANELA)

    enviados = parametros(requisicoes_de(registro, "users.conversations")[0])
    tipos = enviados["types"].split(",")
    assert set(tipos) == {"public_channel", "private_channel", "mpim", "im"}
    assert enviados["exclude_archived"] == "true", "canal arquivado não tem dia de hoje"


def test_recorta_o_historico_pelos_dois_lados_da_janela():
    registro: list[httpx.Request] = []

    fonte(registro=registro).coletar(JANELA)

    enviados = parametros(requisicoes_de(registro, "conversations.history")[0])
    assert float(enviados["oldest"]) == JANELA.inicio.timestamp()
    assert float(enviados["latest"]) == JANELA.fim.timestamp()
    assert enviados["inclusive"] == "true"


def test_o_fim_da_janela_vai_junto_para_o_diario_de_uma_data_passada():
    # Sem o `latest`, gerar o diário de uma segunda-feira traria a semana toda.
    registro: list[httpx.Request] = []
    janela = janela_do_dia(date(2026, 8, 17), "04:00")

    fonte(registro=registro).coletar(janela)

    enviados = parametros(requisicoes_de(registro, "conversations.history")[0])
    assert float(enviados["oldest"]) == janela.inicio.timestamp()
    assert float(enviados["latest"]) == janela.fim.timestamp()


def test_a_thread_e_lida_pelo_ts_da_mensagem_que_a_abriu():
    registro: list[httpx.Request] = []

    fonte(registro=registro).coletar(JANELA)

    das_threads = requisicoes_de(registro, "conversations.replies")
    assert [parametros(r)["ts"] for r in das_threads] == [THREAD]
    assert parametros(das_threads[0])["channel"] == "C0PLATAFORMA"


def test_mensagem_sem_resposta_nao_gasta_uma_requisicao_de_thread():
    registro: list[httpx.Request] = []

    fonte(registro=registro).coletar(JANELA)

    # Cinco mensagens legíveis vêm do histórico; só uma abre thread.
    assert len(requisicoes_de(registro, "conversations.replies")) == 1


# -- A tradução para Evento -------------------------------------------------


def test_mensagem_de_canal_vira_evento_com_quem_falou_e_o_texto():
    eventos = coletar_o_dia_cheio()

    mensagem = eventos["revisando agora & comento por lá"]
    assert mensagem.fonte == "slack"
    assert mensagem.titulo == DO_GABRIEL, "o título diz quem falou"
    assert mensagem.referencia == "#plataforma"
    assert mensagem.momento == MOMENTO_DA_RESPOSTA
    assert mensagem.pessoas == (DO_GABRIEL,)


def test_mencoes_e_links_viram_texto_legivel_com_nome_de_gente():
    eventos = fonte().coletar(JANELA)

    aberta = next(e for e in eventos if e.detalhe.startswith("Subi o fix"))
    assert aberta.detalhe == (
        "Subi o fix do frete em #frete-v2, @Gabriel Velozo revisa? "
        "Contexto em FN-123 & no print."
    )
    assert aberta.pessoas == (DA_ANA, DO_GABRIEL), "quem foi citado entra no filtro"


def test_o_link_do_evento_e_o_permalink_da_mensagem_no_workspace():
    eventos = coletar_o_dia_cheio()

    mensagem = eventos["revisando agora & comento por lá"]
    assert mensagem.url == (
        "https://segundo-cerebro.slack.com/archives/C0PLATAFORMA/p1788445200000200"
    )


def test_resposta_de_thread_entra_marcada_e_com_o_link_da_thread():
    eventos = coletar_o_dia_cheio()

    resposta = eventos["revisei, subi o ajuste do arredondamento"]
    assert resposta.titulo == EM_THREAD
    assert resposta.referencia == "#plataforma"
    assert resposta.momento == datetime(2026, 9, 3, 17, 45, 0, 700, tzinfo=UTC)
    assert resposta.url == (
        "https://segundo-cerebro.slack.com/archives/C0PLATAFORMA/p1788457500000700"
        f"?thread_ts={THREAD}&cid=C0PLATAFORMA"
    )


def test_a_mensagem_que_abriu_a_thread_nao_aparece_duas_vezes():
    # `conversations.replies` devolve a mãe junto das respostas, e ela já veio
    # pelo histórico.
    eventos = fonte().coletar(JANELA)

    aberturas = [e for e in eventos if e.detalhe.startswith("Subi o fix")]
    assert len(aberturas) == 1


def test_mensagem_de_dm_traz_a_conversa_como_referencia():
    eventos = coletar_o_dia_cheio()

    conversa = eventos["consegue olhar o deploy do OMS amanhã cedo?"]
    assert conversa.referencia == f"DM com {DA_ANA}", "id de DM não diz nada ao leitor"
    assert conversa.momento == datetime(2026, 9, 4, 1, 35, 0, 900, tzinfo=UTC)


def test_group_dm_vira_referencia_legivel_em_vez_do_mpdm_cru():
    eventos = coletar_o_dia_cheio()

    combinado = eventos["fechamos o horário da retro?"]
    assert combinado.referencia == "Grupo com gabriel, ana.prado, bruno"


def test_mensagem_de_app_entra_com_o_nome_do_app():
    eventos = coletar_o_dia_cheio()

    aviso = eventos["Deploy do OMS concluído em produção"]
    assert aviso.titulo == DO_BOT
    assert aviso.pessoas == (DO_BOT,)


def test_mensagem_so_com_anexo_aproveita_o_texto_do_anexo():
    eventos = coletar_o_dia_cheio()

    anexo = eventos["Relatório semanal do frete.pdf"]
    assert anexo.titulo == "Bruno Lima"


def test_entrada_e_saida_de_canal_nao_viram_evento():
    # `channel_join` é manutenção do canal, não trabalho do dia.
    eventos = fonte().coletar(JANELA)

    assert not any("has joined the channel" in evento.detalhe for evento in eventos)


def test_mensagem_fora_da_janela_e_descartada_mesmo_vindo_da_api():
    eventos = fonte().coletar(JANELA)

    assert all(JANELA.contem(evento.momento) for evento in eventos)
    assert not any("não deveria ter devolvido" in evento.detalhe for evento in eventos)


def test_todo_evento_sai_marcado_como_da_fonte_slack():
    eventos = fonte().coletar(JANELA)

    assert eventos, "o dia cheio rende eventos"
    assert {evento.fonte for evento in eventos} == {"slack"}
    assert FonteSlack(TOKEN_FALSO).nome == "slack"


def test_nenhum_id_de_pessoa_sobra_no_que_vai_para_a_nota():
    eventos = fonte().coletar(JANELA)

    for evento in eventos:
        texto = "\n".join((evento.titulo, evento.detalhe, *evento.pessoas))
        assert "U0ANA" not in texto
        assert "U0GABRIEL" not in texto
        assert "U0BRUNO" not in texto


def test_o_nome_de_cada_pessoa_e_resolvido_uma_vez_so():
    # Sem cache, o diário gastaria uma requisição por mensagem só para não
    # escrever `U01234`.
    registro: list[httpx.Request] = []

    fonte(registro=registro).coletar(JANELA)

    pedidos = [parametros(r)["user"] for r in requisicoes_de(registro, "users.info")]
    assert len(pedidos) == len(set(pedidos))


def test_momento_vem_aware_no_fuso_local_e_nao_em_utc():
    # O Slack devolve epoch; o agrupamento por dia e o HH:MM da nota dependem
    # da conversão para o relógio do usuário.
    momento = coletar_o_dia_cheio()["revisando agora & comento por lá"].momento

    assert momento == MOMENTO_DA_RESPOSTA
    assert momento.utcoffset() == MOMENTO_DA_RESPOSTA.astimezone().utcoffset()


def test_dia_sem_conversa_nenhuma_devolve_tupla_vazia_e_nao_falha():
    vazio = {"ok": True, "channels": [], "response_metadata": {"next_cursor": ""}}

    assert fonte(respostas={"users.conversations": vazio}).coletar(JANELA) == ()


# -- A blocklist ------------------------------------------------------------


def test_conversa_na_blocklist_nao_e_sequer_consultada():
    """O critério de aceite: nenhuma requisição sai para a conversa excluída."""
    registro: list[httpx.Request] = []

    eventos = fonte(
        registro=registro, excluidas=("#terapia",), proibidos=("C0TERAPIA",)
    ).coletar(JANELA)

    tocaram = [r for r in registro if "C0TERAPIA" in str(r.url)]
    assert tocaram == [], "nenhuma requisição carregou o id da conversa bloqueada"
    assert all(evento.referencia != "#terapia" for evento in eventos)


def test_dm_bloqueada_pelo_nome_da_pessoa_tambem_nao_e_consultada():
    registro: list[httpx.Request] = []

    fonte(
        registro=registro, excluidas=("@joana",), proibidos=("D0JOANA",)
    ).coletar(JANELA)

    assert [r for r in registro if "D0JOANA" in str(r.url)] == []


def test_blocklist_por_id_nao_gasta_requisicao_resolvendo_quem_esta_do_outro_lado():
    # Só com ids não há o que comparar com nome, e `users.info` da pessoa
    # bloqueada nunca chega a ser pedido.
    registro: list[httpx.Request] = []

    fonte(registro=registro, excluidas=("D0JOANA",), proibidos=("D0JOANA",)).coletar(
        JANELA
    )

    pedidos = [parametros(r)["user"] for r in requisicoes_de(registro, "users.info")]
    assert "U0JOANA" not in pedidos


def test_blocklist_ignora_maiusculas_e_o_cerquilha_do_nome_do_canal():
    registro: list[httpx.Request] = []

    fonte(registro=registro, excluidas=("TeRaPiA",), proibidos=("C0TERAPIA",)).coletar(
        JANELA
    )

    assert [r for r in registro if "C0TERAPIA" in str(r.url)] == []


def test_blocklist_vazia_le_todas_as_conversas():
    registro: list[httpx.Request] = []

    fonte(registro=registro).coletar(JANELA)

    lidos = {parametros(r)["channel"] for r in requisicoes_de(registro, "conversations.history")}
    assert lidos == {"C0PLATAFORMA", "C0TERAPIA", "D0ANA", "C0GRUPO", "D0JOANA"}


def test_padrao_em_branco_na_blocklist_nao_bloqueia_o_workspace_inteiro():
    # Substring vazia casaria com tudo e esvaziaria o diário em silêncio.
    registro: list[httpx.Request] = []

    fonte(registro=registro, excluidas=("", "   ")).coletar(JANELA)

    assert requisicoes_de(registro, "conversations.history"), "as conversas foram lidas"


# -- Paginação --------------------------------------------------------------


def test_segunda_pagina_de_conversas_e_lida_com_o_cursor_da_primeira():
    registro: list[httpx.Request] = []

    fonte(registro=registro).coletar(JANELA)

    das_conversas = requisicoes_de(registro, "users.conversations")
    assert len(das_conversas) == 2
    assert "cursor" not in parametros(das_conversas[0])
    assert parametros(das_conversas[1])["cursor"] == "cursor-das-conversas"


def test_segunda_pagina_do_historico_e_lida_com_o_cursor_da_primeira():
    registro: list[httpx.Request] = []

    eventos = fonte(registro=registro).coletar(JANELA)

    do_canal = [
        r
        for r in requisicoes_de(registro, "conversations.history")
        if parametros(r)["channel"] == "C0PLATAFORMA"
    ]
    assert len(do_canal) == 2
    assert parametros(do_canal[1])["cursor"] == "cursor-do-historico"
    assert any(e.titulo == DO_BOT for e in eventos), "a segunda página entrou no dia"


def test_paginacao_para_quando_o_cursor_nao_avanca():
    """Um cursor repetido giraria para sempre e queimaria a cota do usuário."""
    registro: list[httpx.Request] = []
    teimosa = {
        "ok": True,
        "channels": [],
        "response_metadata": {"next_cursor": "sempre-o-mesmo"},
    }

    fonte(registro=registro, respostas={"users.conversations": teimosa}).coletar(JANELA)

    assert len(requisicoes_de(registro, "users.conversations")) == 2


# -- Rate limit -------------------------------------------------------------


def resposta_429(segundos: str | None = "3") -> httpx.Response:
    cabecalhos = {"retry-after": segundos} if segundos is not None else {}
    return httpx.Response(429, headers=cabecalhos, json={"ok": False, "error": "ratelimited"})


def test_429_com_retry_after_e_esperado_e_a_requisicao_refeita():
    esperas: list[float] = []

    eventos = fonte(
        esperas=esperas,
        respostas={
            "conversations.history": [
                resposta_429("3"),
                HISTORICOS["C0PLATAFORMA"][0],
            ]
        },
    ).coletar(JANELA)

    assert esperas == [3.0], "esperou exatamente o que o Retry-After pediu"
    assert any(evento.titulo == DA_ANA for evento in eventos), "a leitura continuou"


def test_429_sem_retry_after_espera_o_padrao_em_vez_de_desistir():
    esperas: list[float] = []

    fonte(
        esperas=esperas,
        respostas={"conversations.history": [resposta_429(None), CONVERSA_VAZIA]},
    ).coletar(JANELA)

    assert esperas == [ESPERA_PADRAO_S]


def test_ok_false_ratelimited_dentro_de_um_200_tambem_e_esperado():
    esperas: list[float] = []
    limitado = httpx.Response(
        200, headers={"retry-after": "2"}, json={"ok": False, "error": "ratelimited"}
    )

    fonte(
        esperas=esperas,
        respostas={"conversations.history": [limitado, CONVERSA_VAZIA]},
    ).coletar(JANELA)

    assert esperas == [2.0]


def test_slack_que_nao_para_de_limitar_vira_erro_de_fonte():
    esperas: list[float] = []

    with pytest.raises(ErroDeFonte) as erro:
        fonte(
            esperas=esperas, respostas={"conversations.history": resposta_429("1")}
        ).coletar(JANELA)

    assert len(esperas) == TENTATIVAS_APOS_429, "insistiu antes de desistir"
    assert "continuou limitando" in str(erro.value)


def test_retry_after_grande_demais_e_recusado_em_vez_de_pendurar_a_tarefa():
    # A tarefa agendada roda de madrugada sem ninguém olhando: melhor um
    # diário marcado como incompleto que um processo dormindo uma hora.
    esperas: list[float] = []

    with pytest.raises(ErroDeFonte) as erro:
        fonte(
            esperas=esperas,
            respostas={"conversations.history": resposta_429(str(ESPERA_MAXIMA_S + 1))},
        ).coletar(JANELA)

    assert esperas == [], "não dormiu"
    assert "teto" in str(erro.value)


# -- Falhas -----------------------------------------------------------------


def test_token_ausente_vira_erro_de_fonte_dizendo_onde_preencher():
    with pytest.raises(ErroDeFonte) as erro:
        fonte(token="   ").coletar(JANELA)

    mensagem = str(erro.value)
    assert "[slack].user_token" in mensagem
    assert "docs/smoke-slack.md" in mensagem


def test_token_recusado_diz_como_gerar_outro():
    recusa = {"ok": False, "error": "invalid_auth"}

    with pytest.raises(ErroDeFonte) as erro:
        fonte(respostas={"auth.test": recusa}).coletar(JANELA)

    mensagem = str(erro.value)
    assert "invalid_auth" in mensagem
    assert "OAuth & Permissions" in mensagem


def test_scope_faltando_diz_qual_scope_falta_e_que_a_app_precisa_reinstalar():
    faltando = carregar_fixture("resposta_slack_erro_scope.json")

    with pytest.raises(ErroDeFonte) as erro:
        fonte(respostas={"conversations.history": faltando}).coletar(JANELA)

    mensagem = str(erro.value)
    assert "im:history" in mensagem, "a mensagem nomeia o scope que falta"
    assert "User Token Scopes" in mensagem
    assert "reinstale" in mensagem


def test_bot_token_no_lugar_do_user_token_e_apontado_pelo_nome():
    recusa = {"ok": False, "error": "not_allowed_token_type"}

    with pytest.raises(ErroDeFonte) as erro:
        fonte(respostas={"auth.test": recusa}).coletar(JANELA)

    mensagem = str(erro.value)
    assert "xoxp" in mensagem
    assert "xoxb" in mensagem


def test_app_sem_aprovacao_do_admin_manda_o_usuario_para_o_roteiro():
    recusa = {"ok": False, "error": "team_access_not_granted"}

    with pytest.raises(ErroDeFonte) as erro:
        fonte(respostas={"auth.test": recusa}).coletar(JANELA)

    assert "docs/smoke-slack.md" in str(erro.value)


def test_canal_que_o_slack_recusa_sozinho_nao_derruba_o_slack_inteiro():
    # Perder um canal é melhor que perder o dia inteiro do diário.
    def recusar_so_o_canal(requisicao: httpx.Request) -> httpx.Response:
        enviados = dict(requisicao.url.params)
        if enviados.get("channel") == "C0PLATAFORMA":
            return httpx.Response(200, json={"ok": False, "error": "not_in_channel"})
        return httpx.Response(
            200, json=responder_padrao("conversations.history", enviados, HISTORICOS)
        )

    eventos = fonte(respostas={"conversations.history": recusar_so_o_canal}).coletar(
        JANELA
    )

    assert any(evento.referencia == f"DM com {DA_ANA}" for evento in eventos)
    assert not any(evento.referencia == "#plataforma" for evento in eventos)


def test_erro_desconhecido_do_slack_ainda_manda_conferir_token_e_scopes():
    with pytest.raises(ErroDeFonte) as erro:
        fonte(respostas={"auth.test": {"ok": False, "error": "bode_expiatorio"}}).coletar(
            JANELA
        )

    mensagem = str(erro.value)
    assert "bode_expiatorio" in mensagem
    assert "[slack].user_token" in mensagem


@pytest.mark.parametrize(
    ("codigo", "esperado"),
    [
        (401, "recusou o token"),
        (403, "recusou o token"),
        (500, "fora do ar"),
        (503, "fora do ar"),
        (418, "recusou a requisição"),
    ],
)
def test_status_http_que_nao_e_200_vira_conselho_em_portugues(codigo: int, esperado: str):
    with pytest.raises(ErroDeFonte) as erro:
        fonte(respostas={"auth.test": httpx.Response(codigo, text="")}).coletar(JANELA)

    mensagem = str(erro.value)
    assert f"HTTP {codigo}" in mensagem
    assert esperado in mensagem


def test_corpo_que_nao_e_json_vira_erro_de_fonte():
    with pytest.raises(ErroDeFonte, match="não é JSON"):
        fonte(respostas={"auth.test": httpx.Response(200, text="<html>oops</html>")}).coletar(
            JANELA
        )


def test_rede_caida_vira_erro_de_fonte_falando_em_conexao():
    def cair(requisicao: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rota para o host", request=requisicao)

    with pytest.raises(ErroDeFonte) as erro:
        fonte(respostas={"auth.test": cair}).coletar(JANELA)

    mensagem = str(erro.value)
    assert "Falha de rede" in mensagem
    assert "Confira a conexão" in mensagem


def test_tempo_esgotado_vira_erro_de_fonte():
    def demorar(requisicao: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("demorou demais", request=requisicao)

    with pytest.raises(ErroDeFonte, match="não respondeu a tempo"):
        fonte(respostas={"auth.test": demorar}).coletar(JANELA)


def test_nenhum_erro_httpx_escapa_para_a_costura():
    # A costura só conhece `ErroDeFonte`; um `httpx.HTTPError` vazando mataria
    # o diário inteiro em vez de marcar só o Slack.
    def cair(requisicao: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("nada responde", request=requisicao)

    with pytest.raises(ErroDeFonte):
        fonte(respostas={"conversations.history": cair}).coletar(JANELA)


@pytest.mark.parametrize(
    "resposta",
    [
        {"ok": False, "error": "invalid_auth"},
        {"ok": False, "error": "missing_scope", "needed": "im:history"},
        httpx.Response(401, text="unauthorized"),
        httpx.Response(500, text="oops"),
    ],
)
def test_o_token_nunca_aparece_na_mensagem_de_erro(resposta):
    segredo = "xoxp-token-secreto-do-usuario"

    with pytest.raises(ErroDeFonte) as erro:
        fonte(token=segredo, respostas={"auth.test": resposta}).coletar(JANELA)

    assert segredo not in str(erro.value)


# -- Scopes -----------------------------------------------------------------


def test_pede_so_os_scopes_de_leitura_e_nao_pede_search_read():
    # `search:read` não é usado por este coletor e é dos que mais levantam
    # bandeira na revisão do admin.
    assert "search:read" not in SCOPES_MINIMOS
    assert set(SCOPES_MINIMOS) == {
        "channels:history",
        "channels:read",
        "groups:history",
        "groups:read",
        "im:history",
        "im:read",
        "mpim:history",
        "mpim:read",
        "users:read",
    }
    assert not any(scope.endswith(":write") for scope in SCOPES_MINIMOS)


# -- Configuração e CLI -----------------------------------------------------


def configuracao_com_slack(
    token: str, tmp_path: Path, excluidas: tuple[str, ...] = ()
) -> Configuracao:
    return Configuracao(
        vault=tmp_path / "vault",
        slack_user_token=token,
        slack_conversas_excluidas=excluidas,
        origem=tmp_path / "config.toml",
    )


def test_de_configuracao_le_o_token_e_a_blocklist_do_arquivo_local(tmp_path: Path):
    registro: list[httpx.Request] = []

    def responder(requisicao: httpx.Request) -> httpx.Response:
        registro.append(requisicao)
        parametros_ = dict(requisicao.url.params)
        if parametros_.get("channel") == "C0TERAPIA":
            raise AssertionError("a blocklist da configuração não foi respeitada")
        metodo = requisicao.url.path.rsplit("/", 1)[-1]
        return httpx.Response(
            200, json=responder_padrao(metodo, parametros_, HISTORICOS)
        )

    coletor = de_configuracao(
        configuracao_com_slack(TOKEN_FALSO, tmp_path, ("#terapia",)),
        cliente=httpx.Client(transport=httpx.MockTransport(responder)),
        dormir=lambda _: None,
    )
    coletor.coletar(JANELA)

    assert coletor.nome == "slack"
    assert registro[0].headers["authorization"] == f"Bearer {TOKEN_FALSO}"


def test_montar_fontes_liga_o_slack_quando_o_token_esta_preenchido(tmp_path: Path):
    fontes = montar_fontes(configuracao_com_slack(TOKEN_FALSO, tmp_path))

    assert [fonte_.nome for fonte_ in fontes] == ["slack"]
    assert isinstance(fontes[0], FonteSlack)


# -- A costura inteira ------------------------------------------------------


def mensagem_no_dia(janela: Janela, minutos: int, **campos) -> dict:
    """Uma mensagem gravada, recolocada dentro da janela local do dia.

    As fixtures fixam epochs em UTC para o teste de tradução não depender do
    relógio da máquina. A costura precisa do contrário: mensagens que caiam na
    janela **local**, rode a suíte no fuso que rodar.
    """
    momento = janela.inicio + timedelta(minutes=minutos)
    return {"type": "message", "ts": f"{momento.timestamp():.6f}", **campos}


def test_o_diario_ganha_a_secao_do_slack_com_as_conversas_do_dia(
    configuracao_do_diario, caminho_do_vault: Path
):
    configuracao = configuracao_do_diario()
    dia = date(2026, 9, 3)
    janela = janela_do_dia(dia, configuracao.diario_inicio_do_dia)
    historicos = {
        "C0PLATAFORMA": [
            {
                "ok": True,
                "messages": [
                    mensagem_no_dia(
                        janela,
                        602,
                        user="U0ANA",
                        text="Subi o fix do frete, <@U0GABRIEL> revisa?",
                    ),
                    mensagem_no_dia(
                        janela, 620, user="U0GABRIEL", text="revisei, tá de pé"
                    ),
                ],
            }
        ],
        "D0ANA": [
            {
                "ok": True,
                "messages": [
                    mensagem_no_dia(
                        janela,
                        700,
                        user="U0ANA",
                        text="consegue olhar o deploy do OMS amanhã cedo?",
                    )
                ],
            }
        ],
    }
    resumo = ResumoDoDiaFake()

    resultado = gerar_diario(
        dia,
        configuracao=configuracao,
        fontes=[fonte(historicos=historicos, excluidas=("#terapia",), proibidos=("C0TERAPIA",))],
        resumo=resumo,
    )

    nota = (caminho_do_vault / "diario" / "2026-09-03.md").read_text(encoding="utf-8")
    assert resultado.fontes_lidas == ("slack",)
    assert "## Slack" in nota
    assert "### #plataforma" in nota
    assert f"### DM com {DA_ANA}" in nota
    assert "> Subi o fix do frete, @Gabriel Velozo revisa?" in nota
    assert "terapia" not in nota, "a conversa bloqueada não chegou nem a ser lida"


# -- Contra a API de verdade ------------------------------------------------
#
# Só roda na máquina do usuário, com o user token da app interna preenchido.
# Sem token, pula — e é isso que se espera enquanto o admin não aprovar a app.
# O roteiro para criar a app está em `docs/smoke-slack.md`.


def token_configurado() -> str:
    try:
        return carregar().slack_user_token
    except ConfiguracaoInvalida:
        return ""


@pytest.mark.rede
def test_rede_le_as_conversas_de_ontem_no_slack_de_verdade():
    """Prova ponta a ponta que token, scopes, paginação e tradução batem.

    Lê a janela de ontem, que é o caso real do diário. Um dia sem conversa
    devolve tupla vazia — isso não é falha, e o teste continua provando que os
    scopes foram aceitos.
    """
    token = token_configurado()
    if not token:
        pytest.skip("sem [slack].user_token na configuração local")

    ontem = date.fromordinal(date.today().toordinal() - 1)
    janela = janela_do_dia(ontem)
    eventos = FonteSlack(token).coletar(janela)

    for evento in eventos:
        assert evento.fonte == "slack"
        assert evento.momento.tzinfo is not None
        assert janela.contem(evento.momento), "a fonte recorta pela janela"
        assert evento.titulo.strip()
