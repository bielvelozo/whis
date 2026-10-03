# Smoke manual: contas nos sites e candidatura sozinho

Roteiro **na sua máquina**, no PowerShell 5.1, de dentro de
`C:\Users\gabri\development\whis` (`python` = `.venv\Scripts\python.exe`). Decisão no
[ADR 0004](adr/0004-o-whis-age-fora-do-pc.md); spec em
`.scratch/vagas-e-freelas/spec-entrega-2.md`. Faça depois do
[smoke da caçada](smoke-cacada.md).

## Riscos declarados

- **É você agindo, pelo Whis.** As contas e as candidaturas saem no seu nome, com o Gmail dedicado.
  Tudo fica em `%LOCALAPPDATA%\whis\cacada\acoes.jsonl` (o que, onde, quando, o texto enviado).
- **Termos dos sites.** Alguns não aceitam automação (a Workana fala em "meios automatizados"). O
  Whis não passa por CAPTCHA nem por verificação: isso é seu.
- **Nada testado contra os sites reais** daqui: o primeiro uso é a prova. Comece com um site só.

## Passo 0 — Pré-requisitos

1. Node.js no PATH (`npx -v` responde) — é o mesmo do Claude Code.
2. No Gmail dedicado: verificação em duas etapas ligada e uma **senha de app** em
   <https://myaccount.google.com/apppasswords>.
3. Na palheta, `settings`, em `[cacada]`: `email`, `senha_de_app`, `nome`, `telefone`, `cidade`
   e, se quiser candidatura na Gupy, `cpf` e `nascimento`. Em `cacada/criterios.md`, *Sobre mim*:
   GitHub, portfólio, LinkedIn e o caminho do currículo em PDF.

## Passo 1 — Um site só, com você olhando

```
python -m whis contas --so Workana
```

O Chrome da caçada abre e o agente cadastra. **Se aparecer CAPTCHA, resolva na própria janela**: o
agente espera uns minutos. **Sucesso:** `Workana: conta ✓ e-mail ✓ perfil ✓`, e
`cacada/contas.md` no Obsidian. **Pendente:** a linha diz o que falta (telefone, documento...);
faça no site e rode de novo — ele continua do passo que falta.

A senha está no cofre: `python -m whis contas --senha Workana`.

## Passo 2 — Os outros sites

```
python -m whis contas
```

ou `accounts` na palheta. Corre site por site; Upwork e Fiverr costumam pedir documento: ficam
pendentes. Uma criação que caiu no meio **não é refeita sozinha** — confira no site.

## Passo 3 — Os logins com Google

Sites em que você prefere entrar com Google (a Gupy, por exemplo):

```
python -m whis navegador https://portal.gupy.io
```

Entre e feche a janela. O agente usa a mesma sessão.

## Passo 4 — Ligar o envio sozinho na caçada

Só depois de uma caçada em que as mensagens de *tentar a sorte* soaram como você: `settings`,
`[cacada].enviar_sozinho = true` (e `maximo_de_envios`, padrão 10).

Na caçada seguinte, as vagas de tentar a sorte na Gupy e nos ATS das empresas saem sozinhas.
**Nunca** freela, **nunca** LinkedIn, **nunca** chance boa, **nunca** a mesma vaga duas vezes. No
relatório: "O Whis enviou sozinho N candidatura(s)", e cada uma marcada *Enviada pelo Whis* ou *O
Whis começou e precisa de você*.

## Passo 5 — A caixa

Com `email` e `senha_de_app` preenchidos, o relatório da caçada ganha *Caixa do Gmail dedicado*: o
que chegou nos últimos 14 dias. O Whis só lê; responder é com você.
