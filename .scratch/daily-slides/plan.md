# Plano de implementação: a daily em slides

> **Para quem executa:** siga tarefa a tarefa, na ordem; os passos usam caixas (`- [ ]`) para
> marcar o andamento. O usuário conduz entregas por `/rb-orchestrate`, e este plano serve de
> entrada para ele. A spec que manda é [spec.md](spec.md): onde este plano e a spec divergirem,
> vale a spec, e a divergência é anotada no `ORCHESTRATION.md`.

**Objetivo:** `whis daily` passa a ler o que ele escreve em `daily/atual.md`, montar um deck do
Claude Slides com o texto literal, publicar sempre no mesmo link e gravar uma cópia datada. A
daily escrita pelo agente (git/Linear/Slack → roteiro) sai inteira.

**Arquitetura:** a nota passa por um modelo puro (`deck.py`: seções → slides), depois por um
renderizador puro (`slides_do_deck.py`: slides → `project/deck.json` + `project/slides/*.html`).
Uma porta publica esses arquivos (`deck_claude.py`: Haiku pelo `_AdaptadorDoJornal`, criando o
deck pelo tipo Slides na primeira vez). A costura (`daily.py`) junta tudo e grava a cópia em
`daily/YYYY-MM-DD.md` com `deck:` no frontmatter. É por esse campo que a próxima geração acha o
endereço, como o jornal faz com `artifact:`.

**Tecnologia:** Python 3.12, `claude_agent_sdk` (CLI do npm com `CLAUDE_CODE_ARTIFACT=1`, como
o jornal), pytest. Comandos a partir da raiz do repositório, no Bash da sessão:
`.venv/Scripts/python.exe -m pytest …`.

---

## Antes de começar

- **Pré-requisito das Tarefas 3 em diante:** em 2026-09-30 a árvore tinha trabalho **não
  commitado** de outras sessões:
  - a remoção da gravação e o `login_do_claude` do jornal, prontos;
  - o coletor de reuniões da Granola, em construção.

  Esse trabalho mexe em `portas.py`, `fakes.py`, `vault.py`, `palheta.py`, `__main__.py`,
  `configuracao.py` e `resumo_dia_claude.py`, os mesmos arquivos das Tarefas 3 a 7, e um commit
  não separa o que é de cada sessão dentro de um arquivo. Por isso:
  1. ele commita a remoção da gravação e o `login_do_claude`;
  2. esta entrega roda num **worktree próprio** (branch `daily-slides`) a partir desse commit,
     enquanto a Granola segue na árvore principal;
  3. o merge em `master` acontece no fim, depois da Tarefa 7, com a suíte verde e com os
     conflitos de `palheta.py`/`__main__.py` resolvidos à mão.

  A alternativa é esperar a Granola ser commitada e rodar tudo na árvore principal. A escolha
  é dele.

  **No worktree,** a `.venv` é a da árvore principal, e o `whis` dela está instalado em modo
  editável apontando para o `src` de lá. Todo comando Python do plano roda então com o `src` do
  worktree na frente, assim:
  `PYTHONPATH=src /c/Users/gabri/development/whis/.venv/Scripts/python.exe -m pytest …`.
  A bandeja e as tarefas agendadas dele continuam no código da árvore principal até o merge, e
  isso também protege o Whis que ele usa no dia a dia. Antes da Tarefa 3, confira `git status --short src tests` no lugar onde vai trabalhar:
  nada de outra sessão pode aparecer. As Tarefas 0 a 2 não tocam nenhum desses arquivos.
- **Ordem diferente da spec:** a spec põe o deck de exemplo na camada 0. Aqui a sonda (Tarefa 0)
  prova só a mecânica, com slides escritos à mão. O deck de exemplo com a nota de verdade dele
  vem na Tarefa 5, já com o renderizador real, para o visual que ele aprovar ser o que vai ao ar.
- **Nenhum teste publica, chama o CLI, mostra toast ou escreve fora do `tmp_path`.** A fixture
  autouse `publicacao_do_deck` (Tarefa 6) garante a publicação; a `toasts` do `conftest` já
  garante o toast.
- **Comentários:** a preferência global dele é não comentar o óbvio. Os docstrings de módulo
  seguem o estilo da casa (explicam o porquê); dentro das funções, nada que o nome já diga.
- Mensagens de commit sem acento, como as do repositório.

## Mapa de arquivos

| Arquivo | Papel | Tarefa |
|---|---|---|
| `.scratch/daily-slides/research/sonda.py` | sonda descartável do Slides headless | 0 |
| `.scratch/daily-slides/research/01-slides-headless.md` | o que a sonda achou | 0 |
| `src/whis/nota_viva.py` | `SECAO_TERMINEI`, `texto_e_profundidade` (T1); sete seções e só escrita a pedido (T6) | 1, 6 |
| `src/whis/deck.py` (novo) | `Deck`, `Slide`, `ItemDoSlide`, `montar_deck`, `paginar` | 1 |
| `src/whis/slides_do_deck.py` (novo) | `slides_do_deck(deck, hoje)` → arquivos do tipo Slides | 2 |
| `src/whis/portas.py` | `ErroDePublicacao(url=)`, `PortaPublicacaoDoDeck`; sai a porta da daily velha | 3, 6 |
| `src/whis/fakes.py` | `PublicacaoDoDeckFake`; saem os fakes da daily velha | 3, 6 |
| `src/whis/deck_claude.py` (novo) | `PublicacaoDoDeckClaude`, pedidos, extratores | 3 |
| `src/whis/vault.py` | `montar_copia_da_daily`, `ultimo_deck` (T4); sai a daily velha (T6) | 4, 6 |
| `.scratch/daily-slides/research/deck-de-exemplo.py`, `semear-deck.py` | deck de exemplo e semente do endereço | 5 |
| `src/whis/daily.py` | reescrito: `gerar_daily` novo, `ResultadoDaDaily` novo | 6 |
| `src/whis/resumo_dia_claude.py` | sai a parte da daily | 6 |
| `src/whis/configuracao.py` | saem `referencias_pessoais` e `contexto_do_time` | 6 |
| `src/whis/palheta.py` | `Resultado.rotulo`, toasts da daily, `comandos_padrao` novo | 6, 7 |
| `src/whis/__main__.py` | `montar_publicacao_do_deck`, `_comando_daily`, saída e relato | 6, 7 |
| `tests/fixtures/daily.py` (novo) | `NOTA_DA_DAILY`, `escrever_nota_da_daily` | 6 |
| `CONTEXT.md`, `docs/smoke-daily.md` | glossário e roteiro da prova | 7 |

---

## Tarefa 0: sonda do Slides headless

Responde, com dinheiro de verdade e um deck de verdade, o que a spec deixou em aberto: o
Haiku headless cria o deck pelo `type_url`? Publica vários arquivos com `root`? Republica de
uma sessão nova removendo um slide? Qual frase a ferramenta devolve? Lista aninhada, `<span>`
monoespaçado e `<a>` sobrevivem? Trocar o `createdOnFiles.at` é aceito?

**Arquivos:**
- Criar: `.scratch/daily-slides/research/sonda.py`
- Criar: `.scratch/daily-slides/research/01-slides-headless.md`

- [ ] **Passo 1: escrever a sonda**

```python
"""Sonda da camada 0 da daily em slides: o tipo Slides publica headless?

Da raiz do repositório, com o Python do projeto:

    .venv/Scripts/python.exe .scratch/daily-slides/research/sonda.py criar
    .venv/Scripts/python.exe .scratch/daily-slides/research/sonda.py preencher <url> v1
    .venv/Scripts/python.exe .scratch/daily-slides/research/sonda.py preencher <url> v2

Cada passo grava o que a sessão do CLI devolveu em sonda-<passo>.txt, ao lado.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from whis.jornal_claude import (
    AMBIENTE_DA_PUBLICACAO,
    FERRAMENTAS_DA_PUBLICACAO,
    MODELO_DA_PUBLICACAO,
    SISTEMA_PUBLICACAO,
    TIMEOUT_DA_PUBLICACAO_S,
    TURNOS_DA_PUBLICACAO,
    _AdaptadorDoJornal,
)
from whis.portas import ErroDePublicacao

TIPO_SLIDES = "https://claude.ai/artifact/8jTsAFQMFDb2oA8MsPJ2eL"
AQUI = Path(__file__).resolve().parent
ESTILO = (
    "background:#16171c;color:#ecebe6;font-family:Inter, 'Segoe UI', sans-serif;"
    "padding:128px 128px 160px;display:flex;flex-direction:column;gap:48px"
)


def secao(id_: str, titulo: str, corpo: str) -> str:
    return (
        f'<section id="{id_}" style="{ESTILO}">\n'
        f'<h2 style="font-size:72px;font-weight:700;line-height:1.1">{titulo}</h2>\n'
        f"{corpo}\n"
        f'<p style="position:absolute;left:128px;bottom:64px;width:1664px;font-size:24px;'
        f'color:#8b8a99">Sonda · {id_}</p>\n'
        "</section>\n"
    )


V1 = {
    "aninhado": secao(
        "aninhado",
        "Lista aninhada",
        '<ul style="font-size:40px;line-height:1.35"><li>pai<ul style="font-size:32px">'
        "<li>filho dentro do li</li></ul></li><li>outro pai</li></ul>",
    ),
    "irmao": secao(
        "irmao",
        "Lista irmã recuada",
        '<div style="display:flex;flex-direction:column;gap:16px">'
        '<ul style="padding-left:48px;font-size:40px;line-height:1.35;color:#ecebe6"><li>pai</li></ul>'
        '<ul style="padding-left:96px;font-size:32px;line-height:1.35;color:#b9b7c6">'
        "<li>filho como lista irmã</li></ul></div>",
    ),
    "inline": secao(
        "inline",
        "Marcas inline",
        '<ul style="font-size:40px;line-height:1.35">'
        "<li><b>negrito</b> e <i>itálico</i></li>"
        '<li><span style="color:#8b7cf6">código em cor</span></li>'
        '<li><span style="font-family:Consolas, monospace">código monoespaçado</span></li>'
        '<li><a href="https://github.com">link</a></li></ul>',
    ),
}
V2 = {
    "aninhado": V1["aninhado"].replace("filho dentro do li", "filho dentro do li (v2)"),
    "inline": V1["inline"],
}


def indice(ids: list[str]) -> str:
    return json.dumps(
        {
            "v": 4,
            "createdOnFiles": {"v": 1, "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
            "lists": "css",
            "title": "Daily",
            "order": ids,
            "sections": {ids[0]: {"description": "Sonda", "start": ids[0]}},
            "cover": ids[0],
            "faces": {
                "inter": {
                    "family": "Inter",
                    "href": "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap",
                }
            },
            "designSystems": [],
        },
        ensure_ascii=False,
        indent=2,
    )


def pedido_de_criacao() -> str:
    return (
        f"Crie um deck novo com a ferramenta Artifact: action publish, type_url={TIPO_SLIDES}, "
        "title 'Daily', sem file_path e sem files. Não leia, não edite nem crie arquivos. "
        "Responda SOMENTE com a URL do deck criado."
    )


def pedido_de_preenchimento(raiz: Path, arquivos: tuple[str, ...], url: str) -> str:
    base = raiz.as_posix()
    mapa = json.dumps({c: c for c in sorted(arquivos) if c != "project/deck.json"}, ensure_ascii=False)
    locais = ", ".join(f"{base}/{c}" for c in sorted(arquivos))
    return (
        f"O deck {url} recebe os slides de hoje no mesmo endereço.\n"
        f"Passo 1: ferramenta Artifact, action read, url={url}. Espere o resultado.\n"
        "Passo 2 (só depois do resultado do passo 1): ferramenta Artifact, action list com scope files "
        f"(se a ferramenta chamar essa ação de list_files, use list_files), url={url}; e leia com a "
        f"ferramenta Read cada um destes arquivos: {locais}. Espere os resultados.\n"
        f"Passo 3 (só depois dos resultados do passo 2): ferramenta Artifact, action publish, url={url}, "
        f"root={base}, file_path={base}/project/deck.json, label 'daily de hoje', e files com este mapa "
        f"{mapa} mais uma entrada com valor null para cada caminho project/slides/* que a listagem do "
        "passo 2 mostrou e que não está nesse mapa; overwrite_unread com a lista de todos os caminhos "
        "project/* que a listagem do passo 2 mostrou. SEM force, sem capabilities, sem contract, sem "
        "type_url.\nNão edite nem crie arquivos. Responda SOMENTE com a URL publicada."
    )


class Sonda(_AdaptadorDoJornal):
    etapa = "sonda do deck"
    erro = ErroDePublicacao

    def __init__(self) -> None:
        super().__init__(modelo=MODELO_DA_PUBLICACAO, cli=None, timeout_s=TIMEOUT_DA_PUBLICACAO_S)

    def rodar(self, passo: str, pedido: str, cwd: Path) -> None:
        opcoes = self._opcoes(
            sistema=SISTEMA_PUBLICACAO,
            ferramentas=FERRAMENTAS_DA_PUBLICACAO,
            max_turns=TURNOS_DA_PUBLICACAO,
            cwd=cwd,
            ambiente=AMBIENTE_DA_PUBLICACAO,
        )
        saida = AQUI / f"sonda-{passo}.txt"
        try:
            conversa = self._conversar(pedido, opcoes)
        except ErroDePublicacao as erro:
            saida.write_text(f"PEDIDO:\n{pedido}\n\nERRO: {erro}\n", encoding="utf-8")
            raise
        relato = [
            f"PEDIDO:\n{pedido}\n",
            f"FERRAMENTAS: {conversa.ferramentas}",
            "RESULTADOS DE FERRAMENTA:",
            *conversa.resultados_de_ferramenta,
            f"TEXTO FINAL: {conversa.texto_final()}",
            f"CUSTO: {conversa.medida.custo_usd} USD em {conversa.medida.segundos} s",
        ]
        saida.write_text("\n".join(relato), encoding="utf-8")
        print("\n".join(relato))


def escrever(versao: str) -> tuple[Path, tuple[str, ...]]:
    slides = V1 if versao == "v1" else V2
    raiz = AQUI / f"sonda-deck-{versao}"
    for id_, html in slides.items():
        destino = raiz / "project" / "slides" / f"{id_}.html"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(html, encoding="utf-8", newline="\n")
    (raiz / "project" / "deck.json").write_text(indice(list(slides)), encoding="utf-8", newline="\n")
    return raiz, ("project/deck.json", *(f"project/slides/{i}.html" for i in slides))


if __name__ == "__main__":
    sonda = Sonda()
    if sys.argv[1] == "criar":
        sonda.rodar("criar", pedido_de_criacao(), AQUI)
    else:
        url, versao = sys.argv[2], sys.argv[3]
        raiz, arquivos = escrever(versao)
        sonda.rodar(f"preencher-{versao}", pedido_de_preenchimento(raiz, arquivos, url), raiz)
```

- [ ] **Passo 2: criar o deck**

Rode: `.venv/Scripts/python.exe .scratch/daily-slides/research/sonda.py criar`.
O esperado é um `RESULTADOS DE FERRAMENTA` com a URL do deck e um `CUSTO` (Haiku, centavos).
Anote a **frase exata** do resultado (por exemplo `Created … at https://claude.ai/artifact/…`)
e a URL. Se a ferramenta não aceitar `type_url` ou a sessão não tiver `Artifact`, o veredito é
**B**: pule para o Passo 8.

- [ ] **Passo 3: ler as regras de formato do tipo no deck criado**

Com a ferramenta `Artifact` desta sessão: `action: read`, `url: <deck>`,
`paths: ["artifact-type/reference/format.md", "artifact-type/reference/deck-files.md"]`. Leia e
anote, para o `01-slides-headless.md`: se `<ul>` aninhado é aceito; se `<span>` aceita
`font-family`; se `padding-left` num `<ul>` é aceito; e se `<a href>`, `<b>`, `<i>`,
`position:absolute` e `<div>` com `display:flex` são aceitos.

- [ ] **Passo 4: preencher com a v1**

Rode: `.venv/Scripts/python.exe .scratch/daily-slides/research/sonda.py preencher <url> v1`.
O esperado são três chamadas na ordem `read`, `list`, `publish`, uma frase de publicação com a
URL e nenhum `force`. Anote a frase exata do resultado do `publish`, o tempo e o custo.

- [ ] **Passo 5: olhar o deck renderizado**

Abra a URL no painel do navegador (`mcp__Claude_Browser__navigate`) e tire um screenshot de cada
um dos três slides. Se o painel não estiver logado no claude.ai, use `Artifact` `action: open`
e peça a ele, em uma linha, que diga se em *Lista aninhada* o filho aparece recuado, se em
*Lista irmã* ele aparece recuado e menor, e se em *Marcas inline* as cinco marcas aparecem.
O julgamento é pelo que se **vê**, não pelo arquivo publicado.

- [ ] **Passo 6: republicar com a v2 numa sessão nova**

Rode: `.venv/Scripts/python.exe .scratch/daily-slides/research/sonda.py preencher <url> v2`.
Depois liste os arquivos do deck (`Artifact` `action: list`, `scope: "files"`, `url`). O
esperado: `project/slides/irmao.html` some, `aninhado.html` traz "(v2)", e o publish passa sem
`force` mesmo com o `createdOnFiles.at` trocado. Se o `at` novo for recusado, anote: a spec já
prevê `deck_criado:` na cópia datada.

- [ ] **Passo 7: registrar e decidir**

Escreva `.scratch/daily-slides/research/01-slides-headless.md` com:
- a frase exata da criação e a do publish;
- o tempo e o custo de cada passo;
- o que o `format.md` diz e o que se viu de lista aninhada, lista irmã, `<span>` e `<a>`;
- se o `at` pôde mudar;
- a URL do deck da sonda, que vira o endereço fixo na Tarefa 5.

Feche com o veredito e os **ajustes deste plano** que ele obriga. O plano parte dos seguintes
padrões:
- sub-item como `<ul>` irmão com `padding-left` (Tarefa 2);
- código em `<span style="color:…">` (Tarefa 2);
- `at` trocando a cada geração (Tarefa 2);
- publicação reconhecida por `Published … at <url>` (Tarefa 3);
- criação reconhecida por qualquer URL de artifact num resultado de ferramenta (Tarefa 3).

Se a sonda contradisser um desses padrões, corrija o código da tarefa correspondente neste
arquivo antes de executá-la.

- [ ] **Passo 8: se o veredito for B**

Pare a execução, registre no `ORCHESTRATION.md` e reescreva as Tarefas 2, 3 e 5 para o plano B
da spec (*Geração e publicação › Plano B*):
- `pagina_do_deck(deck)` gera um HTML único de apresentação;
- a publicação passa a ser `PublicacaoClaude` com sucesso só pela frase da ferramenta.

As Tarefas 1, 4, 6 e 7 não mudam.

- [ ] **Passo 9: commit**

```bash
git add .scratch/daily-slides/research/sonda.py .scratch/daily-slides/research/01-slides-headless.md
git commit -m "Sonda da daily em slides: o tipo Slides cria, publica e republica headless pelo Haiku"
```

(Sem `git add -A`: há trabalho de outras sessões na árvore. `sonda-*.txt` e `sonda-deck-*/`
ficam fora do commit.)

---

## Tarefa 1: o modelo do deck

