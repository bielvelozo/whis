# Dev com IA no jornal — plano de implementação

> Para quem executa: tarefas em ordem, cada uma test-first (`- [ ]` marca o andamento). Rodar a
> suíte com `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` (o `pyproject` já passa
> `-q -m "not rede"`).

**Objetivo:** a seção *Dev com IA* do [spec](spec.md): posts do X (Seguindo, Para você, seis
buscas) lidos por um Chrome com perfil do Whis, escolhidos pelo editor, com a Dica do dia.

**Arquitetura:** um módulo novo `fonte_x.py` tem a parte pura (URL da busca, leitura do HTML de um
post, corte dos candidatos) e o leitor de verdade (Playwright, carregado só na hora). O jornal
chama o leitor uma vez, depois da coleta RSS, e junta os candidatos às seções das linhas `x:`. O
editor ganha a regra da seção e o campo `dica`. A nota e a página ganham a Dica do dia e o aviso
da seção.

**Stack:** Python 3.12, Playwright (`channel="chrome"`, sem baixar navegador), `html.parser` da
stdlib, Claude Agent SDK (editor existente).

## Desvios do spec, decididos aqui

- **Os tipos do X moram em `fonte_x.py`, não em `portas.py`.** `vault.py` importa `portas.py`, e
  `fontes_do_jornal.py` importa `vault.py`. Se `portas.py` importasse `FonteDoX`, o import seria
  circular. Bônus: menos mexida num arquivo que outra sessão também edita.
- **Fixtures do X provisórias.** A camada 0 precisa da conta do Whis, que ele ainda vai criar. Os
  HTML de `tests/fixtures/jornal/x/` são escritos com a estrutura conhecida do X (`data-testid`) e
  trocados pelos reais quando o protótipo rodar. O protótipo usa o próprio `LeitorDoX` com
  `amostras=` para guardá-los.
- **Sem commit.** O working tree é compartilhado com outra sessão, que trabalha sem commitar; um
  commit meu levaria mudanças dela. Fica tudo no working tree, como ele pediu às duas.
- **Leitor ausente = X ignorado.** `gerar_jornal(leitor_do_x=None)` não lê o X nem avisa; quem
  monta as portas de verdade (`montar_portas_do_jornal`, palheta) sempre passa um leitor. Isso
  mantém os testes atuais do jornal sem leitor.

## Arquivos

| Arquivo | O que muda |
|---|---|
| `src/whis/fontes_do_jornal.py` | `FonteDoX`, `Secao.x`, linha `x:`, `fechar()` aceita seção só com `x`, bloco `ia` no topo do modelo |
| `src/whis/fonte_x.py` (novo) | `PostDoX`, `LeituraDoX`, `ErroDoX`, `LoginDoXVenceu`, `PortaDoX`, `url_da_busca`, `ler_post`, `candidatos_do_x`, `e_do_x`, `LeitorDoX`, `abrir_login` |
| `src/whis/portas.py` | `Candidato.curtidas`, `Dica`, `Escolha.dica` |
| `src/whis/jornal_claude.py` | regra de `ia`, `dica` no esquema, `curtidas` no pedido, `_validar_dica` |
| `src/whis/jornal.py` | `PortasDoJornal.leitor_do_x`, `gerar_jornal(leitor_do_x=)`, `_ler_o_x`, `DicaDoJornal`, `SecaoDoJornal.dica/aviso`, `Edicao.links()` |
| `src/whis/pagina_do_jornal.py` | cor de `ia`, cartão da dica, post do X nunca `lead`, `.by.x` sem maiúsculas, aviso da seção |
| `src/whis/vault.py` | `montar_jornal`: Dica do dia e aviso da seção |
| `src/whis/fakes.py` | `LeitorDoXFake`; `EditorFake` devolve dica |
| `src/whis/palheta.py` | `resultado_do_jornal` (login do X), `jornal()` passa o leitor |
| `src/whis/__main__.py` | portas com leitor, `news` passa o leitor, subcomando `x-login` |
| `tests/conftest.py` | trava autouse do navegador |
| `pyproject.toml` | `playwright>=1.47` |
| `docs/adr/0003-x-por-navegador.md`, `docs/smoke-jornal.md` | decisão e passos manuais |
| `.scratch/jornal-dev-com-ia/research/01-x-pelo-navegador/` | protótipo e o que ele responde |

## Tarefa 1 — linhas `x:` em `fontes.md`

Arquivos: `src/whis/fontes_do_jornal.py`, `tests/test_fontes_do_jornal.py`.

