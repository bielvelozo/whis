# Spec: recuperação de contexto — o agente no Slack

Status: ready-for-agent

Origem: [mapa second-brain](../second-brain/map.md) e [Como o agente recupera
contexto](../second-brain/issues/08-recuperacao-de-contexto.md). Escopo fechado com o usuário em
2026-09-04. Glossário em `CONTEXT.md`; ADR 0001 (projeto separado, 100% local) governa a
arquitetura.

> **Esta spec foi reescrita em 2026-09-04.** A primeira versão entregava a busca por comandos de
> terminal (`second-brain perguntar "..."` e `second-brain chat`). O usuário recusou, e com
> razão: *"muito complexo e nada prático — eu abrir um terminal, digitar o comando e mandar minha
> pergunta"*. Um comando por pergunta é formulário, não conversa. O sinal já estava na mesa e eu
> não usei: a bandeja fica ligada o dia inteiro e ele vive no Slack.

## Problem Statement

O vault já tem memória: reuniões transcritas, diários e dailies com as listas cruas de git,
Linear e Slack. Mas ele só responde a quem abre o Obsidian e procura à mão, sabendo de antemão em
que dia a coisa aconteceu.

E o momento em que a pergunta aparece — "o que ficou decidido com o Luan sobre o link coringa?" —
é no meio do trabalho, muitas vezes dentro do próprio Slack, quinze segundos antes de responder
alguém. Qualquer interface que exija sair do fluxo, abrir terminal e montar um comando **não vai
ser usada**, por melhor que a busca seja.

## Solution

Um agente que **mora numa DM do Slack**. O usuário manda mensagem a qualquer hora, do PC ou do
celular, e ele responde ali mesmo — buscando no vault, citando os arquivos de onde tirou cada
afirmação, e consultando git, Linear e Slack ao vivo quando o vault não bastar.

A conversa **lembra por 24 horas**: pergunta de manhã, volta à tarde e o fio continua. Depois de
24 horas sem falar, começa limpo.

Do lado da máquina, um processo que fica escutando — sobe com o logon, junto da bandeja que já
existe. Sem servidor, sem porta aberta: a conexão sai do PC para o Slack (Socket Mode), como
qualquer outra chamada de API que o projeto já faz.

## User Stories

1. Como usuário, quero mandar mensagem para o agente numa DM do Slack e receber a resposta ali, para perguntar sem sair do que estou fazendo.
2. Como quem está no celular, quero perguntar de fora do PC, para o segundo cérebro não depender de eu estar sentado na mesa.
3. Como quem investiga, quero que a conversa lembre do que eu disse antes, para fazer pergunta de acompanhamento sem repetir contexto.
4. Como quem volta no dia seguinte, quero que o fio expire em 24 horas, para uma conversa velha não contaminar uma pergunta nova.
5. Como quem confere, quero a resposta **citando as notas** de onde veio, para eu abrir a fonte e checar.
6. Como usuário, quero que ele diga "não achei" quando não achar, para eu nunca confundir invenção com memória.
7. Como dono das minhas notas, quero uma pasta privada que a busca **nunca** abre, para escrever coisa pessoal no vault sem ela ir ao Claude.
8. Como quem trabalha agora, quero que ele consulte git, Linear e Slack ao vivo quando o vault não tiver a resposta, para perguntar sobre o que aconteceu há dez minutos.
9. Como dono da minha privacidade, quero que a consulta ao vivo respeite as mesmas réguas da daily, para a blocklist do Slack continuar valendo.
10. Como usuário, quero saber que ele está trabalhando na minha pergunta, para não achar que travou enquanto ele busca.
11. Como usuário, quero que ele escreva em `notas/` só quando eu pedir, para a minha zona continuar minha.
12. Como quem deixa o PC ligado, quero que o agente suba sozinho com o logon, para não precisar lembrar de ligar nada.

## Implementation Decisions

- **A interface é uma DM do Slack**, com um **bot** na app interna que já existe. Confirmado na
  documentação em 2026-09-04: Socket Mode exige um **app-level token** (`xapp-`) e um **bot
  token**; o user token `xoxp` de leitura que o usuário já tem **não** serve para receber
  mensagem. Isso custa um passo humano novo — ver *Further Notes*.
- **Socket Mode, não webhook.** A conexão é de dentro para fora, sem porta aberta nem URL
  pública, que é o que mantém o ADR 0001 de pé numa máquina doméstica.
- **Bot, e não o user token postando como o usuário.** A alternativa era o agente responder na
  auto-DM usando `chat:write` no user token — menos configuração, mas as respostas apareceriam
  com o nome do próprio usuário, e um `chat:write` de usuário permite postar como ele em
  **qualquer** conversa do workspace. Um bot que só fala na própria DM é melhor de usar e mais
  fácil de o admin aprovar.
