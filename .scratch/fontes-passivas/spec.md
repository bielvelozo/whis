# Spec: Fontes passivas — o dia vira diário no vault

Status: ready-for-agent

Origem: [handoff da entrega](handoff.md) e [mapa second-brain](../second-brain/map.md). As decisões de fonte, cadência e privacidade vêm de [Decidir as integrações de fontes passivas](../second-brain/issues/13-decidir-fontes-passivas.md); os fatos operacionais de cada API, de [Pesquisar acesso às fontes passivas](../second-brain/research/12-fontes-passivas.md). Glossário em `CONTEXT.md`; ADR 0001 (projeto separado, 100% local) governa a arquitetura.

## Problem Statement

O vault só tem memória dos dias em que houve reunião. Todo o resto do trabalho — o que foi commitado, as issues que andaram, as conversas que decidiram algo — vive espalhado em três lugares que ninguém relê: o histórico do git em repositórios locais, o Linear do time e o Slack. Passada uma semana, o usuário não consegue responder "o que eu fiz na terça" sem reconstruir o dia à mão, fonte por fonte. E o agente que deveria recuperar contexto do vault não tem contexto nenhum para recuperar nos dias sem reunião.

## Solution

Um **coletor de fontes passivas** que roda sozinho no fim do dia e escreve `diario/YYYY-MM-DD.md`: um resumo em português do que aconteceu, seguido das listas cruas de cada fonte e dos links para as reuniões daquele dia. A leitura é **retroativa** — o coletor lê o que já existe (git local, Linear, Slack) numa janela de tempo e vai embora. Nada fica escutando, coerente com **Sob demanda**: a tarefa agendada do Windows é o liga, e o fim da execução é o desliga.

O diário é o que conecta as duas fontes de contexto do vault: as reuniões que o tracer bullet já grava e o trabalho que acontece fora delas.

## User Stories

1. Como usuário, quero que um diário do dia apareça sozinho em `diario/`, para reler o que aconteceu sem montar nada à mão.
2. Como usuário, quero um resumo em português no topo do diário, para entender o dia em trinta segundos.
3. Como usuário que confere, quero as listas cruas de cada fonte abaixo do resumo, para saber de onde cada afirmação veio.
4. Como usuário, quero o diário linkando as reuniões daquele dia, para navegar do dia para a reunião sem busca.
5. Como desenvolvedor, quero os commits do dia em todos os meus repositórios locais, sem cadastrar cada um à mão, para nenhum trabalho ficar de fora por esquecimento.
6. Como membro de um time no Linear, quero a movimentação do time no dia — issues, comentários, mudanças de estado —, e não só a minha, para o diário registrar o contexto em que trabalhei.
7. Como usuário do Slack, quero as conversas do dia em que participei, inclusive DMs, para as decisões tomadas em conversa não se perderem.
8. Como dono da minha privacidade, quero uma blocklist de conversas do Slack que o coletor nunca lê, para conversas pessoais nem serem buscadas.
9. Como dono da minha privacidade, quero um filtro de exclusão configurável aplicado na coleta, para que o que eu marcar nunca vá ao Claude nem seja gravado no vault.
10. Como usuário, quero ver o que seria coletado sem nada ser enviado nem escrito, para conferir o filtro antes de confiar nele.
11. Como usuário sem Slack aprovado pelo admin, quero o diário nascendo mesmo assim com git e Linear, para não ficar sem diário esperando aprovação.
12. Como usuário, quero que uma fonte que falhou apareça marcada na nota, para nunca reler um diário incompleto achando que é completo.
13. Como usuário que trabalha de madrugada, quero que o commit da uma da manhã caia no diário do dia anterior, para o diário bater com o dia que eu vivi.
14. Como usuário, quero rodar o diário de novo no mesmo dia e ver a nota atualizada, para incorporar o trabalho da noite e as reuniões processadas depois.
15. Como usuário, quero gerar o diário de uma data passada por um comando, para preencher um dia em que o PC estava desligado.
16. Como dono das minhas notas, quero que o coletor de diário escreva só em `diario/`, para minhas notas em `notas/` e as reuniões em `reunioes/` nunca serem tocadas por ele.
17. Como usuário, quero que a tarefa agendada deixe rastro em log, para diagnosticar um diário que não nasceu.
18. Como usuário com teto de R$ 100/mês, quero as três fontes rodando a custo zero, para o diário de todo dia não criar despesa nova.

