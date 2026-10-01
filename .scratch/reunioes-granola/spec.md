# Spec: o coletor de reuniões da Granola

Status: ready-for-agent

Origem: conversa de 2026-09-30 em que a gravação própria saiu do Whis ([ADR 0002](../../docs/adr/0002-gravacao-sai-do-whis.md)). O desenho foi fechado com o usuário no mesmo dia, por brainstorming. O MCP oficial da Granola foi testado no plano dele (Basic), e o resultado está no ADR 0002, seção *O MCP testado no plano Basic*. Glossário em `CONTEXT.md`. O ADR 0001 (local, fino, conta do usuário) continua valendo: a Granola é um serviço que ele já usa, e o Whis só lê a conta dele.

## Problem Statement

As reuniões dele voltaram a ser gravadas pela Granola, no plano gratuito. O Whis não lê nada de lá, então o `ask` e o diário não sabem que a reunião aconteceu, e a daily também não. No plano grátis, uma reunião com mais de 30 dias some do MCP: se ninguém a copiar antes, ela nunca chega ao vault.

## Solution

Um coletor novo puxa as reuniões da Granola pelo MCP oficial (`https://mcp.granola.ai/mcp`), usando o SDK `mcp` já presente na venv. Cada reunião com resumo vira uma nota em `reunioes/AAAA-MM-DD-HHMM-titulo.md`, que é o formato que o diário, a daily e o `ask` já leem. Ele roda de dois jeitos:

- pela palheta, com o comando `meetings` (*Pull meetings*), que puxa na hora e faz o login pelo navegador quando falta;
- pela tarefa diária `Whis-Reunioes` às 19:00, que nunca abre navegador e só avisa quando chegou coisa nova ou quando falhou.

A nota é escrita uma vez só e não é tocada depois. O resumo vai literal, como a Granola mandou. A transcrição não vem, porque o plano gratuito não dá.

## User Stories

- Termino uma reunião na Granola, abro a palheta, digito `meetings`, e em segundos um toast diz "1 reunião nova no vault", com o botão que abre a nota no Obsidian.
- Se eu esquecer, a tarefa das 19:00 puxa sozinha. Se o PC estava desligado, ela puxa quando eu ligar. Nenhuma reunião passa dos 30 dias sem chegar ao vault, desde que o PC ligue pelo menos uma vez nesse intervalo.
- Na primeira vez, `meetings` abre a Granola no navegador. Eu entro e autorizo uma vez, e depois não preciso mais.
- Se a Granola pedir login de novo, o toast me diz para rodar `meetings` na palheta. A tarefa das 19:00 não abre navegador sozinha.
- Pergunto ao `ask` "o que ficou decidido na daily de terça?" e ele acha a nota.
- O que eu editar numa nota de reunião no Obsidian fica: o coletor nunca reescreve uma nota que já existe.

## Implementation Decisions

### Vocabulário e zonas

- **Granola**: o app de notas de reunião que grava as reuniões dele, e a fonte deste coletor. Entra no `CONTEXT.md`.
- `reunioes/` volta a ter escritor, o coletor da Granola, com a zona nova `vault.ZONAS_DAS_REUNIOES = (PASTA_REUNIOES,)`. `transcricoes/` continua sem escritor. O teste de zona hoje garante que nenhuma zona alcança `reunioes/`; ele passa a garantir que só `ZONAS_DAS_REUNIOES` alcança, e que `transcricoes/` segue sem zona.
- O coletor não é uma *fonte passiva* (não entra em `montar_fontes`) nem passa pela janela do diário. Ele escreve notas que as costuras existentes já leem.

### A nota

`reunioes/<AAAA-MM-DD-HHMM>-<slug>.md`, com a hora local do início da reunião. O slug segue a regra de `respostas/` (ASCII, `a-z0-9-`, até 60 caracteres); sem nada aproveitável, `reuniao`. O `_slug` do vault ganha um parâmetro de padrão. Se o nome já existe com outro `granola_id`, a nota recebe o sufixo `-2`, `-3` e assim por diante.

```markdown
---
tipo: reuniao
participantes: [Luan Afonso, Gabriel Ribeiro]
granola: https://notes.granola.ai/d/<id>
granola_id: <id>
---
# <título>

<1º de setembro de 2026 (terça-feira), 14:00>

<o resumo da Granola, literal>
```

