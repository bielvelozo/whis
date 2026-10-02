# Research 02c — O Gmail dedicado

Levantado em 2026-10-02.

Parte do [ticket 02](../issues/02-onde-as-vagas-estao.md): o e-mail das contas novas é um **Gmail
só para isso** (ticket 06, rodada 3). Como o Whis lê essa caixa para confirmar conta nova e ver
resposta de cliente, rodando no PC dele, sem servidor (ADR 0001)? E precisa enviar por ela?

Convenção: **[fato]** está na fonte citada; **[código]** é o que o repositório faz hoje;
**[inferência]** é leitura minha; **[não reconferido]** é conhecimento anterior que não consegui
abrir nesta sessão — o proxy bloqueia `support.google.com`, `developers.google.com` e
`workspaceupdates.googleblog.com`, e a cota de busca acabou. **O status das senhas de app em 2026
é exatamente o que ficou sem fonte primária**; a camada 0 abaixo o resolve em um minuto, na conta
dele.

## Resumo

- **Recomendação: IMAP com senha de app, só leitura, `imaplib` da biblioteca padrão.** Zero
  dependência nova, nenhum projeto no Google Cloud, nenhum token que vence em 7 dias, e funciona
  numa tarefa da madrugada sem navegador. A senha de app fica cifrada com DPAPI, como o
  `granola.json` já faz.
- **Pré-requisito: verificação em duas etapas na conta dedicada.** Senha de app só existe com 2SV
  ligada; e não existe se a 2SV for só por chave de segurança/passkey ou se a conta estiver no
  Proteção Avançada [não reconferido]. O "acesso a apps menos seguros" (login IMAP com a senha
  normal) acabou para contas pessoais em 30/05/2022 [não reconferido] — não é opção.
- **Risco do caminho recomendado: o Google desligar senhas de app.** Ele as desestimula há anos,
  mas, até onde sei, seguiam existindo para contas pessoais [não reconferido para 2026]. Camada 0:
  ele abre `myaccount.google.com/apppasswords` na conta dedicada; se a página criar uma senha e o
  `imaplib` logar, o caminho está provado.
- **Plano B: API do Gmail com OAuth, app publicado "In production" sem verificação.** Em
  *Testing*, o refresh token vence em 7 dias [fato, citado do Google na research 02 da interface] —
  o mesmo modo de falha calado do login do Claude em 10/09. Publicado e não verificado, para uso
  pessoal (< 100 usuários), funciona com a tela "o Google não verificou este app" no consentimento
  e **sem** o vencimento semanal [fato de fonte secundária: doc do rclone citando as exceções de
  verificação do Google]. Publicar pede URL de página inicial e de política de privacidade (um
  GitHub Pages serve) [mesma fonte]. `gmail.readonly` é escopo **restrito** [não reconferido], o
  que só pesaria se o app fosse aberto a terceiros.
- **Descartados**: o conector Gmail do claude.ai (lê pelo modelo — gasta a assinatura por e-mail e
  põe texto de terceiro num contexto que tem a ferramenta de *enviar*); o Gmail pelo Playwright (o
  Google recusa login em Chrome automatizado — ADR 0003); o `gws` (não é produto oficial do Google e
  tem a mesma armadilha do OAuth). Um "MCP oficial do Gmail" pelo Google: não consegui confirmar
  que exista.
- **Entrega 1 (a caçada) provavelmente não precisa da caixa.** Ela não cria conta nem envia nada;
  se um site pedir login para listar vagas, ele cria a conta à mão. A leitura do Gmail entra na
  **entrega 2** (agir sozinho): confirmar conta nova e ver resposta de cliente.
- **Enviar e-mail pela conta: não, nas entregas 1 e 2.** Responder cliente é conversa — e "aceitar,
  fechar, marcar entrevista nunca sozinho" (ticket 06). Ele responde pelo Gmail. Se um dia for
  preciso, a mesma senha de app envia por SMTP (`smtp.gmail.com:465`), sem trocar de caminho.
