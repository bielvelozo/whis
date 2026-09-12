# 12 — Camada 5: o toast com botão e a URI do Obsidian

Type: task
Status: ready-for-agent
Blocked by: 09

**What to build:** o aviso que abre a nota certa com um clique, e o conserto do gesto da bandeja
que nunca abriu o Obsidian.

Spec: [../spec.md](../spec.md), *Os avisos*. Fatos: [research/04](../research/04-obsidian-como-interface.md) §1,
[research/02](../research/02-windows-agendador-e-aviso.md) §2.

- [ ] Quando a daily nasce (`whis daily`, agendada ou pela palheta), toast *"A daily está pronta"*
      com botão **Abrir no Obsidian** → `obsidian://open?vault=245833c11ad43e6e&file=daily%2Fatual`
      (`activationType="protocol"`). O ID do vault vem de configuração (`[obsidian].vault`), com
      o valor levantado no modelo.
- [ ] `vault.uri_do_obsidian(caminho_relativo)` com `quote(valor, safe='')` (nunca `+` para
      espaço).
- [ ] `bandeja.abrir_no_windows`: nota do vault abre por URI; pasta continua por `os.startfile`.
- [ ] Armadilha da Daily notes: o roteiro final instrui o usuário a desligar o plugin de núcleo
      ou apontá-lo para `daily/`; do lado do Whis, nada muda no frontmatter (decisão do plano).
- [ ] Suíte inteira verde.

## Notas para o executor

- Reaproveite `avisos.py` da camada 2; aqui entra só o botão e quem o chama.
- Com o Obsidian fechado, o Windows lança o `Obsidian.exe` com a URI; o que ele faz ao subir do
  zero não foi testado — entra no roteiro final como conferência do usuário.
