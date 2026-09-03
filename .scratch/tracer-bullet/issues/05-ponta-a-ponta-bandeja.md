# 05 — Ponta a ponta na bandeja

**What to build:** O tracer bullet completo, no gesto decidido: um ícone na bandeja do Windows com liga/desliga da gravação e indicação visual de estado (gravando/parado). Parar a gravação dispara o pipeline automaticamente (gravador do 02 → pipeline do 01 com adapters reais do 03 e 04) e a nota aparece no vault sem nenhum passo manual. É a demo-mestra da spec: *aperto um botão durante a reunião → nota transcrita/resumida aparece no vault*.

**Blocked by:** 02 — Gravador WASAPI sob demanda; 03 — STT real: adapter Deepgram; 04 — Resumo real: adapter Claude.

**Status:** ready-for-human

- [x] Ícone na bandeja inicia e para a gravação com um clique e mostra o estado atual sem ambiguidade
- [x] Parar a gravação dispara o processamento completo sem interação extra
- [ ] Smoke manual da spec executado: reunião real no Meet → nota com resumo + transcrição linkada no Obsidian
- [x] Erros do pipeline aparecem de forma visível/diagnosticável (a bandeja não engole falhas)
- [x] A bandeja é casca fina: nenhuma lógica de pipeline vive nela

## Comments

**Camada 05 entregue** — `src/second_brain/coletor.py`, `src/second_brain/bandeja.py`, os subcomandos `bandeja` e `init` em `src/second_brain/__main__.py`, a ponte `gravador.de_configuracao()`, o roteiro `docs/smoke-ponta-a-ponta.md` e os testes em `tests/test_coletor.py` e `tests/test_bandeja.py`. Suíte: **204 passaram, 3 desselecionados**.

**A separação que faz a camada ser testável.** A spec exige que a bandeja seja casca fina, e casca fina não se prova por inspeção. O gesto virou dois módulos: o **coletor** (`second_brain.coletor`) é a máquina de estados — grava, para, dispara a costura `processar()` em outra thread, lembra do resultado — sem uma linha de UI; a **bandeja** é pixels, cliques e balões sobre ele. Assim tudo o que o ícone promete ao usuário é provado por teste de comportamento, e sobra para o smoke manual só o que é mesmo de hardware e de tela.

Um teste guarda o critério explicitamente: `test_a_bandeja_nao_conhece_o_pipeline` lê o fonte do módulo e falha se ele passar a importar pipeline, vault, adaptadores ou portas.

**Estados visíveis sem ambiguidade.** Quatro desenhos distintos como imagem (círculo vazado cinza = parado, círculo cheio vermelho = gravando, anel âmbar = processando, vermelho escuro com risco = falhou) — cor sozinha seria ambígua — e o tooltip repete tudo por escrito em português. Um teste compara os bytes dos quatro ícones para garantir que continuam diferentes entre si.

**Erros não são engolidos**, em quatro lugares ao mesmo tempo: ícone de erro, tooltip com a mensagem, balão do Windows com o comando de recuperação (`reprocessar`) e o `bandeja.log` ao lado do `config.toml` — sem console, ele é a única forma de diagnosticar a reunião de ontem (user story 18). A gravação que falhou continua retida, como a camada 06 previu.

**Um acréscimo além dos critérios, e a razão dele.** Na primeira execução real nesta máquina o canal do sistema saiu mudo (nada tocando) e isso só apareceu no log — exatamente a falha que arruinaria uma reunião inteira, porque a nota sairia só com a voz do usuário. A camada 02 já tinha construído `Gravador.niveis()` "para a bandeja mostrar canal mudo"; agora o coletor confere os níveis 20 s depois do início e, se um canal estiver em silêncio digital, a bandeja avisa **durante** a reunião, com o conserto na mensagem. Avisar não é falhar: o estado continua `gravando`.

**Itens do DEFERRED que esta camada fecha:** `second-brain init` cria o `config.toml` com caminhos válidos e comentários (era escrito à mão antes); a mensagem de TOML inválido agora ensina o caso do caminho com barra invertida, em vez de só repetir "Invalid hex value"; e a leitura de configuração duplicada some no caminho que o produto usa — a bandeja lê uma vez e converte pela ponte `gravador.de_configuracao()`.

**Provas executadas nesta máquina** (bandeja de verdade, pystray real, gravador real, portas fake — sem chave da Deepgram aqui):

- Ciclo completo: ícone visível → clique → `gravando` com áudio real captado (`microfone.wav` e `sistema.wav`, 48 kHz, ~3 s) → clique → `processando` → `parado`, com a nota e a transcrição lidas no disco, frontmatter completo e wikilink correto. O `bandeja.log` registrou o caminho inteiro, do dispositivo de cada canal até "Reunião no vault".
- Falha real de STT na bandeja: ícone e tooltip viraram `Falhou: Deepgram devolveu 503`, nenhuma nota parcial foi escrita, `estado.json` ficou `falhou` com o erro, e `second-brain reprocessar` depois completou a mesma gravação no vault.
- Aviso de canal mudo com o loopback apontado de propósito para uma saída silenciosa: o tooltip passou a `Gravando: reunião — nenhum áudio está entrando...` e o balão saiu com a instrução de ajustar `[audio].dispositivo_sistema`. O veredito bateu com o do gravador ao fechar os arquivos (RMS 0,9 e 0,5, ambos MUDO).
- `second-brain init` num caminho limpo: o arquivo gerado é lido de volta por `carregar()` sem erro, com barras normais.