## Implementation Decisions

- **Costura única** (confirmada com o usuário): `gerar_diario(data) → nota em diario/`, com **uma porta só** para as fontes — `PortaFonte.coletar(janela) → eventos` — e três implementações (git, Linear, Slack). Ordem das fontes, degradação graciosa e filtro de exclusão ficam num lugar só; o navegador, se um dia reentrar, é mais uma implementação e não toca a costura.
- **Evento** é o tipo comum que toda fonte devolve. Nenhuma parte do diário conhece o formato de uma API específica; o adaptador traduz. Forma exata no [contrato de fonte passiva](contrato-fonte-passiva.md).
- **Formato do diário** (confirmado): resumo do Claude no topo (narrativa, destaques, pendências), listas cruas por fonte abaixo, links das reuniões do dia, frontmatter com `data`, `tipo`, `fontes`, `fontes_com_falha`, `temas` e `reunioes`.
- **Filtro de exclusão age na coleta** (confirmado): o que casa com o filtro nem entra em memória — não vai ao Claude nem ao vault. A régua é única e aplicada em **um ponto só**, dentro de `gerar_diario`, sobre o que toda fonte devolve: nenhuma fonte pode esquecer de filtrar. A **blocklist do Slack** é a primeira camada, aplicada antes: conversa bloqueada não chega a ser buscada.
- **Janela do dia** (confirmada): chave `[diario].inicio_do_dia`, padrão `"04:00"`. O diário de D cobre `D 04:00 → D+1 04:00`, então trabalho da madrugada cai no dia anterior. `"00:00"` recupera o dia civil puro.
- **Idempotência** (confirmada): rodar de novo **regenera e sobrescreve**. A nota é sempre derivada da janela e das fontes; `diario/` é zona do agente. É assim que o diário incorpora trabalho da noite e reuniões processadas depois.
- **Degradação graciosa** (confirmada): o diário nasce com as fontes que responderam e registra as que falharam, no frontmatter e numa linha visível da nota. **Dia vazio** — zero eventos e zero reuniões — não vira nota. Se **todas** as fontes falharem, nada é escrito e o comando termina com erro: um diário ausente por falha não pode ser confundido com um dia tranquilo.
- **Falha do resumo não impede o diário.** Diferente do pipeline de reunião, onde uma nota sem resumo não valeria nada (a transcrição já existe), o diário sem narrativa ainda carrega as listas cruas — que não existem em nenhum outro lugar. O Claude entra como mais uma coisa que pode falhar e ser marcada.
- **Zona de propriedade por coletor**: `vault.escrever` passa a receber as zonas permitidas. O pipeline de reunião mantém `reunioes/` + `transcricoes/`; o coletor de diário recebe **só** `diario/`. Nenhum dos dois escreve na zona do outro, e `notas/` continua recusada para ambos.
- **Git**: varredura automática de uma raiz de desenvolvimento configurável atrás de repositórios, com lista de exclusão e limite de profundidade. Autoria deduzida do `git config user.email` de cada repositório, com override na configuração. `git log --all --no-merges` na janela.
- **Linear**: API GraphQL (`https://api.linear.app/graphql`) com Personal API Key **read-only**, lendo a movimentação do(s) time(s) do usuário na janela — issues, comentários e mudanças de estado.
- **Slack**: app interna com user token `xoxp`, lendo as conversas de que o usuário participa, inclusive DMs, respeitando a blocklist. É a última camada construída: depende de aprovação de admin no workspace.
- **Cadência**: tarefa agendada do Windows, pelo mesmo mecanismo já usado pela limpeza (`automacao.py`). `second-brain windows --diario` registra; `--remover` desfaz.
- **Configuração**: chaves novas no `config.toml` existente, sem renomear nenhuma. Nenhum segredo no repo; nenhuma variável de ambiente obrigatória.
- **Idioma**: todo texto voltado ao usuário — nota, resumo, logs, mensagens de erro — em português.

