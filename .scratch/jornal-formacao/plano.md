# A formação do jornal com imagem, check e quiz — plano de implementação

> Para quem executa: tarefas em ordem, cada uma test-first (`- [ ]` marca o andamento). Rodar a
> suíte com `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`. Antes de editar,
> `git status` (outras sessões mexem neste working tree). Sem comentário óbvio no código.

**Objetivo:** a [spec](spec.md): figura em toda aula (foto da fonte ou esquema SVG), check "Li esta
aula" na página que trava a trilha por área, e o Quiz da semana no sábado.

**Arquitetura:** três módulos novos e puros cuidam do dado no vault (`esquema.py` valida o SVG,
`aulas.py` lê e escreve `noticias/aulas/`, `quiz.py` lê e escreve `noticias/quiz/`); dois
adaptadores novos do Claude seguem o molde de `jornal_claude.py` (`MarcacoesClaude` lê o banco do
artifact pela `ArtifactData` com `out_dir`, `QuizClaude` escreve as perguntas novas); `jornal.py`
costura: lê as marcações, aplica no vault, calcula as vagas, chama a formação só se há vaga, monta
o quiz no sábado e escreve o que mudou. A página ganha o primeiro `<script>`.

**Stack:** Python 3.12, Claude Agent SDK (CLI do npm por `caminho_do_cli`), `httpx`, `Pillow`,
`xml.etree.ElementTree` e `html.parser` da stdlib. Página: HTML + um script sem dependência.

## Desvios do spec, decididos aqui

- **A leitura do banco é `query` filtrada, lida do texto do resultado** (decidido pela tarefa 0:
  `out_dir` e escrita são negados em `dontAsk`; leitura passa; ver `research/00-banco-e-fotos.md`).
  `PortaMarcacoes.ler(url, *, leituras_desde, quizzes)`; sem nada a ler, não há chamada.
- **O id da pergunta e o estado na página.** A página lê as respostas do quiz com uma `query`
  (`respostas` onde `quiz == <data>`), não uma leitura por pergunta: cada resposta grava também
  `quiz: <data>`.
- **"Sem resposta" é escrito no dia seguinte ao quiz.** A página do sábado só vive até a edição de
  domingo; a sincronização de qualquer dia depois do quiz grava `sem resposta` nas que ficaram
  vazias.
- **Sem commit.** O working tree é compartilhado; fica tudo nele, como nas entregas anteriores.

## Arquivos

| Arquivo | O que muda |
|---|---|
| `src/whis/esquema.py` (novo) | `validar_esquema(svg) -> str` (vazio se recusado) |
| `src/whis/fotos_das_aulas.py` (novo) | `imagem_da_pagina(html, url) -> str \| None` (`og:image`/`twitter:image`) |
| `src/whis/aulas.py` (novo) | `NotaDeAula`, `id_da_aula`, `montar_nota`, `ler_nota`, `ler_aulas`, `escrever_aula`, `aplicar_leituras`, `vagas`, `nascer`, `em_cena` |
| `src/whis/quiz.py` (novo) | `Pergunta`, `QuizDaSemana`, `montar_nota_do_quiz`, `ler_nota_do_quiz`, `ler_quizzes`, `aplicar_respostas`, `atrasadas`, `aulas_do_quiz`, `novo_quiz` |
| `src/whis/marcacoes_claude.py` (novo) | `MarcacoesClaude`, `ler_pasta_das_marcacoes`, `pedido_de_leitura` |
| `src/whis/quiz_claude.py` (novo) | `QuizClaude`, `SISTEMA_QUIZ`, `ESQUEMA_DO_QUIZ`, `interpretar_perguntas` |
| `src/whis/portas.py` | `Aula` com `id`, `visual`, `foto_de`, `esquema`, `imagem`, `foto`, `pendente_desde`; `Marcacoes`, `Resposta`, `PortaMarcacoes`, `ErroDeMarcacoes`, `PerguntaNova`, `PerguntasNovas`, `PortaQuiz`, `ErroDeQuiz` |
| `src/whis/jornal_claude.py` | `_AULA` com `visual`/`foto_de`/`esquema`; regra no `SISTEMA_FORMACAO`; `ensinar(data, trilha, vagas)`; `esquema_da_formacao(vagas)`; `capabilities` nos dois pedidos de publicação |
| `src/whis/jornal.py` | `PortasDoJornal.marcacoes/quiz`; `gerar_jornal(marcacoes=, quiz=, sabado=)`; leitura, sincronização, vagas, nascimento, fotos, quiz, escrita; `Edicao.quiz` |
| `src/whis/pagina_do_jornal.py` | figura da aula, "Pendente desde", botão "Li esta aula", seção Quiz da semana, o `<script>` |
| `src/whis/vault.py` | `montar_jornal`: figura, "Pendente desde", Quiz da semana |
| `src/whis/fakes.py` | `FormacaoFake` com vagas e visual; `MarcacoesFake`; `QuizFake` |
| `src/whis/__main__.py`, `src/whis/palheta.py` | portas novas; `news --sabado` |
| `docs/adr/0005-marcacoes-no-banco-do-artifact.md`, `CONTEXT.md`, `docs/smoke-jornal.md` | decisão, glossário, passos |
| `.scratch/jornal-formacao/research/00-banco-e-fotos*` | a sonda e o que ela responde |

## Tarefa 0 — a sonda (ticket 01)

Arquivos: `.scratch/jornal-formacao/research/00-banco-e-fotos/sonda.py`, `fotos.py`,
`pagina.html`, `saida/`; achados em `.scratch/jornal-formacao/research/00-banco-e-fotos.md`.

- [ ] `sonda.py` — uma subclasse descartável de `_AdaptadorDoJornal` (`modelo="haiku"`, CLI de
  `caminho_do_cli`) que roda um prompt com as ferramentas pedidas e guarda, por passo, em
  `saida/<passo>.json`: `init.tools` (da `SystemMessage` de subtipo `init`), versão do CLI, os
  textos de `resultados_de_ferramenta`, a lista de arquivos que `out_dir` gravou, `custo_usd` e
  segundos.

```python
class Sonda(_AdaptadorDoJornal):
    etapa = "sonda"
    erro = RuntimeError

    def __init__(self) -> None:
        super().__init__(modelo="haiku", cli=None, timeout_s=300)
        self.tools: list[str] = []

    async def _mensagens(self, prompt, opcoes):
        async for mensagem in super()._mensagens(prompt, opcoes):
            if getattr(mensagem, "subtype", None) == "init":
                self.tools = list(mensagem.data.get("tools", []))
            yield mensagem

    def rodar(self, prompt: str, ferramentas: list[str], cwd: Path) -> Conversa:
        opcoes = self._opcoes(
            sistema=SISTEMA_PUBLICACAO, ferramentas=ferramentas, max_turns=12,
            cwd=cwd, ambiente=AMBIENTE_DA_PUBLICACAO,
        )
        return self._conversar(prompt, opcoes)
```

- [ ] `pagina.html` — página de rascunho com um SVG inline (o esquema de exemplo do slip angle) e
  um botão que grava `leituras/sonda-1 = {lida: true, em}` pelo `window.claude?.use("db")`,
  escrevendo na tela o que aconteceu (`null`, rejeição com `code`, ok).
