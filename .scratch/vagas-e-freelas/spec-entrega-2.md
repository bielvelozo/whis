# Spec: agir sozinho fora do LinkedIn (entrega 2 de vagas e freelas)

Status: ready-for-human — construída em 2026-10-03 e provada sem rede (20 testes em
`tests/test_contas_e_envio.py`); a prova real é o [smoke](../../docs/smoke-contas.md). Decisão
registrada no [ADR 0004](../../docs/adr/0004-o-whis-age-fora-do-pc.md).

## Solution

- **`whis contas`** (`accounts` na palheta, num processo próprio): para cada site de *Contas* em
  `cacada/criterios.md`, só o passo que falta — **criar** (senha sorteada e guardada no cofre antes,
  intenção registrada, o agente do navegador cadastra com o Gmail dedicado e os dados de
  `[cacada]`), **confirmar** (lê o Gmail por IMAP e segue o link só do site pedido) e **completar o
  perfil** (título, resumo e habilidades a partir de `cacada/perfil.md`). O que ficou pendente vai
  para `cacada/contas.md`, sem senha; `whis contas --senha <site>` mostra a de um site no terminal.
- **Na caçada**, depois das mensagens de tentar a sorte: com `[cacada].enviar_sozinho = true`, as
  que a política deixa saem pelo agente, até `[cacada].maximo_de_envios`, com intenção e desfecho no
  registro; o relatório marca cada uma (*Enviada pelo Whis* / *precisa de você*) e diz quantas
  saíram. Com o Gmail configurado, a caçada lista no relatório o que chegou nos últimos 14 dias.
- **`whis navegador [url]`**: o Chrome da caçada, comum, para ele entrar à mão (Gupy com Google,
  por exemplo). O agente usa a mesma sessão depois.

## Implementation Decisions

- **A política** (`politica.py`): só tentar a sorte, só vaga, domínio em Gupy, Greenhouse, Lever,
  Ashby, Workable, Breezy, Recruitee ou Teamtailor; nunca LinkedIn, golpe ou repetido. Freela
  nunca (research 02b).
- **O registro** (`acoes.py`, `%LOCALAPPDATA%\whis\cacada\acoes.jsonl`): só acrescenta; intenção
  antes, desfecho depois; intenção sem desfecho nunca é refeita sozinha.
- **O agente** (`navegador_agente.py`): Agent SDK + Playwright MCP (`npx @playwright/mcp`), Chrome
  com o perfil da caçada, `--blocked-origins` no LinkedIn, ferramentas só de página, saída
  estruturada (`feito` / `precisa_de_voce` / `nao_feito`), mesma guarda do plano da caçada.
- **Os dados que ele digita**: nome, telefone, cidade, CPF e nascimento no `config.toml` (fora do
  vault, que o `ask` lê); GitHub, portfólio, LinkedIn e currículo de *Sobre mim*.
- **O Gmail** (`caixa.py`): IMAP com senha de app (`[cacada].senha_de_app`), `EXAMINE` e
  `BODY.PEEK`, sem modelo; confirmação seguida só por regra em código.
- **Contas e caçada usam a mesma trava**: o perfil do Chrome é um só.
- **`enviar_sozinho` nasce `false`** [agente]: a primeira caçada mostra se as mensagens prestam;
  ligar é uma chave no `settings`.

## Out of Scope

- Freela sozinho (nenhum site é grátis e sem limite); qualquer coisa no LinkedIn; responder e-mail;
  aceitar proposta, contrato ou entrevista; pagar plano ou *connects*.