- **Costura única**: `responder(pergunta, conversa) → Resposta`. O Slack é uma casca fina sobre
  ela, como a bandeja é sobre o coletor. Um comando de terminal (`second-brain perguntar`)
  continua existindo **para teste e diagnóstico**, não como o caminho principal.
- **Processo próprio, não dentro da bandeja**: `second-brain atender`. A bandeja tem trava de
  instância e máquina de estados de gravação; misturar as duas coisas arriscaria o pipeline de
  reunião, que está em uso. `second-brain windows` passa a poder instalar os dois no logon.
- **O fio da conversa expira em 24 horas** de silêncio, e vive num arquivo pequeno ao lado do
  `config.toml` — não no vault. Não é memória durável: é rascunho de conversa, e o vault não deve
  guardar rascunho.
- **O agente não recebe o vault cru — recebe ferramentas nossas.** Isto **refina o ticket 08**,
  que dizia "agente com `cwd` no vault, grep/leitura". Com acesso livre ao disco, a pasta privada
  passaria a depender de o modelo obedecer, que é a garantia fraca que já recusamos nas DMs. Com
  ferramentas próprias, a fronteira é verificada no **nosso** código, em um ponto só, e testável.
  O espírito do ticket 08 continua: busca agêntica, sem índice, o modelo decidindo onde olhar.
- **Pasta privada configurável**: `[privacidade].pastas_privadas = []`. O que estiver sob elas não
  aparece na busca, não é lido e não é citado — nem sob pedido.
- **Toda resposta cita a fonte.** Afirmação sem arquivo ao lado é indistinguível de invenção.
- **Fontes ao vivo pelos coletores existentes**, como ferramentas. Reaproveitar não é economia de
  código: é o que faz a blocklist do Slack, o `so_com_mencao` e o filtro de exclusão continuarem
  valendo numa consulta ao vivo, sem ninguém precisar lembrar deles.
- **Sinal de que está trabalhando**: o bot reage à mensagem assim que a recebe e responde depois.
  Uma busca pode levar dezenas de segundos, e silêncio nesse tempo parece pane.
- **Custo por resposta no log**, no formato que a entrega anterior fixou: equivalente da tabela
  da API, com o aviso de que a assinatura não cobra por token.
- **Idioma**: tudo em português.

## Testing Decisions

- **Costura única**: `responder(pergunta, conversa, busca=BuscaFake())`. O fake guarda o que
  recebeu — é assim que se prova o que **não** foi enviado ao Claude.
- **A fronteira da pasta privada é o teste que mais importa**: arquivo dentro dela não aparece na
  busca, não é lido nem por caminho com `..`, e não chega ao fake. Sondada nos dois sentidos,
  como a zona de propriedade já é.
- **O Slack é testado sem Slack**: o cliente de Socket Mode entra por porta injetada, e os testes
  entregam eventos de mensagem como fixture. Nenhum teste novo fala com serviço real fora de
  `@pytest.mark.rede`.
- **A expiração de 24 horas é comportamento**, testada com relógio injetado: mensagem dentro da
  janela continua o fio, fora dela começa limpo.
- Prior art: as duas entregas anteriores. Costura única, fakes nas portas, zero mock de detalhe
  interno.

## Out of Scope

- **Índice semântico e RAG** — gatilho de reavaliação continua o do ticket 08: mais de ~2.000
  notas ou buscas conceituais falhando na prática.
- **Comportamento proativo** (o agente falar sem ser perguntado) — depende de uso real.
- **Canais do Slack** — o agente só atende na DM dele. Responder em canal é decisão nova, com
  outra conversa sobre privacidade.
- **Voz, imagem e anexo** na conversa.
- **Busca de vagas e freelance**; **backup do vault** — seguem no mapa como não especificados.

## Further Notes

- **Passo humano novo, e ele bloqueia a camada do Slack**: acrescentar um **bot** à app interna
  que já existe, com os scopes de bot `im:history`, `im:read`, `chat:write` e `reactions:write`,
  ligar **Socket Mode**, gerar o **app-level token** e assinar o evento `message.im`. O
  [roteiro do Slack](../../docs/smoke-slack.md) dizia ao admin que a app **não** pediria bot
  token; isso muda, e o pedido precisa ser refeito. O argumento a favor: um bot que só lê e
  escreve na própria DM é bem menos invasivo que o user token que já foi aprovado.
- As camadas que não dependem do Slack (costura, fronteira, agente, fontes ao vivo) podem ser
  construídas e provadas **antes** da aprovação, pelo comando de diagnóstico.
- `[privacidade].excluir` continua **vazio** na máquina do usuário: o filtro nunca foi exercitado
  com um padrão real, e ele passa a importar mais com a consulta ao vivo.
- O vocabulário segue o glossário: **Vault**, **Zona de propriedade**, **Fonte passiva**, **Sob
  demanda**.