- [ ] Testes (vermelhos):

```python
def test_as_tres_linhas_do_x_viram_fontes_do_x_da_secao():
    fontes = interpretar_fontes(
        "## Dev com IA (ia) · 4 a 6 itens\n"
        "- X · Seguindo: x:seguindo\n"
        "- X · Para você: x:para-voce\n"
        '- X · Claude Code: x:busca "claude code" min_faves:100\n'
        "- Simon Willison: https://simonwillison.net/atom/everything/\n"
    )

    [ia] = fontes.secoes
    assert ia.x == (
        FonteDoX("X · Seguindo", "seguindo"),
        FonteDoX("X · Para você", "para-voce"),
        FonteDoX("X · Claude Code", "busca", '"claude code" min_faves:100'),
    )
    assert ia.fontes == (Fonte("Simon Willison", "https://simonwillison.net/atom/everything/"),)


def test_secao_so_com_linhas_do_x_e_valida():
    fontes = interpretar_fontes("## Dev com IA (ia)\n- X · Seguindo: x:seguindo\n")

    assert [s.id for s in fontes.secoes] == ["ia"]
    assert fontes.avisos == ()


def test_linha_do_x_com_tipo_desconhecido_ou_busca_vazia_vira_aviso():
    fontes = interpretar_fontes("## Dev com IA (ia)\n- A: x:qualquer\n- B: x:busca\n- C: x:seguindo\n")

    assert [f.nome for f in fontes.secoes[0].x] == ["C"]
    assert len(fontes.avisos) == 2
    assert "x:qualquer" in fontes.avisos[0]


def test_linha_do_x_no_time_e_ignorada_com_aviso():
    fontes = interpretar_fontes("## Time\n- Corinthians: x:busca corinthians\n")

    assert fontes.time is None
    assert fontes.avisos
```

  Atualizar os testes do modelo: a primeira seção passa a ser `ia` (ids
  `["ia", "tecnologia", "mundo", "brasil", "musica", "futebol", "carros"]`), `musica` é
  `secoes[4]`, o teste que prefixa uma seção ao modelo espera `len(fontes.secoes) == 8`, e um
  teste novo confere as oito linhas `x:` de `ia` no modelo.

- [ ] Implementação:

```python
TIPOS_DO_X = ("seguindo", "para-voce", "busca")
_LINHA_DO_X = re.compile(r"^[-*+]\s+(?P<nome>.+?)\s*:\s*x:(?P<tipo>\S+)(?:\s+(?P<consulta>.+?))?\s*$", re.I)


@dataclass(frozen=True)
class FonteDoX:
    """Uma página do X que o leitor visita: uma aba da home ou uma busca."""

    nome: str
    tipo: str
    consulta: str = ""
```

  `Secao` ganha `x: tuple[FonteDoX, ...] = ()`. No laço de `interpretar_fontes`, antes de
  `_ler_fonte`: se `_LINHA_DO_X` casar, validar o tipo (fora de `TIPOS_DO_X` ou `busca` sem
  consulta → aviso `Linha N ignorada: “x:<tipo>” não é x:seguindo, x:para-voce nem x:busca <consulta>`),
  no `## Time` → aviso `Linha N ignorada: o time vem de um feed, não do X`, fora de seção → aviso
  de fonte fora de seção, senão `atual["x"].append(...)`. `fechar()`: `if not atual["fontes"] and
  not atual["x"]`. Modelo: o bloco do spec no topo, depois de `# Fontes do jornal`.

## Tarefa 2 — a parte pura de `fonte_x.py`

Arquivos: `src/whis/fonte_x.py`, `tests/test_fonte_x.py`, `tests/fixtures/jornal/x/*.html`.

Fixtures (estrutura do X, provisórias): `post.html` (post comum, 1.234 curtidas no `aria-label`),
`repost.html` (`socialContext` "reposted", permalink do original), `anuncio.html`
(`placementTracking` e o rótulo "Ad"), `longo.html` (texto cortado com "Show more" fora de
`tweetText`), `sem_curtida.html` (botão `like` com `aria-label="Like"`), `citacao.html` (post que
cita outro: o `<time>` do citado fora de `<a>`, o `tweetText` do citado depois), `curtidas_k.html`
(`aria-label` sem número e o texto visível "1.2K").

- [ ] Testes (vermelhos):

