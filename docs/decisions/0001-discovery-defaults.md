# ADR 0001 · Padrões da descoberta D1-D16

Data: 31/10/2026. Histórico: propostas na F0; padrões aprovados pelo usuário em 31/10/2026 para orientar a F1. A aprovação não preenche valores, contratos ou escolhas que permaneceram em aberto (D3, D6, D9, D12, D13, D15). Este registro agrupa as decisões para revisão; alterações posteriores devem preservar o histórico.

| ID | Decisão proposta | Justificativa / limite | Bloqueia |
|---|---|---|---|
| D1 | Cloud API oficial atrás de `WhatsAppProvider`; um número por clínica; resolver `phone_number_id` no servidor | Separar integração e isolamento; acesso e regras oficiais ainda não verificados | F5 |
| D2 | Colaborador, Recepção/Atendente, Admin e Superadmin; Financeiro como fila | Permissões explícitas; Superadmin sem acesso padrão a pacientes | F2 |
| D3 | Contato pelo telefone WhatsApp; verificação adicional antes de consultar/alterar consulta | Não confiar em posse do número ou nascimento isolado para todos os riscos; CPF opcional, sem base legal presumida | F3 |
| D4 | Contato e paciente separados; dependentes suportados | Vínculo e autorização a detalhar | F1 |
| D5 | Sessão em cookie HttpOnly/Secure/SameSite, CSRF e mesma origem | Domínio, rewrites e comportamento de `vercel.app` a verificar | F2 |
| D6 | Comparar fila/Redis gerenciado com fila PostgreSQL | Gerenciado: custo e dependência externos; PostgreSQL: disputa por conexões, polling e operação. Custos/latências não medidos; nenhuma opção escolhida | F5 |
| D7 | Hold de 10 minutos configurável | Expiração pelo relógio do banco, independente da limpeza | F3 |
| D8 | Estratégia `LeastFutureLoad` intercambiável | Carga futura no período definido, primeiro horário e desempate auditável; período a definir | F3 |
| D9 | Antecedência e limite de remarcação por serviço; sem cobrança | Valores pendentes da clínica | F3 |
| D10 | Bot apenas agenda e encaminha | Texto de emergência fixo aprovado pela clínica | F6 |
| D11 | Sem convênios/preços no MVP; bot não informa preços | Reduz escopo financeiro | · |
| D12 | Retenção configurável; conteúdo de mensagens criptografado | Prazo, chaves e descarte dependem de política aprovada; nenhum prazo escolhido | F7 |
| D13 | Provedor de IA condicionado a contrato/DPA, região e retenção avaliados | Não há provedor nem tratamento internacional aprovado | F6 |
| D14 | Apenas texto; orientar mídia não suportada e oferecer humano | Respeitar silêncio durante handoff | F5 |
| D15 | Expediente humano configurável e solicitação fora do horário | Horários, prazo prometido e responsável a definir | F4 |
| D16 | `held` → `scheduled` → `confirmed` → `completed`; alternativas `canceled`, `no_show`, `rescheduled` | Transições permitidas e relação com tabela de holds a resolver em F1; remarcação vinculada e atômica | F1 |

Não aplicável ainda: modo não interativo com decisões assumidas. Esta sessão tem gate humano explícito; as propostas não autorizam produção, uso de dados de pacientes ou contratação de provedores.
