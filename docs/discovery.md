# F0 — Descoberta

Data: 31/10/2026. Fonte: `Master.md`, fornecido pelo usuário e lido nesta sessão. O documento define o escopo; esta fase não implementa a aplicação.

## Objetivo e contexto

Atender várias clínicas por WhatsApp e portal, com isolamento de dados, agendamento consistente sob concorrência e transferência para atendimento humano. A IA será opcional e limitada à interpretação de linguagem; o backend determina transições e resultados.

Estado inicial verificado: repositório com apenas README, branch `main`, remoto `Gabriel-S-Justino/ProjetoExtensao`, sem alterações locais antes da F0.

## Premissas propostas

- Stack exigida: React/TypeScript strict/SCSS, Python/FastAPI/Pydantic v2/SQLAlchemy 2, PostgreSQL/Neon, Alembic e Vercel. Versões, dependências e compatibilidade serão verificadas antes da implementação; nenhuma versão foi selecionada nesta fase.
- Separar contato de paciente; o vínculo com dependentes precisa de autorização, não basta declarar parentesco.
- Unidade e recursos entram no modelo inicial. Capacidade de recurso, agenda compartilhada e permissões exigem detalhamento na F1.
- Não usar dados reais de pacientes no desenvolvimento ou testes.
- Sem publicação, contratação de serviço, credenciais ou envio de mensagens nesta fase.

## Perguntas e bloqueios

| Pergunta | Proposta / consequência | Prazo |
|---|---|---|
| Os padrões D1–D16 podem orientar o design? | Ver ADR; todos aguardam confirmação | Gate F0 |
| Qual clínica piloto e quem valida regras e textos? | Responsáveis operacional e clínico a indicar | Antes de validar fluxos |
| Quais campos mínimos identificam paciente e autorizam dependentes? | Telefone identifica contato; nascimento sozinho não deve ser tratado como prova forte. Definir verificação proporcional e recuperação por humano | Antes de F3 |
| Quais antecedências, durações, intervalos e limites de remarcação? | Parametrizar; sem regras clínicas inventadas | Antes de F3 |
| Quais filas, permissões e horários de atendimento? | Financeiro como fila; prazo fora do expediente a definir | Antes de F4 |
| Qual orçamento e provedor de fila? | Comparar fila gerenciada/Redis e PostgreSQL em F1; decisão operacional antes de F5 | Antes de F5 |
| Qual provedor de IA, região, contrato e cota mensal? | IA desabilitada até configuração e avaliação aprovadas; menu determinístico permanece | Antes de F6 |
| Quem define retenção, base legal e descarte? | Clínica/jurídico; sem prazo arbitrário ou alegação de conformidade | Antes de produção e fechamento F7 |
| Quais planos, domínio e regiões de Vercel/Neon? | Verificar limites, custos, backup e recuperação contratados | Antes de F8 |
| Qual texto fixo para situações urgentes? | Aprovação da clínica; não redigir orientação clínica como regra final | Antes de F6 |

## Metas não funcionais propostas

| Parâmetro | Meta inicial | Evidência necessária |
|---|---|---|
| Clínicas / profissionais | 10 / 20 por clínica | Carga com isolamento |
| Mensagens recebidas | 5.000/dia; distribuição de pico ainda indefinida | Definir rajada e executar carga |
| ACK webhook | < 2 s | Teste em staging |
| Resposta ao paciente p95 | < 8 s incluindo IA | Medição ponta a ponta |
| Disponibilidade | 99,5%; janela de apuração a definir | Monitoramento operacional |
| RPO / RTO | ≤ 15 min / ≤ 4 h | Backup contratado e restauração cronometrada |
| Cota mensal de IA | Pendente por clínica | Configuração, medição e bloqueio por cota |
| Retenção de mensagens | Pendente com clínica/jurídico | Política aprovada e teste de descarte |

Metas não são garantias: ainda não há testes de desempenho ou serviços contratados verificados.

## Ambiguidades e resoluções propostas

1. D16 inclui `held` em agendamentos, mas a seção 8 propõe holds em tabela própria. F1 deve definir uma única fonte de ocupação e a conversão transacional; não duplicar reservas independentes.
2. RF-AG-09 pede paciente/reserva/agendamento em uma transação, enquanto o hold precede confirmação. Proposta: hold em transação própria; confirmação cria paciente quando necessário, consome hold, cria agendamento e atualiza conversa atomicamente. Validar em F1.
3. RF-CV-05 silencia o bot em handoff, mas RF-WA-09 prevê resposta a mídia. Proposta: handoff prevalece; mídia não dispara resposta automática nesse estado.
4. Exclusão/anônimização e auditoria imutável precisam coexistir. Proposta: auditoria mínima sem conteúdo clínico, referências opacas e política de retenção própria aprovada.
5. Filas e execução serverless precisam de entrega durável e processamento serial; ACK só após persistência durável. Não presumir execução após resposta HTTP.

## Próxima fase proposta

F1 produzirá arquitetura, contratos, modelo de dados, máquina de estados, matriz RBAC, STRIDE e plano de testes. Comparará as duas opções de fila e definirá locks, RLS transacional e fronteiras de identidade. Cada ambiguidade acima precisa de resolução registrada antes da implementação afetada.
