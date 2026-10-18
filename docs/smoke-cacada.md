# Smoke manual: a caçada de vagas e freelas

Roteiro da primeira caçada **na sua máquina**, no seu PowerShell 5.1. A sessão
de agente que construiu a caçada não alcança os sites de vaga (a rede dela
bloqueia quase todos): os leitores foram escritos pelos formatos documentados
e por um projeto que lê a Workana e a 99Freelas todo dia, mas **só o passo 2
prova que cada fonte responde de verdade**. Spec em
`.scratch/vagas-e-freelas/spec.md`.

Rode tudo de dentro de `C:\Users\gabri\development\whis`. Nos exemplos,
`python` significa `.venv\Scripts\python.exe`. No PowerShell 5.1 não existe
`&&`: um comando por linha.

## Riscos declarados

- **Nada é enviado.** A caçada lê, julga e escreve no vault. Candidatura,
  proposta, conta nova e LinkedIn continuam com você nesta entrega.
- **Leitores sem prova real.** Gupy (JSON do portal, não documentado),
  Workana e 99Freelas (HTML público), a busca pública do LinkedIn (dá 429
  depois de umas 10 páginas por IP) e as APIs de vaga remota. Fonte que falha
  aparece no relatório como "não respondeu", e as outras seguem.
- **Termos de uso.** A Workana proíbe "meios automatizados"; a caçada só lê a
  listagem pública, sem conta, três páginas por corrida. O LinkedIn é lido só
  pela busca pública, **nunca pela sua conta**.
- **O plano do Claude.** A caçada gasta o que sobrou da semana. Ela para
  sozinha quando o plano semanal chega a 100% (`[cacada].teto_semanal`), e
  sempre 5 min antes da virada, para não comer a semana nova. Se você rodar
  com a virada a mais de 36 h, ela para em 70%: a rede de segurança para a
  cota do trabalho. A leitura do plano depende do
  `claude.exe` do npm (≥ 2.1.274), o mesmo que o jornal já usa.

## Passo 0 — Atualizar

```
git pull
.venv\Scripts\pip install -e .
```

**Sucesso:** o pip sobe o `claude-agent-sdk` para 0.2.140 ou mais novo (é o que
entrega o erro de limite do plano com o motivo). Feche e abra a bandeja pelo
ícone (*Sair*) e de novo pelo atalho de logon: só assim a palheta ganha o
comando `hunt`.

## Passo 1 — Sem rede e sem Claude

```
python -m whis hunt --fakes
```

**Sucesso:** "Vault temporário: …", e no fim "3 chances boas (3 com pacote) · 1
para tentar a sorte · 2 descartadas". Abra o relatório no vault temporário,
num editor de texto, para ver o formato.

## Passo 2 — As fontes, sem Claude (a camada 0)

```
python -m whis hunt --simular
```

Cria `cacada/criterios.md` no seu vault, se ainda não existe, e lê cada fonte
da seção *Fontes*: diz quantas oportunidades cada uma trouxe, com três
títulos, e quais **não responderam**. Leva de 1 a 3 minutos.

**Sucesso:** a maioria das fontes com número. **Anote as que não
responderam**: é o primeiro conserto. Uma fonte quebrada não impede a caçada.

## Passo 3 — Os seus critérios

Abra `cacada/criterios.md` no Obsidian. É sua: o Whis nunca escreve nela.

- *O que eu procuro* já vem com o que você decidiu (piso, cidades, freela,
  golpe, LinkedIn). Corrija o que quiser.
- **Responda *Sobre mim***: anos de experiência, cargo e se pode citar a
  empresa, formação e semestre, inglês, horas livres, GitHub, portfólio,
  LinkedIn e currículo. É o que mais muda a qualidade das propostas. Item em
  branco vira pergunta no relatório.
- *Fontes*: apague a linha de uma fonte para desligar; acrescente com o mesmo
  formato.

Na palheta, `settings`: preencha `[cacada].email` com o Gmail dedicado.

## Passo 4 (opcional) — O link público das amostras

Sem isto, a amostra do freela fica só no vault, com um print para anexar.
Com isto, ela ganha um link `https://conceitos-xxxxxx.pages.dev/<amostra>/`,
sem o seu nome, que sai do ar em 30 dias.

1. Crie uma conta grátis no Cloudflare (com o Gmail dedicado).
2. *My Profile → API Tokens → Create Token*, modelo *Edit Cloudflare
   Workers*, ou um token só com **Account → Cloudflare Pages → Edit**.
3. Copie o *Account ID* (aparece na lateral do painel).
4. Na palheta, `settings`: `[cacada].cloudflare_token` e
   `[cacada].cloudflare_conta`.

Precisa do Node (o `npx` do mesmo Node em que o Claude Code está instalado).

## Passo 5 — A caçada de verdade

Na véspera da virada semanal do plano (a hora está em claude.ai → Settings →
Usage), num terminal para ver o andamento:

