# Pesquisar opções de captura de atividade do PC

Type: research
Status: resolved

## Question

Quais são as opções concretas para observar a atividade do usuário no Windows 11, com liga/desliga sob demanda?

Levantar fatos, não decidir:

- **ActivityWatch**: o que captura, arquitetura (watchers + API local), como consultar os dados, dá para ligar/desligar facilmente?
- **Screenshots periódicos + resumo por modelo de visão**: custo de armazenamento, custo de API, riscos de privacidade (dados de empregador/clientes na tela).
- **Hooks de janela ativa / título de janela**: o que dá para saber só com isso, bibliotecas.
- **Histórico de navegador e outras fontes passivas** (arquivos recentes, git local).
- Volume de dados gerado por dia em cada abordagem e como isso viraria resumo em nota no vault.

O resultado alimenta [Decidir a abordagem de captura de atividade](06-decidir-captura-atividade.md).

## Answer

Quatro famílias de opções, com perfis bem distintos de custo e privacidade:

- **ActivityWatch** (open-source, MPL-2.0, ~18,6k estrelas, maduro): watchers de janela ativa (app + título), AFK (mouse/teclado) e navegador (URL/título via extensão Chrome/Edge/Firefox). Servidor local com REST API em `localhost:5600/api/0/` (buckets, eventos, Query API para agregações). Liga/desliga pelo `aw-qt` na bandeja ou matando o processo — atende observação sob demanda. ~1 MB/dia de JSON local; resumo diário via Query API + Haiku custa centavos/mês.
- **Screenshots + modelo de visão**: 50 MB–1 GB/dia de imagens; resumir com Claude Haiku (~1.600 tokens/imagem) sai US$ 4–10+/mês — engoliria quase todo o teto de R$ 100 restante. Pior perfil de privacidade: pixels com dados de empregador/clientes indo à nuvem. O precedente do Windows Recall (screenshots + OCR em SQLite sem criptografia, recuo público da Microsoft) mostra que até armazenamento local de tela é alvo. Alternativa intermediária: screenpipe (open-source, Windows, OCR local, API em `localhost:3030`) e enviar só texto ao LLM (~10× mais barato); rem é macOS-only.
- **Hook de título de janela puro** (pywin32/`get-windows`): título já revela arquivo/projeto/aba — bom sinal, mas é exatamente o que o `aw-watcher-window` já faz com AFK e storage prontos.
- **Fontes passivas retroativas**: histórico do navegador (SQLite em `%LOCALAPPDATA%`), arquivos recentes do Windows, `git log` local — custo zero de captura, nada precisa ficar "ligado", KB/dia, resumo por centavos.

Fato central para a decisão: títulos+AFK+URLs (ActivityWatch) somados a git/histórico cobrem a maior parte do sinal de um resumo diário por custo desprezível e exposição mínima; screenshots agregam conteúdo de tela ao maior custo financeiro e de privacidade.

Detalhes e fontes: [../research/05-captura-atividade.md](../research/05-captura-atividade.md)