- Não há campo `data`: o Daily notes do Obsidian o transformaria em link para uma nota que não existe, a armadilha do ticket 04 que `montar_resposta` já evita. A data fica no nome do arquivo e na linha do corpo, por extenso, no formato que `_data_por_extenso` já usa.
- `participantes` traz os nomes de `known_participants` sem o criador da nota (marcado `(note creator)`, que é sempre ele), sem e-mail e sem empresa.
- O resumo vai literal, mesmo em inglês. O Whis não traduz nem reescreve.
- Uma reunião **já está no vault** quando alguma nota de `reunioes/` tem `granola_id: <id>` no frontmatter. Quem decide é o id, não o nome, para que um título trocado na Granola não gere nota duplicada.

### O que a Granola devolve (medido em 2026-09-30, plano Basic)

- O texto de `list_meetings` (com `time_range` padrão `last_30_days`) e de `get_meetings` não é JSON, e `structured_content` vem vazio. É texto com marcação em formato XML:
  - um `<access_notice>` opcional e uma frase avisando que o conteúdo é dado;
  - um `<meetings_data from=… to=… count=…>` com um `<meeting id=… title=… date=… url=…>` por reunião (o `list_meetings` traz atributos a mais);
  - dentro de cada `<meeting>`, `<known_participants>` (texto) e, no `get_meetings`, `<summary>` (markdown).
- Os atributos e os textos vêm com entidades HTML (`&lt;`, `&amp;`); a leitura aplica `html.unescape`.
- A leitura usa expressão regular por elemento, não um parser de XML, porque o markdown do resumo não garante XML válido. Ela ignora tags que não conhece (pode haver `<private_notes>`, o que não foi confirmado). O formato de referência são as amostras em `tests/fixtures/granola/`. Exemplos:
  - `known_participants` é `Nome (note creator) from Empresa <email>, Nome from Empresa <email>, Nome <email>`;
  - a lista vazia é `<meetings_data count="0" />`.
- **A leitura falha alto** (`ErroDaGranola`) quando:
  - o texto não tem `<meetings_data`;
  - o número de `<meeting>` lidos difere do `count=` declarado;
  - uma reunião vem sem `id` ou sem `date`;
  - a `date` não é interpretada.

  Só assim um formato novo vira falha visível (código 1 e toast), em vez de "nada novo" todo dia até as reuniões passarem dos 30 dias.
- `date` vem como `Sep 1, 2026 2:00 PM GMT-3`. O mês é lido por tabela própria, sem depender de locale. O fuso `GMT±H[:MM]` (ou só `GMT`) vira `timezone`, e o resultado é convertido para a hora local.
- `get_meetings` aceita de 1 a 10 ids (`meeting_ids`, UUID). `get_meeting_transcript` responde `is_error` com "Transcripts are only available to paid Granola tiers" e não é chamado.
- Uma reunião sem `<summary>`, ou com o resumo vazio, ainda está sendo gerada. Ela é pulada e entra numa puxada seguinte.

### O login (`granola_login.py`)

- OAuth 2.0 com PKCE e registro dinâmico de cliente (DCR), feito pelo `OAuthClientProvider` do SDK `mcp` 2.0. O retorno chega em `http://127.0.0.1:33418/callback`, um servidor HTTP local que só vive durante o login. A porta é fixa porque o cliente registrado guarda esse redirect. Porta ocupada vira erro legível.
- A **guarda** implementa o `TokenStorage` do SDK e grava em `%APPDATA%\whis\granola.json` (ao lado do `config.toml`) o cliente registrado, os tokens e a hora em que o token de acesso vence (`expira_em`, calculada de `expires_in` menos 5 minutos de margem). O arquivo é cifrado com DPAPI (`win32crypt.CryptProtectData`, escopo do usuário), então só o usuário do Windows dele o abre. A escrita é atômica: um `.tmp` ao lado e depois `os.replace`.
- **A guarda renova o token antes de entregá-lo ao SDK.** Num processo novo, o SDK carrega o token guardado sem a hora de validade e o trata como válido. Se ele já venceu, o servidor responde 401, e o SDK refaz o login inteiro pelo navegador em vez de usar o `refresh_token` (lido em `mcp/client/auth/oauth2.py`, `_initialize` e `async_auth_flow`).
  - Por isso, quando `expira_em` já passou, `get_tokens` faz ela mesma o `grant_type=refresh_token` no `token_endpoint`, com `client_id` (e o `client_secret`, se o registro devolveu um) e `resource=https://mcp.granola.ai/mcp`. A renovação usa o `httpx` do projeto; o SDK usa o `httpx2`. Esse endpoint é descoberto pelo `/.well-known/oauth-protected-resource` e pelo `/.well-known/oauth-authorization-server` do servidor de autorização.
  - O `refresh_token` muda a cada uso, então o novo é gravado na hora. O teste de 2026-09-30 provou isso: HTTP 200, com token e `refresh_token` novos, e duração de 21.600 s.
  - Se a renovação for recusada (HTTP 400 ou 401), a guarda apaga os tokens (o cliente registrado fica) e `get_tokens` devolve `None`. O SDK cai então no login completo.
  - Falha de rede ou HTTP 5xx vira `ErroDaGranola` e **não** apaga nada. Um soluço de rede às 19:00 não pode custar um login novo.
  - Se a resposta não trouxer `refresh_token`, a guarda mantém o anterior.