```
python -m whis hunt
```

ou pela palheta: `ctrl+space`, `hunt`, Enter. A janela some e a caçada corre
num processo próprio. Ela não trava a palheta.

Para a caçada de **freelas rápidos**, só no terminal:

```
python -m whis hunt --freelas
```

Antes, `python -m whis hunt --simular --freelas` mostra que só as fontes de
freela são lidas (Freelancer.com com as buscas do modo, 99Freelas, Workana) e
lista as seis linhas `web` do explorador. **Sucesso:** o relatório se chama
*Caçada de freelas rápidos*, nenhuma vaga de emprego aparece em chance boa, e
cada resumo de freela diz quantas horas leva e o preço. Cada linha `web` do
modo pode levar até 1 h (o explorador vai a fundo). Se ela acabar o principal
antes da virada da semana do plano, o andamento mostra a etapa `extra`
("buscando mais", depois "caprichando") e as chances boas passam de "Abrir o
resumo" para "Abrir o pacote"; se a virada chegar no meio do principal, chega
o toast de pausa até a virada e ela continua sozinha depois.

Com `[cacada].nicho_freela = "shopify"` no config, o `--simular --freelas` diz
"Nicho: shopify", lista as buscas do Freelancer.com que saíram por estar fora
do nicho e termina com *Podem ser chance boa (do nicho)*: só o que cita Shopify
(ou e-commerce perto, no título) pode virar chance boa; o resto fica no máximo
em tentar a sorte, com o motivo "fora do nicho (shopify)". O perfil desse modo
sai em `cacada/perfil-freelas.md`, e `cacada/perfil.md` (o de vaga) não muda.
Com `[cacada].piso_freela` (em R$), o preço de resumo abaixo do piso termina
com "Abaixo do seu piso: peça pelo menos R$ N."

**Sucesso:** o toast *A caçada começou*. Ela leva horas: perfil (1 a 3 min),
fontes (5 a 15 min), o explorador na web (10 a 40 min por linha `web`),
triagem (1 min a cada 20 oportunidades), pacotes (2 a 5 min cada, até 20) e
mensagens de tentar a sorte. O PC não suspende enquanto ela corre.

Para ver em que pé está: `hunt` de novo na palheta mostra a etapa atual. O
relatório `cacada/AAAA-MM-DD-HHMM.md` é reescrito ao fim de cada etapa.

Se a janela de 5 h bater, chega o toast *A caçada pausou* com a hora em que
ela volta. Ela espera sozinha, com o PC acordado.

## Passo 6 — O resultado

No fim chega o toast *A caçada terminou*, com o botão que abre o relatório no
Obsidian. Confira:

