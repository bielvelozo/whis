"""O tema de fábrica: a página inicial da loja comparada com a demonstração oficial do mesmo tema, e o e-mail de redesenho que só cita o que bateu."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from whis import lojas_email, lojas_shopify, tema_de_fabrica
from whis.agencias_email import EmailEscrito
from whis.lojas_shopify import CAMINHO_DA_LISTA_DE_LOJAS, Candidata, PaginaInicial
from whis.medida_no_celular import MedidaNoCelular
from whis.tema_de_fabrica import CORES, FONTES, SECOES, Impressao, TemaDeFabrica

AGORA = datetime(2026, 10, 19, 12, 30, tzinfo=timezone(timedelta(hours=-3)))
TEMA_DO_SITE = "https://themes.shopify.com/themes/horizon"
DEMONSTRACAO = "https://theme-horizon-demo.myshopify.com/"
INKLY = "https://github.com/bielvelozo/inkly-shopify-theme"


def _pagina(nome: str = "Horizon", *, fonte: str = "Inter", fundo: str = "255 255 255", secoes=("hero_TA4rQk", "product_list_qU3bEB"), loja_de_temas: bool = True) -> str:
    id_da_loja = 2481 if loja_de_temas else "null"
    tema = f'<script>Shopify.theme = {{"name":"{nome}","schema_name":"Horizon","schema_version":"3.2.0","theme_store_id":{id_da_loja},"role":"main"}};</script>'
    estilo = (
        f"<style>:root {{ --font-body--family: {fonte}, sans-serif; --font-heading--family: var(--font-body--family); }}"
        f".color-scheme-1 {{ --color-background: rgb({fundo} / 1.0); --color-foreground: rgb(0 0 0 / 0.81);"
        " --color-primary-button-background: rgb(0 0 0 / 1.0); --color-primary-button-text: rgb(255 255 255 / 1.0); }</style>"
    )
    corpo = "".join(f'<div id="shopify-section-template--25678738620737__{s}" class="shopify-section"></div>' for s in secoes)
    return tema + estilo + corpo


PAGINA_DO_TEMA = f'<div data-controller="demo-store" data-demo-store-iframe-url-value="{DEMONSTRACAO}"></div>'


def _abrir(paginas: dict[str, str], abertas: list[str] | None = None):
    def abrir(url: str) -> str | None:
        if abertas is not None:
            abertas.append(url)
        return paginas.get(url)

    return abrir


def test_a_impressao_le_fontes_cores_e_secoes_sem_os_apps():
    html = _pagina(secoes=("hero_TA4rQk", "af42648b-9f77-4652-8563-5141d782af00", "product_list_qU3bEB"))

    impressao = tema_de_fabrica.impressao(html)

    assert impressao.fontes == {"inter"}
    assert "--color-background=255 255 255 1.0" in impressao.cores and len(impressao.cores) == 4
    assert impressao.secoes == ("hero", "product_list")


def test_a_loja_igual_a_demonstracao_e_de_fabrica_e_a_demonstracao_fica_guardada(tmp_path: Path):
    estado = tmp_path / "temas.json"
    abertas: list[str] = []
    abrir = _abrir({TEMA_DO_SITE: PAGINA_DO_TEMA, DEMONSTRACAO: _pagina("Horizon demo store 3.2.0")}, abertas)

    resultado = tema_de_fabrica.conferir(_pagina("Horizon"), abrir=abrir, estado=estado, agora=AGORA)
    de_novo = tema_de_fabrica.conferir(_pagina("Cópia de Horizon"), abrir=abrir, estado=estado, agora=AGORA + timedelta(days=3))

    assert resultado is not None and resultado.de_fabrica
    assert resultado.iguais == (FONTES, CORES, SECOES) and resultado.fontes == ("Inter",) and not resultado.renomeado
    assert de_novo is not None and de_novo.de_fabrica and not de_novo.renomeado
    assert abertas == [TEMA_DO_SITE, DEMONSTRACAO], "a demonstração é aberta uma vez e guardada"
    assert json.loads(estado.read_text(encoding="utf-8"))["horizon"]["demonstracao"] == DEMONSTRACAO
    assert resultado.como_linha() == (
        "Horizon 3.2.0; igual à demonstração em: as mesmas fontes da demonstração do Horizon (Inter), "
        "as mesmas cores da demonstração do Horizon, as mesmas seções, na mesma ordem, da página inicial da demonstração do Horizon"
    )


def test_a_loja_com_fonte_cor_e_secoes_proprias_nao_e_de_fabrica(tmp_path: Path):
    abrir = _abrir({TEMA_DO_SITE: PAGINA_DO_TEMA, DEMONSTRACAO: _pagina()})
    personalizada = _pagina("Minha Loja", fonte="Judgemestar", fundo="241 235 218", secoes=("slideshow_a9YU84", "custom_liquid_LmNqLC", "faq_Q8cAxA"))
    so_a_fonte = _pagina(fundo="241 235 218", secoes=("slideshow_a9YU84", "custom_liquid_LmNqLC"))

    resultado = tema_de_fabrica.conferir(personalizada, abrir=abrir, estado=tmp_path / "t.json", agora=AGORA)
    so_uma = tema_de_fabrica.conferir(so_a_fonte, abrir=abrir, estado=tmp_path / "t.json", agora=AGORA)

    assert resultado is not None and resultado.iguais == () and not resultado.de_fabrica and resultado.renomeado
    assert so_uma is not None and so_uma.iguais == (FONTES,) and not so_uma.de_fabrica
    com_as_cores_da_marca = tema_de_fabrica.conferir(_pagina(fundo="241 235 218"), abrir=abrir, estado=tmp_path / "t.json", agora=AGORA)
    assert com_as_cores_da_marca is not None and com_as_cores_da_marca.iguais == (FONTES, SECOES)
    assert not com_as_cores_da_marca.de_fabrica, "a loja que trocou as cores já tem a marca dela"


def test_tema_sob_medida_ou_demonstracao_que_nao_abre_nao_vira_comparacao(tmp_path: Path):
    sob_medida = '<script>Shopify.theme = {"name":"x","schema_name":"Tema Base - Agência","schema_version":"1.0.0","theme_store_id":null};</script>'
    abertas: list[str] = []

    assert tema_de_fabrica.conferir(sob_medida, abrir=_abrir({}, abertas), estado=tmp_path / "t.json", agora=AGORA) is None
    assert abertas == []
    assert tema_de_fabrica.conferir(_pagina(), abrir=_abrir({}, abertas), estado=tmp_path / "t.json", agora=AGORA) is None
    assert tema_de_fabrica.conferir(_pagina(), abrir=_abrir({}, abertas), estado=tmp_path / "t.json", agora=AGORA + timedelta(days=1)) is None
    assert abertas == [TEMA_DO_SITE], "a demonstração que não abriu espera 30 dias para tentar de novo"


# -- a procura -----------------------------------------------------------------------------------


class _Busca:
    def buscar(self, conhecidas, ramos_fora=()):
        return (
            Candidata("De Fábrica", "Recife/PE", "https://defabrica.com.br", "contato@defabrica.com.br", "moda", "Vende roupa."),
            Candidata("Personalizada", "Recife/PE", "https://personalizada.com.br", "contato@personalizada.com.br", "moda"),
        )


def test_a_loja_rapida_com_o_tema_de_fabrica_entra_na_lista_com_a_comparacao(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / "cacada").mkdir(parents=True)
    paginas = {
        "https://defabrica.com.br/": PaginaInicial(_pagina(), "https://defabrica.com.br/"),
        "https://personalizada.com.br/": PaginaInicial(_pagina(fonte="Judgemestar", fundo="1 2 3", secoes=("slideshow_a9YU84", "faq_Q8cAxA")), "https://personalizada.com.br/"),
        TEMA_DO_SITE: PaginaInicial(PAGINA_DO_TEMA, TEMA_DO_SITE),
        DEMONSTRACAO: PaginaInicial(_pagina("Horizon demo store"), DEMONSTRACAO),
    }

    resultado = lojas_shopify.buscar_se_faltar(
        vault, _Busca(), estado=tmp_path / "lojas.json", na_fila=0, abrir=paginas.get,
        medir_no_celular=lambda url: MedidaNoCelular(2.1, 0.9, 40), agora=AGORA,
    )

    assert [loja.nome for loja in resultado.novas] == ["De Fábrica"]
    assert resultado.novas[0].fabrica is not None and resultado.novas[0].fabrica.de_fabrica
    assert resultado.descartadas == {"a página não é lenta nem tem o tema de fábrica": 1}
    assert (tmp_path / tema_de_fabrica.NOME_DO_ESTADO).is_file(), "a demonstração fica ao lado do estado da procura"
    nota = (vault / CAMINHO_DA_LISTA_DE_LOJAS).read_text(encoding="utf-8")
    assert "**1. De Fábrica** · Recife/PE · https://defabrica.com.br" in nota
    assert "- Tema de fábrica: Horizon 3.2.0; igual à demonstração em: as mesmas fontes da demonstração do Horizon (Inter)" in nota


# -- o e-mail de redesenho -------------------------------------------------------------------------

LISTA = """\
# Lojas Shopify no Brasil