```python
def test_le_link_autor_hora_texto_e_curtidas_do_post():
    post = ler_post(fixture("post.html"))

    assert post == PostDoX(
        link="https://x.com/bcherny/status/1840000000000000001",
        autor="bcherny",
        texto="Tip: put your test command in CLAUDE.md so the agent runs it before every commit.",
        data=datetime(2026, 9, 30, 13, 5, tzinfo=UTC),
        curtidas=1234,
    )


def test_repost_vale_pelo_post_original():
    assert ler_post(fixture("repost.html")).autor == "simonw"


def test_anuncio_fica_fora():
    assert ler_post(fixture("anuncio.html")) is None


def test_post_longo_vem_com_o_texto_visivel_sem_o_show_more():
    texto = ler_post(fixture("longo.html")).texto
    assert texto.startswith("Long thread on context engineering")
    assert "Show more" not in texto


def test_post_sem_curtida_tem_curtidas_none():
    assert ler_post(fixture("sem_curtida.html")).curtidas is None


def test_curtidas_abreviadas_viram_numero():
    assert ler_post(fixture("curtidas_k.html")).curtidas == 1200


def test_post_que_cita_outro_fica_com_o_de_fora():
    post = ler_post(fixture("citacao.html"))
    assert post.autor == "steipete"
    assert "quoted text" not in post.texto


def test_a_busca_acrescenta_filtro_de_respostas_since_e_aba_principais():
    url = url_da_busca('"claude code" min_faves:100', date(2026, 9, 30))

    consulta = parse_qs(urlsplit(url).query)
    assert url.startswith("https://x.com/search?")
    assert consulta["q"] == ['"claude code" min_faves:100 -filter:replies since:2026-09-29']
    assert consulta["f"] == ["top"]
    assert consulta["src"] == ["typed_query"]


def test_candidatos_cortam_24h_repetidos_ja_publicados_e_ordenam_por_curtidas():
    agora = datetime(2026, 9, 30, 11, 20, tzinfo=UTC)
    posts = [
        post_de("a", 1, horas=1, curtidas=10),
        post_de("b", 2, horas=2, curtidas=500),
        post_de("a", 1, horas=1, curtidas=10),
        post_de("c", 3, horas=30, curtidas=900),
        post_de("d", 4, horas=3, curtidas=None),
        post_de("e", 5, horas=1, curtidas=50),
    ]

    candidatos = candidatos_do_x("ia", posts, agora, frozenset({"https://x.com/e/status/5"}))

    assert [c.link.rsplit("/", 1)[-1] for c in candidatos] == ["2", "1", "4"]
    assert [c.id for c in candidatos] == ["ia-x1", "ia-x2", "ia-x3"]
    assert candidatos[0].fonte == "@b" and candidatos[0].curtidas == 500


def test_dois_posts_que_comecam_igual_continuam_dois():
    agora = datetime(2026, 9, 30, 11, 20, tzinfo=UTC)
    iguais = [post_de("a", 1, texto="Claude Code tip: one"), post_de("b", 2, texto="Claude Code tip: two")]

    assert len(candidatos_do_x("ia", iguais, agora)) == 2


def test_teto_de_trinta_e_post_sem_texto_fora():
    agora = datetime(2026, 9, 30, 11, 20, tzinfo=UTC)
    muitos = [post_de(f"u{n}", n, curtidas=n) for n in range(1, 41)] + [post_de("vazio", 99, texto="")]

    candidatos = candidatos_do_x("ia", muitos, agora)

    assert len(candidatos) == 30
    assert candidatos[0].curtidas == 40


def test_e_do_x():
    assert e_do_x("https://x.com/a/status/1")
    assert not e_do_x("https://simonwillison.net/2026/x/")
```

- [ ] Implementação: dataclasses `PostDoX(link, autor, texto, data, curtidas=None)` e
  `LeituraDoX(posts: dict[str, tuple[PostDoX, ...]] = {}, falhas: dict[str, str] = {})`; erros
  `ErroDoX(RuntimeError)` e `LoginDoXVenceu(ErroDoX)`; `PortaDoX` (`ler(fontes, hoje) ->
  LeituraDoX`). `ler_post` com um `HTMLParser` que guarda a pilha de elementos não vazios: o
  permalink é a primeira âncora `/<autor>/status/<id>` aberta quando aparece um `<time
  datetime>`; o texto é o do primeiro `data-testid="tweetText"` (com o `alt` dos `<img>` de
  emoji); as curtidas vêm do `aria-label` de `data-testid="like"`/`"unlike"` (`1234 Likes`) ou do
  texto visível (`1.2K` → 1200); `placementTracking` ou um texto exatamente `Ad`/`Promoted` fora
  do `tweetText` → anúncio. `candidatos_do_x(secao, posts, agora, ja_publicados=frozenset(), *,
  teto=30)`: janela de 24 h com 1 h de tolerância, dedupe pelo id do status, fora o já publicado
  e o sem texto, ordem por curtidas (`None` = 0), `id=f"{secao}-x{n}"`, `fonte=f"@{autor}"`,
  título até 120 caracteres, resumo até 500. `url_da_busca` com `urlencode`.