- **E-mail é texto de terceiro.** A regra das vagas vale aqui: o leitor do e-mail não tem
  ferramenta; um link de confirmação só é seguido se o remetente e o domínio do link baterem com um
  site em que o próprio Whis criou conta (registro de ações, research 07), e golpe de vaga falsa
  ("mande seu CPF para…") vira linha no relatório, nunca ação.

---

## 1. As opções

### A. IMAP com senha de app

Como funciona [não reconferido, comportamento conhecido do Gmail]:

- Liga-se a **verificação em duas etapas** na conta dedicada; em *Segurança › Senhas de app* gera-se
  uma senha de 16 letras para "Whis". O Whis loga em `imap.gmail.com:993` (SSL) com o endereço e
  essa senha.
- O IMAP do Gmail fica sempre ligado — o interruptor nas configurações do Gmail foi removido em
  2024/2025 [não reconferido].
- A senha de app é **revogada quando a senha da conta muda**, e ele pode revogá-la a qualquer
  momento na mesma página [não reconferido].
- Ela dá acesso de e-mail **completo** (IMAP e SMTP, ler, apagar, enviar), não só leitura. Numa conta
  que só existe para isso, o estrago possível fica dentro dela [inferência].

No Whis [inferência]:

- `imaplib.IMAP4_SSL`, **`EXAMINE "INBOX"`** (abre só leitura) e `FETCH … (BODY.PEEK[])` — não
  marca nada como lido, e ele continua vendo o que é novo no Gmail. Busca por `SINCE` / `FROM` /
  `X-GM-RAW` (a busca do Gmail dentro do IMAP) [não reconferido para `X-GM-RAW`].
- O texto vira dado: remetente, assunto, data, corpo em texto, links extraídos em Python. O Claude
  só recebe o que o Python já separou.
- Segredo cifrado com DPAPI (`win32crypt.CryptProtectData`), como `granola_login.py` faz com os
  tokens da Granola [código]. O endereço vai no `config.toml` (ticket 06: *"o endereço vai no
  config, não no repositório"*); a senha, no arquivo cifrado — nunca no config.
- Falha de login (senha trocada, senha de app revogada) vira o mesmo padrão do login vencido do
  Claude e do X: linha no relatório e toast com o que fazer.

Prós: biblioteca padrão; nada a publicar; não vence por tempo; roda sem navegador numa tarefa
agendada. Contras: segredo com poder de conta inteira; depende de o Google manter senhas de app.

### B. API do Gmail com OAuth (app próprio no Google Cloud)

- **Projeto no Google Cloud**, API do Gmail ligada, tela de consentimento *External*, cliente OAuth
  do tipo *Desktop app*, ele mesmo como usuário de teste [fato, README do `gws` e doc do rclone, que
  descrevem o mesmo passo a passo].
- **Em *Testing***: *"Authorizations by a test user will expire seven days from the time of
  consent"* e o refresh token junto [fato, citado da doc do Google em
  [research 02 da interface](../../interface/research/02-windows-agendador-e-aviso.md)]. Um Whis
  que lê a caixa pararia toda semana — justamente na semana da corrida.
- **Publicado ("In production") sem verificação**: a doc do rclone, atualizada com as exceções do
  Google, diz que *"Personal Use apps: if the app is for your personal use (fewer than 100 users),
  you and your limited number of users can keep using it without verification - you will just need
  to click through the 'unverified app' warning screen"*, e recomenda *"publish it (rather than
  leaving it in 'Testing') to avoid the weekly grant expiry"* [fato, fonte secundária
  ([rclone][rclone]) citando [Google — exceções de verificação][excecoes]]. Para o botão "Publish"
  aparecer, *"Google now requires a homepage URL and a privacy policy URL before publishing, even for
  a personal single-user app"* [mesma fonte].