## Nunca contatar

## Outubro de 2026 (busca de 19/10)

**1. Lenta** · São Paulo/SP · https://lenta.com.br
- Contato: contato@lenta.com.br
- Medida em 19/10: no celular em 4G, a maior imagem apareceu em 9,4 s (LCP); 3,2 MB em 140 pedidos; tema Dawn 15.0.0

**2. Moda Boa** · Recife/PE · https://modaboa.com.br
- Contato: contato@modaboa.com.br
- Medida em 19/10: no celular em 4G, a maior imagem apareceu em 2,1 s (LCP); 0,9 MB em 40 pedidos; tema Horizon 3.2.0
- Tema de fábrica: Horizon 3.2.0; igual à demonstração em: as mesmas fontes da demonstração do Horizon (Inter), as mesmas cores da demonstração do Horizon

**3. Outra de Fábrica** · Recife/PE · https://outra.com.br
- Contato: sac@outra.com.br
- Tema de fábrica: Dawn 15.0.0; igual à demonstração em: as mesmas cores da demonstração do Dawn
"""

CRITERIOS = f"""\
## Portfólio

- Tema Shopify Inkly: {INKLY} — tema Online Store 2.0 feito do zero
- Site do portfólio: https://gabrielvelozo.pages.dev — o portfólio inteiro
"""

FABRICA = TemaDeFabrica("Horizon", "3.2.0", DEMONSTRACAO, (FONTES, CORES), ("Inter",), False)


def _corpo_do_redesenho(extra: str = "") -> str:
    return (
        "Oi, pessoal da Moda Boa,\n\n"
        "Reparei que a loja de vocês usa o tema Horizon com as mesmas fontes e cores da demonstração oficial dele. "
        f"Quem conhece o tema reconhece a loja, e a marca aparece pouco além do logo.{extra}\n\n"
        "Sou o Gabriel, desenvolvedor Shopify em Matão (SP), e desde março cuido do tema de uma loja Shopify Plus. "
        f"Fiz este tema do zero: {INKLY}\n\n"
        "Redesenho a página inicial com a tipografia, as cores e as seções da marca, mantendo produtos, apps e checkout, "
        "com escopo, prazo e preço combinados antes. Faz sentido eu mandar como redesenharia, com prazo e preço fechados?\n\n"
        "Se não for prioridade agora, é só responder que eu não escrevo de novo.\n\n"
        "Abraço,\nGabriel Velozo\ngithub.com/bielvelozo"
    )


class _Escritor:
    def __init__(self, redesenhos: list[str] | None = None) -> None:
        self.redesenhos = redesenhos or [_corpo_do_redesenho()]
        self.pedidos: list[tuple[str, str, str]] = []

    def escrever(self, alvo, medida, portfolio, *, corrigir=""):
        self.pedidos.append(("velocidade", alvo.email, corrigir))
        return EmailEscrito("Página inicial no celular", "x")

    def escrever_redesenho(self, alvo, fabrica, portfolio, *, corrigir=""):
        self.pedidos.append(("redesenho", alvo.email, corrigir))
        corpo = self.redesenhos[min(len([p for p in self.pedidos if p[0] == "redesenho"]), len(self.redesenhos)) - 1]
        return EmailEscrito("A Moda Boa com a cara da marca", corpo)


class _Celular(list):
    def __call__(self, texto: str, *, botoes=()) -> bool:
        self.append((texto, tuple(botoes)))
        return True


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    if not vault.exists():
        (vault / "cacada").mkdir(parents=True)
        (vault / CAMINHO_DA_LISTA_DE_LOJAS).write_text(LISTA, encoding="utf-8")
        (vault / "cacada" / "criterios.md").write_text(CRITERIOS, encoding="utf-8")
    return vault


def _preparar(tmp_path: Path, escritor: _Escritor, *, comparacoes: list | None = None, por_dia: int = 0, por_dia_redesenho: int = 1):
    celular = _Celular()
    fila = list(comparacoes) if comparacoes is not None else [FABRICA]
    comparadas: list[str] = []

    def conferir(site: str):
        comparadas.append(site)
        return fila.pop(0) if fila else FABRICA

    feitos = lojas_email.preparar(
        _vault(tmp_path), escritor=escritor, estado=tmp_path / "lojas-emails.json", celular=celular, por_dia=por_dia,
        medir_no_celular=lambda url: MedidaNoCelular(9.2, 3.2, 140), por_dia_redesenho=por_dia_redesenho,
        conferir_tema=conferir, agora=AGORA,
    )
    return feitos, celular, comparadas


def _estado(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "lojas-emails.json").read_text(encoding="utf-8"))["emails"]


def test_a_loja_de_fabrica_ganha_o_email_de_redesenho_com_a_comparacao_de_agora(tmp_path: Path):
    escritor = _Escritor()

    feitos, celular, comparadas = _preparar(tmp_path, escritor)

    assert [f.email for f in feitos] == ["contato@modaboa.com.br"]
    assert comparadas == ["https://modaboa.com.br"]
    assert escritor.pedidos == [("redesenho", "contato@modaboa.com.br", "")], "a lenta não gasta a cota do redesenho"
    [(texto, botoes)] = celular
    assert texto.startswith("E-mail de redesenho para a loja Moda Boa (Recife/PE), para você aprovar")
    assert "Tema comparado agora: Horizon 3.2.0; igual à demonstração em: as mesmas fontes" in texto
    assert botoes == ((lojas_email.ROTULO_DO_BOTAO, lojas_email.chave_do_toque("contato@modaboa.com.br")),)
    registro = _estado(tmp_path)["contato@modaboa.com.br"]
    assert registro["oferta"] == lojas_email.REDESENHO and registro["tema"] == "Horizon" and registro["situacao"] == lojas_email.PARA_APROVAR
    nota = (tmp_path / "vault" / registro["nota"]).read_text(encoding="utf-8")
    assert 'tema: "Horizon 3.2.0; igual à demonstração em:' in nota and "medida:" not in nota


def test_as_duas_cotas_correm_juntas_no_mesmo_dia(tmp_path: Path):
    escritor = _Escritor()

    feitos, _celular, _comparadas = _preparar(tmp_path, escritor, por_dia=1)

    assert [p[:2] for p in escritor.pedidos] == [
        ("velocidade", "contato@lenta.com.br"), ("velocidade", "contato@lenta.com.br"), ("redesenho", "contato@modaboa.com.br"),
    ]
    assert [f.email for f in feitos] == ["contato@modaboa.com.br"], "o de velocidade do escritor falso não passa na conferência"


def test_o_tema_que_mudou_sai_da_fila_e_a_proxima_de_fabrica_e_comparada(tmp_path: Path):
    mudou = TemaDeFabrica("Horizon", "3.2.0", DEMONSTRACAO, (FONTES,))
    dawn = TemaDeFabrica("Dawn", "15.0.0", "https://theme-dawn-demo.myshopify.com/", (CORES, SECOES))
    assert not TemaDeFabrica("Dawn", "15.0.0", "", (FONTES, SECOES)).de_fabrica
    escritor = _Escritor([_corpo_do_redesenho().replace("Horizon", "Dawn")])

    feitos, _celular, comparadas = _preparar(tmp_path, escritor, comparacoes=[mudou, dawn])

    assert comparadas == ["https://modaboa.com.br", "https://outra.com.br"]
    assert [f.email for f in feitos] == ["sac@outra.com.br"]
    assert _estado(tmp_path)["contato@modaboa.com.br"]["motivo"] == "o tema Horizon não bate mais com a demonstração"


def test_o_redesenho_que_julga_o_visual_ou_esquece_o_tema_volta_ao_claude():
    from whis.criterios_da_cacada import PecaDoPortfolio

    pecas = (PecaDoPortfolio("Tema Shopify Inkly", INKLY, "tema feito do zero"),)

    assert lojas_email.problemas_do_redesenho(EmailEscrito("A Moda Boa", _corpo_do_redesenho()), pecas, "Horizon") == []
    julga = lojas_email.problemas_do_redesenho(EmailEscrito("A Moda Boa", _corpo_do_redesenho(" O visual está genérico.")), pecas, "Horizon")
    assert julga == ['julga o visual da loja ("genérico"); diga só o que bateu com a demonstração']
    sem_tema = lojas_email.problemas_do_redesenho(EmailEscrito("A Moda Boa", _corpo_do_redesenho()), pecas, "Prestige")
    assert sem_tema == ['falta o nome do tema, "Prestige"']


def test_o_julgamento_vai_de_volta_ao_claude_e_o_corrigido_sai(tmp_path: Path):
    escritor = _Escritor([_corpo_do_redesenho(" O visual está feio."), _corpo_do_redesenho()])

    feitos, _celular, _comparadas = _preparar(tmp_path, escritor)

    assert [f.email for f in feitos] == ["contato@modaboa.com.br"]
    assert escritor.pedidos[1][2].startswith('julga o visual da loja ("feio")')


def test_o_toque_no_redesenho_confere_o_tema_e_manda_pelo_gmail(tmp_path: Path):
    _preparar(tmp_path, _Escritor())
    enviados: list[tuple[str, str, str]] = []

    resposta = lojas_email.tocou_enviar_email(
        lojas_email.chave_do_toque("contato@modaboa.com.br"), vault=tmp_path / "vault", estado=tmp_path / "lojas-emails.json",
        enviar=lambda para, assunto, corpo: enviados.append((para, assunto, corpo)), agora=AGORA + timedelta(minutes=10),
    )

    assert resposta.texto == "E-mail enviado para a loja Moda Boa (contato@modaboa.com.br), do seu Gmail."
    assert [e[0] for e in enviados] == ["contato@modaboa.com.br"] and "tema Horizon" in enviados[0][2]
    registro = _estado(tmp_path)["contato@modaboa.com.br"]
    assert registro["situacao"] == lojas_email.ENVIADO
    nota = (tmp_path / "vault" / registro["nota"]).read_text(encoding="utf-8")
    assert "status: enviado em 2026-10-19" in nota and 'tema: "Horizon 3.2.0;' in nota


def test_o_pedido_do_redesenho_leva_a_comparacao_e_nao_a_medida():
    alvo = lojas_email.AlvoLoja("Moda Boa", "Recife/PE", "https://modaboa.com.br", "contato@modaboa.com.br", "Tema de fábrica: Horizon")
    from whis.criterios_da_cacada import PecaDoPortfolio

    texto = lojas_email.pedido_do_redesenho(alvo, FABRICA, (PecaDoPortfolio("Tema Shopify Inkly", INKLY, "do zero"),))

    assert "COMPARAÇÃO (feita agora pelo Whis" in texto and "MEDIDA" not in texto
    assert f"comparada com a demonstração oficial do tema ({DEMONSTRACAO}): as mesmas fontes da demonstração do Horizon (Inter)" in texto
    assert "o tema publicado ainda tem o nome de fábrica" in texto
    assert alvo.oferta == lojas_email.REDESENHO
    assert Impressao.de_json(Impressao(frozenset({"inter"}), frozenset({"a=1"}), ("hero",)).para_json()).secoes == ("hero",)
