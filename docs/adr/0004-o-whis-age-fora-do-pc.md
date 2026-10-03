# O Whis age fora do PC em nome dele: contas nos sites e candidaturas de tentar a sorte

> Registro de 2026-10-03.

Até aqui o Whis só lia (git, Linear, Slack, X, Granola) e escrevia no vault e nos artifacts dele. A
entrega 2 de vagas e freelas é a primeira vez que ele **age fora do PC, no nome dele**:

- **cria contas** nos sites de vaga e freela de `cacada/criterios.md` com o Gmail dedicado,
  confirma o e-mail e completa o perfil (`whis contas`, com ele no PC);
- **se candidata sozinho** às vagas de *tentar a sorte* durante a caçada, quando
  `[cacada].enviar_sozinho = true`.

Quem age é o Claude da conta dele dirigindo um Chrome pelo **Playwright MCP** oficial, num perfil
só da caçada (`%LOCALAPPDATA%\whis\navegador-cacada`). Os logins que pedem Google são feitos à mão
num Chrome comum nesse perfil (`whis navegador`), como no ADR 0003. Spec em
`.scratch/vagas-e-freelas/spec-entrega-2.md`.

## Por quê

É o pedido dele, com as bordas dadas por ele no grilling (tickets 01 e 06 de
`.scratch/vagas-e-freelas/`): *"ele pode inclusive criar contas para mim em sites diferentes e
começar a buscar e aplicar"*; o envio sozinho só no que tem pouca chance e só onde mandar é grátis
e sem limite; no LinkedIn, nada.

## As bordas, e onde cada uma mora

- **Quem envia é decidido em código** (`politica.py`), não no prompt: só *tentar a sorte*, só vaga,
  só Gupy e os ATS das empresas (Greenhouse, Lever, Ashby, Workable…), nunca LinkedIn, nunca golpe,
  nunca duas vezes. **Freela nunca sai sozinho**: a pesquisa 02b não achou site de freela grátis e
  sem limite.
- **O registro vem antes da ação** (`acoes.py`, só acrescenta): intenção, depois desfecho. Uma
  intenção sem desfecho nunca é refeita sozinha.
- **O agente lê páginas de terceiros**: as ferramentas são só as de página (sem `evaluate`, sem
  código, sem cookie), o LinkedIn é bloqueado no navegador, o único arquivo é o currículo copiado
  para a pasta de trabalho, e o prompt manda tratar o conteúdo das páginas como dado.
- **Pagar, aceitar contrato, marcar entrevista**: nunca. **CAPTCHA, telefone e documento**: dele —
  o agente espera na tela alguns minutos e devolve "precisa de você".
- **O Gmail é só lido** (IMAP `EXAMINE` e `BODY.PEEK`); um link de confirmação só é seguido se o
  remetente e o link forem do site onde o próprio Whis registrou a intenção de criar conta.
- **Senhas** sorteadas e guardadas no cofre (DPAPI) antes de o agente começar; nunca no vault nem
  no log.
- **O envio sozinho nasce desligado**: liga quando a primeira caçada mostrar que as mensagens de
  tentar a sorte soam como ele.

## Considered Options

- **Só preparar, ele envia tudo**: a entrega 1. Continua sendo o caminho de toda chance boa.
- **Robô por site em Playwright puro** (seletores escritos à mão): cada cadastro muda sem aviso, e
  seriam dezenas de formulários de ATS diferentes.
- **Navegador logado no LinkedIn**: recusado por ele (os colegas o seguem) e pelos termos do
  LinkedIn (research 08).

## Consequences

- Os termos de alguns sites não aceitam automação (a Workana fala em "meios automatizados"); o risco
  de suspensão de conta é dele, e ele o aceitou ao pedir as contas. O Whis não tenta passar por
  CAPTCHA nem por verificação.
- O agente gasta a assinatura por tela; cada candidatura custa alguns minutos de plano.
- Durante a construção, o classificador de segurança da sessão de agente bloqueou uma vez a
  edição que criava a lista de contas; ele pediu de novo, explicitamente, e a construção seguiu.
