# Smoke manual: da bandeja à nota no Obsidian

O roteiro da demo-mestra da spec: *aperto um botão durante a reunião → nota
transcrita e resumida aparece no vault*. Valida o que nenhum teste automatizado
alcança — a bandeja de verdade no Windows, a captura do Meet, a Deepgram e o
Claude falando com as contas do usuário.

Rode na **máquina de destino** (o PC onde o Whis vai morar), com fone
conectado. Tempo: ~15 minutos, sendo ~5 minutos de reunião real.

Nos exemplos, `python` significa `.venv\Scripts\python.exe`.

Pré-requisito: o [smoke do gravador](smoke-gravacao.md) já passou nesta máquina.
Ele é o que prova que os dois canais capturam as vozes certas; aqui a captura é
dada como resolvida.

## Passo 0 — Configuração

```
python -m whis init
```

**Sucesso:** o comando diz onde criou o `config.toml` e lista os próximos
passos. Abra o arquivo e:

1. Confira `vault` e `gravacoes` — as duas pastas ficam **fora** do repositório,
   e `gravacoes` fica **fora** do vault.
2. Cole a chave da Deepgram em `[deepgram].api_key`.
3. Preencha `[audio]` se o smoke do gravador tiver exigido nomes de dispositivo.

**Falha:** se algum comando reclamar de `Invalid hex value`, o caminho está com
barra invertida. Use barras normais (`C:/Users/...`) — a mensagem de erro já
explica isso.

## Passo 1 — Ensaiar o gesto sem gastar crédito

Antes de depender da rede, faça o ciclo inteiro com as portas fake:

```
python -m whis bandeja --fakes
```

Grave 30 segundos de qualquer coisa: clique no ícone, fale, clique de novo.

**Sucesso:**

- o ícone aparece na bandeja (pode estar escondido na setinha "mostrar ícones
  ocultos" — arraste-o para a área visível, o Windows lembra disso);
- ao clicar, ele fica **vermelho cheio** e o tooltip diz `Gravando: reunião`;
- ao clicar de novo, ele passa por **âmbar** (processando) e volta a **cinza
  vazado**, com um balão dizendo `Reunião no vault`;
- a nota existe em `reunioes/` — o texto é fake, e isso é esperado.

**Falha:** se aparecer o balão `A gravação está saindo incompleta`, o canal
mudo é o do smoke do gravador — volte para [aquele roteiro](smoke-gravacao.md)
antes de gastar uma reunião real.

Feche pelo menu do ícone → **Sair**.

## Passo 2 — Subir a bandeja para valer

```
python -m whis bandeja
```

Deixe o terminal aberto (ele só imprime onde está o log). O ícone fica na
bandeja até você escolher **Sair**.

**Sucesso:** a primeira linha diz `Whis na bandeja. Log em ...`. Guarde
esse caminho: é onde qualquer problema desta sessão vai estar escrito.

## Passo 3 — A reunião

1. Entre no Meet e confirme que ouve o outro lado.
2. **Clique no ícone** — ele fica vermelho.
3. Participe normalmente por ~5 minutos, falando e ouvindo.
4. **Clique no ícone de novo.**

**Sucesso:** o ícone fica âmbar assim que você para. Durante a reunião, nenhum
balão de aviso apareceu.

**Falha:** se durante a reunião aparecer `A gravação está saindo incompleta`,
o loopback capturado não é a saída que está tocando o Meet — a reunião vai sair
só com a sua voz. Pare, ajuste `[audio].dispositivo_sistema` como o
[smoke do gravador](smoke-gravacao.md) ensina, e refaça.

## Passo 4 — Esperar o processamento

O ícone fica âmbar enquanto a Deepgram transcreve e o Claude resume. Para uma
reunião de 5 minutos, conte alguns minutos.

**Sucesso:** o ícone volta a cinza e aparece o balão `Reunião no vault` com o
nome do arquivo.

**Falha:** ícone vermelho escuro com risco branco e o balão `A reunião não virou
nota`. Leia a mensagem — ela diz o que falhou. A gravação **não se perdeu**:

```
python -m whis reprocessar
```

completa a reunião depois que o problema (rede, chave, cota) estiver resolvido,
e não chama a Deepgram de novo se a transcrição já tinha vindo.

## Passo 5 — Abrir o vault no Obsidian

Abra o vault como cofre no Obsidian (a pasta que está em `vault` na
configuração).

**Sucesso, e este é o critério que fecha o smoke:**

- em `reunioes/` existe `YYYY-MM-DD-HHMM-<slug>.md` com o frontmatter completo
  (`data`, `tipo`, `participantes`, `transcricao`) e um resumo **em português**
  com decisões, ações/pendências e tópicos que você reconhece da conversa;
- o wikilink `transcricao` abre a transcrição em `transcricoes/`;
- a transcrição distingue a sua fala da dos outros e preserva os termos em
  inglês como foram ditos (deploy, review, rollback...);
- `notas/` continua vazia ou intacta — o coletor nunca escreve lá.

**Falha:** se o resumo estiver em inglês, ou os termos técnicos virarem ruído,
anote a nota gerada e reporte — é ajuste de prompt (camada 04) ou de parâmetro
da Deepgram (camada 03), não de configuração.

## Passo 6 — Conferir a retenção

O áudio bruto fica 7 dias fora do vault e some depois. Confira sem apagar nada:

```
python -m whis limpar --simular
```

**Sucesso:** a reunião de hoje aparece como **preservada**, com o motivo
"transcrita há 0 h, dentro dos 7 dias de retenção".

Rode `python -m whis limpar` (sem `--simular`) de tempos em tempos, ou
agende a tarefa no Windows. Gravações que falharam nunca são apagadas.

## Se a bandeja não aparecer

- O ícone pode estar na área oculta da bandeja: clique na setinha `^` ao lado do
  relógio e arraste o ícone para fora.
- Se o comando terminar sozinho, leia o `bandeja.log` indicado no passo 2 — erro
  de configuração aparece lá com o arquivo e a chave que faltou.
- Um antivírus que bloqueie o acesso ao microfone derruba o canal, não a
  bandeja: nesse caso o ícone sobe e o aviso de canal mudo aparece.
