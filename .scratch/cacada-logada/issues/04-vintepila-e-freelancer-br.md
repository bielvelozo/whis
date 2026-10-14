Status: resolved
Blocked by: 01

# VintePila e freelancer.com.br

VintePila: busca logada na listagem, sai inelegível/5 de 5. freelancer.com.br: plano pago detectado → site pago, nada de lá. Explorador web não procura nos sites cobertos pelo Chrome logado.

## Comments

2026-10-14 (pesquisa, ticket 00): na VintePila o "Inelegível" vem da conta, não do limite de 5: "Você precisa ter pelo menos um serviço ativo para fazer propostas." (aparece até com Candidatos 0/5; o texto só está num script da página, preservado no fim de `vintepila_inelegivel*.html`). Decisão: o leitor detecta esse aviso → VintePila fica de fora inteira e Fontes diz "crie um serviço ativo na VintePila para poder propor"; quando ele criar, volta sozinho. "Candidatos (5/5)" continua tirando o projeto. A listagem não tem filtro de categoria (só ordenação): filtrar por palavra no título/descrição.
freelancer.com.br: deslogado no Chrome dele hoje; não há fixture logada nem da tela de plano. Decisão: o site entra como pago por padrão (o botão "Estou interessado" leva a `/account/upgrade?...trigger=bid_project_no_product`, visto em 13/10); nada de lá até ele dizer que assinou (chave/lista em config). Fixtures reais: `freelancerbr_projeto_deslogado.html`, `freelancerbr_listagem_deslogado.html`.
Freelancer.com com 0 lances não mostra o formulário; o contador "0 ofertas restantes de 6" basta (ticket 05). Repetidos: usar `owner_id` da API (a página logada não mostra o cliente).

## Answer

VintePila: `fontes_da_cacada.coletar_vintepila` lê 3 páginas da listagem logada. Fica o que cita uma palavra de `PALAVRAS_DA_VINTEPILA` ou da stack do perfil (sem acento, por palavra inteira) e ainda não está com todos os candidatos (5/5; o rótulo PRO tira o teto). Uma página de projeto é sempre aberta (a primeira que fica, ou a primeira da listagem). Se ela traz "pelo menos um serviço ativo", a VintePila inteira fica de fora e Fontes diz para criar um serviço ativo. Decisão: a VintePila entra em qualquer modo do `hunt` sempre que ele estiver logado lá, não só no `--freelas`.

freelancer.com.br: lista irmã `[cacada].plataformas_pagas` (padrão `["freelancer.com.br"]`) e `barrar_pagas`. O que vem de lá sai depois da coleta, contado em Fontes ("responder lá pede plano pago"). O site nem é aberto na conferência de login, mas continua nas abas do `whis navegador` para o dia em que ele assinar e tirar o nome da lista.

Explorador: `criterios_de_freelas(..., cobertos=, plataformas_pagas=)`. Com a 99Freelas logada nesta caçada, a linha "recentes" fica só na Workana, ou sai se a Workana estiver sem conta. Com a VintePila logada ou o freelancer.com.br pago, a linha "fora das plataformas grandes" diz para não trazer nada deles. Os sites cobertos vão para o checkpoint (`cobertos`) e valem para as rodadas extras e para a retomada. Quando o login cai, as linhas voltam ao texto de antes.
