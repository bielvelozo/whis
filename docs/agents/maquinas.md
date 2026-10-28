# Onde roda cada coisa

O Gabriel tem duas máquinas, e o app do Claude abre sessão nas duas. Antes de começar, rode `$env:COMPUTERNAME` para saber em qual delas você está. Faça a tarefa só se ela couber nessa máquina. Se não couber, avise e diga em qual ela tem que ser feita.

## As duas máquinas

**note-biel** (o notebook dele; Tailscale 100.108.176.76)
É onde o Whis vive. Ficam lá:
- as tarefas `Whis-*`, a bandeja, o bot do Telegram e o `%APPDATA%\whis\config.toml` com as senhas e chaves;
- a Granola e o Obsidian aberto, que sincroniza o vault `C:\Users\gabri\whis-vault`;
- o Chrome que o Claude in Chrome controla.

O código do Whis de lá é o único atual.

**servidor** (`DESKTOP-FVOEMG4`; "laptop server" no app; Tailscale 100.122.210.76)
O app conecta aqui por SSH. Ficam aqui:
- o checkout do site `C:\Users\gabri\development\gabrielvelozo-site`, na branch `especime-v4`, que é a que vai para produção;
- o wrangler logado na conta Cloudflare dele;
- um clone do Whis parado em 20/10 (5c4d551), sem a Resend, sem config e sem tarefas;
- o vault, mas sem o Obsidian aberto. Por isso o que se escreve nele daqui não chega ao note.

## O que fazer em cada uma

| Tarefa | Onde |
|---|---|
| Código do Whis: mudar, testar, rodar a suíte, commitar | note-biel |
| Rodar o Whis: tarefas, bandeja, Telegram, envio de e-mail, Granola, config | note-biel |
| Escrever no vault (notas, `cacada/`, `voz.md`) | note-biel. No servidor, só com o Obsidian aberto lá |
| Site velozo.dev: mudar e publicar (`wrangler pages deploy site`) | servidor |
| Gmail, Google Admin, Cloudflare, PostHog e outros sites pelo navegador | qualquer uma (o Chrome é o do note-biel) |
| Pesquisa, rascunho de texto, plano, análise | qualquer uma |

## Atenção

- **O Whis no servidor:** o commit feito lá só chega ao note-biel por `git bundle` ou pelo GitHub, e o push é ele quem dá. Teste lá não prova nada sobre o Whis de verdade, porque o clone do servidor é velho e não tem config.
- **O deploy do site:** o checkout do site no note-biel está na `main` velha. Em 28/10, um deploy rodado de lá publicou o site antigo por cima do novo.
- **Da sessão do servidor para o note-biel:** dá para rodar comando lá por `ssh` pelo Tailscale (100.108.176.76), mas só se o OpenSSH Server do note-biel estiver ligado e com a chave do servidor autorizada. Confira antes com `Test-NetConnection 100.108.176.76 -Port 22`.