**Arquivos:**
- Modificar: `src/whis/nota_viva.py` (constante e função novas, nada removido)
- Criar: `src/whis/deck.py`
- Teste: `tests/test_deck.py`

- [ ] **Passo 1: escrever os testes que falham**

`tests/test_deck.py`:

```python
"""O deck da daily: as seções que ele escreveu viram slides, com o texto como está."""

from __future__ import annotations

from whis.deck import ALTURA_DA_LISTA, ItemDoSlide, altura, montar_deck
from whis.nota_viva import NotaViva

NOTA = (
    "---\n"
    "tipo: daily-atual\n"
    "---\n"
    "\n"
    "## O que eu fiz\n"
    "\n"
    "- FN-123 frete corrigido\n"
    "\t- subiu em produção\n"
    "\n"
    "## O que estou fazendo\n"
    "\n"
    "1. FN-130 diário automático\n"
    "\n"
    "## O que terminei\n"
    "\n"
    "## Fazer\n"
    "\n"
    "- [ ] não entra\n"
    "\n"
    "## Dúvidas\n"
    "\n"
    "- quem revisa o PR?\n"
    "\n"
    "## Pontos\n"
    "\n"
    "- também não entra\n"
    "\n"
    "## Falar\n"
    "\n"
    "Parágrafo solto\n"
)


def secao(titulo: str, linhas: list[str]) -> NotaViva:
    return NotaViva.de_texto(f"## {titulo}\n\n" + "\n".join(linhas) + "\n")


def test_cada_secao_com_texto_vira_um_slide_na_ordem_do_deck():
    deck = montar_deck(NotaViva.de_texto(NOTA))

    assert [slide.id for slide in deck.slides] == ["fiz", "fazendo", "duvidas", "falar"]
    assert [slide.titulo for slide in deck.slides] == [
        "O que eu fiz",
        "O que estou fazendo",
        "Dúvidas",
        "Falar",
    ]


def test_o_texto_sai_sem_o_marcador_e_com_a_profundidade():
    fiz, fazendo, *_ = montar_deck(NotaViva.de_texto(NOTA)).slides

    assert fiz.itens == (ItemDoSlide("FN-123 frete corrigido", 0), ItemDoSlide("subiu em produção", 1))
    assert fazendo.itens == (ItemDoSlide("FN-130 diário automático", 0),)


def test_paragrafo_solto_entra_como_item_de_nivel_zero():
    falar = montar_deck(NotaViva.de_texto(NOTA)).slides[-1]

    assert falar.itens == (ItemDoSlide("Parágrafo solto", 0),)


def test_recuo_por_espacos_tambem_e_sub_item():
    deck = montar_deck(secao("O que eu fiz", ["- pai", "  - filho", "    - neto"]))

    assert [item.profundidade for item in deck.slides[0].itens] == [0, 1, 2]


def test_pontos_e_fazer_nunca_entram():
    textos = [item.texto for slide in montar_deck(NotaViva.de_texto(NOTA)).slides for item in slide.itens]

    assert not any("não entra" in texto for texto in textos)


def test_nota_sem_o_que_terminei_monta_o_deck_sem_ela():
    assert [slide.id for slide in montar_deck(secao("O que eu fiz", ["- a"])).slides] == ["fiz"]


def test_nota_sem_texto_e_deck_vazio():
    assert montar_deck(NotaViva.de_texto("## O que eu fiz\n\n-\n\n## Falar\n")).vazio()


def test_o_deck_guarda_as_linhas_literais_das_secoes_que_viraram_slide():
    deck = montar_deck(NotaViva.de_texto(NOTA))

    assert [secao.titulo for secao in deck.secoes] == ["O que eu fiz", "O que estou fazendo", "Dúvidas", "Falar"]
    assert deck.secoes[0].linhas == ("- FN-123 frete corrigido", "\t- subiu em produção")


def test_secao_que_nao_cabe_continua_em_outro_slide_com_a_contagem():
    deck = montar_deck(secao("O que eu fiz", [f"- item {n}" for n in range(1, 21)]))

    assert [slide.id for slide in deck.slides] == ["fiz", "fiz-2", "fiz-3"]
    assert [slide.titulo for slide in deck.slides] == [
        "O que eu fiz (1/3)",
        "O que eu fiz (2/3)",
        "O que eu fiz (3/3)",
    ]
    assert [item.texto for slide in deck.slides for item in slide.itens] == [f"item {n}" for n in range(1, 21)]
    assert {slide.secao for slide in deck.slides} == {"O que eu fiz"}


def test_sub_item_nao_se_separa_do_pai_quando_o_grupo_cabe():
    linhas = [f"- solto {n}" for n in range(8)] + ["- pai", "\t- filho 1", "\t- filho 2"]

    primeiro, segundo = montar_deck(secao("O que eu fiz", linhas)).slides

    assert [item.texto for item in segundo.itens] == ["pai", "filho 1", "filho 2"]
    assert len(primeiro.itens) == 8


def test_grupo_maior_que_um_slide_e_partido_item_a_item_sem_perder_nada():
    linhas = ["- pai"] + [f"\t- filho {n}" for n in range(15)]

    deck = montar_deck(secao("O que eu fiz", linhas))

    assert [item.texto for slide in deck.slides for item in slide.itens] == ["pai"] + [f"filho {n}" for n in range(15)]
    assert len(deck.slides) == 2


def test_linha_longa_ocupa_mais_altura_e_cabe_menos_por_slide():
    assert altura(ItemDoSlide("x" * 300)) > altura(ItemDoSlide("x"))
    assert sum(altura(ItemDoSlide(f"item {n}")) for n in range(9)) <= ALTURA_DA_LISTA
```

- [ ] **Passo 2: rodar e ver falhar**

Rode: `.venv/Scripts/python.exe -m pytest tests/test_deck.py -v`
Esperado: erro de coleta, `ModuleNotFoundError: No module named 'whis.deck'`.

- [ ] **Passo 3: acrescentar `SECAO_TERMINEI` e `texto_e_profundidade` em `nota_viva.py`**

Logo abaixo de `SECAO_FALAR = "Falar"`:

```python
SECAO_TERMINEI = "O que terminei"
```

(`SECOES` **não** muda nesta tarefa: a daily velha continua rodando com seis seções até a
Tarefa 6.)

Logo abaixo de `_ITEM = re.compile(...)`:

```python
#: Um marcador sem texto (`-`, `1.`): o item vazio que o Obsidian deixa ao dar Enter.
_SO_MARCADOR = re.compile(r"^[ \t]*([-*+]|\d+[.)])[ \t]*$")
```

Logo acima de `def sem_brancos_nas_pontas`:

```python
def texto_e_profundidade(linhas: Sequence[str]) -> tuple[tuple[str, int], ...]:
    """Cada linha com texto como `(texto, profundidade)`, para quem só lê a seção.

    O texto vem sem o marcador de lista e sem o recuo; uma linha que não é item
    entra inteira. A profundidade conta as linhas abertas acima dela, pela
    mesma régua de recuo de `_nivel` (tab = 4 colunas).
    """
    resultado: list[tuple[str, int]] = []
    colunas: list[int] = []
    for linha in linhas:
        if _SO_MARCADOR.match(linha):
            continue
        partes = _ITEM.match(linha)
        texto = (partes["texto"] if partes else linha).strip()
        if not texto:
            continue
        coluna = _nivel(linha)
        while colunas and colunas[-1] >= coluna:
            colunas.pop()
        resultado.append((texto, len(colunas)))
        colunas.append(coluna)
    return tuple(resultado)
```

- [ ] **Passo 4: escrever `src/whis/deck.py`**

```python
"""O deck da daily: as seções que ele escreveu em `daily/atual.md`, em slides.

Puro, sem I/O. Recebe a nota e devolve os slides com o texto de cada linha
como ele escreveu, sem o marcador de lista e com a profundidade do recuo.
Quem desenha os arquivos do tipo Slides é `slides_do_deck`; quem publica é a
porta da publicação.

O corte em mais de um slide estima a altura de cada linha pela regra do tipo
Slides (cerca de 0,6 × o tamanho da fonte por caractere na largura útil):
nada encolhe para caber, a seção continua no slide seguinte e um sub-item só
se separa do pai quando o grupo inteiro não cabe num slide.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .nota_viva import (
    SECAO_DUVIDAS,
    SECAO_FALAR,
    SECAO_FAZENDO,
    SECAO_FIZ,
    SECAO_TERMINEI,
    NotaViva,
    texto_e_profundidade,
)

SECOES_DO_DECK = (
    (SECAO_FIZ, "fiz"),
    (SECAO_FAZENDO, "fazendo"),
    (SECAO_TERMINEI, "terminei"),
    (SECAO_DUVIDAS, "duvidas"),
    (SECAO_FALAR, "falar"),
)

LARGURA_UTIL = 1664
#: 1080 − 128 no topo − 160 com o rodapé − o cabeçalho (faixa de 8, vão de 24, título de 72 × 1,1) − o vão de 48.
ALTURA_DA_LISTA = 633
FONTE_DO_ITEM = 40
FONTE_DO_SUBITEM = 32
ALTURA_DA_LINHA = 1.35
ESPACO_ENTRE_ITENS = 16
RECUO_POR_NIVEL = 48
LARGURA_DO_CARACTERE = 0.6


@dataclass(frozen=True)
class ItemDoSlide:
    texto: str
    profundidade: int = 0


@dataclass(frozen=True)
class Slide:
    id: str
    titulo: str
    secao: str
    itens: tuple[ItemDoSlide, ...]


@dataclass(frozen=True)
class SecaoDoDeck:
    """Uma seção da nota que virou slide, com as linhas dela exatamente como estão."""

    titulo: str
    linhas: tuple[str, ...]


@dataclass(frozen=True)
class Deck:
    slides: tuple[Slide, ...] = ()
    secoes: tuple[SecaoDoDeck, ...] = ()

    def vazio(self) -> bool:
        return not self.slides


def montar_deck(nota: NotaViva) -> Deck:
    slides: list[Slide] = []
    secoes: list[SecaoDoDeck] = []
    for titulo, id_base in SECOES_DO_DECK:
        linhas = nota.conteudo(titulo)
        itens = tuple(ItemDoSlide(texto, profundidade) for texto, profundidade in texto_e_profundidade(linhas))
        if not itens:
            continue
        secoes.append(SecaoDoDeck(titulo, linhas))
        paginas = paginar(itens)
        for numero, pagina in enumerate(paginas, start=1):
            slides.append(
                Slide(
                    id=id_base if numero == 1 else f"{id_base}-{numero}",
                    titulo=titulo if len(paginas) == 1 else f"{titulo} ({numero}/{len(paginas)})",
                    secao=titulo,
                    itens=pagina,
                )
            )
    return Deck(slides=tuple(slides), secoes=tuple(secoes))


def altura(item: ItemDoSlide) -> float:
    fonte = FONTE_DO_ITEM if item.profundidade == 0 else FONTE_DO_SUBITEM
    largura = LARGURA_UTIL - RECUO_POR_NIVEL * (item.profundidade + 1)
    por_linha = max(1, int(largura / (LARGURA_DO_CARACTERE * fonte)))
    linhas = max(1, math.ceil(len(item.texto) / por_linha))
    return linhas * fonte * ALTURA_DA_LINHA + ESPACO_ENTRE_ITENS


def paginar(itens: Sequence[ItemDoSlide]) -> tuple[tuple[ItemDoSlide, ...], ...]:
    paginas: list[list[ItemDoSlide]] = [[]]
    usada = 0.0
    for grupo in _grupos(itens):
        pedacos = [grupo] if _soma(grupo) <= ALTURA_DA_LISTA else [[item] for item in grupo]
        for pedaco in pedacos:
            tamanho = _soma(pedaco)
            if paginas[-1] and usada + tamanho > ALTURA_DA_LISTA:
                paginas.append([])
                usada = 0.0
            paginas[-1].extend(pedaco)
            usada += tamanho
    return tuple(tuple(pagina) for pagina in paginas if pagina)


def _grupos(itens: Sequence[ItemDoSlide]) -> list[list[ItemDoSlide]]:
    grupos: list[list[ItemDoSlide]] = []
    for item in itens:
        if item.profundidade == 0 or not grupos:
            grupos.append([item])
        else:
            grupos[-1].append(item)
    return grupos


def _soma(itens: Sequence[ItemDoSlide]) -> float:
    return sum(altura(item) for item in itens)
```

- [ ] **Passo 5: rodar e ver passar**

Rode: `.venv/Scripts/python.exe -m pytest tests/test_deck.py tests/test_nota_viva.py -v`
Esperado: todos `PASSED` (os de `test_nota_viva.py` continuam verdes: nada foi removido).

- [ ] **Passo 6: commit**

```bash
git add src/whis/deck.py src/whis/nota_viva.py tests/test_deck.py
git commit -m "Modelo do deck da daily: secoes da nota viram slides com o texto literal, profundidade do recuo e corte em (1/2) sem separar sub-item do pai"
```

---

## Tarefa 2: os arquivos do tipo Slides

**Arquivos:**
- Criar: `src/whis/slides_do_deck.py`
- Teste: `tests/test_slides_do_deck.py`

- [ ] **Passo 1: escrever os testes que falham**

`tests/test_slides_do_deck.py`:

```python
"""O deck nos arquivos do tipo Slides: um `<section>` por arquivo e o `deck.json`."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone

import pytest

from whis.deck import Deck, ItemDoSlide, Slide, montar_deck
from whis.nota_viva import NotaViva
from whis.slides_do_deck import ACENTO, CAMINHO_DO_INDICE, slides_do_deck

HOJE = date(2026, 9, 30)
AGORA = datetime(2026, 9, 30, 16, 55, tzinfo=timezone.utc)
PERMITIDAS = {"section", "div", "h2", "ul", "li", "p", "b", "i", "a", "span"}


def deck_de(*itens: ItemDoSlide) -> Deck:
    return Deck(slides=(Slide("fiz", "O que eu fiz", "O que eu fiz", tuple(itens)),))


def html_de(*textos: str) -> str:
    deck = deck_de(*(ItemDoSlide(texto) for texto in textos))
    return slides_do_deck(deck, HOJE, agora=AGORA)["project/slides/fiz.html"]


def arquivos_de(texto_da_nota: str) -> dict[str, str]:
    return slides_do_deck(montar_deck(NotaViva.de_texto(texto_da_nota)), HOJE, agora=AGORA)


def test_um_arquivo_por_slide_com_um_section_de_id_igual_ao_nome():
    arquivos = arquivos_de("## O que eu fiz\n\n- a\n\n## Falar\n\n- b\n")

    assert sorted(arquivos) == ["project/deck.json", "project/slides/falar.html", "project/slides/fiz.html"]
    for id_ in ("fiz", "falar"):
        conteudo = arquivos[f"project/slides/{id_}.html"]
        assert conteudo.startswith(f'<section id="{id_}" ')
        assert conteudo.count("<section") == 1
        assert conteudo.rstrip().endswith("</section>")


def test_so_elementos_e_estilos_que_o_tipo_slides_aceita():
    conteudo = html_de("**a** *b* `c` [d](https://e.com) [[f|g]]", "texto")

    assert set(re.findall(r"</?([a-zA-Z0-9-]+)", conteudo)) <= PERMITIDAS
    for estilo in re.findall(r'style="([^"]*)"', conteudo):
        for fora_do_subconjunto in ("margin", "var(", "z-index", "padding-left", "padding-top"):
            assert fora_do_subconjunto not in estilo
        assert not re.search(r"\d(\.\d+)?em\b", estilo)
    assert "<ul" not in "".join(re.findall(r"<li>(.*?)</li>", conteudo)), "lista aninhada não existe no tipo"
    assert "class=" not in conteudo and "<style" not in conteudo
    assert all(int(tamanho) >= 24 for tamanho in re.findall(r"font-size:(\d+)px", conteudo))


def test_html_da_nota_sai_escapado():
    conteudo = html_de('<script>alert(1)</script> & "aspas"')

    assert "<script" not in conteudo
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;aspas&quot;" in conteudo


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("**feito**", "<b>feito</b>"),
        ("*quase*", "<i>quase</i>"),
        ("_quase_", "<i>quase</i>"),
        ("nome_de_funcao_x", "nome_de_funcao_x"),
        ("`git push`", f'<span style="color:{ACENTO}">git push</span>'),
        ("[PR](https://github.com/x/y/pull/1)", '<a href="https://github.com/x/y/pull/1">PR</a>'),
        ("[[notas/frete|frete]]", "frete"),
        ("[[frete]]", "frete"),
        ("[x](javascript:alert(1))", "[x](javascript:alert(1))"),
    ],
)
def test_markdown_simples_vira_formatacao(texto: str, esperado: str):
    assert f"<li>{esperado}</li>" in html_de(texto)


def test_sub_item_e_uma_lista_irma_mais_recuada_e_menor():
    conteudo = slides_do_deck(
        deck_de(ItemDoSlide("pai"), ItemDoSlide("filho", 1)), HOJE, agora=AGORA
    )["project/slides/fiz.html"]

    pai, filho = re.findall(r'<ul style="padding:0 0 0 (\d+)px;font-size:(\d+)px', conteudo)
    assert int(filho[0]) > int(pai[0]) and int(filho[1]) < int(pai[1])
    assert "<li>pai</li></ul>" in conteudo


def test_rodape_com_a_data_por_extenso_e_a_pagina():
    arquivos = arquivos_de("## O que eu fiz\n\n- a\n\n## Falar\n\n- b\n")

    assert "Daily · 30 de setembro de 2026 (quarta-feira) · 1/2" in arquivos["project/slides/fiz.html"]
    assert "· 2/2" in arquivos["project/slides/falar.html"]


def test_o_indice_segue_o_formato_do_tipo():
    linhas = "\n".join(f"- item {n}" for n in range(12))
    arquivos = arquivos_de(f"## O que eu fiz\n\n{linhas}\n\n## Falar\n\n- b\n")

    indice = json.loads(arquivos[CAMINHO_DO_INDICE])
    assert indice["v"] == 4 and indice["lists"] == "css" and indice["title"] == "Daily"
    assert indice["createdOnFiles"] == {"v": 1, "at": "2026-09-30T16:55:00Z"}
    assert indice["order"] == ["fiz", "fiz-2", "falar"]
    assert indice["cover"] == "fiz"
    assert indice["sections"] == {
        "fiz": {"description": "O que eu fiz", "start": "fiz"},
        "falar": {"description": "Falar", "start": "falar"},
    }
    assert indice["designSystems"] == []
    [face] = indice["faces"].values()
    assert face["href"].startswith("https://fonts.googleapis.com/css2?")
    assert sorted(arquivos) == sorted([CAMINHO_DO_INDICE, *(f"project/slides/{i}.html" for i in indice["order"])])


def test_deck_vazio_nao_tem_arquivo():
    assert slides_do_deck(Deck(), HOJE, agora=AGORA) == {}
```

- [ ] **Passo 2: rodar e ver falhar**

Rode: `.venv/Scripts/python.exe -m pytest tests/test_slides_do_deck.py -v`
Esperado: `ModuleNotFoundError: No module named 'whis.slides_do_deck'`.

- [ ] **Passo 3: escrever `src/whis/slides_do_deck.py`**