**Decisão deliberada: a bandeja não apaga áudio sozinha.** O `DEFERRED.md` sugeria a bandeja rodar a limpeza ao iniciar. Deixei de fora: apagar é irreversível e o usuário não pediu que acontecesse sem ele saber. A limpeza continua em `second-brain limpar`, com `--simular`, e o roteiro de smoke ensina a agendar.

Achados registrados em `.scratch/tracer-bullet/DEFERRED.md`: nada impede duas bandejas simultâneas disputando os dispositivos; a bandeja não sobe com o Windows; toda gravação pela bandeja nasce sem título; e a duplicação de leitura de configuração sobrevive só no CLI do gravador, de propósito.

**O que falta para a camada fechar — critério 3, e é do usuário.** O smoke de ponta a ponta com um Meet real, a chave da Deepgram e o Claude está escrito em `docs/smoke-ponta-a-ponta.md` e precisa ser executado na máquina de destino. É o mesmo critério que fecha o tracer bullet inteiro.

**Metade do critério 3, provada em reunião real (2026-09-03).** A reunião de 40
minutos virou nota no vault com Deepgram e Claude de verdade: 623 falas, 7
decisões, 12 ações, 14 tópicos, `participantes: [Daniel, Zeno, João, Biel,
Ribeiro]` inferidos da conversa pelo Claude, transcrição linkada por wikilink e
o usuário confirmando que o resumo é fiel. Tempo total do pós-gravação: **76
segundos** para 40 minutos de reunião (23 s + 24 s de transcrição, 37 s de
resumo).

**O que ainda falta: o gesto.** A reunião já tinha começado quando o usuário
pediu para gravar, então a captura foi disparada por um script chamando o mesmo
`Coletor` — não pelo clique no ícone. A bandeja em si foi exercitada hoje com
pystray real, gravador real e áudio real (registrado acima), mas nunca durante
uma reunião de verdade. O critério fecha na próxima reunião, com um clique.

**Acabamento entregue (2026-09-03)** — `src/second_brain/instancia.py`,
`src/second_brain/janelas.py`, `src/second_brain/automacao.py`,
`src/second_brain/registro.py` e o subcomando `windows`, com testes em
`tests/test_acabamento.py`. Suíte: **227 passaram, 3 desselecionados**.

Quatro furos que só apareceriam no uso diário, fechados de uma vez:

- **Instância única.** Duas bandejas disputando os mesmos dispositivos é como
  uma reunião acaba não sendo gravada por ninguém. A trava é bloqueio de faixa
  do próprio Windows (`msvcrt.locking`), não um arquivo-marcador — o sistema a
  libera sozinho quando o processo morre, então um crash não exige limpeza
  manual. Verificado: segunda instância recusada com o PID de quem segura,
  processo morto com `taskkill`, terceira instância subiu normalmente.
- **Sobe com o logon.** `second-brain windows` cria um atalho na pasta de
  Inicialização apontando para `pythonw.exe -m second_brain bandeja` (sem
  console piscando). Verificado de ponta a ponta com `APPDATA` temporário, para
  não mexer na inicialização real da máquina: o `.lnk` foi criado e relido pelo
  `WScript.Shell` com alvo, argumentos e diretório corretos, e `--remover` o
  apagou.
- **Título automático.** Sem lugar para digitar, o nome da reunião sai da janela
  do Meet/Zoom/Teams. Código de sala (`abc-defg-hij`) é descartado de propósito:
  não é nome de coisa nenhuma. É palpite, então só vira nome de arquivo, e um
  palpite que exploda não derruba a gravação (teste cobre). Verificado que a
  varredura de janelas funciona nesta máquina (10 janelas, nenhuma reunião
  aberta → `None`, correto).
- **Limpeza agendada.** `second-brain windows --limpeza` registra uma tarefa
  diária no Agendador rodando `limpar`. Verificado de verdade: criada sem
  privilégio de administrador, conferida no `schtasks /Query` (12:00, comando
  certo, apontando a mesma configuração) e removida em seguida, sem deixar
  resíduo.

**Furo encontrado durante a verificação e corrigido:** a tarefa agendada roda com
`pythonw.exe`, que não tem console — o relatório do que foi apagado iria para o
nada. O log de arquivo saiu da bandeja para `second_brain.registro` e agora o
`limpar` também escreve nele. Confirmado no `bandeja.log` da máquina.

O critério 3 continua aberto: falta o clique numa reunião real.