- [ ] Passos, nesta ordem, cada um um `rodar(...)`:
  1. `publish` do `pagina.html` **sem** `capabilities` → URL do rascunho (`saida/1-publicar.json`).
  2. `ArtifactData list leituras` com `out_dir` **antes** de declarar o banco → fixture
     `antes-de-declarar`.
  3. Republish no mesmo endereço (os três passos de `pedido_de_republicacao`) **com**
     `capabilities: {"db": {}}`. Se recusar, repetir com `{"db": {}, "user": {}}` e anotar.
  4. `list leituras` com `out_dir` → fixture `colecao-vazia`.
  5. `set leituras/2026-10-06-negocios {lida: true, em: "..."}` e `list` com `out_dir` → fixture
     `uma-linha` (os arquivos JSON e o texto do resultado).
  6. `set` em mais dois documentos e `list` com `query.limit = 2` → fixture `com-cursor`; depois o
     `list` com o `cursor` → `ultima-pagina`.
  7. Republish com HTML novo **sem** `capabilities` → `list` → as linhas continuam? A declaração
     continua (um `set` ainda passa)?
  8. `set respostas/2026-10-10-q1 {escolha: 1, certa: false, quiz: "2026-10-10", em}` e `list`.
- [ ] Página no claude.ai: abrir a URL do rascunho no navegador embutido
  (`mcp__Claude_Browser__navigate`). Se o claude.ai estiver logado, tocar no botão, ler o que a
  página escreveu e rodar um `list leituras` headless: o documento `sonda-1` aparece? Anotar
  quando o pedido de permissão apareceu. Deslogado: anotar e deixar para o ticket 08.
- [ ] `fotos.py` — 12 URLs de fonte tiradas das linhas `Fontes:` das últimas notas de
  `noticias/` do vault dele (Wikipédia e outras); para cada uma, GET com `UA_DAS_CAPAS`, o
  `og:image`/`twitter:image`, e se `_baixar_imagem` o aceita. Tabela no achado.
- [ ] Escrever `research/00-banco-e-fotos.md` com as respostas às sete perguntas do ticket, os
  custos, e **o formato exato** de: arquivo JSON do `out_dir`, texto do resultado com e sem
  `next_cursor`, resposta antes de declarar. Copiar as fixtures para
  `tests/fixtures/jornal/marcacoes/` (`antes-de-declarar.txt`, `colecao-vazia.txt`,
  `uma-linha/…`, `com-cursor.txt`, `ultima-pagina.txt`).
- [ ] Resolver o ticket 01 (`## Answer`, `Status: resolved`). **Se as perguntas 2 ou 4 falharem,
  parar aqui** e voltar para ele com a alternativa B.

## Tarefa 1 — o esquema SVG validado (`esquema.py`)

Arquivos: `src/whis/esquema.py`, `tests/test_esquema.py`.

- [ ] Testes (vermelhos):

```python
from whis.esquema import LIMITE_DO_ESQUEMA, validar_esquema

BOM = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 120">'
    '<defs><marker id="seta" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">'
    '<path d="M0,0 L8,4 L0,8 z" fill="currentColor"/></marker></defs>'
    '<rect x="10" y="10" width="100" height="40" fill="none" stroke="currentColor"/>'
    '<line x1="110" y1="30" x2="190" y2="30" stroke="currentColor" marker-end="url(#seta)"/>'
    '<text x="60" y="35" text-anchor="middle" font-size="12">Custo</text></svg>'
)


def test_esquema_bom_passa_igual():
    assert validar_esquema(BOM) == BOM


def test_espaco_em_volta_e_tirado():
    assert validar_esquema(f"  \n{BOM}\n") == BOM


@pytest.mark.parametrize(
    "ruim",
    [
        "",
        "<div>oi</div>",
        BOM.replace("<rect", "<script>alert(1)</script><rect"),
        BOM.replace('<rect x="10"', '<rect onload="x()" x="10"'),
        BOM.replace("<rect", '<image href="https://x.com/a.png"/><rect'),
        BOM.replace("<rect", '<a href="https://x.com"><rect/></a><rect'),
        BOM.replace("<rect", '<foreignObject><div/></foreignObject><rect'),
        BOM.replace('fill="none"', 'fill="url(https://x.com/a)"'),
        BOM.replace('fill="none"', 'style="fill:red"'),
        '<!DOCTYPE svg [<!ENTITY a "b">]>' + BOM,
        "<svg><rect",
    ],
)
def test_esquema_ruim_e_recusado(ruim):
    assert validar_esquema(ruim) == ""


def test_esquema_grande_demais_e_recusado():
    grande = BOM.replace("Custo", "x" * LIMITE_DO_ESQUEMA)
    assert validar_esquema(grande) == ""
```

- [ ] Implementação:

```python
"""O esquema de uma aula: um SVG que o Claude desenha e a página põe inline.

Inline quer dizer que o SVG roda no mesmo documento da página, então só passa
o que é desenho: uma lista fechada de elementos e atributos, nada de script,
evento, link ou recurso de fora.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

LIMITE_DO_ESQUEMA = 30_000

ELEMENTOS = frozenset(
    {"svg", "g", "rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "text",
     "tspan", "defs", "marker", "title"}
)
ATRIBUTOS = frozenset(
    {"viewBox", "width", "height", "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry",
     "d", "points", "fill", "stroke", "stroke-width", "stroke-dasharray", "stroke-linecap",
     "stroke-linejoin", "opacity", "fill-opacity", "stroke-opacity", "transform", "font-size",
     "font-weight", "font-family", "font-style", "text-anchor", "dominant-baseline", "dx", "dy",
     "id", "class", "marker-start", "marker-end", "markerWidth", "markerHeight", "refX", "refY",
     "orient", "markerUnits", "role", "aria-label", "preserveAspectRatio", "letter-spacing"}
)
_URL_LOCAL = re.compile(r"url\(#[\w-]+\)")


def validar_esquema(svg: str) -> str:
    """O SVG como veio, sem o espaço em volta; vazio se qualquer parte não for desenho."""
    texto = (svg or "").strip()
    if not texto.startswith("<svg") or len(texto.encode("utf-8")) > LIMITE_DO_ESQUEMA:
        return ""
    if "<!" in texto or "<?" in texto:
        return ""
    try:
        raiz = ET.fromstring(texto)
    except ET.ParseError:
        return ""
    for elemento in raiz.iter():
        if _local(elemento.tag) not in ELEMENTOS:
            return ""
        for nome, valor in elemento.attrib.items():
            if _local(nome) not in ATRIBUTOS:
                return ""
            if "url(" in valor and not _URL_LOCAL.fullmatch(valor.strip()):
                return ""
            if "javascript:" in valor.lower():
                return ""
    return texto


def _local(nome: str) -> str:
    return nome.rsplit("}", 1)[-1]
```

## Tarefa 2 — a formação pede a figura (`portas.py`, `jornal_claude.py`)

Arquivos: `src/whis/portas.py`, `src/whis/jornal_claude.py`, `tests/test_jornal_claude.py`.

- [ ] `Aula` ganha campos com padrão (os testes atuais continuam valendo):

```python
@dataclass(frozen=True)
class Aula:
    """Um texto da formação, escrito a partir das páginas em `fontes`."""

    titulo: str
    texto: str
    fontes: tuple[str, ...]
    trilha: str = ""
    visual: str = ""
    foto_de: str = ""
    esquema: str = ""
    imagem: str = ""
    foto: str = ""
    id: str = ""
    pendente_desde: date | None = None
```

- [ ] Testes (vermelhos), em `test_jornal_claude.py`, com `_aula(...)` ganhando `visual`,
  `foto_de`, `esquema` opcionais:

