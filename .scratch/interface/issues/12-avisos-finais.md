# 12 — Camada 5: o toast com botão e a URI do Obsidian

Type: task
Status: resolved
Blocked by: 09

**What to build:** o aviso que abre a nota certa com um clique, e o conserto do gesto da bandeja
que nunca abriu o Obsidian.

Spec: [../spec.md](../spec.md), *Os avisos*. Fatos: [research/04](../research/04-obsidian-como-interface.md) §1,
[research/02](../research/02-windows-agendador-e-aviso.md) §2.

- [x] Quando a daily nasce (`whis daily`, agendada ou pela palheta), toast *"A daily está pronta"*
      com botão **Abrir no Obsidian** → `obsidian://open?vault=245833c11ad43e6e&file=daily%2Fatual`
      (`activationType="protocol"`). O ID do vault vem de configuração (`[obsidian].vault`), com
      o valor levantado no modelo.
- [x] `vault.uri_do_obsidian(caminho_relativo)` com `quote(valor, safe='')` (nunca `+` para
      espaço).
- [x] `bandeja.abrir_no_windows`: nota do vault abre por URI; pasta continua por `os.startfile`.
- [x] Armadilha da Daily notes: o roteiro final instrui o usuário a desligar o plugin de núcleo
      ou apontá-lo para `daily/`; do lado do Whis, nada muda no frontmatter (decisão do plano).
- [x] Suíte inteira verde.

## Notas para o executor

- Reaproveite `avisos.py` da camada 2; aqui entra só o botão e quem o chama.
- Com o Obsidian fechado, o Windows lança o `Obsidian.exe` com a URI; o que ele faz ao subir do
  zero não foi testado — entra no roteiro final como conferência do usuário.

## Comments

**Camada 5 construída** (2026-09-12, executor "windows"; sem commit, nenhum toast e nenhuma
abertura real).

- Novos: `src/whis/obsidian.py` (`nome_do_vault`, `uri_da_nota`) e `tests/test_avisos_finais.py`
  (21 testes). A URI mora em módulo próprio porque `test_a_bandeja_nao_conhece_o_pipeline`
  proíbe a bandeja de importar `vault` — `vault.uri_do_obsidian` existe como pedido e delega.
- Alterados: `configuracao.py` (`obsidian_vault`, `[obsidian].vault`), `vault.py`
  (`uri_do_obsidian`), `__main__.py` (`[obsidian]` no modelo; toast após `gerar_daily`;
  `texto_do_toast_da_daily`), `bandeja.py` (`alvo_para_abrir`, `abrir_no_windows(caminho,
  configuracao, *, lancar)`, `_lancar` com a segunda porta por `cmd /c start`).
- Suíte: **966 verdes** (eram 945), 8 desselecionados. Nenhum teste existente editado.
- O checkbox da Daily notes está marcado pelo lado do Whis (nada muda no frontmatter); a linha
  do roteiro final é da sessão principal.

**Camada 5 entregue e fechada** (2026-09-12; executor `windows`, revisão e gate na sessão principal).

- `src/whis/obsidian.py` (`nome_do_vault`, `uri_da_nota` com `quote(safe='')`, `\` → `/`); mora fora de
  `vault.py` porque a bandeja não pode conhecer o vault (regra provada por teste existente).
  `[obsidian].vault` no modelo com o ID `245833c11ad43e6e`; vazio = nome da pasta.
- Toast ao nascer a daily (título `A daily está pronta`, texto com os itens novos/movidos ou a falha,
  botão `Abrir no Obsidian` → `obsidian://open?vault=245833c11ad43e6e&file=daily%2Fatual`). Só quando a
  nota viva existe e não é `--simular`; o código de saída não muda.
- `bandeja.abrir_no_windows(caminho, configuracao)`: `.md` dentro do vault → URI por `os.startfile`,
  com `cmd /c start "" <uri>` se o `ShellExecute` recusar; pasta e arquivo fora do vault como antes.
- Suíte: **966 verdes** (eram 945; 21 novos em `tests/test_avisos_finais.py`); nenhum teste existente editado.
- A abertura real da URI **não foi sondada** aqui de propósito: abre o Obsidian e reescreve
  `.obsidian/workspace.json` dentro do vault do usuário. Entra no roteiro final como conferência dele
  (com o Obsidian aberto e fechado), junto com a Daily notes.
