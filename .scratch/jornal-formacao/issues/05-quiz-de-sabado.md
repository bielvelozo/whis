# 05 — O quiz de sábado

Type: task
Status: resolved
Blocked by: 04

Camada 4 da [spec](../spec.md#camada-4--o-quiz-de-sábado-quizpy-novo-quiz_claudepy-novo-jornalpy-pagina_do_jornalpy-vaultpy).

- Sábado (BRT) sem vaga de aula; Quiz da semana como primeira seção.
- 1 pergunta nova por aula lida sem `quiz:`, todas; `PortaQuiz` + `QuizClaude`.
- Atrasadas (erradas ou sem resposta, ainda não acertadas em nenhuma versão) com id novo e
  `origem`, até 10.
- `quiz.py`: nota `noticias/quiz/AAAA-MM-DD.md`, ida e volta testadas; `Resultado:` escrito pela
  sincronização diária.
- Página: alternativas como botões, revelação, `respostas/<id>`; sem banco revela sem guardar.
- Falha do `QuizClaude` com atrasadas; nada para perguntar; reaproveitar no mesmo sábado.
- `QuizFake`.

## Comments

- 2026-10-06 — Resolvido. Tarefas 9–11. `quiz.py` e `quiz_claude.py` (executor, revisados; `ErroDeQuiz` quando todas as perguntas caem), sábado sem vaga, quiz como primeira seção, atrasadas com id novo e `origem`, `sem resposta` gravado no dia seguinte. Script do quiz conferido no navegador embutido com uma página de teste: errada vermelha, certa verde, explicação aberta, outras perguntas livres.