```python
def test_aula_de_foto_guarda_a_pagina_da_foto_se_ela_e_fonte():
    dados = {**FORMACAO_COMPLETA, "carros": [
        _aula("RX-7", ["https://en.wikipedia.org/wiki/Mazda_RX-7"], "carros: rx-7",
              visual="foto", foto_de="https://en.wikipedia.org/wiki/Mazda_RX-7"),
    ]}
    [aula] = interpretar_formacao(dados, DIA).carros
    assert (aula.visual, aula.foto_de) == ("foto", "https://en.wikipedia.org/wiki/Mazda_RX-7")


def test_foto_de_pagina_que_nao_e_fonte_vira_aula_sem_figura():
    dados = {**FORMACAO_COMPLETA, "carros": [
        _aula("RX-7", ["https://en.wikipedia.org/wiki/Mazda_RX-7"], "carros: rx-7",
              visual="foto", foto_de="https://outro.com/x"),
    ]}
    [aula] = interpretar_formacao(dados, DIA).carros
    assert (aula.visual, aula.foto_de) == ("", "")


def test_aula_de_esquema_guarda_o_svg_validado():
    svg = '<svg viewBox="0 0 10 10"><rect x="1" y="1" width="8" height="8"/></svg>'
    dados = {**FORMACAO_COMPLETA, "negocios": _aula(
        "Margem", ["https://exemplo.com"], "negócios: margem", visual="esquema", esquema=svg)}
    aula = interpretar_formacao(dados, DIA).negocios
    assert (aula.visual, aula.esquema) == ("esquema", svg)


def test_esquema_recusado_vira_aula_sem_figura_mas_a_aula_fica():
    dados = {**FORMACAO_COMPLETA, "negocios": _aula(
        "Margem", ["https://exemplo.com"], "negócios: margem", visual="esquema",
        esquema="<svg><script/></svg>")}
    aula = interpretar_formacao(dados, DIA).negocios
    assert aula.titulo == "Margem" and (aula.visual, aula.esquema) == ("", "")


def test_a_regra_da_figura_esta_no_prompt():
    assert "esquema" in SISTEMA_FORMACAO and "foto" in SISTEMA_FORMACAO
    assert {"visual", "foto_de", "esquema"} <= set(ESQUEMA_DA_FORMACAO["properties"]["carros"]["items"]["properties"])
```

- [ ] Implementação. `_AULA` ganha `"visual": {"type": "string", "enum": ["foto", "esquema"]}`,
  `"foto_de": {"type": "string"}`, `"esquema": {"type": "string"}`, todos em `required`. No fim
  das regras do `SISTEMA_FORMACAO`, antes do "Use no máximo 6 buscas":

```
- Toda aula tem uma figura. "visual": "foto" quando o assunto é uma coisa que tem foto na página \
de uma das fontes (um carro, uma marca, uma pessoa, um lugar): ponha em "foto_de" a URL dessa fonte \
e deixe "esquema" vazio. "visual": "esquema" quando o assunto é um conceito ou um mecanismo: \
desenhe em "esquema" um SVG simples (viewBox, até uns 12 elementos: caixas, setas, rótulos curtos \
em português; só rect, circle, ellipse, line, polyline, polygon, path, text, tspan, g, defs, marker; \
cores só currentColor, none ou #5b3fb5 e #8a5a2b; nada de script, link, imagem ou estilo) e deixe \
"foto_de" vazio. O esquema não pode trazer número, nome ou dado que não esteja no texto da aula.
```

  Em `_aula(...)`:

```python
    visual = _texto(bruta.get("visual"))
    foto_de = _texto(bruta.get("foto_de"))
    esquema = validar_esquema(_texto(bruta.get("esquema"))) if visual == "esquema" else ""
    if visual == "foto" and foto_de not in fontes:
        visual, foto_de = "", ""
    elif visual == "esquema" and not esquema:
        visual = ""
    elif visual != "foto":
        foto_de = ""
```

  e `Aula(..., visual=visual, foto_de=foto_de, esquema=esquema)`.

## Tarefa 3 — id da aula, foto baixada e figura na página (`fotos_das_aulas.py`, `jornal.py`, `pagina_do_jornal.py`, `vault.py`)

Arquivos: `src/whis/fotos_das_aulas.py`, `src/whis/jornal.py`, `src/whis/pagina_do_jornal.py`,
`src/whis/vault.py`, `tests/test_fotos_das_aulas.py`, `tests/test_jornal.py`.

- [ ] Testes de `imagem_da_pagina` (vermelhos):

```python
def test_og_image_vence_e_url_relativa_vira_absoluta():
    html = ('<html><head><meta property="og:image" content="/img/rx7.jpg">'
            '<meta name="twitter:image" content="https://x.com/t.jpg"></head></html>')
    assert imagem_da_pagina(html, "https://en.wikipedia.org/wiki/Mazda_RX-7") == "https://en.wikipedia.org/img/rx7.jpg"


def test_sem_og_usa_twitter_image():
    html = '<meta name="twitter:image" content="https://cdn.exemplo.com/a.png">'
    assert imagem_da_pagina(html, "https://exemplo.com/p") == "https://cdn.exemplo.com/a.png"


def test_sem_meta_nenhuma_e_none():
    assert imagem_da_pagina("<html><body><img src='a.jpg'></body></html>", "https://exemplo.com") is None
```

- [ ] `fotos_das_aulas.py`: um `HTMLParser` que guarda o primeiro `content` de `meta[property=og:image]`
  e de `meta[name=twitter:image]`; devolve `urljoin(url, og or twitter)` se começar com `http`.
