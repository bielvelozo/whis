# Coletor de reuniões da Granola — plano de implementação

> Execução inline nesta mesma sessão (quem planeja é quem constrói, com o contexto inteiro). Por isso o plano fixa arquivos, interfaces, testes e comandos, e não repete o código que a própria tarefa escreve. Sem commits: a árvore tem trabalho não commitado de outras sessões, e o commit é dele.

**Goal:** puxar as reuniões da Granola (MCP oficial, plano Basic) para `reunioes/` no vault, pela palheta (`meetings`) e por uma tarefa diária (`Whis-Reunioes`).

**Architecture:** porta `PortaReunioes` com o adaptador `GranolaMCP`, que usa o SDK `mcp` 2.0 com OAuth (DCR + PKCE) e uma guarda própria do login: DPAPI, renovação antes do SDK, trava entre processos. A costura `reunioes.puxar_reunioes` escreve uma vez só, reconhecendo a reunião pelo `granola_id`. A casca segue o molde do `news`.

**Tech Stack:** Python 3.12, `mcp` 2.0.0, `httpx`, `pywin32` (`win32crypt`) e pytest com `httpx.MockTransport` e dublês.

**Comando da suíte:** `.venv\Scripts\python.exe -m pytest -p no:cacheprovider -o addopts="" -m "not rede" -q` (linha de base: 1101 verdes).

---

## Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/whis/portas.py` (mod) | `ReuniaoListada`, `Reuniao`, `ErroDaGranola`, `LoginNecessario`, `PortaReunioes` |
| `src/whis/granola.py` (novo) | leitura do texto do MCP (`ler_lista`, `ler_reunioes`, `ler_data`, `ler_participantes`) e o adaptador `GranolaMCP` |
| `src/whis/granola_login.py` (novo) | `GuardaDoLogin` (o `TokenStorage` do SDK sobre DPAPI, com a renovação), `vez_da_granola` (a trava com espera) e `pasta_do_login` |
| `src/whis/reunioes.py` (novo) | `puxar_reunioes`, `ResultadoDasReunioes` |
| `src/whis/vault.py` (mod) | `ZONAS_DAS_REUNIOES`, `caminho_da_reuniao`, `montar_reuniao`, `granola_ids_no_vault`, `_slug(texto, padrao)` |
| `src/whis/fakes.py` (mod) | `ReunioesFake` |
| `src/whis/configuracao.py` (mod) | `[granola].horario` |
| `src/whis/palheta.py` (mod) | o comando `meetings`, `resultado_das_reunioes` e `resultado_das_reunioes_que_falharam` |
| `src/whis/automacao.py` (mod) | `Whis-Reunioes` e o vigia |
| `src/whis/__main__.py` (mod) | `whis meetings`, `windows --meetings`, `montar_reunioes` |
| `pyproject.toml` (mod) | `mcp>=2.0` |
| `tests/fixtures/granola/*.txt` (novo) | amostras do formato medido, com conteúdo inventado |
| `tests/test_granola.py`, `tests/test_granola_login.py`, `tests/test_reunioes.py`, `tests/test_casca_das_reunioes.py` (novos) | os contratos |
| `CONTEXT.md`, `docs/adr/0002-…`, `docs/smoke-reunioes.md` | os documentos |

## Task 1: porta e leitura do texto

- `portas.py`: os tipos da spec, com `Sequence` importado de `collections.abc`.
- `granola.py` (só a leitura nesta tarefa):
  - `ler_data("Sep 1, 2026 2:00 PM GMT-3")` devolve o datetime na hora local. O mês vem de uma tabela, a conversão de 12 h para 24 h é feita à mão, e o fuso `GMT±H[:MM]` (ou só `GMT`) vira `timezone`.
  - `ler_participantes(texto)`: `html.unescape`, divisão por `,` depois de `>`, descarte do `(note creator)`, e retirada de `<email>` e de ` from <org>`.
  - `ler_lista(texto)` e `ler_reunioes(texto)`: expressão regular por `<meeting …>…</meeting>`, atributos por `(\w+)="([^"]*)"`, e `<summary>` e `<known_participants>` por expressão regular.
  - Um texto sem `<meetings_data` levanta `ErroDaGranola("…formato inesperado…")`. O auto-fechado `count="0"` devolve `()`.
- Amostras: `tests/fixtures/granola/lista.txt`, com `access_notice` e três reuniões, uma delas com `&amp;` no título; `detalhes.txt`, com duas reuniões, uma com resumo e `<private_notes>`, a outra sem `<summary>`; e `vazia.txt`.
- Testes em `tests/test_granola.py`:
  - `test_a_lista_traz_id_titulo_e_inicio_local`
  - `test_entidades_viram_texto`
  - `test_lista_vazia_e_tupla_vazia`
  - `test_formato_inesperado_falha_alto`
  - `test_detalhes_trazem_resumo_participantes_e_link`
  - `test_reuniao_sem_resumo_vem_com_resumo_vazio`
  - `test_tag_desconhecida_e_ignorada`
  - `test_data_com_fuso` (parametrizado: `GMT-3`, `GMT+5:30`, `GMT`, `12:05 AM`, `12:30 PM`)
  - `test_participantes_sem_criador_email_nem_empresa`