- **Antes de tudo**: o que o Whis quer que você responda em *Sobre mim*.
- **Chances boas**: por padrão, cada uma com o link do resumo ("Abrir o
  resumo"): *O que pedem*, *Por que casa*, *Ponto fraco* (uma frase) e
  *Salário*, sem proposta nem como enviar; e as tentar a sorte sem mensagem
  pronta. Com `[cacada].pacote_completo = true` no config, o link vira "Abrir o
  pacote" e vale o resto deste item. No pacote, a proposta pronta
  (num bloco de código, com o botão de copiar do Obsidian), preço e prazo,
  alertas, como enviar e, no freela web, a amostra. Confira também: o *O que
  pedem* diz se é período integral, meio período ou freela; o *Preço* começa
  pelo número pronto para o campo (moeda e unidade da vaga); a vaga com
  formulário traz *Respostas de formulário*, uma por linha; o *Como enviar* diz
  qual currículo anexar; e a proposta lê como alguém digitando, sem passos
  numerados nem travessão de efeito.
- **Tentar a sorte**: a mensagem curta, recolhida, e como enviar.
- **Descartadas**: recolhidas, com o motivo de cada uma. Se uma boa caiu aqui,
  é sinal para ajustar *O que eu procuro*.
- **Fontes**: quantas cada uma trouxe e quais não responderam.

**Se parou antes do fim** (toast *A caçada parou antes do fim*), o relatório
diz por quê. Rodar `hunt` de novo continua de onde parou, sem refazer o que já
estava pronto. Para começar outra do zero: `python -m whis hunt --do-zero`.

## O que devolver ao próximo agente

- A saída do passo 2 (quais fontes não responderam e o motivo).
- O relatório da primeira caçada: quantas chances boas, se as descartadas
  fazem sentido, se as propostas soam como você.
- O `bandeja.log` (`%APPDATA%\whis\`), se algo falhou.

## Passo 7 — O acompanhamento

Depois de enviar uma chance boa, abra o pacote e troque `status: preparada` por `enviada` (e
depois `entrevista`, `proposta`, `recusada` ou `fechado`). No fim de cada caçada — ou na hora, com
`python -m whis candidaturas` — `cacada/candidaturas.md` junta os seus pacotes, o que o Whis enviou
sozinho e, com o Gmail configurado, os e-mails que parecem ser resposta da empresa.

Freela tem o **Funil** no relatório: as notas de `cacada/` com link de plataforma de freela e
`status:` começando por `enviada` (ou `respondida`, `entrevista`, `proposta`, `fechado`, `recusada`)
contam por semana do envio. A data vem de "enviada em AAAA-MM-DD" no `status:`; sem ela, da pasta.
Das que ainda estão `enviada`, o Chrome da caçada abre o projeto no fim da corrida: na 99Freelas,
"aberto, esperando o cliente" ou "o cliente já escolheu um freelancer"; no Freelancer.com, "sua
proposta em 60º de 98". Quando o cliente responder, troque o `status:` (o Whis não lê a conversa).

## Passo 7a — O que os clientes pedem e as agências do mês

```
python -m whis o-que-pedem
```

**Sucesso:** "N anúncios de shopify em M caçadas" e uma linha por pedido (montar a loja, checkout e frete,
tema e seção, app e integração...), com a mediana do teto do orçamento em dólar; a nota sai em
`cacada/o-que-pedem.md`, com os exemplos de cada pedido e os que nenhuma regra reconheceu.

```
python -m whis agencias --fakes
```

**Sucesso:** "Agências do mês: 1 agência nova" (a fictícia; a Aloft, que já está na lista, sai). Sem
`--fakes` ela usa o Claude, uma vez por mês (`--forcar` repete), e acrescenta a seção do mês em
`cacada/agencias-shopify-novas.md`. A caçada de freelas inteira faz isso sozinha quando o mês ainda não foi
feito. Nada é enviado a ninguém.

## Passo 7b — A vigia de freelas

```
python -m whis vigia-freelas --fakes
```

**Sucesso:** um toast *Freela de Shopify novo: Ajuste no tema da loja Shopify (teste)* com o botão
"Abrir o projeto". Depois, com `[cacada].nicho_freela` no config:

```
python -m whis windows --vigia-freelas
```

**Sucesso:** "Vigia de freelas agendada como 'Whis-Vigia-Freelas'", nas horas de
`[cacada].horarios_da_vigia_de_freelas`. A primeira rodada só guarda o que já está aberto; dali em
diante, cada projeto novo de Shopify na 99Freelas ou no Freelancer.com vira um toast (até três por
rodada, e um "Mais N"). Atenção: `whis windows --remover --vigia-freelas`, como os outros
`--remover`, também tira a bandeja do logon.

## Passo 7c — O celular e a proposta automática

1. No Telegram, o @BotFather (`/newbot`) cria o bot; mande `/start` para ele. Depois:

```
python -m whis celular
```

**Sucesso:** pede o token sem mostrar, diz "Bot @... encontrado", acha o chat e grava `[celular]`; chega
"Pronto: o Whis vai te avisar aqui..." no celular. `python -m whis celular --teste` manda outra.

2. `python -m whis vigia-freelas --fakes` agora também manda ao celular um *Ensaio: esta proposta sairia
agora na 99Freelas* com um projeto falso (sem Claude, sem Chrome, vault temporário).

3. Entre na 99Freelas pelo `python -m whis navegador` e **feche o Chrome**. Com
`[cacada].propostas_auto = "ensaio"`, cada rodada da vigia escreve a proposta dos projetos novos que
passam nas travas, preenche o formulário sem clicar e manda o texto ao celular; as notas ficam em
`cacada/propostas-auto/` e o dia em `cacada/propostas-auto.md`. Só com `"ligado"` ela envia.

4. Com a bandeja no ar (reinicie depois de gravar `[celular]`), a proposta do ensaio e a que não sai
sozinha (cota cheia, 80 propostas ou mais, conexões na reserva; até `[cacada].propostas_auto_para_aprovar`
por dia) chegam com o botão **Enviar esta proposta**. `python -m whis celular --pendentes` manda de novo
as que esperam o toque.

**Sucesso:** o toque mostra "Recebido" na hora; em cerca de um minuto chega a resposta na conversa
("Enviada na 99Freelas: ... sobram N conexões"), o botão some, a nota vira `status: enviada` e o
projeto mostra "Melhorar proposta" no site. Chrome ocupado ou deslogado responde o motivo e deixa o
botão para tocar de novo.

## Passo 8 — O lembrete da véspera

```
python -m whis windows --hunt
```

**Sucesso:** "Lembrete da caçada agendado como 'Whis-Lembrete-Cacada'". Todo dia em
`[cacada].hora_do_lembrete` (20:00) ele olha se a semana do plano vira nas próximas 30 h e, se
vira, mostra **um** toast por semana: *Véspera da virada do plano*. Antes da primeira caçada ele
ainda não sabe a hora da virada e faz uma sonda de um turno do Haiku para descobrir. Ele só
lembra: soltar a caçada continua com você. Para conferir agora: `python -m whis lembrete`.

