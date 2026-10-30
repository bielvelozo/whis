import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from whis import instagram
from whis.instagram import InstagramFake, arroba_limpa, buscar_do_dia, conferir, mensagem_no_celular, problemas_da_mensagem, seguidores

AGORA = datetime(2026, 10, 30, 12, 30, tzinfo=timezone(timedelta(hours=-3)))

BOA = (
    "Oi, pessoal da Casa Lume, tudo certo? Aqui é o Gabriel, faço lojas Shopify. Dei uma olhada no perfil e reparei "
    "que os pedidos vão todos pelo direct. Com uma loja simples, a cliente escolhe, paga e calcula o frete sozinha, "
    "a qualquer hora. Posso te mandar um exemplo de como ficaria?"
)


def _bruto(arroba: str, **campos: str) -> dict:
    return {
        "arroba": arroba, "nome": arroba.title(), "nicho": "velas", "seguidores": "2,1 mil", "problema": "Vende pelo direct",
        "prova": "Pedidos pelo direct", "mensagem": BOA, **campos,
    }


class Porta:
    def __init__(self, *brutos: dict) -> None:
        self.brutos = brutos
        self.pedidos: list[tuple[int, list[str]]] = []

    def buscar(self, quantos, conhecidos, voz):
        self.pedidos.append((quantos, list(conhecidos)))
        return self.brutos


@pytest.mark.parametrize(
    ("texto", "numero"),
    [("4.374", 4374), ("3,6 mil", 3600), ("4,3K", 4300), ("1.2k", 1200), ("Mais de 2 mil seguidores", 2000), ("850", 850), ("", None)],
)
def test_os_seguidores_como_a_busca_mostra_viram_numero(texto, numero):
    assert seguidores(texto) == numero


def test_o_arroba_sai_limpo_do_link_ou_do_texto():
    assert arroba_limpa("@Casa.Lume") == "casa.lume"
    assert arroba_limpa("https://www.instagram.com/casa_lume/?hl=pt") == "casa_lume"
    assert arroba_limpa("não é um @ válido") == ""


def test_a_mensagem_no_jeito_do_voz_passa():
    assert problemas_da_mensagem(BOA) == []


def test_o_whatsapp_e_o_preco_da_marca_podem_ser_a_observacao():
    mensagem = BOA.replace("os pedidos vão todos pelo direct", "os pedidos de moda praia saem pelo WhatsApp da bio").replace(
        "a cliente escolhe", "a cliente vê o preço, escolhe"
    )

    assert problemas_da_mensagem(mensagem) == []


@pytest.mark.parametrize(
    ("mensagem", "problema"),
    [
        (BOA.replace("Posso", "Dá uma olhada: velozo.dev. Posso"), "tem link (a primeira mensagem vai sem link)"),
        (BOA.replace("Posso", "Sai por R$ 400. Posso"), 'usa "R$"'),
        (BOA.replace("Posso", "Me chama no WhatsApp. Posso"), 'usa "meu WhatsApp"'),
        (BOA.replace("Posso", "Uso IA no trabalho. Posso"), 'usa "IA"'),
        (BOA.replace("Oi, pessoal da Casa Lume, tudo certo?", "Oi! Amei os produtos de vocês."), "abre com elogio"),
        (BOA + " 😊", "tem emoji"),
        (BOA.removesuffix("?") + ".", "não termina em pergunta"),
        (BOA.replace("Faz", "faz") + " Faz sentido pra vocês?", 'usa "faz sentido"'),
        (BOA * 3, "passa de 450 caracteres"),
    ],
)
def test_a_mensagem_fora_do_jeito_e_barrada(mensagem, problema):
    assert problema in problemas_da_mensagem(mensagem)


def test_perfil_fora_da_faixa_de_seguidores_ou_ja_conhecido_fica_de_fora():
    assert conferir(_bruto("grande", seguidores="12 mil"), set())[1] == "fora de 500 a 5 mil seguidores"
    assert conferir(_bruto("pequena", seguidores="320"), set())[1] == "fora de 500 a 5 mil seguidores"
    assert conferir(_bruto("casalume"), {"casalume"})[1] == "já recebeu"
    assert conferir(_bruto("semprova", prova=""), set())[1] == "sem a prova do problema"