## Tarefa 3 — o leitor de verdade, a trava e a dependência

Arquivos: `src/whis/fonte_x.py`, `tests/conftest.py`, `pyproject.toml`.

- [ ] `_playwright()` importa `playwright.sync_api.sync_playwright` só na chamada; é o único
  ponto que toca o navegador. `LeitorDoX(perfil=None, sem_janela=SEM_JANELA, amostras=None,
  dormir=time.sleep, sortear=random.uniform)`:
  - `ler(fontes, hoje)`: Playwright ausente → `ErroDoX("o Playwright não está instalado")`;
    `launch_persistent_context(perfil, channel="chrome", headless=sem_janela, locale="en-US")`;
    Chrome ausente → `ErroDoX("o Chrome não foi encontrado")`; perfil ocupado → `ErroDoX("o perfil
    do X está em uso por outro processo")`.
  - Por fonte: home + clique na aba (`get_by_role("tab", name=...)`) ou `goto(url_da_busca)`;
    `/login` ou `/i/flow/` na URL → `LoginDoXVenceu`; espera `article[data-testid="tweet"]` ou
    `[data-testid="emptyState"]`, senão `ErroDoX("a página do X mudou: sem post nem aviso de
    vazio")`; vazio → `()`. Coleta o `outerHTML` dos `article` antes e depois de cada uma das 4
    rolagens (o X recicla os elementos da lista), com pausa sorteada entre 1,5 e 3 s.
  - Falha de uma página vai para `LeituraDoX.falhas[nome]`; o login vencido propaga.
  - `amostras`: grava cada `outerHTML` e, na página vazia, o HTML inteiro.
- [ ] `abrir_login(perfil=None, *, esperar_s=600) -> bool`: Chrome com janela em
  `https://x.com/login`; `True` quando a URL chega a `https://x.com/home`.
- [ ] `tests/conftest.py`: fixture autouse `navegador_trancado` troca `fonte_x._playwright` por
  uma função que levanta `AssertionError`.
- [ ] `pyproject.toml`: `"playwright>=1.47",` e `pip install playwright` no `.venv` (sem
  `playwright install`: usa o Chrome instalado).

## Tarefa 4 — editor: regra, curtidas e Dica do dia

Arquivos: `src/whis/portas.py`, `src/whis/jornal_claude.py`, `tests/test_jornal_claude.py`.

- [ ] Testes (vermelhos):

```python
def candidatos_com_x():
    return {
        "ia": (
            Candidato("ia-1", "ia", "Simon Willison", "Blog", "https://simonwillison.net/x"),
            Candidato("ia-x1", "ia", "@bcherny", "Tip", "https://x.com/bcherny/status/1", curtidas=900),
            Candidato("ia-x2", "ia", "@simonw", "Tip 2", "https://x.com/simonw/status/2", curtidas=40),
        ),
        "tecnologia": (Candidato("tecnologia-1", "tecnologia", "HN", "N", "https://e.com/1"),),
    }


def test_o_esquema_so_pede_a_dica_quando_ia_tem_post_do_x():
    assert "dica" in esquema_da_escolha(candidatos_com_x())["properties"]
    assert "dica" not in esquema_da_escolha({"tecnologia": candidatos_com_x()["tecnologia"]})["properties"]


def test_o_pedido_leva_as_curtidas_e_o_prompt_a_regra_da_secao():
    pedido = montar_pedido_de_escolha(candidatos_com_x(), {}, ())
    assert '"curtidas": 900' in pedido
    assert "Dev com IA" in SISTEMA_ESCOLHA and '"dica"' in SISTEMA_ESCOLHA


def test_dica_valida_sai_da_lista_da_secao():
    dados = {
        "secoes": {"ia": [{"id": "ia-x1", "titulo": "T1", "resumo": "R1"}, {"id": "ia-x2", "titulo": "T2", "resumo": "R2"}],
                   "tecnologia": []},
        "time": [],
        "dica": {"id": "ia-x1", "titulo": "Teste no CLAUDE.md", "como_aplicar": "Ponha o comando de teste no CLAUDE.md."},
    }

    escolha = interpretar_escolha(dados, candidatos_com_x(), {}, ())

    assert escolha.dica.candidato.id == "ia-x1"
    assert escolha.dica.titulo == "Teste no CLAUDE.md"
    assert [i.candidato.id for i in escolha.secoes["ia"]] == ["ia-x2"]


@pytest.mark.parametrize("dica", [
    {"id": "ia-1", "titulo": "T", "como_aplicar": "C"},
    {"id": "tecnologia-1", "titulo": "T", "como_aplicar": "C"},
    {"id": "ia-x9", "titulo": "T", "como_aplicar": "C"},
    {"id": "ia-x1", "titulo": "T", "como_aplicar": ""},
])
def test_dica_invalida_cai(dica):
    dados = {"secoes": {"ia": [], "tecnologia": []}, "time": [], "dica": dica}
    assert interpretar_escolha(dados, candidatos_com_x(), {}, ()).dica is None
```