```python
"""O deck da daily nos arquivos do tipo Slides: `project/deck.json` e um HTML por slide.

O formato é o de `artifact-type/reference/format.md` do tipo Slides (release
1790810190-bbd5, lido na sonda `.scratch/daily-slides/research/01-slides-headless.md`):
um `<section>` por arquivo, canvas de 1920×1080, só estilo inline do
subconjunto que o tipo aceita. O que está fora dele some na leitura sem aviso,
e é por isso que o recuo vai no atalho `padding` (não há `padding-left`), o
sub-item é um `ul` irmão mais recuado (não há lista aninhada) e o código é só
um `span` com cor (span não aceita fonte). Cada item é o seu próprio `ul`: o
vão entre itens fica com o `gap` do `div`, igual à estimativa de `deck.py`.
"""

from __future__ import annotations

import html
import json
import re
from datetime import date, datetime, timezone

from .deck import (
    ALTURA_DA_LINHA,
    ESPACO_ENTRE_ITENS,
    FONTE_DO_ITEM,
    FONTE_DO_SUBITEM,
    RECUO_POR_NIVEL,
    Deck,
    ItemDoSlide,
    Slide,
)
from .vault import _data_por_extenso

TITULO_DO_DECK = "Daily"
CAMINHO_DO_INDICE = "project/deck.json"
PASTA_DOS_SLIDES = "project/slides"

FUNDO = "#16171c"
TEXTO = "#ecebe6"
TEXTO_DO_SUBITEM = "#b9b7c6"
RODAPE = "#8b8a99"
ACENTO = "#8b7cf6"
FAMILIA = "Inter"
PILHA_DE_FONTES = "Inter, 'Segoe UI', sans-serif"
HREF_DA_FONTE = "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap"
FONTE_DO_TITULO = 72
FONTE_DO_RODAPE = 24

_MARCAS = re.compile(
    r"\[\[(?P<nota>[^\]|]+)(?:\|(?P<apelido>[^\]]+))?\]\]"
    r"|\[(?P<rotulo>[^\]]+)\]\((?P<url>https?://[^)\s]+)\)"
    r"|\*\*(?P<negrito>.+?)\*\*"
    r"|`(?P<codigo>[^`]+)`"
    r"|\*(?P<italico>[^*\s][^*]*)\*"
    r"|(?<!\w)_(?P<sublinhado>[^_\s][^_]*)_(?!\w)"
)


def slides_do_deck(deck: Deck, hoje: date, *, agora: datetime | None = None) -> dict[str, str]:
    """Caminho publicado → conteúdo. Deck vazio não tem arquivo."""
    if deck.vazio():
        return {}
    total = len(deck.slides)
    arquivos = {
        f"{PASTA_DOS_SLIDES}/{slide.id}.html": html_do_slide(slide, hoje, numero, total)
        for numero, slide in enumerate(deck.slides, start=1)
    }
    arquivos[CAMINHO_DO_INDICE] = indice_do_deck(deck, agora or datetime.now(timezone.utc))
    return arquivos


def indice_do_deck(deck: Deck, agora: datetime) -> str:
    inicios: dict[str, str] = {}
    for slide in deck.slides:
        inicios.setdefault(slide.secao, slide.id)
    indice = {
        "v": 4,
        "createdOnFiles": {"v": 1, "at": agora.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "lists": "css",
        "title": TITULO_DO_DECK,
        "order": [slide.id for slide in deck.slides],
        "sections": {inicio: {"description": secao, "start": inicio} for secao, inicio in inicios.items()},
        "cover": deck.slides[0].id,
        "faces": {FAMILIA.lower(): {"family": FAMILIA, "href": HREF_DA_FONTE}},
        "designSystems": [],
    }
    return json.dumps(indice, ensure_ascii=False, indent=2) + "\n"


def html_do_slide(slide: Slide, hoje: date, numero: int, total: int) -> str:
    rodape = f"{TITULO_DO_DECK} · {_data_por_extenso(hoje)} · {numero}/{total}"
    return "\n".join(
        [
            f'<section id="{slide.id}" style="background:{FUNDO};color:{TEXTO};font-family:{PILHA_DE_FONTES};'
            'padding:128px 128px 160px;display:flex;flex-direction:column;gap:48px">',
            '<div style="display:flex;flex-direction:column;gap:24px">',
            f'<div style="width:96px;height:8px;background:{ACENTO}"></div>',
            f'<h2 style="font-size:{FONTE_DO_TITULO}px;font-weight:700;line-height:1.1;color:{TEXTO}">'
            f"{html.escape(slide.titulo)}</h2>",
            "</div>",
            f'<div style="display:flex;flex-direction:column;gap:{ESPACO_ENTRE_ITENS}px">',
            *(_lista(item) for item in slide.itens),
            "</div>",
            f'<p style="position:absolute;left:128px;bottom:64px;width:1664px;font-size:{FONTE_DO_RODAPE}px;'
            f'color:{RODAPE}">{html.escape(rodape)}</p>',
            "</section>",
        ]
    ) + "\n"


def _lista(item: ItemDoSlide) -> str:
    fonte = FONTE_DO_ITEM if item.profundidade == 0 else FONTE_DO_SUBITEM
    cor = TEXTO if item.profundidade == 0 else TEXTO_DO_SUBITEM
    recuo = RECUO_POR_NIVEL * (item.profundidade + 1)
    return (
        f'<ul style="padding:0 0 0 {recuo}px;font-size:{fonte}px;line-height:{ALTURA_DA_LINHA};color:{cor}">'
        f"<li>{_inline(item.texto)}</li></ul>"
    )


def _inline(texto: str) -> str:
    partes: list[str] = []
    fim = 0
    for marca in _MARCAS.finditer(texto):
        partes.append(html.escape(texto[fim : marca.start()]))
        partes.append(_marca(marca))
        fim = marca.end()
    partes.append(html.escape(texto[fim:]))
    return "".join(partes)


def _marca(marca: re.Match[str]) -> str:
    escapar = html.escape
    if marca["nota"] is not None:
        return escapar((marca["apelido"] or marca["nota"]).strip())
    if marca["url"] is not None:
        return f'<a href="{escapar(marca["url"])}">{escapar(marca["rotulo"])}</a>'
    if marca["negrito"] is not None:
        return f"<b>{escapar(marca['negrito'])}</b>"
    if marca["codigo"] is not None:
        return f'<span style="color:{ACENTO}">{escapar(marca["codigo"])}</span>'
    return f"<i>{escapar(marca['italico'] or marca['sublinhado'])}</i>"
```

- [ ] **Passo 4: rodar e ver passar**

Rode: `.venv/Scripts/python.exe -m pytest tests/test_slides_do_deck.py tests/test_deck.py -v`
Esperado: todos `PASSED`.

- [ ] **Passo 5: commit**

```bash
git add src/whis/slides_do_deck.py tests/test_slides_do_deck.py
git commit -m "Arquivos do deck no formato do tipo Slides: um section por slide so com o que o SKILL documenta, markdown simples escapado e deck.json com order, sections e fonte"
```

---

## Tarefa 3: a porta da publicação e o adaptador

**Pré-requisito:** a árvore sem trabalho de outras sessões em `portas.py` e `fakes.py` (ver
*Antes de começar*).

**Arquivos:**
- Modificar: `src/whis/portas.py` (`ErroDePublicacao` ganha `url`; porta nova)
- Modificar: `src/whis/fakes.py` (`PublicacaoDoDeckFake`)
- Criar: `src/whis/deck_claude.py`
- Teste: `tests/test_deck_claude.py`

- [ ] **Passo 1: escrever os testes que falham**

`tests/test_deck_claude.py`:

```python
"""A publicação do deck: Haiku, só a ferramenta Artifact, sempre no mesmo endereço.

A rede entra trocada por mensagens gravadas, uma lista por sessão do CLI.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolResultBlock, UserMessage

from whis.claude_cli import VARIAVEIS_DE_API_PAGA
from whis.deck_claude import TIPO_SLIDES, PublicacaoDoDeckClaude, pedido_de_criacao, pedido_de_preenchimento
from whis.portas import ErroDePublicacao, PortaPublicacaoDoDeck

URL = "https://claude.ai/artifact/DeckDaDaily123"
NOVA = "https://claude.ai/artifact/DeckNovo456"
ARQUIVOS = ("project/deck.json", "project/slides/falar.html", "project/slides/fiz.html")


def _resultado(texto: str = "", **extras) -> ResultMessage:
    campos = {
        "subtype": "success",
        "duration_ms": 1000,
        "duration_api_ms": 900,
        "is_error": False,
        "num_turns": 3,
        "session_id": "sessao-de-teste",
        "total_cost_usd": 0.05,
        "usage": {},
        "result": texto,
    }
    return ResultMessage(**{**campos, **extras})


def _ferramenta(conteudo: str) -> UserMessage:
    return UserMessage(content=[ToolResultBlock(tool_use_id="t1", content=conteudo)])


def _publicado(url: str) -> UserMessage:
    return _ferramenta(
        f"Updated the Artifact at {url} (Version 2) with C:\\tmp\\trabalho\\project\\deck.json (and any "
        f"`files` listed); own files not sent this time were kept. Its page comes from the Artifact "
        f"type {TIPO_SLIDES} (release 1790810190-bbd5) and can't be changed here."
    )


def _criado(url: str) -> UserMessage:
    return _ferramenta(
        f"Created a new Artifact at {url} (version 1790816110-1bca) from the Artifact type "
        f"{TIPO_SLIDES} (release 1790810190-bbd5). Its own files (add yours under `project/`): none."
    )


def _texto(texto: str) -> AssistantMessage:
    return AssistantMessage(content=[TextBlock(text=texto)], model="claude-haiku-4-5-20251001")


class PublicacaoGravada(PublicacaoDoDeckClaude):
    def __init__(self, *chamadas: list, **extras) -> None:
        super().__init__(**extras)
        self.chamadas = list(chamadas)
        self.prompts: list[str] = []
        self.opcoes: list = []

    async def _mensagens(self, prompt, opcoes):
        self.prompts.append(prompt)
        self.opcoes.append(opcoes)
        for mensagem in self.chamadas.pop(0):
            yield mensagem


@pytest.fixture(autouse=True)
def _sem_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    for nome in VARIAVEIS_DE_API_PAGA:
        monkeypatch.delenv(nome, raising=False)


@pytest.fixture
def raiz(tmp_path: Path) -> Path:
    pasta = tmp_path / "trabalho"
    for caminho in ARQUIVOS:
        (pasta / caminho).parent.mkdir(parents=True, exist_ok=True)
        (pasta / caminho).write_text("x", encoding="utf-8")
    return pasta


def test_cumpre_a_porta():
    assert isinstance(PublicacaoDoDeckClaude(), PortaPublicacaoDoDeck)


def test_com_endereco_republica_numa_sessao_so(raiz: Path):
    publicacao = PublicacaoGravada([_publicado(URL), _resultado(URL)])

    feita = publicacao.publicar(raiz, ARQUIVOS, URL)

    assert feita.url == URL
    assert len(publicacao.prompts) == 1
    assert f"action read, url={URL}" in publicacao.prompts[0]


def test_sem_endereco_cria_pelo_tipo_slides_e_preenche_noutra_sessao(raiz: Path):
    publicacao = PublicacaoGravada(
        [_criado(NOVA), _resultado(NOVA)],
        [_publicado(NOVA), _resultado(NOVA)],
    )

    feita = publicacao.publicar(raiz, ARQUIVOS, None)

    assert feita.url == NOVA
    criar, preencher = publicacao.prompts
    assert f"type_url={TIPO_SLIDES}" in criar and "title 'Daily'" in criar
    assert f"url={NOVA}" in preencher


def test_a_frase_do_artifact_comum_tambem_conta_como_publicado(raiz: Path):
    publicacao = PublicacaoGravada([_ferramenta(f"Published C:/tmp/deck.json at {URL} (Version 4)"), _resultado(URL)])

    assert publicacao.publicar(raiz, ARQUIVOS, URL).url == URL


def test_a_criacao_nao_confunde_o_deck_com_a_url_do_tipo(raiz: Path):
    publicacao = PublicacaoGravada([_criado(NOVA), _resultado(NOVA)], [_publicado(NOVA), _resultado(NOVA)])

    publicacao.publicar(raiz, ARQUIVOS, None)

    assert f"url={NOVA}" in publicacao.prompts[1]
    assert f"url={TIPO_SLIDES}" not in publicacao.prompts[1]


def test_url_so_no_texto_nao_conta_como_publicado(raiz: Path):
    publicacao = PublicacaoGravada([_texto(URL), _resultado(URL)])

    with pytest.raises(ErroDePublicacao) as erro:
        publicacao.publicar(raiz, ARQUIVOS, URL)

    assert erro.value.url == URL


def test_listagem_de_arquivos_nao_conta_como_publicacao(raiz: Path):
    publicacao = PublicacaoGravada(
        [_ferramenta(f"Published files at {URL} (version 1), 3 files by path"), _resultado("nada")]
    )

    with pytest.raises(ErroDePublicacao):
        publicacao.publicar(raiz, ARQUIVOS, URL)


def test_falha_no_preenchimento_depois_de_criar_leva_o_endereco_criado(raiz: Path):
    publicacao = PublicacaoGravada(
        [_criado(NOVA), _resultado(NOVA)],
        [_texto("não consegui"), _resultado("não consegui")],
    )

    with pytest.raises(ErroDePublicacao) as erro:
        publicacao.publicar(raiz, ARQUIVOS, None)

    assert erro.value.url == NOVA


def test_erro_do_cli_no_preenchimento_tambem_leva_o_endereco(raiz: Path):
    publicacao = PublicacaoGravada(
        [_criado(NOVA), _resultado(NOVA)],
        [_resultado("boom", is_error=True, subtype="error_during_execution")],
    )

    with pytest.raises(ErroDePublicacao) as erro:
        publicacao.publicar(raiz, ARQUIVOS, None)

    assert erro.value.url == NOVA


def test_criacao_sem_endereco_num_resultado_de_ferramenta_e_erro_sem_url(raiz: Path):
    publicacao = PublicacaoGravada([_texto(NOVA), _resultado(NOVA)])

    with pytest.raises(ErroDePublicacao) as erro:
        publicacao.publicar(raiz, ARQUIVOS, None)

    assert erro.value.url is None


def test_pedido_de_preenchimento_le_lista_e_publica_sem_force(raiz: Path):
    pedido = pedido_de_preenchimento(raiz, ARQUIVOS, URL)

    leitura, listagem, publicar = (pedido.index("action read"), pedido.index("scope files"), pedido.index("action publish"))
    assert leitura < listagem < publicar
    base = raiz.as_posix()
    assert f"root={base}" in pedido and f"file_path={base}/project/deck.json" in pedido
    mapa = pedido.split("files com este mapa ", 1)[1].split(" mais uma", 1)[0]
    assert '"project/slides/fiz.html": "project/slides/fiz.html"' in mapa
    assert "project/deck.json" not in mapa
    assert "null" in pedido[publicar:] and "overwrite_unread" in pedido[publicar:]
    assert "SEM force" in pedido and "\\" not in pedido


def test_pedido_de_criacao_nao_leva_arquivo():
    pedido = pedido_de_criacao()

    assert f"type_url={TIPO_SLIDES}" in pedido and "sem file_path" in pedido and "claude.ai/artifact/Deck" not in pedido


def test_opcoes_haiku_com_artifact_e_read_na_pasta_de_trabalho(raiz: Path):
    publicacao = PublicacaoGravada([_publicado(URL), _resultado(URL)])

    publicacao.publicar(raiz, ARQUIVOS, URL)

    opcoes = publicacao.opcoes[0]
    assert opcoes.model == "haiku"
    assert opcoes.tools == ["Artifact", "Read"] and opcoes.allowed_tools == ["Artifact", "Read"]
    assert Path(opcoes.cwd) == raiz
    assert opcoes.env["CLAUDE_CODE_ARTIFACT"] == "1"
```

- [ ] **Passo 2: rodar e ver falhar**

Rode: `.venv/Scripts/python.exe -m pytest tests/test_deck_claude.py -v`
Esperado: `ModuleNotFoundError: No module named 'whis.deck_claude'`.

- [ ] **Passo 3: `ErroDePublicacao` com `url` e a porta nova em `portas.py`**

Troque a classe `ErroDePublicacao` por:

```python
class ErroDePublicacao(RuntimeError):
    """A página não saiu; a nota já existe no vault.

    `url` é o endereço que já existe quando a falha veio depois de criá-lo: o
    deck da daily nasce numa sessão do CLI e é preenchido na seguinte.
    """

    def __init__(self, *args: object, url: str | None = None) -> None:
        super().__init__(*args)
        self.url = url
```

E acrescente, logo depois de `PortaPublicacao`:

```python
@runtime_checkable
class PortaPublicacaoDoDeck(Protocol):
    """Publica os arquivos do deck da daily no Claude Slides, sempre no mesmo endereço."""

    def publicar(self, raiz: Path, arquivos: tuple[str, ...], url_atual: str | None) -> Publicacao:
        """`arquivos` são os caminhos publicados (`project/...`) sob `raiz`, o índice incluído.

        Sem `url_atual`, cria o deck pelo tipo Slides e o preenche. Levanta
        `ErroDePublicacao`, com `url` quando o deck chegou a ser criado.
        """
        ...
```

- [ ] **Passo 4: o fake em `fakes.py`**

Logo depois de `URL_DO_JORNAL_FAKE`:

```python
URL_DO_DECK_FAKE = "https://claude.ai/artifact/fake-daily"
```

E no fim do arquivo:

```python
class PublicacaoDoDeckFake:
    """Publicação do deck que não publica: guarda o que recebeu e devolve uma URL fixa.

    `conteudos` é lido na hora da chamada, porque a pasta de trabalho é
    temporária. Só os testes a usam: `--fakes` na daily é simulação.
    """

    def __init__(self, url: str = URL_DO_DECK_FAKE, erro: Exception | None = None) -> None:
        self._url = url
        self._erro = erro
        self.chamadas = 0
        self.url_recebida: str | None = None
        self.conteudos: dict[str, str] = {}

    def publicar(self, raiz: Path, arquivos: tuple[str, ...], url_atual: str | None) -> Publicacao:
        self.chamadas += 1
        self.url_recebida = url_atual
        self.conteudos = {caminho: (raiz / caminho).read_text(encoding="utf-8") for caminho in arquivos}
        if self._erro is not None:
            raise self._erro
        return Publicacao(url=url_atual or self._url, medida=MEDIDA_DA_PUBLICACAO_FAKE)
```

- [ ] **Passo 5: escrever `src/whis/deck_claude.py`**

```python
"""A publicação do deck da daily: um Haiku que só opera a ferramenta Artifact.

Mesmo adaptador do jornal (`_AdaptadorDoJornal`: OAuth da conta, CLI do npm,
ambiente neutro, custo no log), com duas diferenças que só o deck tem:

- o deck nasce do tipo **Slides** numa sessão do CLI e é preenchido na
  seguinte; se a segunda falhar, o erro leva o endereço criado, para a cópia
  datada guardá-lo e o link continuar o mesmo;
- publicado é **só** o que a ferramenta confirma: a URL já vai no pedido, e um
  Haiku que a repete sem publicar não pode contar como sucesso.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions

from .jornal_claude import (
    AMBIENTE_DA_PUBLICACAO,
    FERRAMENTAS_DA_PUBLICACAO,
    MODELO_DA_PUBLICACAO,
    SISTEMA_PUBLICACAO,
    TIMEOUT_DA_PUBLICACAO_S,
    TURNOS_DA_PUBLICACAO,
    Conversa,
    _AdaptadorDoJornal,
)
from .portas import ErroDePublicacao, Publicacao
from .slides_do_deck import CAMINHO_DO_INDICE, PASTA_DOS_SLIDES, TITULO_DO_DECK

_log = logging.getLogger("whis.daily")

TIPO_SLIDES = "https://claude.ai/artifact/8jTsAFQMFDb2oA8MsPJ2eL"
TURNOS_DA_CRIACAO = 4

_URL = r"(https://claude\.ai/(?:code/)?artifact/[\w-]+)"
#: Num artifact tipado a ferramenta diz `Updated the Artifact at`; no comum, `Published … at`.
_PADRAO_DO_DECK_PUBLICADO = re.compile(rf"\bUpdated the Artifact at {_URL}|\bPublished (?!files\b)[^\n]*? at {_URL}")
#: A frase da criação traz depois a URL do tipo: casar a frase, nunca pegar a última URL.
_PADRAO_DO_DECK_CRIADO = re.compile(rf"\bCreated a new Artifact at {_URL}")
_PADRAO_DE_QUALQUER_URL = re.compile(_URL)


class PublicacaoDoDeckClaude(_AdaptadorDoJornal):
    etapa = "publicação da daily"
    erro = ErroDePublicacao

    def __init__(
        self,
        *,
        modelo: str | None = MODELO_DA_PUBLICACAO,
        cli: str | None = None,
        timeout_s: float = TIMEOUT_DA_PUBLICACAO_S,
    ) -> None:
        super().__init__(modelo=modelo or MODELO_DA_PUBLICACAO, cli=cli, timeout_s=timeout_s)

    def publicar(self, raiz: Path, arquivos: tuple[str, ...], url_atual: str | None) -> Publicacao:
        url = url_atual or self._criar(raiz)
        try:
            conversa = self._conversar(
                pedido_de_preenchimento(raiz, arquivos, url), self._opcoes_do_deck(raiz, TURNOS_DA_PUBLICACAO)
            )
        except ErroDePublicacao as erro:
            raise ErroDePublicacao(str(erro), url=url) from erro
        publicada = url_do_deck_publicado(conversa)
        if publicada is None:
            raise ErroDePublicacao(
                "A ferramenta Artifact não confirmou a publicação dos slides. "
                f"Começo da resposta: {conversa.texto_final()[:300]!r}",
                url=url,
            )
        return Publicacao(url=publicada, medida=conversa.medida)

    def _criar(self, raiz: Path) -> str:
        conversa = self._conversar(pedido_de_criacao(), self._opcoes_do_deck(raiz, TURNOS_DA_CRIACAO))
        criada = url_do_deck_criado(conversa)
        if criada is None:
            raise ErroDePublicacao(
                "O deck da daily não foi criado: nenhuma URL veio da ferramenta. "
                f"Começo da resposta: {conversa.texto_final()[:300]!r}"
            )
        _log.info("Deck da daily criado em %s.", criada)
        return criada

    def _opcoes_do_deck(self, raiz: Path, turnos: int) -> ClaudeAgentOptions:
        return self._opcoes(
            sistema=SISTEMA_PUBLICACAO,
            ferramentas=FERRAMENTAS_DA_PUBLICACAO,
            max_turns=turnos,
            cwd=raiz,
            ambiente=AMBIENTE_DA_PUBLICACAO,
        )


def pedido_de_criacao() -> str:
    return (
        f"Crie um deck novo com a ferramenta Artifact: action publish, type_url={TIPO_SLIDES}, "
        f"title '{TITULO_DO_DECK}', sem file_path e sem files. Não leia, não edite nem crie arquivos. "
        "Responda SOMENTE com a URL do deck criado."
    )


def pedido_de_preenchimento(raiz: Path, arquivos: tuple[str, ...], url: str) -> str:
    """Três passos em turnos separados, na ordem que o jornal provou no ticket 09."""
    base = raiz.as_posix()
    mapa = json.dumps(
        {caminho: caminho for caminho in sorted(arquivos) if caminho != CAMINHO_DO_INDICE}, ensure_ascii=False
    )
    locais = ", ".join(f"{base}/{caminho}" for caminho in sorted(arquivos))
    return (
        f"O deck {url} recebe os slides de hoje no mesmo endereço.\n"
        f"Passo 1: ferramenta Artifact, action read, url={url}. Espere o resultado.\n"
        "Passo 2 (só depois do resultado do passo 1): ferramenta Artifact, action list com scope files "
        f"(se a ferramenta chamar essa ação de list_files, use list_files), url={url}; e leia com a "
        f"ferramenta Read cada um destes arquivos: {locais}. Espere os resultados.\n"
        f"Passo 3 (só depois dos resultados do passo 2): ferramenta Artifact, action publish, url={url}, "
        f"root={base}, file_path={base}/{CAMINHO_DO_INDICE}, label 'daily de hoje', e files com este mapa "
        f"{mapa} mais uma entrada com valor null para cada caminho {PASTA_DOS_SLIDES}/* que a listagem do "
        "passo 2 mostrou e que não está nesse mapa; overwrite_unread com a lista de todos os caminhos "
        "project/* que a listagem do passo 2 mostrou. SEM force, sem capabilities, sem contract, sem "
        "type_url.\nNão edite nem crie arquivos. Responda SOMENTE com a URL publicada."
    )


def url_do_deck_publicado(conversa: Conversa) -> str | None:
    for resultado in reversed(conversa.resultados_de_ferramenta):
        achada = _PADRAO_DO_DECK_PUBLICADO.search(resultado)
        if achada:
            return achada.group(1) or achada.group(2)
    return None


def url_do_deck_criado(conversa: Conversa) -> str | None:
    """A URL que a ferramenta deu ao deck novo; nunca a do tipo, nem a do texto do modelo."""
    for resultado in reversed(conversa.resultados_de_ferramenta):
        achada = _PADRAO_DO_DECK_CRIADO.search(resultado)
        if achada:
            return achada.group(1)
    for resultado in reversed(conversa.resultados_de_ferramenta):
        for url in _PADRAO_DE_QUALQUER_URL.findall(resultado):
            if url != TIPO_SLIDES:
                return url
    return None
```

(As frases são as que a sonda registrou em `research/01-slides-headless.md`.)

- [ ] **Passo 6: rodar e ver passar**

Rode: `.venv/Scripts/python.exe -m pytest tests/test_deck_claude.py tests/test_jornal_claude.py -v`
Esperado: todos `PASSED` (o jornal continua verde com o `ErroDePublicacao` novo).

- [ ] **Passo 7: commit**

```bash
git add src/whis/portas.py src/whis/fakes.py src/whis/deck_claude.py tests/test_deck_claude.py
git commit -m "Publicacao do deck da daily: Haiku cria pelo tipo Slides e preenche noutra sessao, sucesso so pela frase da ferramenta e o erro leva o endereco criado"
```

---

## Tarefa 4: a cópia datada e o endereço

**Arquivos:**
- Modificar: `src/whis/vault.py` (duas funções novas, nada removido)
- Teste: `tests/test_copia_da_daily.py`

- [ ] **Passo 1: escrever os testes que falham**

`tests/test_copia_da_daily.py`:

```python
"""A cópia em `daily/YYYY-MM-DD.md`: o que foi para o deck, e o link de onde a próxima republica."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fixtures.leitura import corpo, ler_frontmatter
from whis import vault

AGORA = datetime(2026, 9, 30, 13, 55, tzinfo=timezone(timedelta(hours=-3)))
URL = "https://claude.ai/artifact/DeckDaDaily123"
ANTIGA = "https://claude.ai/artifact/DeckAntigo789"
SECOES = [("O que eu fiz", ("- FN-123 frete", "\t- subiu")), ("Falar", ("- sexta saio cedo",))]


def escrever(pasta: Path, texto: str, nome: str = "2026-09-30.md") -> Path:
    arquivo = pasta / "daily" / nome
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(texto, encoding="utf-8")
    return arquivo


def test_a_copia_tem_tipo_deck_e_hora_e_nenhum_campo_data(tmp_path: Path):
    arquivo = escrever(tmp_path, vault.montar_copia_da_daily(gerada=AGORA, deck=URL, secoes=SECOES))

    assert ler_frontmatter(arquivo) == {"tipo": "daily", "deck": URL, "gerada": "2026-09-30T13:55:00-03:00"}


def test_a_copia_guarda_as_secoes_com_as_linhas_literais_e_o_link(tmp_path: Path):
    texto = corpo(escrever(tmp_path, vault.montar_copia_da_daily(gerada=AGORA, deck=URL, secoes=SECOES)))

    assert texto.lstrip().startswith("# Daily — 30 de setembro de 2026 (quarta-feira)\n")
    assert f"> [!info] [Abrir os slides]({URL})" in texto
    assert "## O que eu fiz\n\n- FN-123 frete\n\t- subiu\n\n## Falar\n\n- sexta saio cedo\n" in texto


def test_sem_deck_a_copia_nao_tem_o_campo_nem_o_link(tmp_path: Path):
    arquivo = escrever(tmp_path, vault.montar_copia_da_daily(gerada=AGORA, deck=None, secoes=SECOES))

    assert "deck" not in ler_frontmatter(arquivo)
    assert "Abrir os slides" not in corpo(arquivo)


def test_o_aviso_vira_callout(tmp_path: Path):
    arquivo = escrever(
        tmp_path,
        vault.montar_copia_da_daily(gerada=AGORA, deck=URL, secoes=SECOES, aviso="Os slides não saíram: x"),
    )

    assert "> [!warning] Os slides não saíram: x" in corpo(arquivo)


def test_o_endereco_vem_da_copia_mais_recente_que_tem_um(tmp_path: Path):
    escrever(
        tmp_path,
        vault.montar_copia_da_daily(gerada=AGORA - timedelta(days=2), deck=ANTIGA, secoes=SECOES),
        "2026-09-28.md",
    )
    escrever(tmp_path, "---\ntipo: daily\ndata: 2026-09-29\ndesde: 2026-09-28T13:55:00-03:00\n---\n\n# Antiga\n", "2026-09-29.md")
    escrever(tmp_path, "---\ntipo: daily-atual\n---\n", "atual.md")

    assert vault.ultimo_deck(tmp_path) == ANTIGA

    escrever(tmp_path, vault.montar_copia_da_daily(gerada=AGORA, deck=URL, secoes=SECOES))

    assert vault.ultimo_deck(tmp_path) == URL


def test_sem_copia_com_deck_nao_ha_endereco(tmp_path: Path):
    assert vault.ultimo_deck(tmp_path) is None

    escrever(tmp_path, "sem frontmatter nenhum", "2026-09-29.md")

    assert vault.ultimo_deck(tmp_path) is None
```

- [ ] **Passo 2: rodar e ver falhar**

Rode: `.venv/Scripts/python.exe -m pytest tests/test_copia_da_daily.py -v`
Esperado: `AttributeError: module 'whis.vault' has no attribute 'montar_copia_da_daily'`.

- [ ] **Passo 3: escrever as duas funções em `vault.py`**

Junto das outras constantes de módulo:

```python
_DECK_NO_FRONTMATTER = re.compile(r'^deck:\s*"?(https://[^\s"]+)"?\s*$', re.M)
```

Logo depois de `caminho_da_daily`:

```python
def montar_copia_da_daily(
    *,
    gerada: datetime,
    deck: str | None,
    secoes: Sequence[tuple[str, Sequence[str]]],
    aviso: str | None = None,
) -> str:
    """A cópia do que foi para o deck, com o link no frontmatter.

    Sem campo `data`: a Daily notes do Obsidian o transformaria em link para
    uma nota que não existe (passo 8 de `docs/smoke-interface.md`).
    """
    campos: dict[str, object] = {"tipo": TIPO_DAILY}
    if deck:
        campos["deck"] = deck
    campos["gerada"] = gerada.isoformat(timespec="seconds")

    linhas = [f"# Daily — {_data_por_extenso(gerada.date())}", ""]
    if deck:
        linhas.extend([f"> [!info] [Abrir os slides]({deck})", ""])
    if aviso:
        linhas.extend([f"> [!warning] {aviso}", ""])
    for titulo, conteudo in secoes:
        linhas.extend([f"## {titulo}", "", *conteudo, ""])
    return _frontmatter(campos) + "\n".join(linhas)


def ultimo_deck(vault: Path) -> str | None:
    """O `deck:` da nota datada mais recente de `daily/` que tem um."""
    pasta = Path(vault) / PASTA_DAILY
    if not pasta.is_dir():
        return None
    datadas = sorted(
        ((dia, arquivo) for arquivo in pasta.glob("*.md") if (dia := _data_do_nome(arquivo.stem)) is not None),
        reverse=True,
    )
    for _dia, arquivo in datadas:
        casou = _DECK_NO_FRONTMATTER.search(_frontmatter_cru(arquivo))
        if casou:
            return casou.group(1)
    return None


def _frontmatter_cru(arquivo: Path) -> str:
    texto = arquivo.read_text(encoding="utf-8", errors="replace")
    if not texto.startswith("---"):
        return ""
    fim = texto.find("\n---", 3)
    return texto[: fim if fim != -1 else 0]
```

- [ ] **Passo 4: rodar e ver passar**

Rode: `.venv/Scripts/python.exe -m pytest tests/test_copia_da_daily.py tests/test_daily.py -v`
Esperado: todos `PASSED` (a daily velha não muda).

- [ ] **Passo 5: commit**

```bash
git add src/whis/vault.py tests/test_copia_da_daily.py
git commit -m "Copia datada da daily: secoes que foram para o deck com as linhas literais, deck no frontmatter sem campo data, e o endereco lido da copia mais recente que tem um"
```

---

## Tarefa 5: deck de exemplo, aprovação do visual e semente do endereço

Tudo daqui vai ao ar na conta dele. A nota lida é a `daily/atual.md` de verdade.

**Arquivos:**
- Criar: `.scratch/daily-slides/research/deck-de-exemplo.py`
- Criar: `.scratch/daily-slides/research/semear-deck.py`

- [ ] **Passo 1: o script do deck de exemplo**

```python
"""Publica o deck de exemplo com a nota de verdade dele, no endereço da sonda.

    .venv/Scripts/python.exe .scratch/daily-slides/research/deck-de-exemplo.py <url-da-sonda>
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from whis.configuracao import carregar
from whis.deck import montar_deck
from whis.deck_claude import PublicacaoDoDeckClaude
from whis.slides_do_deck import slides_do_deck
from whis.vault import ler_nota_viva

AQUI = Path(__file__).resolve().parent

url = sys.argv[1]
configuracao = carregar()
deck = montar_deck(ler_nota_viva(configuracao.vault))
print(f"Vault: {configuracao.vault} — {len(deck.slides)} slide(s)")
if deck.vazio():
    raise SystemExit("A nota está vazia: escreva em daily/atual.md antes do deck de exemplo.")

agora = datetime.now().astimezone()
raiz = AQUI / "deck-de-exemplo"
arquivos = slides_do_deck(deck, agora.date(), agora=agora)
for caminho, conteudo in arquivos.items():
    destino = raiz / caminho
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(conteudo, encoding="utf-8", newline="\n")

feita = PublicacaoDoDeckClaude(cli=configuracao.claude_cli or None).publicar(raiz, tuple(sorted(arquivos)), url)
print(f"Publicado em {feita.url} — US$ {feita.medida.custo_usd} em {feita.medida.segundos} s")
```

- [ ] **Passo 2: publicar e conferir o vault lido**

Rode: `.venv/Scripts/python.exe .scratch/daily-slides/research/deck-de-exemplo.py <url-da-sonda>`.
O esperado é o vault de verdade dele na primeira linha (o `config.toml` da sessão é uma cópia
virtual; se o caminho parecer errado, pare e pergunte) e depois `Publicado em <url-da-sonda>`.
A listagem do deck (`Artifact` `action: list`, `scope: "files"`) não pode ter mais nenhum slide
da sonda (`aninhado`, `inline`).

- [ ] **Passo 3: a aprovação dele**

Mande o link e peça o veredito sobre o visual (cores, fonte, tamanho, recuo de sub-item,
rodapé). Ajuste as constantes de `slides_do_deck.py` (`FUNDO`, `TEXTO`, `ACENTO`, tamanhos) pelo
que ele pedir, rode `tests/test_slides_do_deck.py` e republique (Passo 2), até ele aprovar.
**Não siga sem o "aprovado" dele em chat.** Commit dos ajustes, se houver:

```bash
git add src/whis/slides_do_deck.py
git commit -m "Visual do deck da daily ajustado pela aprovacao dele"
```

- [ ] **Passo 4: o script da semente**

```python
"""Semeia o endereço do deck aprovado na nota datada mais recente de um dia anterior.

    .venv/Scripts/python.exe .scratch/daily-slides/research/semear-deck.py <url>
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

from whis.configuracao import carregar

url = sys.argv[1]
pasta = Path(carregar().vault) / "daily"
anteriores = sorted(
    (
        arquivo
        for arquivo in pasta.glob("*.md")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", arquivo.stem) and date.fromisoformat(arquivo.stem) < date.today()
    ),
    reverse=True,
)
alvo = anteriores[0]
texto = alvo.read_bytes().decode("utf-8")
quebra = "\r\n" if "\r\n" in texto else "\n"
abertura = f"---{quebra}"
assert texto.startswith(abertura), f"{alvo} não começa com frontmatter"
assert "deck:" not in texto.split(f"{quebra}---", 1)[0], f"{alvo} já tem deck:"
alvo.write_bytes(texto.replace(abertura, f'{abertura}deck: "{url}"{quebra}', 1).encode("utf-8"))
print(f"deck: {url} semeado em {alvo}")
```

Nunca na nota de hoje: a daily velha, ainda ativa até a Tarefa 6, reescreve a de hoje sem o
campo.

- [ ] **Passo 5: semear e conferir**

Rode: `.venv/Scripts/python.exe .scratch/daily-slides/research/semear-deck.py <url-aprovada>`
Depois: `.venv/Scripts/python.exe -c "from whis.configuracao import carregar; from whis.vault import ultimo_deck; print(ultimo_deck(carregar().vault))"`
Esperado: a URL aprovada.

- [ ] **Passo 6: commit**

```bash
git add .scratch/daily-slides/research/deck-de-exemplo.py .scratch/daily-slides/research/semear-deck.py
git commit -m "Deck de exemplo com a nota dele no endereco da sonda e a semente do endereco fixo"
```

---

## Tarefa 6: a troca (um commit só)

A partir daqui a árvore fica quebrada até o fim da tarefa. **Nada é commitado antes do Passo
16**, porque a `Whis-Daily` dispara às 13:55/10:25 e não pode apontar para uma daily pela
metade. Rode a tarefa inteira longe desses horários.

**Arquivos:**
- Criar: `tests/fixtures/daily.py`
- Modificar: `tests/conftest.py`
- Reescrever: `src/whis/daily.py`, `src/whis/nota_viva.py`, `tests/test_daily.py`, `tests/test_comando_daily.py`
- Modificar: `src/whis/vault.py`, `src/whis/resumo_dia_claude.py`, `src/whis/portas.py`, `src/whis/fakes.py`, `src/whis/configuracao.py`, `src/whis/palheta.py`, `src/whis/__main__.py`
- Apagar: `tests/test_roteiro_da_daily.py`, `tests/test_daily_do_trabalho.py`
- Ajustar: `tests/test_nota_viva.py`, `tests/test_palheta.py`, `tests/test_avisos_finais.py`, `tests/test_comando_codigos_de_saida.py`, `tests/test_login_do_claude.py`, `tests/test_daily_ativa.py`, `tests/test_prompts.py`, `tests/test_painel.py`, `tests/test_configuracao_escrita.py`, `tests/test_detalhe_longo_no_prompt.py`

- [ ] **Passo 1: a nota de exemplo e a fixture da publicação**

`tests/fixtures/daily.py`:

```python
"""A nota da daily como ele a escreve no Obsidian, ainda sem `## O que terminei`."""

from __future__ import annotations

from pathlib import Path

NOTA_DA_DAILY = (
    "---\n"
    "tipo: daily-atual\n"
    "---\n"
    "\n"
    "## O que eu fiz\n"
    "\n"
    "- FN-123 frete do checkout corrigido\n"
    "\t- subiu em produção\n"
    "\n"
    "## O que estou fazendo\n"
    "\n"
    "- FN-130 diário automático\n"
    "\n"
    "## Fazer\n"
    "\n"
    "- [ ] não vai para o deck\n"
    "\n"
    "## Dúvidas\n"
    "\n"
    "- quem revisa o PR do frete?\n"
    "\n"
    "## Pontos\n"
    "\n"
    "- também não vai\n"
    "\n"
    "## Falar\n"
    "\n"
    "- sexta eu saio mais cedo\n"
)


def escrever_nota_da_daily(vault: Path, texto: str = NOTA_DA_DAILY) -> Path:
    arquivo = Path(vault) / "daily" / "atual.md"
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_bytes(texto.encode("utf-8"))
    return arquivo
```

No fim de `tests/conftest.py`:

```python
@pytest.fixture(autouse=True)
def publicacao_do_deck(monkeypatch: pytest.MonkeyPatch):
    """Nenhum teste publica o deck da daily de verdade: `whis daily` e a bandeja caem neste fake."""
    from whis import __main__ as cli
    from whis.fakes import PublicacaoDoDeckFake

    fake = PublicacaoDoDeckFake()
    monkeypatch.setattr(cli, "montar_publicacao_do_deck", lambda _configuracao: fake)
    return fake
```

- [ ] **Passo 2: os testes novos da costura**

Substitua `tests/test_daily.py` inteiro por:

```python
"""A costura da daily: a nota que ele escreveu vira deck publicado e cópia em `daily/`."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from fixtures.daily import NOTA_DA_DAILY, escrever_nota_da_daily
from fixtures.leitura import corpo, ler_frontmatter
from whis import vault
from whis.configuracao import Configuracao
from whis.daily import gerar_daily
from whis.fakes import URL_DO_DECK_FAKE, PublicacaoDoDeckFake
from whis.nota_viva import MODELO_DA_NOTA_VIVA
from whis.portas import ErroDePublicacao

AGORA = datetime(2026, 9, 30, 13, 55, tzinfo=timezone(timedelta(hours=-3)))
ANTIGA = "https://claude.ai/artifact/DeckAntigo789"
NOVA = "https://claude.ai/artifact/DeckNovo456"


@pytest.fixture
def configuracao(caminho_do_vault: Path) -> Configuracao:
    return Configuracao(vault=caminho_do_vault)


def gerar(configuracao, publicacao, tmp_path: Path, **extras):
    return gerar_daily(AGORA, configuracao=configuracao, publicacao=publicacao, pasta=tmp_path / "trabalho", **extras)


def copia_de_hoje(caminho_do_vault: Path) -> Path:
    return caminho_do_vault / "daily" / "2026-09-30.md"


def semear(caminho_do_vault: Path, url: str, nome: str = "2026-09-29.md") -> None:
    texto = vault.montar_copia_da_daily(gerada=AGORA - timedelta(days=1), deck=url, secoes=[])
    (caminho_do_vault / "daily").mkdir(parents=True, exist_ok=True)
    (caminho_do_vault / "daily" / nome).write_text(texto, encoding="utf-8")


def test_a_nota_vira_deck_publicado_e_copia_com_o_link(configuracao, caminho_do_vault: Path, tmp_path: Path):
    escrever_nota_da_daily(caminho_do_vault)
    publicacao = PublicacaoDoDeckFake()

    resultado = gerar(configuracao, publicacao, tmp_path)

    assert resultado.publicado and resultado.url == URL_DO_DECK_FAKE
    assert [slide.id for slide in resultado.deck.slides] == ["fiz", "fazendo", "duvidas", "falar"]
    assert publicacao.url_recebida is None
    assert sorted(publicacao.conteudos) == [
        "project/deck.json",
        "project/slides/duvidas.html",
        "project/slides/falar.html",
        "project/slides/fazendo.html",
        "project/slides/fiz.html",
    ]
    assert json.loads(publicacao.conteudos["project/deck.json"])["order"] == ["fiz", "fazendo", "duvidas", "falar"]
    assert resultado.copia.resolve() == copia_de_hoje(caminho_do_vault).resolve()
    frente = ler_frontmatter(resultado.copia)
    assert frente["tipo"] == "daily" and frente["deck"] == URL_DO_DECK_FAKE and "data" not in frente


def test_a_copia_tem_so_as_secoes_que_viraram_slide_com_as_linhas_literais(
    configuracao, caminho_do_vault: Path, tmp_path: Path
):
    escrever_nota_da_daily(caminho_do_vault)

    resultado = gerar(configuracao, PublicacaoDoDeckFake(), tmp_path)

    texto = corpo(resultado.copia)
    assert "## O que eu fiz\n\n- FN-123 frete do checkout corrigido\n\t- subiu em produção\n" in texto
    for fora in ("## Pontos", "## Fazer", "## O que terminei"):
        assert fora not in texto


def test_republica_no_endereco_da_copia_mais_recente_que_tem_um(configuracao, caminho_do_vault: Path, tmp_path: Path):
    escrever_nota_da_daily(caminho_do_vault)
    semear(caminho_do_vault, ANTIGA, "2026-09-28.md")
    (caminho_do_vault / "daily" / "2026-09-29.md").write_text(
        "---\ntipo: daily\ndesde: 2026-09-28T13:55:00-03:00\n---\n\n# Daily velha\n", encoding="utf-8"
    )
    publicacao = PublicacaoDoDeckFake()

    resultado = gerar(configuracao, publicacao, tmp_path)

    assert publicacao.url_recebida == ANTIGA
    assert resultado.url == ANTIGA
    assert ler_frontmatter(resultado.copia)["deck"] == ANTIGA


def test_nota_sem_o_que_terminei_ganha_o_titulo_e_nada_mais_muda(configuracao, caminho_do_vault: Path, tmp_path: Path):
    arquivo = escrever_nota_da_daily(caminho_do_vault)

    gerar(configuracao, PublicacaoDoDeckFake(), tmp_path)
    gerar(configuracao, PublicacaoDoDeckFake(), tmp_path)

    texto = arquivo.read_bytes().decode("utf-8")
    assert texto.count("## O que terminei") == 1
    assert "- FN-130 diário automático\n\n## O que terminei\n\n## Fazer\n" in texto
    assert texto.replace("## O que terminei\n\n", "", 1) == NOTA_DA_DAILY


def test_simular_nao_publica_nem_escreve_nada_nem_o_titulo(configuracao, caminho_do_vault: Path, tmp_path: Path):
    arquivo = escrever_nota_da_daily(caminho_do_vault)

    resultado = gerar_daily(AGORA, configuracao=configuracao, publicacao=None, simular=True)

    assert resultado.simulado and len(resultado.deck.slides) == 4
    assert arquivo.read_bytes().decode("utf-8") == NOTA_DA_DAILY
    assert sorted(p.name for p in (caminho_do_vault / "daily").iterdir()) == ["atual.md"]


def test_nota_vazia_nao_publica_nem_grava_copia_mas_ganha_o_titulo(configuracao, caminho_do_vault: Path, tmp_path: Path):
    arquivo = escrever_nota_da_daily(caminho_do_vault, "---\ntipo: daily-atual\n---\n\n## O que eu fiz\n\n## Falar\n")
    publicacao = PublicacaoDoDeckFake()

    resultado = gerar(configuracao, publicacao, tmp_path)

    assert resultado.vazio and publicacao.chamadas == 0
    assert not copia_de_hoje(caminho_do_vault).exists()
    assert "## O que terminei" in arquivo.read_text(encoding="utf-8")


def test_sem_nota_nenhuma_grava_o_modelo_e_nao_publica(configuracao, caminho_do_vault: Path, tmp_path: Path):
    resultado = gerar(configuracao, PublicacaoDoDeckFake(), tmp_path)

    assert resultado.vazio
    assert (caminho_do_vault / "daily" / "atual.md").read_bytes().decode("utf-8") == MODELO_DA_NOTA_VIVA


def test_falha_da_publicacao_grava_a_copia_com_aviso_e_o_endereco_antigo(
    configuracao, caminho_do_vault: Path, tmp_path: Path
):
    escrever_nota_da_daily(caminho_do_vault)
    semear(caminho_do_vault, ANTIGA)

    resultado = gerar(configuracao, PublicacaoDoDeckFake(erro=ErroDePublicacao("o Claude caiu")), tmp_path)

    assert not resultado.publicado and resultado.falha_da_publicacao == "o Claude caiu"
    assert ler_frontmatter(resultado.copia)["deck"] == ANTIGA
    assert "> [!warning] Os slides não saíram nesta geração: o Claude caiu" in corpo(resultado.copia)


def test_falha_depois_de_criar_guarda_o_endereco_criado(configuracao, caminho_do_vault: Path, tmp_path: Path):
    escrever_nota_da_daily(caminho_do_vault)

    resultado = gerar(configuracao, PublicacaoDoDeckFake(erro=ErroDePublicacao("preencher falhou", url=NOVA)), tmp_path)

    assert resultado.url == NOVA
    assert ler_frontmatter(resultado.copia)["deck"] == NOVA


def test_falha_sem_deck_nenhum_grava_a_copia_sem_deck(configuracao, caminho_do_vault: Path, tmp_path: Path):
    escrever_nota_da_daily(caminho_do_vault)

    resultado = gerar(configuracao, PublicacaoDoDeckFake(erro=ErroDePublicacao("sem conta")), tmp_path)

    assert resultado.url is None
    assert "deck" not in ler_frontmatter(resultado.copia)


def test_fora_da_simulacao_a_publicacao_e_obrigatoria(configuracao):
    with pytest.raises(ValueError):
        gerar_daily(AGORA, configuracao=configuracao, publicacao=None)
```

- [ ] **Passo 3: os testes novos do subcomando**

Substitua `tests/test_comando_daily.py` inteiro por:

```python
"""O subcomando `whis daily`: a nota dele vira slides no link de sempre.

O que o comando imprime e o toast são comportamento: os testes leem a saída
do terminal e o aviso. A publicação é o fake autouse do `conftest`.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest

from fixtures.daily import NOTA_DA_DAILY, escrever_nota_da_daily
from fixtures.leitura import arquivos_do_vault, ler_frontmatter
from whis import __main__ as cli
from whis import vault as modulo_vault
from whis.__main__ import SAIDA_COMPLETA, SAIDA_PARCIAL, main
from whis.fakes import URL_DO_DECK_FAKE, PublicacaoDoDeckFake
from whis.portas import ErroDePublicacao


def nota_viva(vault: Path) -> Path:
    return vault / "daily" / "atual.md"


def copia_de_hoje(vault: Path) -> Path:
    return vault / "daily" / f"{date.today().isoformat()}.md"


def test_daily_publica_imprime_os_slides_e_o_link_e_sai_com_zero(
    configuracao_do_diario, caminho_do_vault: Path, publicacao_do_deck, toasts, capsys: pytest.CaptureFixture
):
    configuracao_do_diario()
    escrever_nota_da_daily(caminho_do_vault)

    codigo = main(["daily"])

    saida = capsys.readouterr().out
    assert codigo == SAIDA_COMPLETA
    assert publicacao_do_deck.chamadas == 1
    assert "O que eu fiz:\n  FN-123 frete do checkout corrigido\n    subiu em produção\n" in saida
    assert f"Slides: {URL_DO_DECK_FAKE}" in saida
    assert toasts[-1] == ("A daily está pronta", "4 slides no link de sempre.", ("Abrir slides", URL_DO_DECK_FAKE))
    assert ler_frontmatter(copia_de_hoje(caminho_do_vault))["deck"] == URL_DO_DECK_FAKE


@pytest.mark.parametrize("bandeira", ["--fakes", "--simular"])
def test_fakes_e_simular_mostram_os_slides_sem_publicar_escrever_ou_avisar(
    bandeira: str, configuracao_do_diario, caminho_do_vault: Path, publicacao_do_deck, toasts, capsys
):
    configuracao_do_diario()
    arquivo = escrever_nota_da_daily(caminho_do_vault)

    codigo = main(["daily", bandeira])

    saida = capsys.readouterr().out
    assert codigo == SAIDA_COMPLETA
    assert publicacao_do_deck.chamadas == 0
    assert arquivo.read_bytes().decode("utf-8") == NOTA_DA_DAILY
    assert arquivos_do_vault(caminho_do_vault) == {"daily/atual.md"}
    assert toasts == []
    assert "Simulação" in saida and "Dúvidas:" in saida


def test_nota_vazia_sai_com_zero_e_o_toast_pede_para_escrever(
    configuracao_do_diario, caminho_do_vault: Path, publicacao_do_deck, toasts
):
    configuracao_do_diario()

    codigo = main(["daily"])

    assert codigo == SAIDA_COMPLETA
    assert publicacao_do_deck.chamadas == 0
    titulo, _texto, botao = toasts[-1]
    assert titulo == "A nota da daily está vazia"
    assert botao[0] == "Abrir no Obsidian"
    assert nota_viva(caminho_do_vault).is_file()
    assert not copia_de_hoje(caminho_do_vault).exists()


def test_publicacao_que_falha_sai_parcial_grava_a_copia_e_o_toast_abre_a_nota(
    configuracao_do_diario, caminho_do_vault: Path, monkeypatch, toasts
):
    configuracao_do_diario()
    escrever_nota_da_daily(caminho_do_vault)
    monkeypatch.setattr(
        cli,
        "montar_publicacao_do_deck",
        lambda _c: PublicacaoDoDeckFake(erro=ErroDePublicacao("o Claude caiu")),
    )

    codigo = main(["daily"])

    assert codigo == SAIDA_PARCIAL
    titulo, texto, botao = toasts[-1]
    assert titulo == "A daily não publicou" and "o Claude caiu" in texto
    assert botao[0] == "Abrir no Obsidian"
    assert copia_de_hoje(caminho_do_vault).is_file()


def test_comando_daily_deixa_rastro_no_arquivo_de_log(configuracao_do_diario, caminho_do_vault: Path):
    configuracao = configuracao_do_diario()
    escrever_nota_da_daily(caminho_do_vault)

    main(["daily"])

    log = configuracao.origem.parent / "bandeja.log"
    assert "Daily de" in log.read_text(encoding="utf-8")


# -- --anotar: o único gesto do agente numa seção do usuário -----------------


def test_anotar_faz_a_nota_viva_nascer_do_modelo_com_a_linha_em_pontos(
    configuracao_do_diario, caminho_do_vault: Path, capsys: pytest.CaptureFixture
):
    configuracao_do_diario()

    codigo = main(["daily", "--anotar", "quero puxar a retenção de 180 dias"])

    texto = nota_viva(caminho_do_vault).read_text(encoding="utf-8")
    assert codigo == 0
    assert texto.startswith("---\ntipo: daily-atual\n---\n")
    assert texto.endswith("## Pontos\n- quero puxar a retenção de 180 dias\n\n## Falar\n")
    assert "Anotado em" in capsys.readouterr().out


def test_anotar_so_acrescenta_em_pontos_e_nao_muda_nenhum_outro_byte(configuracao_do_diario, caminho_do_vault: Path):
    configuracao_do_diario()
    modulo_vault.preparar(caminho_do_vault)
    original = (
        "---\ntipo: daily-atual\n---\n\n"
        "## O que eu fiz\n\n1. Planejei o pix \n\n"
        "## O que estou fazendo\n\n1. Correções do ribeiro\n\t1. FN-1786 \n\n"
        "## Dúvidas\n\n- uma dúvida minha\n\n"
        "## Pontos\n\n- ponto antigo\n\n"
        "## Falar\n\n- avisar da folga\n\n"
    )
    nota_viva(caminho_do_vault).write_bytes(original.encode("utf-8"))
    hash_do_original = hashlib.sha256(original.encode("utf-8")).hexdigest()

    main(["daily", "--anotar", "ponto novo"])

    texto = nota_viva(caminho_do_vault).read_bytes().decode("utf-8")
    assert texto.count("- ponto novo\n") == 1
    assert hashlib.sha256(texto.replace("- ponto novo\n", "", 1).encode("utf-8")).hexdigest() == hash_do_original
    assert "## Pontos\n\n- ponto antigo\n- ponto novo\n\n## Falar\n\n- avisar da folga\n\n" in texto


def test_anotar_nao_publica_nem_escreve_copia(configuracao_do_diario, caminho_do_vault: Path, publicacao_do_deck):
    configuracao_do_diario()
    modulo_vault.preparar(caminho_do_vault)
    antes = arquivos_do_vault(caminho_do_vault)

    main(["daily", "--anotar", "um ponto"])

    assert arquivos_do_vault(caminho_do_vault) - antes == {"daily/atual.md"}
    assert publicacao_do_deck.chamadas == 0


def test_o_ponto_anotado_fica_na_nota_e_fora_do_deck(configuracao_do_diario, caminho_do_vault: Path, publicacao_do_deck):
    configuracao_do_diario()
    escrever_nota_da_daily(caminho_do_vault)
    main(["daily", "--anotar", "combinar a retenção de 180 dias"])

    main(["daily"])

    assert "- também não vai\n- combinar a retenção de 180 dias\n" in nota_viva(caminho_do_vault).read_text(encoding="utf-8")
    assert publicacao_do_deck.chamadas == 1
    assert all("combinar a retenção" not in conteudo for conteudo in publicacao_do_deck.conteudos.values())


def test_anotar_vazio_e_recusado(configuracao_do_diario, caminho_do_vault: Path, caplog: pytest.LogCaptureFixture):
    configuracao_do_diario()

    codigo = main(["daily", "--anotar", "   "])

    assert codigo == 1
    assert "--anotar precisa de um texto" in caplog.text
    assert not nota_viva(caminho_do_vault).exists()
```

- [ ] **Passo 4: rodar e ver falhar**

Rode: `.venv/Scripts/python.exe -m pytest tests/test_daily.py tests/test_comando_daily.py -v`
Esperado: FAIL. Os testes novos chamam `gerar_daily(..., publicacao=...)`, que a daily velha
não aceita (`TypeError`), e o `whis daily` velho não chama `montar_publicacao_do_deck`.

- [ ] **Passo 5: reescrever `src/whis/nota_viva.py`**

Substitua o arquivo inteiro. O que fica é a leitura, `anotar` e a abertura de seção. Saem
`aplicar`, `mover`, `arquivar_fiz`, `itens`, `com_ids`, `id_de`, `Item`, `Mudancas`, os ids e
`SECOES_DO_AGENTE`.

```python
"""A nota viva `daily/atual.md`: o texto que ele escreve e de onde sai a daily.

Este módulo só conhece texto. Ele lê a nota como uma sequência de linhas, acha
as sete seções e as linhas dentro delas, e faz as duas únicas escritas do
agente ali: **anotar** uma linha em *Pontos*, *Dúvidas* ou *Fazer* a pedido
dele (`note`, `doubt`, `do`) e **abrir** o título de uma seção que falte. O
resto da nota é dele; quem a lê para o deck é `deck.py`, e quem lê e grava o
arquivo é `vault.py`.

A regra que governa tudo aqui: cada linha que já está na nota sai **byte a
byte** igual — inclusive os espaços à direita, as linhas em branco dentro de
uma seção e a indentação por tab. Por isso a nota é guardada como linhas cruas
e toda edição é a inserção de linhas inteiras, nunca a reescrita de uma.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

TIPO_NOTA_VIVA = "daily-atual"

SECAO_FIZ = "O que eu fiz"
SECAO_FAZENDO = "O que estou fazendo"
SECAO_TERMINEI = "O que terminei"
SECAO_FAZER = "Fazer"
SECAO_DUVIDAS = "Dúvidas"
SECAO_PONTOS = "Pontos"
SECAO_FALAR = "Falar"

SECOES = (
    SECAO_FIZ,
    SECAO_FAZENDO,
    SECAO_TERMINEI,
    SECAO_FAZER,
    SECAO_DUVIDAS,
    SECAO_PONTOS,
    SECAO_FALAR,
)

SECOES_ANOTAVEIS = (SECAO_PONTOS, SECAO_DUVIDAS, SECAO_FAZER)

SECOES_COM_CAIXA = (SECAO_FAZER,)

CAIXA = "[ ] "

#: Só o frontmatter e os títulos: ele sabe o que cada seção é (ticket 13).
MODELO_DA_NOTA_VIVA = f"""\
---
tipo: {TIPO_NOTA_VIVA}
---

## O que eu fiz

## O que estou fazendo

## O que terminei

## Fazer

## Dúvidas

## Pontos

## Falar
"""

_ITEM = re.compile(r"^(?P<indentacao>[ \t]*)(?P<marcador>[-*+]|\d+[.)])[ \t]+(?P<texto>.*)$")

#: Um marcador sem texto (`-`, `1.`): o item vazio que o Obsidian deixa ao dar Enter.
_SO_MARCADOR = re.compile(r"^[ \t]*([-*+]|\d+[.)])[ \t]*$")

#: Só `#` e `##` delimitam seção; `###` fica dentro dela.
_TITULO = re.compile(r"^#{1,2}[ \t]+(?P<titulo>.*?)[ \t]*$")

_TAB = 4


@dataclass
class _Bloco:
    titulo: str | None
    linhas: list[str]


class NotaViva:
    """A nota viva como texto editável, guardada linha a linha.

    A quebra de linha do arquivo é detectada e devolvida como veio, para o
    Obsidian e o hash não verem diferença.
    """

    def __init__(self, linhas: Sequence[str], quebra: str = "\n") -> None:
        self._quebra = quebra
        self._blocos = _blocos(list(linhas))

    @classmethod
    def de_texto(cls, texto: str) -> NotaViva:
        quebra = "\r\n" if "\r\n" in texto else "\n"
        return cls(texto.replace("\r\n", "\n").split("\n"), quebra)

    @classmethod
    def do_modelo(cls) -> NotaViva:
        return cls.de_texto(MODELO_DA_NOTA_VIVA)

    def texto(self) -> str:
        return self._quebra.join(linha for bloco in self._blocos for linha in bloco.linhas)

    def tem_secao(self, titulo: str) -> bool:
        return self._bloco(titulo) is not None

    def conteudo(self, titulo: str) -> tuple[str, ...]:
        """As linhas de uma seção, sem as em branco das pontas. `()` se não existe."""
        bloco = self._bloco(titulo)
        return sem_brancos_nas_pontas(_corpo(bloco)) if bloco else ()

    def secoes(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        return tuple((secao, self.conteudo(secao)) for secao in SECOES)

    def acrescentar(self, titulo: str, texto: str) -> tuple[str, ...]:
        """`- texto` no fim de uma seção, aberta no lugar dela se faltar."""
        bloco = self._bloco(titulo) or self._abrir_secao(titulo)
        item_novo = f"- {texto.strip()}"
        bloco.linhas.insert(1 + _fim_do_conteudo(_corpo(bloco)), item_novo)
        return (item_novo,)

    def garantir_secao(self, titulo: str) -> bool:
        """Abre `## titulo` vazio no lugar dele, se faltar. `True` quando abriu."""
        if self._bloco(titulo) is not None:
            return False
        self._abrir_secao(titulo)
        return True

    def anotar(self, texto: str, secao: str = SECAO_PONTOS) -> str:
        """`- texto` no fim de *Pontos*, *Dúvidas* ou *Fazer*, a pedido dele.

        Em *Fazer* o item nasce `- [ ] texto`: a caixa é dele, e marcá-la é o
        gesto que fecha a tarefa. O agente nunca mais volta nessa linha.
        """
        if _chave(secao) not in {_chave(anotavel) for anotavel in SECOES_ANOTAVEIS}:
            raise ValueError(f"Só se anota em {' ou '.join(SECOES_ANOTAVEIS)}; {secao!r} não tem comando.")
        com_caixa = _chave(secao) in {_chave(secao_marcavel) for secao_marcavel in SECOES_COM_CAIXA}
        return self.acrescentar(secao, f"{CAIXA}{texto.strip()}" if com_caixa else texto)[0]

    def _bloco(self, titulo: str) -> _Bloco | None:
        chave = _chave(titulo)
        for bloco in self._blocos:
            if bloco.titulo is not None and _chave(bloco.titulo) == chave:
                return bloco
        return None

    def _abrir_secao(self, titulo: str) -> _Bloco:
        """Uma seção nova no lugar dela na ordem das sete; no fim, se nenhuma vem depois.

        Só linhas inteiras entram: uma em branco antes do título, quando a seção
        anterior não a tem.
        """
        seguinte = self._bloco_seguinte(titulo)
        if seguinte is not None:
            posicao = self._blocos.index(seguinte)
            anterior = self._blocos[posicao - 1].linhas
            if anterior and anterior[-1] != "":
                anterior.append("")
            bloco = _Bloco(titulo, [f"## {titulo}", ""])
            self._blocos.insert(posicao, bloco)
            return bloco

        ultimo = self._blocos[-1].linhas
        termina_em_quebra = bool(ultimo) and ultimo[-1] == ""
        if termina_em_quebra:
            ultimo.pop()
        if ultimo and ultimo[-1] != "":
            ultimo.append("")
        bloco = _Bloco(titulo, [f"## {titulo}", ""] if termina_em_quebra else [f"## {titulo}"])
        self._blocos.append(bloco)
        return bloco

    def _bloco_seguinte(self, titulo: str) -> _Bloco | None:
        ordem = [_chave(secao) for secao in SECOES]
        if _chave(titulo) not in ordem:
            return None
        for secao in SECOES[ordem.index(_chave(titulo)) + 1 :]:
            bloco = self._bloco(secao)
            if bloco is not None:
                return bloco
        return None


def _blocos(linhas: list[str]) -> list[_Bloco]:
    blocos = [_Bloco(None, [])]
    for linha in linhas:
        titulo = _TITULO.match(linha)
        if titulo is not None:
            blocos.append(_Bloco(titulo["titulo"], []))
        blocos[-1].linhas.append(linha)
    return blocos


def _corpo(bloco: _Bloco) -> list[str]:
    return bloco.linhas[1:] if bloco.titulo is not None else bloco.linhas


def _fim_do_conteudo(corpo: Sequence[str]) -> int:
    for indice in range(len(corpo) - 1, -1, -1):
        if corpo[indice].strip():
            return indice + 1
    return 0


def _nivel(linha: str) -> int:
    indentacao = linha[: len(linha) - len(linha.lstrip(" \t"))]
    return len(indentacao.expandtabs(_TAB))


def texto_e_profundidade(linhas: Sequence[str]) -> tuple[tuple[str, int], ...]:
    """Cada linha com texto como `(texto, profundidade)`, para quem só lê a seção.

    O texto vem sem o marcador de lista e sem o recuo; uma linha que não é item
    entra inteira. A profundidade conta as linhas abertas acima dela, pela
    mesma régua de recuo de `_nivel` (tab = 4 colunas).
    """
    resultado: list[tuple[str, int]] = []
    colunas: list[int] = []
    for linha in linhas:
        if _SO_MARCADOR.match(linha):
            continue
        partes = _ITEM.match(linha)
        texto = (partes["texto"] if partes else linha).strip()
        if not texto:
            continue
        coluna = _nivel(linha)
        while colunas and colunas[-1] >= coluna:
            colunas.pop()
        resultado.append((texto, len(colunas)))
        colunas.append(coluna)
    return tuple(resultado)


def sem_brancos_nas_pontas(linhas: Sequence[str]) -> tuple[str, ...]:
    inicio, fim = 0, len(linhas)
    while inicio < fim and not linhas[inicio].strip():
        inicio += 1
    while fim > inicio and not linhas[fim - 1].strip():
        fim -= 1
    return tuple(linhas[inicio:fim])


def _chave(titulo: str) -> str:
    """`O que eu fiz `, `o que eu FIZ` e `Duvidas`/`Dúvidas` são a mesma seção."""
    decomposto = unicodedata.normalize("NFKD", titulo)
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())
```

- [ ] **Passo 6: ajustar `tests/test_nota_viva.py`**

- Docstring do módulo: troque a última frase por "a única coisa que o agente faz é anotar a
  pedido e abrir um título que falte."
- Imports: tire `id_do_item` e a linha `from whis.portas import Daily, ItemNovo`; acrescente
  `SECAO_TERMINEI` ao import de `whis.nota_viva`.
- Apague estas funções inteiras:
  - `test_os_itens_de_uma_secao_vem_com_a_subarvore_e_os_ancestrais`
  - `test_o_id_e_estavel_e_nao_depende_da_posicao`
  - `test_dois_itens_com_o_mesmo_texto_ganham_ids_diferentes`
  - `test_as_secoes_do_usuario_nao_tem_id`
  - `test_mover_leva_a_linha_e_a_subarvore_byte_a_byte_e_tira_de_fazendo`
  - `test_mover_nao_duplica_um_ancestral_que_ja_esta_em_fiz`
  - `test_mover_um_item_de_primeiro_nivel_vai_para_o_fim_de_fiz`
  - `test_mover_id_inexistente_ou_ja_em_fiz_nao_muda_nada`
  - `test_mover_aceita_o_id_como_o_modelo_copia_da_pergunta`
  - `test_acrescentar_sob_um_item_entra_como_ultimo_filho_com_a_indentacao_dos_irmaos`
  - `test_acrescentar_sob_um_item_sem_filhos_indenta_um_nivel_a_mais`
  - `test_acrescentar_em_fiz_sob_um_grupo_de_fazendo_copia_o_cabecalho_literal`
  - `test_o_que_ele_marcou_a_mao_em_fazer_fica_como_esta_quando_a_janela_vira`
  - `test_arquivar_fiz_devolve_o_bloco_literal_e_recomeca_a_secao`
  - `test_aplicar_faz_os_movimentos_antes_dos_acrescimos_e_nao_toca_o_resto`
  - `test_aplicar_nao_repete_texto_que_ja_esta_na_nota`
  - `test_aplicar_monta_um_grupo_com_sub_itens_numa_resposta_so`
  - `test_aplicar_ignora_pai_inexistente_e_ainda_acrescenta_o_item`
- Troque `test_o_modelo_tem_as_seis_secoes_na_ordem_e_nenhuma_explicacao` por:

```python
def test_o_modelo_tem_as_sete_secoes_na_ordem_e_nenhuma_explicacao():
    """Ele sabe o que cada seção é (ticket 13): só o frontmatter e os títulos."""
    nota = NotaViva.do_modelo()

    assert [secao for secao, _ in nota.secoes()] == [
        SECAO_FIZ,
        SECAO_FAZENDO,
        SECAO_TERMINEI,
        SECAO_FAZER,
        SECAO_DUVIDAS,
        SECAO_PONTOS,
        SECAO_FALAR,
    ]
    assert all(linhas == () for _, linhas in nota.secoes())
    assert MODELO_DA_NOTA_VIVA.startswith("---\ntipo: daily-atual\n---\n")
    assert "\ndata:" not in MODELO_DA_NOTA_VIVA, "campo `data` vira link da Daily notes do Obsidian"
    assert ">" not in MODELO_DA_NOTA_VIVA
    assert [linha for linha in MODELO_DA_NOTA_VIVA.splitlines() if linha and not linha.startswith(("##", "---", "tipo:"))] == []
```

- Acrescente no fim:

```python
def test_garantir_secao_abre_o_titulo_que_falta_no_lugar_dele_uma_vez_so():
    nota = NotaViva.de_texto(NOTA)

    assert nota.garantir_secao(SECAO_TERMINEI) is True
    assert nota.garantir_secao(SECAO_TERMINEI) is False

    texto = nota.texto()
    assert texto.count("## O que terminei") == 1
    assert texto.replace("## O que terminei\n\n", "", 1) == NOTA
    assert texto.index("## O que estou fazendo") < texto.index("## O que terminei") < texto.index("## Dúvidas")
```

- [ ] **Passo 7: reescrever `src/whis/daily.py`**

Substitua o arquivo inteiro:

```python
"""A costura da daily: `daily/atual.md` → deck no Claude Slides + cópia em `daily/`.

Ele escreve a nota pelo Obsidian; o Whis não escreve nada nela além do título
de seção que faltar. A geração lê as seções, monta o deck (`deck.py`), escreve
os arquivos do tipo Slides numa pasta de trabalho (`slides_do_deck.py`),
publica sempre no mesmo endereço e grava `daily/YYYY-MM-DD.md` com o que foi
para o deck e o link. O endereço mora no frontmatter dessa cópia: o vault é a
fonte da verdade, como no jornal.

Falhar na publicação não custa a cópia: ela nasce com o aviso e com o endereço
que já existia (ou o recém-criado), para a geração seguinte republicar no
mesmo link.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from . import vault as _vault
from .configuracao import Configuracao
from .deck import Deck, montar_deck
from .nota_viva import SECAO_TERMINEI
from .portas import ErroDePublicacao, Medida, PortaPublicacaoDoDeck
from .slides_do_deck import slides_do_deck

_log = logging.getLogger("whis.daily")


@dataclass(frozen=True)
class ResultadoDaDaily:
    data: date
    deck: Deck
    url: str | None = None
    publicado: bool = False
    copia: Path | None = None
    falha_da_publicacao: str | None = None
    medida: Medida | None = None
    vazio: bool = False
    simulado: bool = False


def gerar_daily(
    agora: datetime,
    *,
    configuracao: Configuracao,
    publicacao: PortaPublicacaoDoDeck | None,
    simular: bool = False,
    pasta: Path | None = None,
) -> ResultadoDaDaily:
    """Publica o deck da nota e grava a cópia; `simular` só monta o deck.

    Gerar de novo no mesmo dia republica no mesmo endereço e reescreve a cópia
    daquele dia. Nota vazia não publica nem grava cópia.
    """
    hoje = agora.date()
    nota = _vault.ler_nota_viva(configuracao.vault)
    deck = montar_deck(nota)
    _log.info("Daily de %s: %d slide(s) da nota.", hoje.isoformat(), len(deck.slides))

    if simular:
        _log.info("Simulação — nada publicado nem gravado.")
        return ResultadoDaDaily(data=hoje, deck=deck, vazio=deck.vazio(), simulado=True)
    if publicacao is None:
        raise ValueError("Fora da simulação, gerar_daily precisa da publicação do deck.")

    raiz = _vault.preparar(configuracao.vault)
    existia = (raiz / _vault.CAMINHO_DA_NOTA_VIVA).is_file()
    if nota.garantir_secao(SECAO_TERMINEI) or not existia:
        _vault.escrever_nota_viva(raiz, nota)
        _log.info("Nota viva gravada com '## %s'.", SECAO_TERMINEI)

    if deck.vazio():
        _log.info("A nota da daily está vazia — nada publicado.")
        return ResultadoDaDaily(data=hoje, deck=deck, vazio=True)

    trabalho = Path(pasta) if pasta else Path(tempfile.mkdtemp(prefix=f"whis-daily-{hoje.isoformat()}-"))
    arquivos = slides_do_deck(deck, hoje, agora=agora)
    for caminho, conteudo in arquivos.items():
        destino = trabalho / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo, encoding="utf-8", newline="\n")

    url_atual = _vault.ultimo_deck(raiz)
    url, publicado, falha, medida = url_atual, False, None, None
    try:
        feita = publicacao.publicar(trabalho, tuple(sorted(arquivos)), url_atual)
        url, publicado, medida = feita.url, True, feita.medida
        _log.info("Slides publicados em %s.", url)
    except ErroDePublicacao as erro:
        falha = str(erro)
        url = erro.url or url_atual
        _log.error("Os slides não saíram: %s", erro)

    copia = _vault.escrever(
        raiz,
        _vault.caminho_da_daily(hoje),
        _vault.montar_copia_da_daily(
            gerada=agora,
            deck=url,
            secoes=[(secao.titulo, secao.linhas) for secao in deck.secoes],
            aviso=f"Os slides não saíram nesta geração: {falha}" if falha else None,
        ),
        zonas=_vault.ZONAS_DA_DAILY,
    )
    return ResultadoDaDaily(
        data=hoje,
        deck=deck,
        url=url,
        publicado=publicado,
        copia=copia,
        falha_da_publicacao=falha,
        medida=medida,
    )
```

- [ ] **Passo 8: tirar a daily velha de `vault.py`**

- Apague as funções `ate_da_daily_anterior`, `desde_da_daily_de`, `arquivo_da_nota_viva`,
  `montar_daily`, `_secao_das_mudancas`, `_alinhado`, `cobertura_da_janela`,
  `_avisos_da_daily`, `_temas_dos_eventos`, `_momento_do_frontmatter` e `_dia_curto`.
- Apague as constantes `SECAO_MUDANCAS` e `SECAO_ARQUIVO`.
- Fica `_data_do_nome`, que `ultimo_deck` usa.
- No `from .nota_viva import (...)`, tire `SECAO_FAZENDO`, `SECAO_FIZ`, `Mudancas` e
  `sem_brancos_nas_pontas`. Ficam `SECAO_DUVIDAS`, `SECAO_FALAR` e `SECAO_PONTOS`, que outros
  módulos leem por `vault.`, e `NotaViva`.
- No bloco `if TYPE_CHECKING:`, tire `from .daily import JanelaDaDaily`.
- Docstring do módulo: troque "o da daily, só em `daily/`" por "o da daily, só em `daily/`
  (a cópia datada e, a pedido, a nota viva)", e a frase sobre a nota viva por "A nota viva
  `daily/atual.md` mora em `daily/` e é dele; o que o agente pode escrever nela é decidido em
  `nota_viva.py`".

Confira com `grep -n "Mudancas\|JanelaDaDaily\|_momento_do_frontmatter\|_dia_curto\|SECAO_FIZ\|SECAO_FAZENDO" src/whis/vault.py`.
Esperado: nada.

- [ ] **Passo 9: tirar a daily de `resumo_dia_claude.py`, `portas.py` e `fakes.py`**

`resumo_dia_claude.py`:
- Apague `PROMPT_DA_DAILY`, o método `resumir_daily`, o método `_recusar_periodo_longo`, o
  parâmetro e o atributo `contexto_do_time` de `__init__` (com o comentário dele), e as funções
  `montar_pergunta_da_daily`, `_linhas_da_nota_viva`, `interpretar_daily` e `_itens_novos`.
- Imports: tire a linha de `.nota_viva`; em `.portas`, deixe só `ErroDeResumoDoDia` e
  `ResumoDoDia`.
- Docstring do módulo: tire o item de `resumir_daily` e diga que o adaptador responde só ao
  diário. Na docstring da classe, tire "e da daily" e "ou `ErroDeDaily` (daily)".
- Rode `grep -n "Iterable\|Sequence\|json\." src/whis/resumo_dia_claude.py` e tire do import o
  que ficou sem uso.

`portas.py`:
- Apague `ItemNovo`, `Daily`, `ErroDeDaily`, `PortaDaily` e o bloco
  `if TYPE_CHECKING: from .nota_viva import NotaViva`.
- Tire `TYPE_CHECKING` do `from typing import` se ficar sem uso.
- Docstring do módulo: "o resumo do dia, a publicação do deck da daily e as três do jornal".

`fakes.py`:
- Apague `ITEM_ABERTO_DE_EXEMPLO`, `DAILY_PADRAO`, `FonteDaJanela`, `fontes_de_exemplo_da_daily`
  e `DailyFake`.
- Imports: tire `NotaViva, id_do_item`, `Daily`, `ItemNovo` e o que ficar sem uso (`replace`,
  se só `FonteDaJanela` o usava).
- Docstring: "As exceções são `ResumoDoDiaFake` e `BuscaFake`".

- [ ] **Passo 10: tirar as duas chaves de `configuracao.py`**

- No `MODELO_DE_CONFIGURACAO`, apague as linhas `referencias_pessoais = []  …` e
  `contexto_do_time = ""  …` de `[daily]`.
- Em `CHAVES`, apague as duas `Chave("daily", "referencias_pessoais", …)` e
  `Chave("daily", "contexto_do_time", …)`.
- Na dataclass `Configuracao`, apague `daily_referencias_pessoais` e `daily_contexto_do_time`, e
  o parágrafo da docstring que começa em "`daily_referencias_pessoais` vazia significa".
- Em `carregar_texto`, apague as duas linhas `daily_referencias_pessoais=` e
  `daily_contexto_do_time=`.

- [ ] **Passo 11: `palheta.py`**

Imports:
- tire `from .fontes import PortaFonte`, se ficar sem uso (`grep -n PortaFonte src/whis/palheta.py`);
- troque `from .portas import PortaDaily` por `from .portas import PortaPublicacaoDoDeck`.

Constantes: troque `TITULO_DA_DAILY_QUE_NAO_NASCEU = "A daily não nasceu"` por:

```python
TITULO_DA_DAILY_VAZIA = "A nota da daily está vazia"
TITULO_DA_DAILY_SEM_SLIDES = "A daily não publicou"
TITULO_DA_DAILY_SIMULADA = "Simulação da daily"
ROTULO_DO_BOTAO_DOS_SLIDES = "Abrir slides"
```

`Resultado` ganha o rótulo:

```python
@dataclass(frozen=True)
class Resultado:
    """O que um comando devolve, e que a palheta transforma no toast.

    `nota` é o caminho relativo ao vault da nota que o botão abre; `link`,
    quando há, é um endereço `https://` que o botão abre no lugar dela, com o
    texto de `rotulo` (sem ele, *Abrir jornal*). Sem `nota` e sem `link`, o
    toast não tem botão.
    """

    titulo: str
    texto: str
    nota: str | None = None
    link: str | None = None
    rotulo: str | None = None
```

Em `avisar_resultado`, troque `botao = (ROTULO_DO_BOTAO_DO_JORNAL, resultado.link)` por:

```python
        botao = (resultado.rotulo or ROTULO_DO_BOTAO_DO_JORNAL, resultado.link)
```

Apague `texto_do_toast_da_daily` e troque `resultado_da_daily` por:

```python
def resultado_da_daily(resultado: ResultadoDaDaily) -> Resultado:
    """O toast da daily — o mesmo para `whis daily` e para a palheta."""
    quantos = len(resultado.deck.slides)
    slides = f"{quantos} slide{'s' if quantos != 1 else ''}"
    if resultado.simulado:
        return Resultado(TITULO_DA_DAILY_SIMULADA, f"Simulação: {slides}, nada publicado.")
    if resultado.vazio:
        return Resultado(
            TITULO_DA_DAILY_VAZIA,
            "Escreva o que fez, está fazendo e terminou, e gere de novo.",
            nota=_vault.CAMINHO_DA_NOTA_VIVA,
        )
    if not resultado.publicado:
        if _login.vencido(resultado.falha_da_publicacao):
            return Resultado(
                _login.TITULO,
                f"{_login.PEDIDO} Os slides não saíram; leia de {_vault.CAMINHO_DA_NOTA_VIVA}.",
                nota=_vault.CAMINHO_DA_NOTA_VIVA,
            )
        return Resultado(
            TITULO_DA_DAILY_SEM_SLIDES,
            _encurtar(f"Os slides não saíram: {resultado.falha_da_publicacao}"),
            nota=_vault.CAMINHO_DA_NOTA_VIVA,
        )
    return Resultado(
        TITULO_DO_TOAST_DA_DAILY,
        f"{slides} no link de sempre.",
        link=resultado.url,
        rotulo=ROTULO_DO_BOTAO_DOS_SLIDES,
    )
```

Em `comandos_padrao`, troque os dois parâmetros `fontes_da_daily` e `roteiro_da_daily` por:

```python
    publicacao_do_deck: Callable[[Configuracao], PortaPublicacaoDoDeck],
    busca: Callable[[Configuracao], PortaBusca],
    simular_daily: bool = False,
```

E o comando `daily` por:

```python
    def daily(_argumento: str, configuracao: Configuracao) -> Resultado:
        resultado = gerar_daily(
            agora(),
            configuracao=configuracao,
            publicacao=None if simular_daily else publicacao_do_deck(configuracao),
            simular=simular_daily,
        )
        return resultado_da_daily(resultado)
```

Na docstring de `comandos_padrao`, acrescente: "`simular_daily` é a bandeja em `--fakes`: a
daily só monta o deck, porque uma publicação fake gravaria um `deck:` falso no vault."

- [ ] **Passo 12: `__main__.py`**

Imports:
- tire `DailyFake` e `fontes_de_exemplo_da_daily` do `from .fakes import (...)`;
- apague as duas linhas de reexport `from .palheta import ROTULO_DO_BOTAO as ROTULO_DO_BOTAO_DA_DAILY`
  e `from .palheta import TITULO_DO_TOAST_DA_DAILY, texto_do_toast_da_daily`;
- troque `from .portas import PortaDaily, PortaResumoDoDia` por
  `from .portas import PortaPublicacaoDoDeck, PortaResumoDoDia`.

Apague `montar_fontes_da_daily` e `montar_roteiro_da_daily`, e no lugar delas escreva:

```python
def montar_publicacao_do_deck(configuracao: Configuracao) -> PortaPublicacaoDoDeck:
    """A publicação do deck da daily: o Haiku da conta do usuário, pelo CLI de `[claude].cli`.

    Não há fake aqui de propósito: `--fakes` na daily é simulação, e uma
    publicação fake que gravasse a cópia deixaria um `deck:` falso no vault.
    """
    from .deck_claude import PublicacaoDoDeckClaude

    return PublicacaoDoDeckClaude(cli=configuracao.claude_cli or None)
```

Troque `_comando_daily` e apague `_avisar_que_a_daily_nasceu`:

```python
def _comando_daily(args: argparse.Namespace) -> int:
    """Publica os slides da nota viva no link de sempre e grava a cópia em `daily/`.

    O que sai no terminal são os slides como foram, e o link; quem chama na
    hora agendada é a tarefa `Whis-Daily`, e o toast com o botão é o único
    sinal de que os slides saíram.
    """
    configuracao = _configuracao(args)
    if args.anotar is not None:
        return _anotar_ponto(configuracao, args.anotar)

    _registro.acrescentar_arquivo(configuracao, verboso=args.verboso)
    if args.agendada and not configuracao.daily_ativa:
        _log.info(
            "Daily desligada em [daily].ativa de %s — a tarefa agendada não gerou nada.",
            configuracao.origem,
        )
        return SAIDA_COMPLETA
    simular = args.simular or args.fakes
    resultado = gerar_daily(
        datetime.now().astimezone(),
        configuracao=configuracao,
        publicacao=None if simular else montar_publicacao_do_deck(configuracao),
        simular=simular,
    )
    _relatar_daily(resultado)
    if not simular:
        _palheta.avisar_resultado(configuracao, _palheta.resultado_da_daily(resultado))
    return _codigo_da_daily(resultado)


def _codigo_da_daily(resultado: ResultadoDaDaily) -> int:
    """0 com os slides no ar ou com a nota vazia; 3 quando só a cópia nasceu."""
    if resultado.simulado or resultado.vazio or resultado.publicado:
        _log.info("Daily de %s: saída %d.", resultado.data.isoformat(), SAIDA_COMPLETA)
        return SAIDA_COMPLETA
    _log.warning(
        "Daily de %s: os slides não saíram (saída %d).", resultado.data.isoformat(), SAIDA_PARCIAL
    )
    return SAIDA_PARCIAL
```

Troque `_relatar_daily`:

```python
def _relatar_daily(resultado: ResultadoDaDaily) -> None:
    print(f"Daily — {resultado.data.isoformat()}")
    print()
    for slide in resultado.deck.slides:
        print(f"{slide.titulo}:")
        for item in slide.itens:
            print(f"{'  ' * (item.profundidade + 1)}{item.texto}")
        print()

    if resultado.simulado:
        print("Simulação — nada foi publicado nem gravado.")
        if resultado.vazio:
            print("A nota da daily está vazia: nenhum slide sairia.")
        return
    if resultado.vazio:
        print(f"A nota da daily está vazia — escreva em {_vault.CAMINHO_DA_NOTA_VIVA} e rode de novo.")
        return
    if resultado.publicado:
        print(f"Slides: {resultado.url}")
    else:
        print(f"Os slides não saíram: {resultado.falha_da_publicacao}")
    if resultado.copia is not None:
        print(f"Cópia: {resultado.copia}")
```

Em `_comando_bandeja`, troque as duas linhas `fontes_da_daily=…` e `roteiro_da_daily=…` por:

```python
        publicacao_do_deck=lambda atual: montar_publicacao_do_deck(atual),
        simular_daily=fakes,
```

(A `lambda` resolve o nome na hora da chamada; é ela que deixa a fixture dos testes trocar a
publicação.)

- [ ] **Passo 13: apagar e ajustar os outros testes**

Apague: `git rm tests/test_roteiro_da_daily.py tests/test_daily_do_trabalho.py`.

`tests/test_detalhe_longo_no_prompt.py`: tire `montar_pergunta_da_daily` do import, troque o
laço `for montar in (montar_pergunta, montar_pergunta_da_daily):` por
`for montar in (montar_pergunta,):`, e troque `montar_pergunta_da_daily` por `montar_pergunta`
nos outros dois testes.

`tests/test_palheta.py`:
- No import de `whis.fakes`, troque `DAILY_PADRAO, RESPOSTA_PADRAO, BuscaFake, DailyFake,
  fontes_de_exemplo_da_daily` por `RESPOSTA_PADRAO, URL_DO_DECK_FAKE, BuscaFake,
  PublicacaoDoDeckFake`, e acrescente
  `from fixtures.daily import NOTA_DA_DAILY, escrever_nota_da_daily`.
- Na docstring do módulo, troque `DailyFake` por `PublicacaoDoDeckFake`.
- Na fixture `montar`, troque a assinatura e as duas fábricas:

```python
    def construir(*, busca=None, publicacao=None, simular_daily=False, lancados=None, abrir_painel=None, extras=()):
        configuracao = configuracao_do_diario()
        comandos = comandos_padrao(
            publicacao_do_deck=lambda _atual: publicacao or PublicacaoDoDeckFake(),
            busca=lambda _atual: busca or BuscaFake(),
            simular_daily=simular_daily,
            lancar=(lancados if lancados is not None else []).append,
            relogio=lambda: MOMENTO,
        )
```

- Apague `test_daily_pela_palheta_gera_a_nota_viva_e_avisa_com_o_botao`,
  `test_o_toast_da_daily_e_o_mesmo_do_subcomando`, `test_daily_que_nao_nasce_avisa_sem_botao` e
  `_vazio`, e no lugar deles, sob `# -- daily ---`, escreva:

```python
def test_daily_pela_palheta_publica_os_slides_e_avisa_com_o_link(montar, caminho_do_vault: Path, aviso):
    escrever_nota_da_daily(caminho_do_vault)
    publicacao = PublicacaoDoDeckFake()
    palheta = montar(publicacao=publicacao)

    assert palheta.despachar("daily") is True

    assert publicacao.chamadas == 1
    assert aviso.ultimo() == ("A daily está pronta", "4 slides no link de sempre.", ("Abrir slides", URL_DO_DECK_FAKE))


def test_o_toast_da_daily_e_o_mesmo_do_subcomando(montar, caminho_do_vault: Path, aviso, monkeypatch):
    """Um lugar só monta o toast: o subcomando e a palheta dizem a mesma coisa."""
    escrever_nota_da_daily(caminho_do_vault)
    montar().despachar("daily")
    da_palheta = aviso.ultimo()
    monkeypatch.setattr(avisos, "avisar", aviso)

    cli.main(["daily"])

    assert aviso.ultimo() == da_palheta


def test_daily_com_a_bandeja_em_fakes_simula_sem_publicar_nem_escrever(montar, caminho_do_vault: Path, aviso):
    arquivo = escrever_nota_da_daily(caminho_do_vault)
    publicacao = PublicacaoDoDeckFake()
    palheta = montar(publicacao=publicacao, simular_daily=True)

    palheta.despachar("daily")

    assert publicacao.chamadas == 0
    assert arquivo.read_bytes().decode("utf-8") == NOTA_DA_DAILY
    assert aviso.ultimo() == ("Simulação da daily", "Simulação: 4 slides, nada publicado.", None)


def test_daily_com_a_nota_vazia_avisa_com_o_botao_da_nota(montar, caminho_do_vault: Path, aviso):
    montar().despachar("daily")

    titulo, _texto, botao = aviso.ultimo()
    assert titulo == "A nota da daily está vazia"
    assert botao == ("Abrir no Obsidian", f"obsidian://open?vault={caminho_do_vault.name}&file=daily%2Fatual")
```

- Rode `grep -n "roteiro=" tests/test_palheta.py`. Se algum teste ainda passar `roteiro=` a
  `montar`, apague o argumento.

`tests/test_prompts.py`:
- Troque `from whis.fakes import BuscaFake, DailyFake, fontes_de_exemplo_da_daily` por
  `from whis.fakes import BuscaFake, PublicacaoDoDeckFake`.
- Em `palheta_com`, troque as duas fábricas por
  `publicacao_do_deck=lambda _c: PublicacaoDoDeckFake(),`.

`tests/test_daily_ativa.py`:
- Acrescente `from fixtures.daily import escrever_nota_da_daily`.
- Troque os três testes de `# -- o comando ---` e o `_palheta` por:

```python
def test_a_tarefa_agendada_com_a_daily_desligada_sai_sem_escrever(
    config_da_daily, caminho_do_vault: Path, publicacao_do_deck
):
    config_da_daily(ativa=False)
    escrever_nota_da_daily(caminho_do_vault)

    codigo = main(["daily", "--agendada"])

    assert codigo == 0
    assert publicacao_do_deck.chamadas == 0
    assert sorted(p.name for p in (caminho_do_vault / "daily").iterdir()) == ["atual.md"]


def test_a_tarefa_agendada_com_a_daily_ligada_publica(config_da_daily, caminho_do_vault: Path, publicacao_do_deck):
    config_da_daily(ativa=True)
    escrever_nota_da_daily(caminho_do_vault)

    main(["daily", "--agendada"])

    assert publicacao_do_deck.chamadas == 1


def test_whis_daily_no_terminal_publica_mesmo_com_a_daily_desligada(
    config_da_daily, caminho_do_vault: Path, publicacao_do_deck
):
    config_da_daily(ativa=False)
    escrever_nota_da_daily(caminho_do_vault)

    main(["daily"])

    assert publicacao_do_deck.chamadas == 1


def _palheta(configuracao, avisos: list):
    from whis.fakes import BuscaFake, PublicacaoDoDeckFake
    from whis.palheta import Palheta, comandos_padrao

    comandos = comandos_padrao(
        publicacao_do_deck=lambda _c: PublicacaoDoDeckFake(),
        busca=lambda _c: BuscaFake(),
        lancar=lambda _uri: None,
    )

    def avisar(titulo, texto, *, botao=None, executar=None):
        avisos.append((titulo, texto))
        return True

    return Palheta(comandos, configuracao, avisar=avisar, iniciar_thread=lambda alvo: alvo())
```

- Na docstring do módulo, troque "sai com 0 sem escrever nada" por "sai com 0 sem publicar nem
  escrever".
- Acrescente, na seção `# -- a chave ---`, o teste que protege o `config.toml` dele:

```python
def test_config_antigo_com_as_chaves_da_daily_velha_ainda_carrega(tmp_path: Path):
    corpo = '[daily]\nativa = true\nreferencias_pessoais = ["whis"]\ncontexto_do_time = "processo"\n'

    configuracao = carregar(escrever(tmp_path, corpo))

    assert configuracao.daily_ativa is True
    assert not hasattr(configuracao, "daily_contexto_do_time")
```

`tests/test_avisos_finais.py`:
- Troque o import `from whis.__main__ import MODELO_DE_CONFIGURACAO, main, texto_do_toast_da_daily`
  por `from whis.__main__ import MODELO_DE_CONFIGURACAO, main`.
- Apague os imports de `JanelaDaDaily, ResultadoDaDaily`, `DailyFake`, `Mudancas` e `ErroDeDaily`.
- Acrescente `from fixtures.daily import escrever_nota_da_daily`.
- Apague `resultado_com`, `test_o_texto_conta_os_novos_e_os_movidos`,
  `test_o_texto_diz_quando_nada_mudou`, `test_o_texto_diz_quando_a_nota_nasceu_parcial`,
  `test_quando_a_daily_nasce_sai_o_toast_com_o_botao_do_obsidian`, `test_simular_nao_avisa` e
  `test_a_nota_parcial_avisa_que_ficou_como_estava`.
- Troque `test_o_botao_usa_o_id_do_vault_quando_configurado`,
  `test_a_suite_nunca_mostra_um_toast_de_verdade` e
  `test_o_toast_que_nao_saiu_nao_muda_o_codigo_de_saida` por:

```python
def test_o_botao_da_nota_usa_o_id_do_vault_quando_configurado(configuracao_do_diario, aviso: AvisoEspiao):
    configuracao = configuracao_do_diario()
    arquivo = configuracao.origem
    arquivo.write_text(
        arquivo.read_text(encoding="utf-8") + f'\n[obsidian]\nvault = "{ID_DO_VAULT}"\n',
        encoding="utf-8",
    )

    main(["daily"])

    assert aviso.avisos[0][2][1] == f"obsidian://open?vault={ID_DO_VAULT}&file=daily%2Fatual"


def test_a_suite_nunca_mostra_um_toast_de_verdade(configuracao_do_diario, caminho_do_vault: Path, toasts):
    """A fixture autouse do `conftest` intercepta: rodar a suíte não enche a central de avisos.

    Sem ela, cada `main(["daily", ...])` dos testes chamava o PowerShell de
    `avisar` e deixava uma notificação real no Windows de quem roda a suíte —
    dezenas por execução, guardadas três dias.
    """
    configuracao_do_diario()
    escrever_nota_da_daily(caminho_do_vault)

    main(["daily"])

    assert [titulo for titulo, _, _ in toasts] == ["A daily está pronta"]
    assert avisos.avisar.__module__ == "conftest", "o `avisar` de verdade não pode estar no caminho"


def test_o_toast_que_nao_saiu_nao_muda_o_codigo_de_saida(configuracao_do_diario, caminho_do_vault: Path, monkeypatch):
    configuracao_do_diario()
    escrever_nota_da_daily(caminho_do_vault)
    monkeypatch.setattr(avisos, "avisar", AvisoEspiao(saiu=False))

    assert main(["daily"]) == 0
```

- Rode `grep -n "\bdate\b\|datetime\|re\.\|cli\." tests/test_avisos_finais.py` e tire do topo o
  import que ficou sem uso.

`tests/test_comando_codigos_de_saida.py`:
- Apague `test_daily_inteira_sai_com_zero`, `test_daily_sem_uma_fonte_nasce_marcada_e_sai_parcial`,
  `test_daily_sem_roteiro_nasce_com_as_listas_cruas_e_sai_parcial`,
  `test_daily_sem_nada_no_periodo_nao_nasce_e_sai_um`,
  `test_daily_com_todas_as_fontes_falhando_nao_nasce_e_sai_um`,
  `test_daily_simulada_com_fonte_falhando_tambem_sai_parcial`,
  `test_o_motivo_da_fonte_que_falhou_e_o_mesmo_no_log_e_na_nota` e
  `test_o_log_diz_como_a_daily_terminou`, além do cabeçalho `# -- daily: …` e do auxiliar
  `_fontes_com_o_slack_falhando`.
- Imports: tire `DailyFake`, `FonteDaJanela` e `ErroDeDaily`. Rode
  `grep -n "EVENTOS_DE_GIT\|_unica_nota\|_sem_nota" tests/test_comando_codigos_de_saida.py` e
  tire o que ficou sem uso.
- Docstring do módulo: troque o terceiro parágrafo por "As fábricas de `__main__` do diário são o
  ponto em que a CLI injeta as portas; trocá-las por uma fonte ou um resumo que falham é injetar
  outra porta, não espiar por dentro. Os códigos da daily estão em `test_comando_daily.py`."

`tests/test_login_do_claude.py`:
- Troque `from whis.daily import JanelaDaDaily, ResultadoDaDaily` por
  `from whis.daily import ResultadoDaDaily` mais `from whis.deck import Deck, ItemDoSlide, Slide`.
- Troque `daily_com` e os dois testes da daily por:

```python
def daily_com(falha: str) -> ResultadoDaDaily:
    deck = Deck(slides=(Slide("fiz", "O que eu fiz", "O que eu fiz", (ItemDoSlide("a"),)),))
    return ResultadoDaDaily(
        data=date(2026, 9, 29),
        deck=deck,
        copia=Path("daily/2026-09-29.md"),
        falha_da_publicacao=falha,
    )


def test_a_daily_sem_slides_por_login_vencido_pede_o_login():
    resultado = resultado_da_daily(daily_com(VENCIDO_NA_DAILY))

    assert resultado.titulo == "O login do Claude venceu"
    assert resultado.texto.startswith("Rode 'claude auth login' num terminal.")
    assert resultado.nota == "daily/atual.md" and resultado.link is None


def test_a_daily_sem_slides_por_outro_motivo_diz_o_motivo_e_abre_a_nota():
    resultado = resultado_da_daily(daily_com("o Claude caiu"))

    assert resultado.titulo == "A daily não publicou"
    assert resultado.texto == "Os slides não saíram: o Claude caiu"
    assert resultado.nota == "daily/atual.md"
```

`tests/test_painel.py`:
- Em `test_campos_cobrem_toda_chave_do_modelo_e_nenhuma_a_mais`, troque o conjunto por
  `{"[daily].ativa", "[daily].horarios"}` e a contagem por `len(CAMPOS) == 24`.
- Em `test_os_quatro_segredos_os_dois_caminhos_e_as_listas_tem_o_tipo_certo`, tire
  `"[daily].referencias_pessoais"` do conjunto de `Tipo.LISTA`.
- Em `test_preencher_e_salvar_reescreve_o_arquivo_e_recarrega`, apague
  `formulario.digitar("[daily].contexto_do_time", CONTEXTO)` e
  `assert relida.daily_contexto_do_time == CONTEXTO`.
- Se `CONTEXTO` ficar sem uso no arquivo, apague a constante.

`tests/test_configuracao_escrita.py`:
- Em `COMPLETO`, apague as linhas `referencias_pessoais = …` e `contexto_do_time = …`.
- Apague `assert dados["daily"]["contexto_do_time"] == …`.
- Troque `== 26` por `== 24`.

- [ ] **Passo 14: varrer o que sobrou**

Rode: `grep -rn "PortaDaily\|ErroDeDaily\|DailyFake\|fontes_de_exemplo_da_daily\|resumir_daily\|Mudancas\|arquivar_fiz\|referencias_pessoais\|contexto_do_time\|cobertura_da_janela\|montar_daily\|JanelaDaDaily\|texto_do_toast_da_daily\|roteiro_da_daily\|fontes_da_daily\|TITULO_DA_DAILY_QUE_NAO_NASCEU\|ItemNovo\|SECOES_DO_AGENTE\|id_do_item" src tests --include=*.py`
Esperado: nada.

- [ ] **Passo 15: rodar a suíte inteira**

Rode: `.venv/Scripts/python.exe -m pytest`
Esperado: tudo verde, `0 failed`. Anote o número de testes para o `ORCHESTRATION.md`.

- [ ] **Passo 16: commit único**

```bash
git add src/whis/daily.py src/whis/nota_viva.py src/whis/vault.py src/whis/resumo_dia_claude.py src/whis/portas.py src/whis/fakes.py src/whis/configuracao.py src/whis/palheta.py src/whis/__main__.py tests/fixtures/daily.py tests/conftest.py tests/test_daily.py tests/test_comando_daily.py tests/test_nota_viva.py tests/test_palheta.py tests/test_avisos_finais.py tests/test_comando_codigos_de_saida.py tests/test_login_do_claude.py tests/test_daily_ativa.py tests/test_prompts.py tests/test_painel.py tests/test_configuracao_escrita.py tests/test_detalhe_longo_no_prompt.py
git commit -m "A daily vira slides: whis daily le as secoes que ele escreve em daily/atual.md, publica o deck no Claude Slides no link de sempre e grava a copia datada; sai a daily escrita pelo agente (fontes, roteiro, mover, arquivar, referencias_pessoais e contexto_do_time)"
```

(Os dois `git rm` do Passo 13 já estão no índice.)

---

## Tarefa 7: acabamento

**Arquivos:**
- Modificar: `src/whis/__main__.py`, `src/whis/palheta.py`, `src/whis/configuracao.py`
- Modificar: `CONTEXT.md`
- Reescrever: `docs/smoke-daily.md`
- Teste: `tests/test_comando_codigos_de_saida.py`

- [ ] **Passo 1: o teste do texto de ajuda**

Em `tests/test_comando_codigos_de_saida.py`, troque `test_o_help_documenta_os_codigos_de_saida`
por:

```python
def test_o_help_do_diario_documenta_os_codigos_de_saida(capsys: pytest.CaptureFixture):
    with pytest.raises(SystemExit) as saida:
        main(["diario", "--help"])

    ajuda = capsys.readouterr().out
    assert saida.value.code == 0
    assert f"{SAIDA_COMPLETA}  a nota nasceu inteira" in ajuda
    assert f"{SAIDA_PARCIAL}  a nota nasceu parcial" in ajuda
    assert f"{SAIDA_NAO_NASCEU}  a nota não nasceu" in ajuda
    assert "bandeja.log" in ajuda


def test_o_help_da_daily_documenta_os_codigos_dela(capsys: pytest.CaptureFixture):
    with pytest.raises(SystemExit):
        main(["daily", "--help"])

    ajuda = capsys.readouterr().out
    assert f"{SAIDA_COMPLETA}  os slides saíram no link de sempre, ou a nota estava vazia" in ajuda
    assert f"{SAIDA_PARCIAL}  os slides não saíram" in ajuda
    assert "a nota nasceu inteira" not in ajuda
    assert "fontes e roteiro" not in ajuda
```

Rode: `.venv/Scripts/python.exe -m pytest tests/test_comando_codigos_de_saida.py -v`
Esperado: `test_o_help_da_daily_documenta_os_codigos_dela` FAIL.

- [ ] **Passo 2: os textos de `__main__.py`**

Logo depois de `CODIGOS_DE_SAIDA`:

```python
CODIGOS_DA_DAILY = f"""\
códigos de saída:
  {SAIDA_COMPLETA}  os slides saíram no link de sempre, ou a nota estava vazia e nada foi publicado
  {SAIDA_PARCIAL}  os slides não saíram: a cópia em daily/ nasceu com o aviso e o toast abre a nota
  {SAIDA_NAO_NASCEU}  não rodou: configuração inválida
  2  erro de uso (argumento inválido)
o rastro de toda execução fica em bandeja.log, ao lado do config.toml"""
```

No parser da `daily`:

```python
    daily_cmd = subcomandos.add_parser(
        "daily",
        help="publica os slides de daily/atual.md no link de sempre e grava a cópia em daily/",
        epilog=CODIGOS_DA_DAILY,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
```

E os textos de ajuda:
- `--fakes`: `"o mesmo que --simular: mostra os slides sem publicar nem escrever"`;
- `--simular`: `"mostra os slides que sairiam, sem publicar e sem escrever"`.

No docstring do módulo:
- troque "`daily.gerar_daily` para a nota viva da daily" por "`daily.gerar_daily` para os slides
  da daily";
- troque a linha de uso da daily por `python -m whis daily [--anotar TEXTO] [--simular] [--fakes] [--agendada]`;
- no parágrafo dos códigos, troque "`diario`, `daily` e `news` saem com um código…" por
  "`diario` e `news` saem com um código…" e acrescente uma frase: "`daily` tem os seus: 0 com os
  slides no ar ou com a nota vazia, 3 quando só a cópia nasceu."

- [ ] **Passo 3: palheta e configuração**

`palheta.py`:
- no `Comando` da `daily`, troque a ajuda por `"publica os slides de daily/atual.md agora"` e
  `descricao` por `"Publish the daily slides from daily/atual.md (~1 min)"`;
- na docstring do módulo, troque "a pergunta leva um minuto e a daily quarenta segundos" por "a
  pergunta e a daily levam um minuto", e "as fontes, o roteiro, a busca" por "a publicação do
  deck, a busca".

`configuracao.py`:
- no `MODELO_DE_CONFIGURACAO`, o comentário de `ativa` passa a ser
  `# false = sem daily: a tarefa agendada não publica os slides e a palheta esconde "Generate daily"`;
- o de `horarios` passa a ser `# hora em que os slides da daily saem em cada dia (segunda..domingo, sem acento); dia ausente = sem daily`;
- no parágrafo de `daily_ativa` da docstring, troque "sai sem gerar nada" por "sai sem publicar
  nada".

Rode: `.venv/Scripts/python.exe -m pytest tests/test_comando_codigos_de_saida.py tests/test_painel.py tests/test_configuracao_escrita.py -v`
Esperado: todos `PASSED`. O painel mostra o comentário do modelo como ajuda, e
`test_a_ajuda_de_cada_campo_e_o_comentario_do_modelo` cobre isso.

- [ ] **Passo 4: `CONTEXT.md`**

Troque o bloco **Daily** (do `**Daily**:` até o `_Avoid_` dele) por:

```markdown
**Daily**:
O deck que o usuário apresenta na reunião diária do time, no Claude Slides, sempre no mesmo link. Nasce do que **ele** escreve na **Nota viva** (`daily/atual.md`): um slide por seção com texto em *O que eu fiz*, *O que estou fazendo*, *O que terminei*, *Dúvidas* e *Falar*, com as linhas como ele as escreveu. Sai nos horários de `[daily].horarios` pela tarefa `Whis-Daily`, ou por `daily` na palheta; cada geração deixa `daily/YYYY-MM-DD.md`, a cópia do que foi para o deck, com o link no frontmatter (`deck:`) — é dali que a geração seguinte republica no mesmo endereço. Uma edição feita à mão no deck é sobrescrita na geração seguinte: o deck é a renderização da nota. `[daily].ativa = false` desliga a tarefa e esconde `daily` da palheta; `whis daily` no terminal ainda publica. Até 2026-09-30 a daily era um roteiro que o agente escrevia a partir de git, Linear e Slack — aposentado porque ele não usava.
_Avoid_: standup, resumo diário, roteiro
```

Troque o bloco **Nota viva** por:

```markdown
**Nota viva**:
`daily/atual.md` — a nota da daily, escrita por ele no Obsidian, em sete seções: *O que eu fiz*, *O que estou fazendo*, *O que terminei*, *Fazer*, *Dúvidas*, *Pontos*, *Falar*. É dele inteira, e quem a limpa depois da reunião é ele. O agente só escreve ali a pedido explícito — `note` (→ *Pontos*), `doubt` (→ *Dúvidas*) e `do` (→ *Fazer*, com a caixa `- [ ]`) acrescentam uma linha — e abre, vazio e no lugar dele, o título de uma seção que falte. Em *Fazer* quem marca `[x]` é ele. A nota não carrega explicação nenhuma: ele sabe o que cada seção é.
_Avoid_: painel, dashboard, `daily/hoje.md`, `notas/daily.md`
```

Em **Zona de propriedade**, troque "e a **Nota viva**, onde os dois escrevem, cada um nas suas
seções." por "e a **Nota viva**, que é dele e onde o agente só acrescenta a pedido.", e
"vive nas seções do usuário da nota viva" por "vive na nota viva".

- [ ] **Passo 5: `docs/smoke-daily.md`**

Substitua o arquivo inteiro:

````markdown
# Prova da daily em slides

`python` significa `.venv\Scripts\python.exe`, rodado da pasta do repositório. No PowerShell 5.1
não existe `&&`: um comando por linha.

## Passo 1 — Escrever a nota

Abra a palheta (`ctrl+space`), rode `open` e escreva em `daily/atual.md`, no Obsidian:
- em *O que eu fiz*, *O que estou fazendo* e *O que terminei*, uma linha por coisa, com
  sub-itens por tab quando quiser;
- em *Dúvidas* e *Falar*, o que for levar à reunião.

Se a nota ainda não tem `## O que terminei`, o Whis põe o título na primeira geração.

## Passo 2 — Conferir sem publicar

```powershell
python -m whis daily --simular
```

O terminal mostra os slides que sairiam, um bloco por seção, com o seu texto. Nada é publicado
nem gravado.

## Passo 3 — Publicar

```powershell
python -m whis daily
```

Em cerca de um minuto chega o toast **A daily está pronta**, com o botão **Abrir slides**. O
deck abre no link de sempre: um slide por seção com texto, na ordem da nota, com a data e a
página no rodapé. *Pontos* e *Fazer* não aparecem.

## Passo 4 — A cópia

Abra `daily/` no Obsidian. A nota de hoje (`AAAA-MM-DD.md`) tem `deck:` no frontmatter, o link
**Abrir os slides** e as seções que foram para o deck, com as suas linhas.

## Passo 5 — Gerar de novo

Mude uma linha, apague tudo de *Dúvidas* e rode `daily` na palheta. O link é o mesmo, a linha
mudou, e o slide de *Dúvidas* sumiu.

## Passo 6 — A tarefa agendada

```powershell
Start-ScheduledTask -TaskName Whis-Daily
```

Espere o toast e depois:

```powershell
(Get-ScheduledTaskInfo -TaskName Whis-Daily).LastTaskResult
```

O esperado é `0`. Com `3` os slides não saíram: o toast diz o motivo e o rastro fica em
`%APPDATA%\whis\bandeja.log`.

## Passo 7 — A prova de verdade

Na próxima daily do time, apresente pelo deck que a tarefa publicou alguns minutos antes. Conte
no chat o que faltou ou sobrou: é a confirmação que fecha a entrega.
````

- [ ] **Passo 6: suíte e commit**

Rode: `.venv/Scripts/python.exe -m pytest`
Esperado: tudo verde.

```bash
git add src/whis/__main__.py src/whis/palheta.py src/whis/configuracao.py CONTEXT.md docs/smoke-daily.md tests/test_comando_codigos_de_saida.py
git commit -m "Acabamento da daily em slides: codigos de saida e ajuda proprios, descricao na palheta, comentario do config, Daily e Nota viva no CONTEXT e o roteiro da prova"
```

---

## Tarefa 8: a prova

Publica de verdade, na conta dele, a partir da nota dele. Se a entrega rodou num worktree, esta
tarefa só começa **depois do merge em `master`**, na árvore principal: é de lá que a bandeja e
a `Whis-Daily` rodam.

- [ ] **Passo 1: `whis daily` real a partir da sessão**

Rode: `.venv/Scripts/python.exe -m whis daily`.
Esperado: saída `0`, `Slides: <url semeada na Tarefa 5>` e a cópia de hoje no vault com o
mesmo `deck:`. Confira com `Artifact` `action: list`, `scope: "files"`, `url`: só os slides das
seções com texto. Anote o tempo e o custo do log.

- [ ] **Passo 2: reiniciar a bandeja com o código novo**

Pela rota da tarefa descartável (`.scratch/interface/research/rota-tarefa-descartavel/LEIA-ME.md`):
1. pare a bandeja com `parar-bandeja.ps1`;
2. espere a tarefa de parar sair de `Running`;
3. suba a bandeja com `.venv\Scripts\pythonw.exe -m whis bandeja`, sem limite de tempo;
4. confira o processo.

Sem isso, o `daily` da palheta roda o código velho que está na memória.

- [ ] **Passo 3: a tarefa agendada disparada à mão**

Rode no PowerShell: `Start-ScheduledTask -TaskName Whis-Daily`.
Espere até `(Get-ScheduledTask -TaskName Whis-Daily).State` sair de `Running`.
Depois: `(Get-ScheduledTaskInfo -TaskName Whis-Daily).LastTaskResult`.
Esperado: `0` e a cópia de hoje com um `gerada:` novo. Pelo `bandeja.log` real
(`ler-log-da-bandeja.ps1`, pela rota descartável), confira a linha `Slides publicados em`.

- [ ] **Passo 4: registrar e entregar o gate humano**

- No `ORCHESTRATION.md`: os commits, a suíte, as provas 1 a 3 com tempo e custo, e o gate
  pendente.
- Na memória `projeto-whis-daily-slides.md`: o estado novo.
- Para ele: o link do deck e o passo 7 de `docs/smoke-daily.md`, que fecha a entrega quando
  ele apresentar a próxima daily pelo deck.
