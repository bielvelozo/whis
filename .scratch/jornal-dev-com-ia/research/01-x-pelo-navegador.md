# 01 — O X pelo navegador

Status: aguardando a conta do Whis no X (precisa dele)

A camada 0 do [spec](../spec.md). O leitor (`src/whis/fonte_x.py`) já existe, escrito com a
estrutura conhecida do HTML do X; o protótipo usa o próprio leitor para provar o que só a conta de
verdade responde.

## Antes de rodar (ele)

1. Criar a conta do Whis no X **com o idioma em inglês** (Settings → Accessibility, display and
   languages → Languages).
2. Seguir a lista inicial do spec, conferindo cada @.

## Rodar

Da raiz do repositório, no PowerShell dele (não numa sessão de agente: o `%LOCALAPPDATA%` dela pode
ser outro):

```
.venv\Scripts\python.exe .scratch\jornal-dev-com-ia\research\01-x-pelo-navegador\prototipo.py --login
.venv\Scripts\python.exe .scratch\jornal-dev-com-ia\research\01-x-pelo-navegador\prototipo.py
```

Se a segunda falhar em todas as páginas, rodar de novo com `--com-janela`.

## O que responde

- O X aceita o Chrome sem janela com a sessão válida? O Chrome sem janela se anuncia como
  `HeadlessChrome` no user agent (visto em 2026-09-30, Chrome 154). Se o X recusar, o caminho do
  spec é o Chrome com janela minimizada: `SEM_JANELA = False` em `fonte_x.py`.
- Quantos posts úteis cada página traz nas últimas 24 h, e se os `min_faves` do modelo cortam
  demais ou de menos (`medidas.json`, campo `curtidas`).
- Como a página marca anúncio, repost, busca vazia, a hora e as curtidas: comparar `amostras/` com
  `tests/fixtures/jornal/x/` e trocar as fixtures pelas reais.

## Resposta

(preencher com as medidas da primeira rodada)