- Rodar `tests/test_granola.py` (falha), implementar, rodar (passa).

## Task 2: a guarda do login

- `granola_login.py`:
  - `pasta_do_login(configuracao)`, ao lado da configuração, como `registro` e `instancia`.
  - `GuardaDoLogin(pasta, *, agora=time.time, transporte=None, cifrar=_cifrar, decifrar=_decifrar)`, com os quatro métodos assíncronos do `TokenStorage`. Ela grava o JSON `{"cliente", "tokens", "expira_em"}` cifrado em `granola.json`, de forma atômica.
  - Em `get_tokens`, quando `expira_em` já passou, a guarda renova: descobre o endpoint pelos dois `.well-known` e faz o POST de `refresh_token`.
    - HTTP 200: grava e devolve o token novo.
    - HTTP 400 ou 401: apaga os tokens, mantém o cliente e devolve `None`.
    - Rede ou HTTP 5xx: levanta `ErroDaGranola` e não apaga nada.
  - Um arquivo que não decifra ou não é JSON conta como sem login (log de aviso).
  - `vez_da_granola(pasta, espera_s=120)`: um gerenciador de contexto que tenta `instancia.Trava(pasta / "granola.lock").adquirir()` em laço, com `sleep(0.25)`. Passado o tempo, levanta `ErroDaGranola("Outra puxada da Granola está em andamento…")`.
- Testes em `tests/test_granola_login.py`:
  - `test_ida_e_volta_pelo_dpapi` (DPAPI de verdade, com `tmp_path`)
  - `test_o_arquivo_nao_tem_o_token_em_claro`
  - `test_token_valido_nao_renova`
  - `test_token_vencido_renova_e_grava_o_refresh_novo`
  - `test_renovacao_recusada_apaga_tokens_e_mantem_o_cliente`
  - `test_renovacao_sem_rede_levanta_e_nao_apaga`
  - `test_arquivo_ilegivel_e_sem_login`
  - `test_a_segunda_vez_espera_e_desiste`
- As respostas HTTP vêm de `httpx.MockTransport`.

## Task 3: o adaptador

- `GranolaMCP(guarda, *, pasta, pode_logar, abrir_navegador=webbrowser.open, sessao=None)` implementa `listar()` e `detalhar(ids)`.
- Cada chamada entra em `vez_da_granola(pasta)`, faz `asyncio.run` de `_chamar(ferramenta, argumentos)` e lê o texto.
- Antes de abrir a sessão, quando `pode_logar=False`, o adaptador chama `await guarda.get_tokens()`: se vier `None`, levanta `LoginNecessario` sem rede.
- A sessão real: `OAuthClientProvider` (`client_name="Whis"`, o redirect `127.0.0.1:33418/callback`, `token_endpoint_auth_method="none"`), `create_mcp_http_client(auth=…)`, `streamable_http_client` e `ClientSession.initialize`.
- `_redirecionar(url)`:
  - com `pode_logar=False`, levanta `LoginNecessario`;
  - senão, sobe o servidor de retorno (porta ocupada vira `ErroDaGranola`) e chama `abrir_navegador(url)`.
- `_esperar_retorno()` espera o `code` ou o `error` por até 5 minutos e derruba o servidor.
- `is_error` vira `ErroDaGranola(texto)`. Outras exceções, inclusive dentro de `ExceptionGroup`, viram `ErroDaGranola`, mas um `LoginNecessario` aninhado é desembrulhado.
- Testes em `tests/test_granola.py`, com a sessão dublê:
  - `test_listar_e_detalhar_leem_o_texto_da_ferramenta`
  - `test_detalhar_manda_os_ids`
  - `test_is_error_vira_erro_da_granola`
  - `test_sem_login_e_sem_permissao_nao_abre_navegador`
  - `test_redirecionar_sem_permissao_levanta_login_necessario`
  - `test_login_necessario_aninhado_e_desembrulhado`

## Task 4: a costura e a nota

- `vault.py`:
  - `_slug(texto, padrao=TIPO_RESPOSTA)`;
  - `ZONAS_DAS_REUNIOES`;
  - `TIPO_REUNIAO = "reuniao"`;
  - `caminho_da_reuniao(inicio, titulo)`;
  - `montar_reuniao(reuniao)`: frontmatter `tipo`, `participantes`, `granola` e `granola_id`, sem `data`; depois `# título`, a linha `_data_por_extenso(inicio.date()) + ", HH:MM"` e o resumo;
  - `granola_ids_no_vault(vault)`: a expressão regular `^granola_id:\s*(\S+)` no frontmatter de cada `reunioes/*.md`.
