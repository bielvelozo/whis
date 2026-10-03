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
- **Chances boas**: cada uma com o link do pacote. No pacote, a proposta pronta
  (num bloco de código, com o botão de copiar do Obsidian), preço e prazo,
  alertas, como enviar e, no freela web, a amostra.
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