- **Quem pode abrir o navegador:** o `redirect_handler` só abre se o adaptador foi criado com `pode_logar=True` (palheta e terminal). Com `pode_logar=False` (tarefa agendada), ele levanta `LoginNecessario` em vez de abrir. O login espera o retorno por no máximo 5 minutos.
- **Trava:** a sessão inteira do MCP (renovação, chamadas e gravação dos tokens) roda sob a trava de arquivo `%APPDATA%\whis\granola.lock`, no mesmo esquema de `msvcrt.locking` de `instancia.Trava`, mas esperando até 120 s em vez de recusar na hora.
  - Sem a trava, a palheta e a tarefa poderiam renovar ao mesmo tempo, e o `refresh_token` usado por uma invalidaria o da outra.
  - Passado o tempo de espera, o erro é "outra puxada da Granola está em andamento".

### O adaptador (`granola.py`)

- `GranolaMCP(guarda, *, pode_logar: bool, abrir_navegador=webbrowser.open)` implementa a porta.
- Cada operação abre uma sessão MCP (`streamable_http_client` + `ClientSession`) sob a trava e a fecha no fim, num `asyncio.run` próprio, porque as costuras do Whis são síncronas.
- Erros:
  - falha de rede, HTTP de erro ou `is_error` viram `ErroDaGranola`, com a mensagem da Granola;
  - falta de login sem permissão de abrir o navegador vira `LoginNecessario`, uma subclasse.
  - **O SDK embrulha as exceções.** Uma exceção levantada no `redirect_handler`, ou um erro de rede, sai do `streamable_http_client` como `ExceptionGroup`, porque o anyio 4.14 embrulha o que cai dentro do task group. O revisor da spec provou isso com uma sonda local. O adaptador varre o grupo (e as cadeias `__cause__`/`__context__`) e relevanta o `LoginNecessario` ou o `ErroDaGranola` que achar; o resto vira `ErroDaGranola`. Um teste passa pelo `streamable_http_client` real com `httpx2.MockTransport`, sem rede.
  - Quando `pode_logar=False`, o adaptador consulta a guarda antes de abrir a sessão. Sem token (nem renovável), levanta `LoginNecessario` sem tocar na rede.
  - Cada operação cria o seu `OAuthClientProvider`, porque ele guarda o token em memória e o `refresh_token` muda a cada uso.
- A leitura do texto fica em funções puras, testáveis sem rede: `ler_lista(texto) -> tuple[ReuniaoListada, ...]` e `ler_reunioes(texto) -> tuple[Reuniao, ...]`.

### A porta e a costura (`portas.py`, `reunioes.py`)

```python
@dataclass(frozen=True)
class ReuniaoListada:
    id: str
    titulo: str
    inicio: datetime          # com fuso

@dataclass(frozen=True)
class Reuniao:
    id: str
    titulo: str
    inicio: datetime
    participantes: tuple[str, ...]
    resumo: str               # markdown; "" quando a Granola ainda não gerou
    url: str

class ErroDaGranola(RuntimeError): ...
class LoginNecessario(ErroDaGranola): ...

class PortaReunioes(Protocol):
    def listar(self) -> tuple[ReuniaoListada, ...]: ...                    # últimos 30 dias
    def detalhar(self, ids: Sequence[str]) -> tuple[Reuniao, ...]: ...     # até 10 por chamada
```

`reunioes.puxar_reunioes(configuracao, porta) -> ResultadoDasReunioes`:

1. Prepara o vault e lê os `granola_id` que já estão em `reunioes/`.
2. Chama `porta.listar()`. Se falhar, o erro sobe: não há o que puxar.
3. Separa os ids que ainda não estão no vault, do mais antigo para o mais novo, e chama `porta.detalhar` em lotes de 10.
   - Um lote que falha com `ErroDaGranola` (que não seja `LoginNecessario`) entra em `falhas`, e os outros lotes seguem.
   - `LoginNecessario` sobe.
4. Para cada reunião detalhada: sem resumo, entra em `sem_resumo`; com resumo, escreve a nota pela zona `ZONAS_DAS_REUNIOES` e entra em `novas`.

`ResultadoDasReunioes(novas: tuple[str, ...], ja_no_vault: int, sem_resumo: tuple[str, ...], falhas: tuple[str, ...])`:

- `novas` traz caminhos relativos ao vault, em ordem cronológica;
- `sem_resumo` traz títulos;
- `falhas` traz **uma entrada por reunião**, no formato `"<título>: <motivo>"`. Uma reunião de lote que falhou e um id pedido que não voltou no `get_meetings` entram aqui, um por um.

O nome que colide com **qualquer** arquivo existente ganha sufixo, porque `vault.escrever` sobrescreveria sem avisar. O leitor de `granola_id` aceita o valor com ou sem aspas: `vault._frontmatter` põe aspas em UUID que começa por dígito e em URL.

Uma nota de reunião apagada no Obsidian **volta** na puxada seguinte, enquanto a reunião estiver nos 30 dias da Granola, porque o critério é o `granola_id` estar no vault. É o preço aceito de não manter um registro paralelo do que já foi puxado.

### A casca

- **`[granola]` no `config.toml`**: só `horario = "19:00"`. A explicação vai no modelo, e a chave entra em `CHAVES` (`Tipo.HORA`), no dataclass (`granola_horario`) e em `carregar_texto`, validada por `_hora`. As contagens dos testes passam de 26 para 27 (`test_painel.py`, `test_configuracao_escrita.py`). O painel mostra a chave.
- **CLI `whis meetings [--agendada] [--fakes]`**, no molde do `news`:
  - sem `--agendada`, pode abrir o navegador para o login;
  - com `--agendada`, não abre, e o toast só sai quando há nota nova ou falha (reunião só sem resumo não avisa: a puxada seguinte a pega);
  - `--fakes` usa `ReunioesFake`, sem rede, e escreve num **vault temporário**, cujo caminho é impresso, como o `news --fakes`. Uma reunião inventada no vault de verdade ficaria lá para sempre e seria lida pelo `ask`. Na bandeja com `--fakes`, `meetings` responde que não está disponível nesta execução.
  - Os códigos de saída seguem a convenção da casa:

    | Código | Quando |
    |---|---|
    | `0` | Puxou tudo que havia, mesmo sem nada novo ou só sem resumo |
    | `3` | Parcial: há notas novas e também falhas |
    | `1` | Nada: há falhas e nenhuma nota nova, sem login, `listar` falhou ou configuração inválida |
  - O `vigia.ps1` trata qualquer código diferente de zero como falha. Os códigos 1 e 3 da tarefa também aparecem na ronda dele, como já acontece com o `news`.
  - O relatório impresso lista as notas novas, as reuniões sem resumo e as falhas. Tudo vai também para o `bandeja.log`.
- **Agendamento**: `automacao.agendar_reunioes(configuracao)` registra `Whis-Reunioes` com gatilho `Daily=<granola_horario>`, rodando `meetings --agendada` pelo `pythonw`, com o trio `agendar/desagendar/reunioes_agendada`.
  - `whis windows --meetings` (e `--remover --meetings`) cuida dela e reagenda o vigia se ele existe, como o `--news`.
  - `tarefas_vigiadas` inclui `Whis-Reunioes` quando ela existe.