## Testing Decisions

- **Costura única**: `gerar_diario(data, fontes=[...]) → nota em diario/`. Todo teste de comportamento passa por ela, com **fontes fake** e **resumo do dia fake**, verificando só o que aparece no vault: o arquivo certo no lugar certo, com frontmatter, listas cruas, links das reuniões e as marcas de fonte que falhou.
- Casos de falha exercitados pela mesma costura: uma fonte falhando (a nota nasce marcada), todas falhando (nada é escrito e o comando falha), dia vazio (nenhuma nota), resumo do Claude falhando (a nota nasce com as listas cruas).
- **Filtro de exclusão testado como comportamento**: um evento que casa com o filtro não aparece no vault **e** não chega ao fake de resumo — o fake guarda o que recebeu, e o teste prova que o conteúdo excluído não passou por ele.
- **Janela testada como comportamento**: um evento à 01:00 do dia seguinte entra no diário do dia anterior com `inicio_do_dia = "04:00"` e não entra com `"00:00"`.
- **Idempotência**: gerar duas vezes deixa um arquivo só, e a segunda execução reflete o que mudou entre elas.
- **Zona de propriedade**: o coletor de diário só escreve em `diario/`; os testes existentes do pipeline de reunião continuam provando que ele **não** escreve em `diario/`.
- **Fora da costura**: as três APIs reais. Cada adaptador ganha testes de tradução (payload gravado → `Evento`) sem rede, mais um teste `@pytest.mark.rede` que só roda de propósito, e um smoke manual documentado para o que depende de token de terceiro (Linear e Slack).
- Prior art: o tracer bullet. Mesma forma — costura única, fakes nas portas, zero mock de detalhe interno, `conftest.py` montando o cenário.

## Out of Scope

- **Histórico de navegador** — cortado da v1 em [Decidir as integrações](../second-brain/issues/13-decidir-fontes-passivas.md); reentra só se os diários se provarem rasos.
- **Recuperação de contexto** (chat no terminal + one-shot) — entrega separada, decidida em [recuperação de contexto](../second-brain/issues/08-recuperacao-de-contexto.md).
- Resumo semanal ou mensal; edição do diário pelo usuário dentro da zona do agente; busca de vagas/freelance; backup do vault; qualquer monitoramento de atividade do PC (fora do escopo do esforço inteiro).
- Retry com backoff compartilhado entre adaptadores — está no [DEFERRED do tracer bullet](../tracer-bullet/DEFERRED.md) e continua deferido; três fontes novas tornam o tema mais provável, mas a degradação graciosa já cobre o caso de uso.

## Further Notes

- **Tarefas humanas antes da primeira execução**: criar a Personal API Key read-only no Linear (Settings → Security & access) e, para o Slack, criar a app interna com os user scopes de leitura e obter aprovação do admin do workspace. Ambas viram roteiro no repo pelas camadas 03 e 05.
- **Confira as datas da pesquisa**: [research 12](../second-brain/research/12-fontes-passivas.md) é de agosto de 2026. A exceção de rate limit para apps internas do Slack é o alicerce do plano e merece re-checagem antes da camada 05.
- O vocabulário desta spec segue o glossário (`CONTEXT.md`): **Coletor**, **Fonte passiva**, **Vault**, **Sob demanda**, **Diário**, **Zona de propriedade**.
