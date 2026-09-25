# Smoke manual: o jornal do Whis

Roteiro da prova do jornal **na sua máquina**, no seu PowerShell 5.1. O
`%APPDATA%` que uma sessão de agente enxerga não é o seu: tarefa agendada,
toast e `config.toml` só contam quando **você** os vê. A entrega só fecha no
passo 7, com a edição das 08:20 lida no celular.

Rode tudo de dentro de `C:\Users\gabri\development\whis`. Nos exemplos,
`python` significa `.venv\Scripts\python.exe`. No PowerShell 5.1 não existe
`&&`: um comando por linha.

## Riscos declarados

- `CLAUDE_CODE_ARTIFACT=1` (liga a ferramenta Artifact no SDK) e o parâmetro
  `files` (as capas) **não são documentados**; o `files` depende de um flag
  remoto. Se sumirem, a publicação falha, a nota continua no vault e o toast
  diz que a página não saiu. Plano B para ler: a nota no Obsidian do PC.
- `unifiedWindows` (o consumo do plano) é interno: se sumir, o cabeçalho diz
  "sem leitura do plano".
- A API de placar da ESPN não é documentada e os termos da Disney proíbem
  acesso automatizado. Uso pessoal, 14 chamadas por dia; se quebrar, a seção
  diz "Placar indisponível hoje" e segue com as manchetes. A alternativa
  legítima (football-data.org) não traz artilheiro.

## Passo 1 — Sem Claude

```
python -m whis news --fakes
```

**Sucesso:** a lista de seções com contagens, "Simulação — nada publicado" e
o caminho de uma `jornal.html` numa pasta temporária. Abra essa página no
navegador: papel claro, seções numeradas, capas.
**Falha:** "O jornal não nasceu" = nenhum feed respondeu (sem rede).

## Passo 2 — Com o Claude, sem publicar

```
python -m whis news --simular
```

**Sucesso:** o mesmo, agora com títulos em português, resumos, *Aprender
hoje* e *Para aprender*, e a linha de custo (≈ US$ 0,60) e do plano.
**Falha:** "Faltou: seleção automática indisponível" = o editor não
respondeu; olhe `bandeja.log`. Credencial vencida: `claude login`.

## Passo 3 — A edição de verdade

```
python -m whis news
```

**Sucesso:** "Página: https://claude.ai/artifact/AYhYVZDhevQdWv4YaNuoge" (o
mesmo endereço do protótipo, que já está no seu favorito) e a nota
`noticias/AAAA-MM-DD.md` no Obsidian. Abra o link no celular.
**Falha:** "A página não saiu" — a nota existe; a mensagem diz por quê.

## Passo 4 — O toast

No fim do passo 3 chega o toast *O jornal de hoje está pronto*, com o botão
**Abrir jornal**. Clique.

**Sucesso:** o navegador abre a página do jornal.
**Falha:** botão que não faz nada — o Windows não abriu o `https://` pelo
toast; anote e me diga.

## Passo 5 — A tarefa das 08:20

```
python -m whis windows --news
Get-ScheduledTask -TaskName Whis-Noticias | Get-ScheduledTaskInfo
```

**Sucesso:** `NextRunTime` amanhã às 08:20. No Agendador, a tarefa tem
"Executar a tarefa o mais cedo possível após uma inicialização agendada ter
sido perdida" marcada. Para desligar sem apagar: `[noticias].ativa = false`
no painel (`settings` na palheta).

## Passo 6 — Uma fonte a mais ou a menos

Abra `noticias/fontes.md` no Obsidian. Apague uma linha `- Nome: URL` ou
acrescente uma; troque um nome em `## Nomes`. Rode o passo 2.

**Sucesso:** a fonte some/aparece (ou aparece em "Não responderam" se a URL
estiver errada). O Whis nunca reescreve esse arquivo.

## Passo 7 — A prova de verdade

Amanhã, **sem rodar nada**, abra o favorito no celular depois das 08:20 (ou
depois de ligar o PC, se ele estava desligado).

**Sucesso:** a data de hoje e a hora da edição no topo, as seis seções, o
placar (ou "sem jogo"), e o consumo do plano. Preencha:

### Quanto pesa na assinatura

| Data | Duração | ≈ US$ | Plano 5 h | Plano semana |
|---|---|---|---|---|
| | | | → | → |
| | | | → | → |
| | | | → | → |

Se uma edição passar de 15 min ou de US$ 2, olhe primeiro a formação (buscas)
e o tamanho dos candidatos no `bandeja.log`.