- **Escopo**: `gmail.readonly` é classificado como restrito (o mesmo grupo de `gmail.modify` e
  `https://mail.google.com/`) [não reconferido]; app público com escopo restrito exige verificação e
  avaliação de segurança anual — o que não se aplica a um app pessoal não verificado com menos de
  100 usuários [inferência a partir da exceção acima].
- **Outras mortes do refresh token** (documentadas pelo Google, já levantadas na research 02 da
  interface): seis meses sem uso, revogação, e **troca de senha quando há escopo do Gmail**.
- **No Whis**: `httpx` (já é dependência) contra `gmail.googleapis.com`, ou `google-auth` +
  `google-api-python-client` (duas dependências novas); token cifrado com DPAPI como o da Granola.
  Login pelo navegador **comum** uma vez (o fluxo de *loopback* do OAuth para app desktop abre o
  navegador padrão, não o Chrome do Playwright).

Prós: escopo só de leitura; nenhum segredo com poder de senha; busca do Gmail (`q=`), rótulos, e a
API de histórico para "o que chegou desde a última vez". Contras: projeto no Cloud, página de
política de privacidade, a tela de aviso, e mais um OAuth para manter vivo — o tipo de peça que
o projeto já viu cair calada.

### C. O conector Gmail do claude.ai (Anthropic)

- Faz *"Search and read emails"*, *"Draft emails"* e *"Send, reply to, and forward emails"*, sobre
  *"the Google account you've connected"* [fato, [support][conector]].
- Aparece no Claude Code quando o login é a assinatura do claude.ai; o Gmail **não aceita OAuth
  local pelo Claude Code** — conecta-se no claude.ai e ele aparece [fato, [MCP][mcp]].
