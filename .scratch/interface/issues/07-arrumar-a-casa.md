# 07 — Camada 0: arrumar a casa

Type: task
Status: resolved
Blocked by: nada

**What to build:** o que falta para um processo residente do Whis subir na máquina do usuário
com os nomes novos — e com o pré-requisito do toast já resolvido.

Spec: [../spec.md](../spec.md), *Camada zero*. Fatos: [research/01](../research/01-pontos-de-contato.md)
§2, [research/02](../research/02-windows-agendador-e-aviso.md) §2.

- [x] `automacao.py` cria, além do atalho de Inicialização, um atalho **no Menu Iniciar**
      (`Start Menu\Programs\Whis.lnk`) com a propriedade `System.AppUserModel.ID` — sem ela um
      app não empacotado não consegue disparar toast. A AUMID é uma constante do módulo
      (`AUMID = "Whis.Agente"`).
- [x] O atalho do atendente **não é instalado** por `whis windows`: o Slack dorme. O flag
      `--atendente` continua existindo como opt-in explícito (o código fica; seis testes
      existentes o exercitam e não precisaram ser editados).
- [x] `whis windows --remover-legado` apaga `Second Brain.lnk` da Inicialização e a tarefa
      `SecondBrain-Limpeza` do Agendador, por `executar` injetável. Sozinho, não instala nada.
- [x] Testes por `executar`: o comando montado é o que se espera; nenhum teste toca o Windows.
- [x] Suíte inteira verde, sem editar teste existente.

## Notas para o executor

- O passo humano (renomear a pasta e refazer o `pip install -e .`) **já foi feito**: o `.pth`
  do editable install aponta para `whis\src`.
- Quem roda `whis windows` na máquina é o usuário, no PowerShell 5.1 — o `%APPDATA%` do agente
  pode não ser o dele. O roteiro final (`docs/smoke-interface.md`) carrega os comandos.
- A tarefa de limpeza nova é da camada 2 (módulo `ScheduledTasks`); aqui só se remove a antiga.

## Comments

**Camada 0 entregue e fechada** (2026-09-12, sessão principal).

- O `.lnk` com AUMID é gravado por `src/whis/atalho_com_aumid.ps1` (empacotado via
  `package-data`, com BOM porque o PowerShell 5.1 lê `.ps1` sem BOM como ANSI): `WScript.Shell`
  cria o atalho e um `Add-Type` abre-o como `IPropertyStore` para gravar
  `System.AppUserModel.ID`. **Provado nesta máquina** num `.lnk` temporário fora do Menu
  Iniciar: o script saiu 0 e o `propsys` leu de volta `AUMID lida: Whis.Agente`, alvo
  `pythonw.exe`, argumentos `-m whis bandeja`.
- `instalar_inicializacao` passa a disparar dois comandos (Inicialização por `-Command`, Menu
  Iniciar por `-File`); `remover_inicializacao` leva os dois. `remover_legado` devolve
  `Legado(atalho, tarefa)`.
- Suíte: **873 verdes** (eram 862; 11 novos em `tests/test_arrumar_a_casa.py`), 8 desselecionados,
  nenhum teste existente editado.
- O atalho real na máquina do usuário só nasce quando ele rodar `whis windows` — está no
  roteiro final.