- [ ] Id: em `jornal.py`, as aulas que a formação devolve ganham id antes de montar a edição:
  `<hoje>-negocios`, `<hoje>-carros-1`, `<hoje>-carros-2` (na tarefa 5 o número vira "o menor
  livre na data").
- [ ] Testes em `test_jornal.py` (vermelhos), com `FormacaoDublê` devolvendo uma aula de carro
  `visual="foto", foto_de="https://en.wikipedia.org/wiki/Turbocharger"` e a de negócios
  `visual="esquema"` com um SVG válido, e `rede_das_capas` respondendo o HTML da Wikipédia com
  `og:image` apontando para `img.exemplo.com`:

```python
def test_aula_de_foto_sai_com_a_foto_publicada_e_a_url_na_nota(cenario):
    publicacao = PublicacaoDublê()
    gerar(cenario, publicacao=publicacao)
    html, capas, _ = publicacao.chamadas[0]
    assert "img/aula-2026-09-25-carros-1.jpg" in capas
    assert '<img class="foto" src="img/aula-2026-09-25-carros-1.jpg"' in html
    assert "![](https://img.exemplo.com/turbo.jpg)" in nota_de(cenario)


def test_aula_de_esquema_sai_com_o_svg_inline(cenario):
    publicacao = PublicacaoDublê()
    gerar(cenario, publicacao=publicacao)
    html = publicacao.chamadas[0][0]
    assert '<figure class="esquema"><svg' in html


def test_foto_que_nao_baixa_deixa_a_aula_sem_figura_e_sem_aviso(cenario):
    ...  # FormacaoDublê com foto_de cuja página responde 404
    assert "aula-" not in "".join(capas) and not resultado.edicao.avisos
```

- [ ] Implementação em `jornal.py`:
  - `_achar_fotos(aulas, rede) -> tuple[Aula, ...]`: para cada aula `visual == "foto"` sem
    `imagem`, GET de `foto_de` com o cliente das capas e `imagem_da_pagina`; com URL, `replace(aula,
    imagem=url)`.
  - `baixar_fotos_das_aulas(aulas, pasta, rede) -> dict[str, str]` (`{id: "img/aula-<id>.jpg"}`)
    reaproveitando `_baixar_imagem`; `_com_fotos(edicao, fotos)` põe `foto=` em `aprender` e
    `para_aprender`. O mapa `arquivos_das_capas` passa a juntar capas e fotos.
- [ ] `pagina_do_jornal._aula`: antes do `<h4>`, `<img class="foto" src="{foto}" alt="">` se
  `aula.foto`, senão `<figure class="esquema">{aula.esquema}</figure>` se `aula.esquema` (o SVG
  já validado entra sem escape). CSS: `.aula img.foto{width:100%;max-height:280px;object-fit:contain;
  background:var(--papel);border:1px solid var(--fio);margin:0 0 10px}` e
  `.aula .esquema{margin:0 0 10px;color:var(--tinta)}.aula .esquema svg{width:100%;height:auto;max-height:320px}`.
- [ ] `vault.montar_jornal.aula`: `![](<imagem>)` logo depois do título quando há `imagem`.

## Tarefa 4 — a nota da aula (`aulas.py`)

Arquivos: `src/whis/aulas.py`, `tests/test_aulas.py`.

- [ ] Testes (vermelhos):

```python
HOJE = date(2026, 10, 7)


def nota(id_, status="pendente", **extras) -> NotaDeAula:
    area = "negocios" if id_.endswith("negocios") else "carros"
    aula = Aula("Margem: o que sobra", "Linha 1: com dois-pontos.\n\n# não é título",
                ("https://exemplo.com/a", "https://exemplo.com/b"), f"- {id_[:10]} — negócios: margem",
                visual="foto", imagem="https://img.exemplo.com/m.jpg", id=id_)
    return NotaDeAula(id=id_, area=area, data=date.fromisoformat(id_[:10]), status=status, aula=aula, **extras)


def test_ida_e_volta_da_nota():
    original = nota("2026-10-06-negocios", lida_em="2026-10-06T21:10:00-03:00", quiz="2026-10-10")
    assert ler_nota(montar_nota(original)) == original


def test_status_posto_a_mao_no_obsidian_vale():
    texto = montar_nota(nota("2026-10-06-negocios")).replace("status: pendente", "status: Lida")
    assert ler_nota(texto).status == "lida"


def test_esquema_vem_do_arquivo_ao_lado(tmp_path):
    escrever_aula(tmp_path, replace(nota("2026-10-06-negocios"), aula=replace(
        nota("2026-10-06-negocios").aula, visual="esquema", imagem="", esquema=SVG)))
    [lida] = ler_aulas(tmp_path)
    assert lida.aula.esquema == SVG
    assert "![[2026-10-06-negocios.svg]]" in (tmp_path / "noticias/aulas/2026-10-06-negocios.md").read_text("utf-8")


def test_vagas_descontam_as_pendentes_antigas():
    notas = [nota("2026-10-06-carros-1"), nota("2026-10-05-negocios")]
    assert vagas(notas, HOJE, sabado=False) == {"negocios": 0, "carros": 1}


def test_ja_nasceu_aula_hoje_nao_ha_vaga():
    notas = [nota("2026-10-07-carros-1", status="lida")]
    assert vagas(notas, HOJE, sabado=False) == {"negocios": 0, "carros": 0}


def test_aula_antiga_lida_nao_ocupa_vaga():
    notas = [nota("2026-10-06-negocios", status="lida"), nota("2026-10-06-carros-1", status="lida")]
    assert vagas(notas, HOJE, sabado=False) == {"negocios": 1, "carros": 2}


def test_sabado_nao_tem_vaga():
    assert vagas([], date(2026, 10, 10), sabado=True) == {"negocios": 0, "carros": 0}


def test_aula_nova_de_carro_pega_o_menor_numero_livre_da_data():
    ja = nota("2026-10-07-carros-1", status="lida")
    nova = Aula("Turbo", "t", ("https://exemplo.com",), "carros: turbo")
    [nascida] = nascer(Formacao(carros=(nova,)), HOJE, [ja])
    assert nascida.id == "2026-10-07-carros-2" and nascida.aula.id == nascida.id


def test_em_cena_poe_pendentes_antigas_depois_as_de_hoje():
    notas = [nota("2026-10-07-carros-1"), nota("2026-10-05-carros-1"), nota("2026-10-04-carros-2", status="lida")]
    cena = em_cena(notas, HOJE)
    assert [a.id for a in cena.carros] == ["2026-10-05-carros-1", "2026-10-07-carros-1"]
    assert cena.carros[0].pendente_desde == date(2026, 10, 5) and cena.carros[1].pendente_desde is None


def test_aplicar_leituras_so_leva_pendente_para_lida():
    notas = [nota("2026-10-06-negocios"), nota("2026-10-05-carros-1", status="lida", lida_em="x")]
    novas = aplicar_leituras(notas, {"2026-10-06-negocios": "2026-10-06T22:00:00-03:00"})
    assert novas[0].status == "lida" and novas[0].lida_em == "2026-10-06T22:00:00-03:00"
    assert novas[1] is notas[1]
```

- [ ] Implementação. `PASTA_DAS_AULAS = "noticias/aulas"`. `NotaDeAula` (frozen): `id`, `area`
  (`negocios`/`carros`), `data`, `status`, `aula: Aula`, `lida_em: str = ""`, `quiz: str = ""`.
  - `id_da_aula(data, area, n=1)`: `f"{data}-negocios"` ou `f"{data}-carros-{n}"`.
  - `montar_nota(nota)`: frontmatter com `vault._frontmatter` (`tipo: aula`, `id`, `area`
    (`negócios`/`carros`), `data`, `status`, `lida_em`, `visual`, `imagem`, `trilha`, `quiz`), e
    o corpo: `# <título>`, linha em branco, a figura (`![](<imagem>)` ou `![[<id>.svg]]`), o texto
    entre `<!-- texto -->` e `<!-- /texto -->` (o texto pode ter `#` e `:` à vontade), `Fontes:`
    com uma URL por item `- <url>`.
  - `ler_nota(texto) -> NotaDeAula | None`: frontmatter como `acompanhamento.ler_pacotes`
    (`partition(":")`, `strip('"')`, `status` em `casefold()`; `lida` só se for `lida`), o título
    da primeira linha `# `, o texto entre os marcadores, as fontes das linhas `- http` depois de
    `Fontes:`. Sem `tipo: aula` ou sem marcadores → `None`.
  - `ler_aulas(vault)`: todas as `noticias/aulas/*.md` lidas, mais o `.svg` ao lado quando
    `visual: esquema` (passado por `validar_esquema` de novo); ordenadas por `id`.
  - `escrever_aula(vault, nota)`: `vault.escrever(..., zonas=ZONAS_DO_JORNAL)` da nota e, com
    esquema, do `.svg` (`literal=True`).
  - `aplicar_leituras(notas, lidas: dict[str, str])`, `vagas(notas, hoje, *, sabado)`,
    `nascer(formacao, hoje, notas) -> tuple[NotaDeAula, ...]` (status `pendente`, `data=hoje`,
    id pelo menor número livre) e `em_cena(notas, hoje) -> Formacao` (as `pendente` de data
    anterior, mais antigas antes, com `pendente_desde`; depois as de hoje, em qualquer status; por
    área; carros até 2, negócios até 1).

## Tarefa 5 — a área só avança lida (`jornal.py`, `jornal_claude.py`, `fakes.py`)

Arquivos: `src/whis/jornal.py`, `src/whis/jornal_claude.py`, `src/whis/portas.py`,
`src/whis/fakes.py`, `src/whis/vault.py`, `src/whis/pagina_do_jornal.py`, `tests/test_jornal.py`,
`tests/test_jornal_claude.py`, `tests/test_fakes_do_jornal.py`.

- [ ] `PortaFormacao.ensinar(data, trilha, vagas: Mapping[str, int])`. `FormacaoClaude.ensinar`
  usa `esquema_da_formacao(vagas)` (só as áreas com vaga; `negocios` como objeto, `carros` como
  array de `maxItems = vagas["carros"]`) e o pedido diz `Hoje: <n> aula(s) de negócios e <m> de
  carros.`. `FormacaoFake` e `FormacaoDublê` respeitam as vagas e guardam as recebidas.
- [ ] Testes em `test_jornal.py` (vermelhos):

```python
def test_aula_nao_marcada_volta_e_a_area_nao_avanca(cenario):
    gerar(cenario)
    formacao = FormacaoDublê()
    gerar(cenario, formacao=formacao, agora=AGORA + timedelta(days=4))
    assert formacao.vagas_recebidas == {"negocios": 0, "carros": 1}
    assert "Pendente desde 25/09" in nota_de(cenario, "2026-09-29")


def test_sem_vaga_a_formacao_nem_e_chamada(cenario):
    ...  # duas aulas de carro e a de negócios pendentes de ontem; FormacaoDublê(erro=AssertionError)


def test_aula_marcada_no_obsidian_libera_a_area(cenario):
    gerar(cenario)
    arquivo = cenario["vault"] / "noticias/aulas/2026-09-25-negocios.md"
    arquivo.write_text(arquivo.read_text("utf-8").replace("status: pendente", "status: lida"), "utf-8")
    formacao = FormacaoDublê()
    gerar(cenario, formacao=formacao, agora=AGORA + timedelta(days=1))
    assert formacao.vagas_recebidas["negocios"] == 1


def test_rodar_de_novo_no_mesmo_dia_nao_duplica_aula_nem_trilha(cenario):
    gerar(cenario)
    trilha = (cenario["vault"] / CAMINHO_DA_TRILHA).read_text("utf-8")
    formacao = FormacaoDublê()
    gerar(cenario, formacao=formacao)
    assert formacao.vagas_recebidas is None
    assert (cenario["vault"] / CAMINHO_DA_TRILHA).read_text("utf-8") == trilha
    assert len(list((cenario["vault"] / "noticias/aulas").glob("*.md"))) == 2


def test_simular_nao_escreve_nota_de_aula(cenario):
    gerar(cenario, simular=True)
    assert not (cenario["vault"] / "noticias/aulas").exists()
```

  (`FormacaoDublê.vagas_recebidas` começa `None` e só muda se `ensinar` for chamado; o dublê
  devolve uma aula de negócios e **uma** de carro, por isso sobra uma vaga de carro. `AGORA` é
  sexta, 25/09; a edição seguinte nos testes é a de terça, 29/09, longe do sábado.)

- [ ] Implementação em `gerar_jornal`, depois da escolha:

```python
    notas = _aulas.ler_aulas(vault)
    vagas = _aulas.vagas(notas, hoje, sabado=e_sabado)
    trilha = ler_trilha(vault)
    novas = _ensinar(formacao, hoje, trilha, vagas, avisos) if any(vagas.values()) else Formacao()
    nascidas = _aulas.nascer(novas, hoje, notas)
    nascidas = tuple(replace(n, aula=a) for n, a in zip(nascidas, _achar_fotos([n.aula for n in nascidas], rede)))
    cena = _aulas.em_cena([*notas, *nascidas], hoje)
```

  `_montar_edicao` recebe `cena` no lugar de `aulas` (`aprender=cena.negocios`,
  `para_aprender=cena.carros`); `medidas` continua com `novas.medida`. Fora do `simular`, depois
  da nota: `for n in nascidas: _aulas.escrever_aula(raiz, n)` e `acrescentar_trilha(raiz, hoje,
  novas)` (só as que nasceram agora). A trilha não é escrita quando `novas` é vazia.
- [ ] Página e nota: aula com `pendente_desde` ganha `<p class="pend">Pendente desde dd/mm</p>`
  (CSS: `.aula .pend{font-size:12px;color:#8a2f1d;margin:0 0 6px;text-transform:uppercase;
  letter-spacing:.08em}`) e, na nota, `_Pendente desde dd/mm_` sob o título. A nota do dia mostra o
  esquema como `![[<id>.svg]]`.

## Tarefa 6 — o check na página e o banco declarado (`pagina_do_jornal.py`, `jornal_claude.py`)

Arquivos: `src/whis/pagina_do_jornal.py`, `src/whis/jornal_claude.py`,
`tests/test_jornal.py`, `tests/test_jornal_claude.py`.

- [ ] Testes (vermelhos):

```python
def test_aula_com_id_tem_o_botao_e_a_pagina_tem_o_script(cenario):
    publicacao = PublicacaoDublê()
    gerar(cenario, publicacao=publicacao)
    html = publicacao.chamadas[0][0]
    assert '<button class="li" data-aula="2026-09-25-negocios" type="button">Li esta aula</button>' in html
    assert html.count("<script>") == 1 and 'use("db")' in html


def test_os_dois_pedidos_de_publicacao_declaram_o_banco():
    primeira = pedido_de_primeira_publicacao(Path("C:/x/jornal.html"), {})
    segunda = pedido_de_republicacao(Path("C:/x/jornal.html"), {}, "https://claude.ai/artifact/abc")
    for pedido in (primeira, segunda):
        assert f"capabilities exatamente {json.dumps(CAPACIDADES_DA_PAGINA)}" in pedido
        assert "sem capabilities" not in pedido.lower() and "não passe capabilities" not in pedido.lower()
```

- [ ] `CAPACIDADES_DA_PAGINA = {"db": {}}` em `jornal_claude.py` (ou o que a tarefa 0 provou). Nos
  dois pedidos, trocar "Não passe capabilities"/"sem capabilities" por `capabilities exatamente
  {json.dumps(CAPACIDADES_DA_PAGINA)}`.
- [ ] `_aula(aula)`: com `aula.id`, no fim do cartão,
  `<div class="marca"><button class="li" data-aula="{id}" type="button">Li esta aula</button><span class="li-nota"></span></div>`.
  CSS: `.marca{display:flex;align-items:center;gap:10px;margin-top:10px}button.li{min-height:44px;
  padding:0 16px;border:1px solid var(--c);background:var(--papel);color:var(--tinta);
  font:600 15px/1 var(--sans);border-radius:22px}button.li.lida{background:var(--c);color:#fff}
  button.li:disabled{opacity:.45}.li-nota{font-size:12px;color:var(--cinza)}`.
- [ ] `SCRIPT` (uma constante em `pagina_do_jornal.py`, posta antes de `</main>` só quando a página
  tem botão ou quiz):

```javascript
(async () => {
  const botoes = [...document.querySelectorAll("button.li")];
  const perguntas = [...document.querySelectorAll(".pergunta")];
  let db = null;
  try { db = window.claude ? await window.claude.use("db") : null; } catch (e) { db = null; }
  const nota = (b, t) => { const n = b.parentElement.querySelector(".li-nota"); if (n) n.textContent = t; };
  const sem = (t) => { for (const b of botoes) { b.disabled = true; nota(b, t); } };
  const pintar = (b, lida) => { b.classList.toggle("lida", lida); b.textContent = lida ? "Lida ✓" : "Li esta aula"; };
  if (!db) sem("Para marcar, abra logado no claude.ai.");
  else {
    try {
      for (const b of botoes) {
        const doc = await db.doc("leituras/" + b.dataset.aula).get();
        pintar(b, !!(doc.exists && doc.data().lida));
      }
      for (const b of botoes) b.addEventListener("click", async () => {
        const antes = b.classList.contains("lida");
        b.disabled = true; pintar(b, !antes); nota(b, "");
        try { await db.doc("leituras/" + b.dataset.aula).set({ lida: !antes, em: new Date().toISOString() }); }
        catch (e) { pintar(b, antes); nota(b, "Não consegui guardar."); }
        b.disabled = false;
      });
    } catch (e) { db = null; sem("Para marcar, abra logado no claude.ai."); }
  }
  /* o quiz entra na tarefa 11 */
})();
```

## Tarefa 7 — ler o banco (`portas.py`, `marcacoes_claude.py`, `fakes.py`)

Arquivos: `src/whis/portas.py`, `src/whis/marcacoes_claude.py`, `src/whis/fakes.py`,
`tests/test_marcacoes_claude.py`, `tests/fixtures/jornal/marcacoes/*`.

- [ ] Em `portas.py`:

```python
@dataclass(frozen=True)
class Resposta:
    escolha: int
    certa: bool


@dataclass(frozen=True)
class Marcacoes:
    """O que ele marcou na página: aulas lidas (`id → quando`) e respostas do quiz (`id → Resposta`)."""

    leituras: Mapping[str, str] = field(default_factory=dict)
    respostas: Mapping[str, Resposta] = field(default_factory=dict)
    medida: Medida = field(default_factory=Medida)


class ErroDeMarcacoes(RuntimeError):
    """Não deu para ler o banco da página; nada avança hoje."""


@runtime_checkable
class PortaMarcacoes(Protocol):
    def ler(self, url: str) -> Marcacoes:
        """Levanta `ErroDeMarcacoes`."""
        ...
```

- [ ] Testes (vermelhos), com as fixtures da tarefa 0 (os nomes abaixo; o conteúdo é o real):

```python
FIXTURES = Path(__file__).parent / "fixtures" / "jornal" / "marcacoes"


def test_pasta_com_uma_leitura_e_uma_resposta(tmp_path):
    shutil.copytree(FIXTURES / "uma-linha", tmp_path, dirs_exist_ok=True)
    leituras, respostas = ler_pasta_das_marcacoes(tmp_path)
    assert leituras == {"2026-10-06-negocios": "2026-10-06T22:00:00.000Z"}
    assert respostas == {"2026-10-10-q1": Resposta(1, False)}


def test_leitura_desmarcada_nao_conta(tmp_path): ...


def test_colecao_nunca_escrita_e_banco_nao_declarado_sao_vazios():
    for nome in ("colecao-vazia.txt", "antes-de-declarar.txt"):
        assert resultado_vazio((FIXTURES / nome).read_text("utf-8"))


def test_pagina_seguinte_nao_lida_e_erro():
    leitor = MarcacoesGravada([... resultado de com-cursor.txt e nenhum list com o cursor ...])
    with pytest.raises(ErroDeMarcacoes, match="página seguinte"):
        leitor.ler(URL)


def test_o_texto_do_modelo_e_ignorado(tmp_path):
    ...  # a resposta final do Haiku diz "lidas: todas"; o resultado vem só da pasta


def test_a_leitura_usa_so_artifact_data_no_cli_do_jornal():
    leitor = MarcacoesGravada([...])
    leitor.ler(URL)
    opcoes = leitor.opcoes[0]
    assert opcoes.tools == ["ArtifactData"] and opcoes.model == "haiku"
    assert opcoes.env["CLAUDE_CODE_ARTIFACT"] == "1"
```

- [ ] **Revisado pela tarefa 0.** `PortaMarcacoes.ler(url, *, leituras_desde: str | None,
  quizzes: Sequence[str]) -> Marcacoes`. `marcacoes_claude.py`: `MarcacoesClaude(_AdaptadorDoJornal)`,
  `etapa = "leitura das marcações"`, `erro = ErroDeMarcacoes`, `modelo="haiku"`, `timeout_s=180`,
  `tools=["Artifact", "ArtifactData"]`, `AMBIENTE_DA_PUBLICACAO`, `max_turns=12`. Sem
  `leituras_desde` e sem `quizzes`, devolve `Marcacoes()` sem chamar. O pedido manda uma `query`
  por coleção pedida (`leituras` com `where [["em", ">=", leituras_desde]]`; `respostas` com
  `where [["quiz", "in", quizzes]]`), `limit` 1000, seguindo `next_cursor`. O Python lê **os
  resultados da ferramenta**: `ler_documentos(texto) -> (colecao, docs, cursor)` reconhece o
  cabeçalho `N documents from collection "x":`, as linhas JSON entre `=== BEGIN ARTIFACT DB` e
  `=== END`, e a linha `next_cursor: "…"`; `VAZIOS` são os dois textos exatos das fixtures
  (`colecao-vazia.txt`, `antes-de-declarar.txt`). Qualquer outro texto (o `negado.txt`, por
  exemplo) → `ErroDeMarcacoes`. Uma coleção pedida sem resultado, ou cujo último resultado ainda
  tem cursor → `ErroDeMarcacoes("página seguinte não lida")`. `leituras` → só `data.lida is True`
  (`id → data.em`); `respostas` → `Resposta(int(escolha), bool(certa))`.
- [ ] `MarcacoesFake(leituras=None, respostas=None, erro=None)` em `fakes.py`, guardando as URLs
  recebidas.

## Tarefa 8 — a edição lê o banco e copia para o vault (`jornal.py`)

Arquivos: `src/whis/jornal.py`, `tests/test_jornal.py`.

- [ ] Testes (vermelhos):

```python
def test_aula_marcada_na_pagina_vira_lida_no_vault_e_libera_a_area(cenario):
    gerar(cenario)
    marcacoes = MarcacoesFake(leituras={"2026-09-25-negocios": "2026-09-25T22:00:00Z"})
    formacao = FormacaoDublê()
    gerar(cenario, formacao=formacao, marcacoes=marcacoes, agora=AGORA + timedelta(days=4))
    assert marcacoes.urls == [URL_DO_ARTIFACT]
    texto = (cenario["vault"] / "noticias/aulas/2026-09-25-negocios.md").read_text("utf-8")
    assert "status: lida" in texto and "2026-09-25T22:00:00Z" in texto
    assert formacao.vagas_recebidas["negocios"] == 1


def test_falha_na_leitura_vira_aviso_e_nada_avanca(cenario):
    gerar(cenario)
    formacao = FormacaoDublê()
    resultado = gerar(cenario, formacao=formacao, marcacoes=MarcacoesFake(erro=ErroDeMarcacoes("x")),
                      agora=AGORA + timedelta(days=4))
    assert AVISO_DAS_MARCACOES in resultado.edicao.avisos and resultado.parcial
    assert formacao.vagas_recebidas is None


def test_sem_artifact_ainda_a_leitura_nem_roda(cenario):
    marcacoes = MarcacoesFake()
    gerar(cenario, marcacoes=marcacoes)
    assert marcacoes.urls == []


def test_simular_le_o_banco_mas_nao_escreve(cenario):
    gerar(cenario)
    marcacoes = MarcacoesFake(leituras={"2026-09-25-negocios": "x"})
    formacao = FormacaoDublê()
    gerar(cenario, formacao=formacao, marcacoes=marcacoes, simular=True, agora=AGORA + timedelta(days=4))
    assert formacao.vagas_recebidas["negocios"] == 1
    assert "status: pendente" in (cenario["vault"] / "noticias/aulas/2026-09-25-negocios.md").read_text("utf-8")
```

- [ ] `AVISO_DAS_MARCACOES = "não consegui ler o que você marcou na página; as aulas pendentes
  continuam"`. `gerar_jornal(..., marcacoes: PortaMarcacoes | None = None)`.
  `_ler_marcacoes(porta, url, avisos) -> Marcacoes`: sem porta ou sem url → `Marcacoes()`;
  `ErroDeMarcacoes` → aviso e `Marcacoes()`. Depois de `ler_aulas`: `notas =
  _aulas.aplicar_leituras(notas, marcacoes.leituras)`; fora do `simular`, `escrever_aula` das que
  mudaram (comparar com a lista lida). `marcacoes.medida` entra em `medidas`. `PortasDoJornal`
  ganha `marcacoes: PortaMarcacoes | None = None`.

## Tarefa 9 — o quiz no vault (`quiz.py`)

Arquivos: `src/whis/quiz.py`, `tests/test_quiz.py`.

- [ ] Testes (vermelhos):

```python
def p(id_, aula="2026-10-06-negocios", resultado="", origem=""):
    return Pergunta(id=id_, aula=aula, pergunta="O que é margem?", alternativas=("A", "B", "C"),
                    certa=1, explicacao="Porque sim.", origem=origem, resultado=resultado)


def test_ida_e_volta_da_nota_do_quiz():
    original = QuizDaSemana(date(2026, 10, 10), (p("2026-10-10-q1", resultado="errada"), p("2026-10-10-q2", origem="2026-10-03-q4")))
    assert ler_nota_do_quiz(montar_nota_do_quiz(original)) == original


def test_atrasadas_sao_as_erradas_e_sem_resposta_ainda_nao_acertadas():
    q1 = QuizDaSemana(date(2026, 10, 3), (p("2026-10-03-q1", resultado="errada"), p("2026-10-03-q2", resultado="certa"),
                                          p("2026-10-03-q3", resultado="sem resposta")))
    q2 = QuizDaSemana(date(2026, 10, 10), (p("2026-10-10-q1", origem="2026-10-03-q1", resultado="certa"),
                                           p("2026-10-10-q2", origem="2026-10-03-q3", resultado="errada")))
    [a] = atrasadas([q1, q2], date(2026, 10, 17))
    assert a.origem == "2026-10-03-q3" and a.resultado == ""


def test_atrasadas_tem_teto_de_dez_mais_antigas_primeiro(): ...


def test_respostas_viram_resultado_e_o_vazio_de_quiz_passado_vira_sem_resposta():
    quiz = QuizDaSemana(date(2026, 10, 10), (p("2026-10-10-q1"), p("2026-10-10-q2")))
    [novo] = aplicar_respostas([quiz], {"2026-10-10-q1": Resposta(1, True)}, hoje=date(2026, 10, 11))
    assert [x.resultado for x in novo.perguntas] == ["certa", "sem resposta"]


def test_no_proprio_sabado_o_vazio_continua_vazio():
    quiz = QuizDaSemana(date(2026, 10, 10), (p("2026-10-10-q1"),))
    [novo] = aplicar_respostas([quiz], {}, hoje=date(2026, 10, 10))
    assert novo.perguntas[0].resultado == ""


def test_aulas_do_quiz_sao_as_lidas_sem_quiz(): ...


def test_novo_quiz_numera_novas_e_atrasadas_com_id_do_dia():
    quiz = novo_quiz(date(2026, 10, 17), novas=[...uma PerguntaNova...], atrasadas=[p("x", origem="2026-10-03-q3")])
    assert [x.id for x in quiz.perguntas] == ["2026-10-17-q1", "2026-10-17-q2"]
```

- [ ] `quiz.py`: `PASTA_DOS_QUIZZES = "noticias/quiz"`; `Pergunta` (frozen: `id`, `aula`,
  `pergunta`, `alternativas: tuple[str, ...]`, `certa: int`, `explicacao`, `origem = ""`,
  `resultado = ""`); `QuizDaSemana` (`data`, `perguntas`, `aviso: str = ""`). Nota: frontmatter
  `tipo: quiz`, `data`; por pergunta, `## N. <pergunta>`, a linha
  `<!-- id: … · aula: … · origem: … · certa: N -->`, as alternativas `- a) …` (a certa com `✓`
  no fim, só para leitura humana), `Explicação: …`, `Resultado: …`. `ler_nota_do_quiz` lê pelo
  comentário e pelas linhas; `ler_quizzes(vault)` ordena por data; `escrever_quiz(vault, quiz)`.
  `aplicar_respostas(quizzes, respostas, hoje)`, `atrasadas(quizzes, hoje, limite=10)`,
  `aulas_do_quiz(notas)` (lidas e `quiz == ""`, mais antigas primeiro), `novo_quiz(hoje, novas,
  atrasadas)`.

## Tarefa 10 — as perguntas novas (`portas.py`, `quiz_claude.py`, `fakes.py`)

Arquivos: `src/whis/portas.py`, `src/whis/quiz_claude.py`, `src/whis/fakes.py`,
`tests/test_quiz_claude.py`.

- [ ] `portas.py`: `PerguntaNova` (`aula`, `pergunta`, `alternativas`, `certa`, `explicacao`),
  `PerguntasNovas` (`perguntas: tuple[PerguntaNova, ...]`, `medida`), `ErroDeQuiz`, `PortaQuiz`
  (`perguntar(aulas: Sequence[Aula]) -> PerguntasNovas`).
- [ ] Testes (vermelhos), com `QuizGravada(_Gravado, QuizClaude)`:

```python
def test_uma_pergunta_por_aula_validada():
    dados = {"perguntas": [
        {"aula": "2026-10-06-negocios", "pergunta": "Margem é?", "alternativas": ["a", "b", "c"], "certa": 2, "explicacao": "e"},
        {"aula": "2026-10-06-negocios", "pergunta": "Sem alternativa", "alternativas": ["a"], "certa": 0, "explicacao": "e"},
        {"aula": "2026-10-06-negocios", "pergunta": "Certa fora", "alternativas": ["a", "b", "c"], "certa": 3, "explicacao": "e"},
        {"aula": "id-que-nao-veio", "pergunta": "x", "alternativas": ["a", "b", "c"], "certa": 0, "explicacao": "e"},
    ]}
    assert [q.pergunta for q in interpretar_perguntas(dados, {"2026-10-06-negocios"})] == ["Margem é?"]


def test_o_pedido_leva_o_id_o_titulo_e_o_texto_de_cada_aula(): ...


def test_quiz_sem_ferramentas_e_com_saida_estruturada(): ...
```

- [ ] `quiz_claude.py`: `SISTEMA_QUIZ` (português; uma pergunta de múltipla escolha por aula
  recebida; 3 ou 4 alternativas; só o que está no texto da aula; alternativas erradas plausíveis;
  explicação de uma ou duas frases dizendo por que a certa é a certa; para quem está aprendendo),
  `ESQUEMA_DO_QUIZ`, `QuizClaude(_AdaptadorDoJornal)` (`etapa = "quiz"`, `erro = ErroDeQuiz`,
  `ferramentas=[]`, `max_turns=4`, `timeout_s=240`), `interpretar_perguntas(dados, ids)`.
  `QuizFake` em `fakes.py`.

## Tarefa 11 — o sábado (`jornal.py`, `pagina_do_jornal.py`, `vault.py`)

Arquivos: `src/whis/jornal.py`, `src/whis/pagina_do_jornal.py`, `src/whis/vault.py`,
`tests/test_jornal.py`.

- [ ] Testes (vermelhos), `SABADO = datetime(2026, 9, 26, 8, 20, tzinfo=BRT)`:

```python
def test_sabado_tem_quiz_e_nenhuma_aula_nova(cenario):
    gerar(cenario)
    marcar_lidas(cenario, "2026-09-25-negocios", "2026-09-25-carros-1")
    formacao, quiz = FormacaoDublê(), QuizDublê()
    resultado = gerar(cenario, formacao=formacao, quiz=quiz, agora=SABADO)
    assert formacao.vagas_recebidas is None
    assert [a.id for a in quiz.aulas_recebidas] == ["2026-09-25-carros-1", "2026-09-25-negocios"]
    nota = (cenario["vault"] / "noticias/quiz/2026-09-26.md").read_text("utf-8")
    assert "2026-09-26-q1" in nota and "2026-09-26-q2" in nota
    assert "quiz: 2026-09-26" in (cenario["vault"] / "noticias/aulas/2026-09-25-negocios.md").read_text("utf-8")
    assert resultado.edicao.quiz is not None


def test_pagina_do_sabado_abre_com_o_quiz(cenario): ...  # seção "Quiz da semana" antes de "Aprender hoje", .pergunta com data-id e data-certa


def test_sabado_sem_nada_lido_diz_que_volta_no_proximo(cenario): ...


def test_quiz_que_falha_ainda_traz_as_atrasadas_e_avisa(cenario): ...


def test_rodar_de_novo_no_sabado_reaproveita_o_quiz(cenario): ...


def test_resposta_do_quiz_vira_resultado_no_domingo(cenario): ...
```

- [ ] `gerar_jornal(..., quiz: PortaQuiz | None = None, sabado: bool | None = None)`;
  `e_sabado = hoje.weekday() == 5 if sabado is None else sabado`. Depois das marcações:

```python
    quizzes = _quiz.aplicar_respostas(_quiz.ler_quizzes(vault), marcacoes.respostas, hoje)
    quiz_de_hoje = _montar_quiz(quiz, hoje, notas, quizzes, avisos) if e_sabado else None
```

  `_montar_quiz`: se já existe o quiz de hoje em `quizzes`, devolve ele; senão, `aulas =
  _quiz.aulas_do_quiz(notas)`, `novas = porta.perguntar([n.aula for n in aulas])` (com
  `ErroDeQuiz` → aviso `AVISO_DO_QUIZ = "quiz novo indisponível hoje"` e nenhuma nova),
  `_quiz.novo_quiz(hoje, novas.perguntas, _quiz.atrasadas(quizzes, hoje))`; sem nenhuma pergunta,
  `QuizDaSemana(hoje, (), aviso="Nenhuma aula lida desde o último quiz. O quiz volta no próximo
  sábado.")`. Fora do `simular`: escrever os quizzes que `aplicar_respostas` mudou, o de hoje, e
  `quiz: <hoje>` nas aulas que entraram. `Edicao.quiz: QuizDaSemana | None = None`.
- [ ] Página: com `edicao.quiz`, a primeira seção é *Quiz da semana* (cor `#b5651d`), cada
  pergunta `<div class="pergunta" data-id="{id}" data-certa="{certa}" data-quiz="{data}">` com
  `<h4>`, as alternativas `<button class="alt" data-i="{i}" type="button">`, uma
  `<p class="q-nota"></p>` e `<details><summary>Ver resposta</summary><p>{letra}) {certa}. {explicação}</p></details>`.
  CSS dos botões como `button.li`, `.alt.certa{background:#2f7d3a;color:#fff}.alt.errada{background:#a8382f;color:#fff}`.
  No `SCRIPT`, no lugar do comentário:

```javascript
  const revelar = (q, escolha) => {
    const certa = Number(q.dataset.certa);
    q.querySelectorAll("button.alt").forEach((a, i) => {
      a.disabled = true;
      if (i === certa) a.classList.add("certa");
      else if (i === escolha) a.classList.add("errada");
    });
    q.querySelector("details").open = true;
  };
  let feitas = {};
  if (db && perguntas.length) {
    try {
      const snap = await db.collection("respostas").where("quiz", "==", perguntas[0].dataset.quiz).get();
      for (const d of snap.docs) feitas[d.id] = d.data();
    } catch (e) { feitas = {}; }
  }
  for (const q of perguntas) {
    if (feitas[q.dataset.id]) { revelar(q, feitas[q.dataset.id].escolha); continue; }
    if (!db) q.querySelector(".q-nota").textContent = "Sua resposta não vai ficar guardada.";
    q.querySelectorAll("button.alt").forEach((a) => a.addEventListener("click", async () => {
      const escolha = Number(a.dataset.i);
      revelar(q, escolha);
      if (!db) return;
      try {
        await db.doc("respostas/" + q.dataset.id).set({
          escolha, certa: escolha === Number(q.dataset.certa), quiz: q.dataset.quiz, em: new Date().toISOString(),
        });
      } catch (e) { q.querySelector(".q-nota").textContent = "Não consegui guardar a resposta."; }
    }));
  }
```

- [ ] Nota do dia: `## Quiz da semana` no topo, as perguntas com as alternativas e um link
  `[[noticias/quiz/AAAA-MM-DD]]`.

## Tarefa 12 — a casca (`__main__.py`, `palheta.py`)

Arquivos: `src/whis/__main__.py`, `src/whis/palheta.py`, `tests/test_casca_do_jornal.py`.

- [ ] Testes (vermelhos): `news --sabado` sozinho sai com código 2 e a mensagem *"--sabado só vale
  com --simular ou --fakes"*; `news --fakes --sabado` gera página com *Quiz da semana*;
  `montar_portas_do_jornal(fakes=False)` tem `MarcacoesClaude` e `QuizClaude`, com `fakes=True`
  `MarcacoesFake` e `QuizFake`.
- [ ] `montar_portas_do_jornal` e `PortasDoJornal` com `marcacoes` e `quiz`; `_comando_news` e
  `palheta.jornal()` passam `marcacoes=portas.marcacoes, quiz=portas.quiz`, e `sabado=True` com
  `--sabado`. `_relatar_jornal` imprime `Quiz: N perguntas` quando há quiz.

## Tarefa 13 — docs (ticket 07)

- [ ] `docs/adr/0005-marcacoes-no-banco-do-artifact.md` no molde da 0003/0004 (Contexto,
  Decisão, Consequências), com o que a spec diz na camada 6 e os números da tarefa 0.
- [ ] `CONTEXT.md`: verbetes **Aula** e **Quiz da semana**; **Trilha** e **Jornal** como a spec diz.
- [ ] `docs/smoke-jornal.md`: os passos novos do ticket 08, com os comandos em PowerShell 5.1.

## Tarefa 14 — fechamento

- [ ] Suíte inteira verde (a falha conhecida da caçada com data fixa não é desta entrega; dizer se
  ainda estiver lá).
- [ ] `whis news --simular` e `whis news --simular --sabado` com o config dele; abrir a página local
  no navegador embutido e conferir figuras, botões apagados (fora do claude.ai) e o quiz revelando.
- [ ] Resolver os tickets 02 a 07; o 08 fica para ele.