- [ ] Implementação: `Candidato.curtidas: int | None = None`; `Dica(candidato, titulo,
  como_aplicar)`; `Escolha.dica: Dica | None = None`. Em `jornal_claude.py`: `SECAO_DA_DICA =
  "ia"`, `_DICA` (objeto `{id, titulo, como_aplicar}`), `_posts_da_dica(candidatos)` (os de `ia`
  com `e_do_x(link)`), `esquema_da_escolha` põe `dica` nas propriedades só quando há posts,
  `_candidato_no_pedido` leva `curtidas`, `_validar_dica`, e `interpretar_escolha` tira da lista
  de `ia` o candidato da dica. `SISTEMA_ESCOLHA` ganha a regra do spec e o pedido da dica.

## Tarefa 5 — a costura: o leitor, os avisos e a dica na edição

Arquivos: `src/whis/jornal.py`, `tests/test_jornal.py`.

- [ ] Testes (vermelhos), com `LeitorDublê(posts=..., erro=..., falhas=...)` que conta chamadas e
  um `fontes.md` escrito no vault do cenário com a seção `ia`:
  - os posts entram em `editor.recebido[0]["ia"]` com ids `ia-x<N>` e `fonte="@autor"`;
  - o leitor recebe as `FonteDoX` da seção e é chamado **uma vez** mesmo quando a espera da rede
    repete a coleta (duas coletas sem rede antes da boa);
  - login vencido → `AVISO_DO_LOGIN_DO_X` em `edicao.avisos`, na `SecaoDoJornal.aviso` de `ia`,
    `resultado.parcial` verdadeiro;
  - `ErroDoX("o Chrome não foi encontrado")` → aviso `X indisponível hoje: o Chrome não foi
    encontrado`;
  - todas as páginas em `falhas` → aviso "indisponível" com o primeiro motivo; uma só →
    `fontes_com_falha` ganha `X · Contexto (tempo esgotado)`, sem aviso, `parcial` falso;
  - sem leitor (`leitor_do_x=None`) ou sem linha `x:` → nenhuma chamada e nenhum aviso;
  - o link da dica vai para a nota como `[…](link)` e entra em `links_publicados` no dia seguinte.
- [ ] Implementação: constantes `AVISO_DO_LOGIN_DO_X = "o login do X venceu: rode python -m whis
  x-login"` e `INICIO_DO_X_INDISPONIVEL = "X indisponível hoje"`; `DicaDoJornal(item, titulo,
  como_aplicar)`; `SecaoDoJornal.dica` e `.aviso`; `Edicao.links()` com o link das dicas;
  `PortasDoJornal.leitor_do_x = None`; `gerar_jornal(..., leitor_do_x=None)` chama
  `_ler_o_x(leitor, fontes, coleta, agora, ja_publicados)` logo depois de
  `_coletar_esperando_a_rede`, que devolve a coleta com os candidatos do X somados às seções e
  as falhas parciais em `fontes_com_falha`, e `{secao: aviso}`; os avisos abrem a lista de avisos
  da edição; `_montar_edicao` recebe os avisos por seção e monta a dica da seção do candidato.

## Tarefa 6 — página e nota

Arquivos: `src/whis/pagina_do_jornal.py`, `src/whis/vault.py`, `tests/test_jornal.py`.