def test_a_lista_do_dia_grava_o_estado_a_nota_e_manda_um_perfil_por_mensagem(tmp_path: Path):
    estado, mandadas = tmp_path / "instagram.json", []
    porta = Porta(_bruto("casalume"), _bruto("ja.foi"), _bruto("velasdalu", mensagem="Oi, Lu. velozo.dev"), _bruto("ateliecasca"))
    estado.write_text(json.dumps({"perfis": {"ja.foi": {"quando": "2026-10-29T12:30-03:00"}}}), encoding="utf-8")

    resultado = buscar_do_dia(tmp_path, porta, estado=estado, avisar=lambda t: mandadas.append(t) or True, por_dia=10, agora=AGORA)

    assert [p.arroba for p in resultado.novos] == ["casalume", "ateliecasca"]
    assert resultado.descartados == {"já recebeu": 1, "mensagem fora do jeito": 1}
    assert porta.pedidos == [(10 + instagram.FOLGA, ["ja.foi"])]
    memoria = json.loads(estado.read_text(encoding="utf-8"))
    assert set(memoria["perfis"]) == {"ja.foi", "casalume", "ateliecasca"} and memoria["ultimo_dia"] == "2026-10-30"
    nota = (tmp_path / "cacada/instagram/2026-10-30.md").read_text(encoding="utf-8")
    assert "@casalume" in nota and BOA in nota
    assert len(mandadas) == 3 and mandadas[0].startswith("Instagram de hoje: 2 perfis")
    assert "<pre>Oi, pessoal da Casa Lume" in mandadas[1]


def test_so_uma_lista_por_dia_a_nao_ser_forcando(tmp_path: Path):
    estado = tmp_path / "instagram.json"
    buscar_do_dia(tmp_path, Porta(_bruto("casalume")), estado=estado, avisar=lambda t: True, por_dia=10, agora=AGORA)

    de_novo = buscar_do_dia(tmp_path, Porta(_bruto("outra")), estado=estado, avisar=lambda t: True, por_dia=10, agora=AGORA)
    forcada = buscar_do_dia(tmp_path, Porta(_bruto("outra")), estado=estado, avisar=lambda t: True, por_dia=10, agora=AGORA, forcar=True)

    assert de_novo.ja_feita and forcada.novos[0].arroba == "outra"


def test_para_no_numero_do_dia(tmp_path: Path):
    porta = Porta(*(_bruto(f"marca{n}") for n in range(8)))

    resultado = buscar_do_dia(tmp_path, porta, estado=tmp_path / "e.json", avisar=lambda t: True, por_dia=3, agora=AGORA)

    assert len(resultado.novos) == 3


def test_com_zero_por_dia_nem_busca(tmp_path: Path):
    porta = Porta(_bruto("casalume"))

    assert buscar_do_dia(tmp_path, porta, estado=tmp_path / "e.json", avisar=lambda t: True, por_dia=0, agora=AGORA).ja_feita
    assert porta.pedidos == []


def test_no_celular_o_texto_vem_escapado_e_num_bloco_que_copia():
    perfil, _ = conferir(_bruto("casalume", nome="Casa <Lume> & Cia"), set())

    texto = mensagem_no_celular(perfil)

    assert "Casa &lt;Lume&gt; &amp; Cia" in texto and "2,1 mil" in texto and texto.endswith("</pre>")


def test_o_fake_tem_um_que_passa_e_um_que_nao():
    brutos = InstagramFake().buscar(10, [], "")

    assert [conferir(b, set())[1] for b in brutos] == ["", "mensagem fora do jeito"]


def test_o_pedido_ao_claude_proibe_link_e_abrir_o_instagram():
    assert "Sem link" in instagram.SISTEMA_DO_INSTAGRAM and "Nunca abra o instagram.com" in instagram.SISTEMA_DO_INSTAGRAM