- `reunioes.py`: `puxar_reunioes` e `ResultadoDasReunioes`, como na spec. As falhas são por reunião (`"<título>: <motivo>"`), e um id pedido que não volta conta como "não veio".
- `fakes.py`: `ReunioesFake(listadas=…, detalhadas=…, erro_ao_listar=None, erro_ao_detalhar=None)`. Ele guarda os lotes pedidos e tem um padrão de duas reuniões de exemplo.
- `tests/test_zona_de_propriedade.py`: só `ZONAS_DAS_REUNIOES` alcança `reunioes/`, e nenhuma zona alcança `transcricoes/`.
- Testes em `tests/test_reunioes.py`:
  - `test_escreve_so_a_reuniao_nova`
  - `test_reconhece_pelo_granola_id_mesmo_com_titulo_trocado`
  - `test_pula_reuniao_sem_resumo`
  - `test_nome_com_a_hora_local`
  - `test_nome_que_colide_ganha_sufixo`
  - `test_lotes_de_dez`
  - `test_lote_que_falha_da_parcial_e_o_resto_e_escrito`
  - `test_id_que_nao_volta_conta_como_falha`
  - `test_login_necessario_sobe`
  - `test_a_nota_tem_o_frontmatter_e_nao_tem_data`
  - `test_o_resumo_entra_literal`
  - `test_listar_que_falha_sobe`

## Task 5: a casca

- `configuracao.py`:
  - a seção `[granola]` no modelo, depois de `[noticias]`: `horario = "19:00"`, com a explicação "quando a tarefa agendada puxa as reuniões da Granola";
  - `Chave("granola", "horario", "granola_horario", Tipo.HORA)` e o campo `granola_horario: str = "19:00"`;
  - a validação por `_hora` em `carregar_texto`.
- `automacao.py`: `NOME_DA_TAREFA_DAS_REUNIOES = "Whis-Reunioes"`, `agendar_reunioes`, `desagendar_reunioes` e `reunioes_agendada`. `tarefas_vigiadas` inclui `Whis-Reunioes` quando ela existe.
- `palheta.py`:
  - `NOME_DAS_REUNIOES = "meetings"`, na `ORDEM_DAS_ACOES` depois de `news`;
  - `comandos_padrao(..., reunioes=None)`, com o comando `meetings` (`rotulo="Pull meetings"`, `descricao="Granola meetings into reunioes/"`, `icone="◷"`);
  - `resultado_das_reunioes(resultado)` e `resultado_das_reunioes_que_falharam(erro)`.
- `__main__.py`:
  - `montar_reunioes(configuracao, *, fakes, pode_logar)`;
  - `_comando_meetings`: o código de saída 0, 3 ou 1; toast, exceto com `--agendada` sem nada novo e sem falha; nenhum toast com `--fakes`; e o relatório impresso;
  - o subparser `meetings`, com `--agendada`, `--fakes` e `--config`;
  - `windows --meetings`, com o par `--remover` e o vigia reagendado;
  - a bandeja passa `reunioes=` para `comandos_padrao`;
  - a docstring do módulo.
- `pyproject.toml`: `"mcp>=2.0"`.
- Ajustes de contagem nos testes existentes:
  - `test_painel` (27 campos e `[granola].horario` no tipo HORA);
  - `test_configuracao_escrita` (27 chaves e `[granola]` em `COMPLETO`);
  - `test_palheta` (`COMANDOS` com `meetings`, `ACOES` com a `Acao` de `meetings` depois de `news`, e os índices de `completar`);
  - `test_prompts` (o recorte `[4:6]`);
  - `test_agendamento_e_aviso` e `test_casca_do_jornal` (o vigia com `Whis-Reunioes`).
- Testes em `tests/test_casca_das_reunioes.py`:
  - a chave `horario`: padrão, lida e recusada quando inválida;
  - o painel mostra a chave;
  - a tarefa é registrada com `meetings --agendada` e o gatilho certo;
  - o vigia com e sem a tarefa;
  - `windows --meetings` e `--remover --meetings`;
  - `whis meetings --fakes` escreve as notas e sai com 0;
  - os códigos 3 e 1, com a porta trocada;
  - `--agendada` sem nada novo não mostra toast;
  - o toast de cada caso;
  - `meetings` na palheta escreve e avisa;
  - o login necessário vira o toast certo.

## Task 6: documentos e prova

- `CONTEXT.md`: o verbete **Granola**; `reunioes/` escrita pelo coletor da Granola na *Zona de propriedade*; `meetings` na *Palheta*; o *Vigia* olhando as reuniões.
- `docs/adr/0002-…`: uma linha "Construído em 2026-09-30: `whis meetings`, a palheta `meetings` e a `Whis-Reunioes`".
- `docs/smoke-reunioes.md`, no molde do `smoke-jornal.md`:
  1. `whis meetings --fakes` num vault de teste;
  2. o login pela palheta e a puxada real;
  3. conferir as notas no Obsidian e no `ask`;
  4. `whis windows --meetings` e a tarefa no Agendador;
  5. a puxada agendada do dia seguinte.
- A suíte inteira verde. Depois, a bandeja reiniciada na máquina dele pela tarefa descartável, para a palheta ganhar `meetings`.