- [ ] Testes (vermelhos), pela `Edicao` montada à mão e pelo `PublicacaoDublê`:
  - página: `Dica do dia · <título>`, `Ver no X` com o link, nenhum post do X em
    `<article class="lead">`, `<div class="by x">@bcherny`, `--c:#0e7c86` na seção `ia`;
  - seção vazia com aviso: o aviso no lugar de "Nada relevante"; com itens: o aviso depois deles;
  - nota: `### Dica do dia`, `**[título](https://x.com/...)**`, o `como_aplicar`, o aviso em
    itálico.
- [ ] Implementação: `CORES["ia"] = "#0e7c86"`; CSS `.by.x{text-transform:none;letter-spacing:.02em}`
  e `.aula .ver`; `_item` usa `by x` para `e_do_x(link)`; `_lista` só escolhe `lead` entre os
  itens que não são do X (sem nenhum, todos como item); `_dica(dica)`; no laço, dica antes da
  lista, lista quando há itens ou nada de dica/aviso, aviso por último. Em `montar_jornal`, o
  mesmo para a nota.

## Tarefa 7 — fakes, casca e toast

Arquivos: `src/whis/fakes.py`, `src/whis/__main__.py`, `src/whis/palheta.py`,
`tests/test_casca_do_jornal.py` ou `tests/test_fakes_do_jornal.py`, `tests/test_login_do_claude.py`.

- [ ] Testes (vermelhos):
  - `LeitorDoXFake().ler(fontes, hoje)` devolve dois posts por fonte, do dia, autores distintos;
    `EditorFake` devolve dica do primeiro post do X de `ia` e o tira da lista;
  - `main(["news", "--fakes"])` (vault novo, modelo com `ia`) imprime a seção `Dev com IA` com
    itens e não abre navegador (a trava do conftest garante);
  - `main(["x-login", "--help"])` documenta o comando; `_comando_x_login` com `abrir_login`
    trocado imprime "Sessão do X salva" / "Login não concluído" e sai 0 / 1;
  - toast: login do X vencido com página → título "O login do X venceu", texto "Rode 'python -m
    whis x-login' num terminal. O jornal saiu sem a parte do X.", botão da página; sem página e
    login do X vencido → título "O jornal não foi publicado" e "o login do X também venceu" no
    texto; login do Claude vencido continua vencendo.
- [ ] Implementação: `LeitorDoXFake(posts=None, erro=None)`; `EditorFake` com `Dica`;
  `montar_portas_do_jornal` passa `LeitorDoXFake()` nos fakes e `LeitorDoX()` de verdade;
  `_comando_news` e o `jornal()` da palheta passam `leitor_do_x=portas.leitor_do_x`; subparser
  `x-login` logo abaixo do `news_cmd`; `TITULO_DO_LOGIN_DO_X = "O login do X venceu"` e a
  precedência em `resultado_do_jornal`.

## Tarefa 8 — protótipo, ADR, smoke e a suíte inteira

- [ ] `.scratch/jornal-dev-com-ia/research/01-x-pelo-navegador/prototipo.py`: `--login` chama
  `abrir_login()`; sem argumento, para cada `FonteDoX` do bloco `ia` do modelo, abre o
  `LeitorDoX(amostras=pasta/"amostras")` só com ela, mede segundos, posts lidos e posts das
  últimas 24 h, grava `medidas.json`; `--com-janela` testa o modo com janela.
- [ ] `research/01-x-pelo-navegador.md`: as perguntas da camada 0 e como rodar.
- [ ] `docs/adr/0003-x-por-navegador.md`.
- [ ] `docs/smoke-jornal.md`: criar a conta (em inglês) e seguir a lista; `x-login`; colar o bloco
  no topo de `fontes.md`; uma edição com a seção; login vencido simulado apagando o perfil.
- [ ] Suíte inteira verde; `whis news --fakes` mostra a seção.

## Autorrevisão contra o spec

Cobertos: formato e lugar da seção (T1, T6), as três linhas e os acréscimos da busca (T1, T2),
herança da seção e id `ia` (T1, T4, T5), não contar para nascer (T1, T5), leitor uma vez depois da
espera (T5), corte e teto à parte do RSS (T2), busca vazia (T3), falhas por página e do X inteiro
(T3, T5), Dica do dia só de post do X e fora da lista (T4), lead e `@` minúsculo (T6), aviso da
seção (T5, T6), link da dica no já publicado (T5, T6), trava do conftest (T3), `x-login` e toast
(T7), ADR e smoke (T8). Pendente de propósito: fixtures reais, `min_faves` e o modo sem janela,
que dependem da conta e do protótipo (T8).