- Contra, para o Whis [inferência]: os adaptadores rodam com `setting_sources=[]` e
  `strict_mcp_config=True` [código], que deixam os conectores de fora — teria de abrir a porta; cada
  e-mail passa pelo modelo e gasta a assinatura; o conector seria o da conta claude.ai **dele**, e o
  Gmail ligado ali é o que ele escolher (trocar para o dedicado tira o Gmail dele do claude.ai); e,
  sobretudo, junta no mesmo contexto texto de terceiro e a ferramenta de **enviar** — o oposto de
  "quem lê não é quem age". Há também relato de conector do claude.ai que não autentica em `-p`
  ([#91847][i91847]).

### D. O Gmail pelo navegador (Playwright)

O Google recusa login em Chrome controlado por automação (*"This browser or app may not be
secure"*) — provado pelo próprio Whis com o X [fato, ADR 0003]. Daria para logar num Chrome comum
e reaproveitar o perfil, como o `x-login`, mas ler a interface web do Gmail é frágil e lento. Não.

### E. Outras

- **`gws` (googleworkspace/cli)**: CLI para Gmail e Workspace, com *skills* para agentes; *"This is
  **not** an officially supported Google product"*, e usa o mesmo OAuth (app em *testing*, aviso de
  app não verificado) [fato, [README][gws]]. Não resolve nada que B não resolva.
- **MCP oficial do Gmail pelo Google**: não consegui confirmar que exista em 2026 (fontes do Google
  bloqueadas nesta sessão). Mesmo existindo, cairia no problema de C (texto de terceiro no contexto
  com ferramentas).
- **Apps Script na conta dedicada** exportando para uma planilha: troca um OAuth por outro e põe
  lógica fora do PC. Não.

## 2. Comparação

| | A. IMAP + senha de app | B. API + OAuth publicado | C. Conector claude.ai |
|---|---|---|---|
| Configuração | 2SV + gerar senha | projeto Cloud, consentimento, cliente, política de privacidade, publicar | conectar no claude.ai |
| Vence sozinho? | não (só troca de senha/revogação) | não se publicado; **7 dias** em *Testing* | segue o login do claude.ai |
| Poder do segredo | conta de e-mail inteira | só leitura | ler e **enviar** |
| Dependência nova | nenhuma | 0–2 bibliotecas | nenhuma, mas abre MCP nos adaptadores |
| Custo na assinatura | zero (Python lê) | zero (Python lê) | por e-mail lido |
| Separação leitor/agente | Python lê, Claude recebe dado | idem | não |
| Risco de sumir | Google tirar senhas de app | Google mudar regra de app não verificado | Anthropic/Google mudarem o conector |
| Fonte primária confirmada nesta sessão | não | parcialmente (7 dias sim; exceção pessoal por fonte secundária) | sim |

## 3. O que o Whis lê na caixa (entrega 2)

[inferência]

- **Confirmação de conta**: na corrida, depois de criar a conta no site X, procurar e-mail de
  remetente do domínio de X chegado depois da criação; extrair o link; **só seguir** se o domínio do
  link for o de X e houver `intencao` de criar conta em X no registro de ações (research 07, seção
  4). Seguir o link é uma ação externa e vai para o registro.
- **Resposta de cliente / recrutador**: classificar (resposta a proposta enviada, convite, recusa,
  golpe) e pôr no relatório com o link para ele abrir no Gmail. Nunca responder.
- **Código de verificação por e-mail** (alguns sites mandam um número em vez de link): mesmo
  critério do link — remetente e janela de tempo batendo com a ação que o pediu.
- **Quando ler**: nos pontos da corrida que esperam e-mail (com espera curta, poucos minutos) e uma
  vez no fim, para o relatório. Sem IDLE, sem processo escutando — sob demanda, como todo coletor.

## 4. Camada 0 (ele, uns 5 minutos)

1. Na conta Gmail dedicada: ligar a verificação em duas etapas (app autenticador ou telefone).
2. Abrir `https://myaccount.google.com/apppasswords`, criar "Whis". Se a página disser que a
   opção não está disponível, anotar a mensagem exata — é o sinal para o plano B.
3. Rodar um script de dez linhas com `imaplib`: `login`, `EXAMINE INBOX`, contar mensagens, listar
   os assuntos das cinco últimas sem marcar como lidas; conferir no Gmail que continuam não lidas.

## Fontes

- [Research 02 da interface — Google Calendar e o OAuth em *Testing*](../../interface/research/02-windows-agendador-e-aviso.md) (citações da doc do Google: *Manage app audience*, *Using OAuth 2.0*)
- [rclone — Google Drive: Making your own client_id][rclone] (exceções de verificação para uso pessoal; publicar para evitar a expiração semanal; URLs exigidas para publicar)
- [Google Cloud — Exceptions to verification requirements][excecoes] (não aberta: domínio bloqueado no proxy)
- [Google — Senhas de app][apppw], [Google — apps menos seguros][lsa], [Gmail API — escopos][escopos] (não abertas: domínio bloqueado no proxy)
- [Claude Help Center — Gmail connector][conector]
- [Claude Code — MCP: claude.ai connectors][mcp]
- [googleworkspace/cli — README][gws]
- [anthropics/claude-code#91847][i91847] (conector do claude.ai sem autenticar em `-p`)
- ADR 0003 (Google recusa login em Chrome do Playwright); `src/whis/granola_login.py` (DPAPI); `src/whis/busca_claude.py` e `jornal_claude.py` (`strict_mcp_config`, `setting_sources=[]`)

[rclone]: https://github.com/rclone/rclone/blob/master/docs/content/drive.md
[excecoes]: https://support.google.com/cloud/answer/13464323
[apppw]: https://support.google.com/accounts/answer/185833
[lsa]: https://support.google.com/accounts/answer/6010255
[escopos]: https://developers.google.com/workspace/gmail/api/auth/scopes
[conector]: https://support.claude.com/en/articles/10166901
[mcp]: https://code.claude.com/docs/en/mcp
[gws]: https://github.com/googleworkspace/cli
[i91847]: https://github.com/anthropics/claude-code/issues/91847