- **Palheta**: o comando `meetings`, com `rotulo="Pull meetings"`, `descricao="Granola meetings into reunioes/"` e `icone="◷"`. Entra em `ORDEM_DAS_ACOES` depois de `news`. Dispara e some, e pode abrir o navegador.
  - O toast é montado por `palheta.resultado_das_reunioes`, o mesmo para a palheta e para a CLI:
    - **com notas novas**: título "Reuniões no vault", texto "N reunião(ões) nova(s): <títulos>", e o botão abre a mais recente;
    - **sem nada novo**: "Nada novo na Granola";
    - **só reuniões sem resumo**: "Nada novo na Granola" com "N reunião(ões) ainda sem resumo; puxe de novo em alguns minutos";
    - **parcial**: acrescenta "; N não veio";
    - **só falhas**: título "As reuniões não vieram", com a primeira falha;
    - **falta de login**: título "A Granola pediu login", texto "Rode meetings na palheta.";
    - **outro erro**: o título de falha de sempre, com a mensagem.
  - O `login_do_claude` não se aplica aqui.
- **`pyproject.toml`**: `mcp>=2.0` passa a ser dependência direta, porque o Whis o importa.
- **Docs**:
  - `CONTEXT.md`: o verbete *Granola*; o *Coletor* deixa de dizer que só captura fontes passivas; a *Zona de propriedade* com `reunioes/` escrita pelo coletor da Granola; a *Palheta* com `meetings`.
  - ADR 0002: uma linha dizendo que o coletor foi construído.
  - `docs/smoke-reunioes.md`: o roteiro da prova.

## Testing Decisions

- **Sem rede na suíte.** As amostras de resposta ficam em `tests/fixtures/granola/` e seguem o formato medido em 2026-09-30, com conteúdo inventado: nenhuma reunião real dele entra no repositório.
- **Contratos com teste**, um por comportamento:
  - **leitura**: a lista com `access_notice`; os detalhes com resumo e participantes; as entidades; uma tag desconhecida ignorada; a data com `GMT-3`, `GMT+5:30` e `GMT` sem deslocamento; o resumo ausente vira `""`;
  - **costura**: escreve só a reunião nova; reconhece a reunião pelo `granola_id`, mesmo com o título trocado; pula a reunião sem resumo; escreve o nome com a hora local; aplica o sufixo `-2` quando o nome colide; respeita lotes de 10; um lote que falha dá parcial e o resto é escrito; `LoginNecessario` sobe; a nota tem o frontmatter certo e não tem `data`; nada é escrito fora de `reunioes/`;
  - **guarda**: ida e volta pelo DPAPI; o arquivo não guarda o token em texto claro; o token vencido é renovado com HTTP falso (`httpx.MockTransport`) e o `refresh_token` novo é gravado; a renovação recusada apaga os tokens e mantém o cliente; a trava entre dois donos;
  - **adaptador**: o `redirect_handler` com `pode_logar=False` levanta `LoginNecessario` sem abrir o navegador; o `is_error` vira `ErroDaGranola`. A sessão MCP entra por um dublê, e o SDK não é exercitado contra o servidor;
  - **casca**: os códigos de saída; `--agendada` sem nada novo não mostra toast; o toast de cada caso; a palheta tem `meetings` na ordem; o registro da tarefa; o vigia com e sem `Whis-Reunioes`; `[granola].horario` no painel e na escrita.
- O login de verdade, a puxada real e a tarefa ficam para a prova na máquina dele (`docs/smoke-reunioes.md`).

## Out of Scope

- A transcrição. No Basic não há; se ele assinar o Business, é outra entrega, pela API oficial.
- Reescrever ou atualizar uma nota já escrita (decisão dele: escreve uma vez só).
- Traduzir o resumo.
- `query_granola_meetings`: no teste, ele pediu esclarecimento até com o id da reunião.
- Pastas da Granola (`list_meeting_folders` é só dos planos pagos).
- Puxar antes de cada `ask`, ou pela bandeja de tempos em tempos (descartado na escolha do gatilho).

## Further Notes

- **Prazo:** as reuniões de 31/08 saem da janela de 30 dias em 2026-10-01, e a de 01/09 em 2026-10-02. A primeira puxada real decide se elas entram no vault.
- **Riscos declarados:**
  - o formato do texto do MCP não é contrato documentado: se mudar, a leitura falha alto (`falhas`/código 1), e a amostra do teste deve ser atualizada;
  - quanto tempo o `refresh_token` vale parado não está documentado: se vencer, o caminho é o login pela palheta.
- **Ordem de construção sugerida:**
  1. leitura e porta (puras);
  2. guarda (DPAPI, renovação, trava);
  3. adaptador;
  4. costura e nota;
  5. casca (configuração, CLI, palheta, tarefa e vigia);
  6. docs e a prova dele.
