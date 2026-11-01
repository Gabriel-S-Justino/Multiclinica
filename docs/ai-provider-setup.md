# Contrato de IA e configuração futura

RF-IA-01–13. Nenhum provedor/modelo/endpoint contratado, configurado ou testado. IA permanece desabilitada até D13 e cota definidas. Não é necessário token de IA na F1/F2.

Interface proposta `IntentInterpreter.interpret(SafeConversationContext, UntrustedText, AllowedIntentSet) -> IntentResult`. Schema: intent enum permitido, campos extraídos com limites, needs_clarification e confidence opcional; campos inesperados são rejeitados. Resultados não são comandos de domínio. Tenant, patient_id, permissões e transição vêm do servidor, nunca do modelo.

Portas adicionais: `AIQuota.reserve/settle`, `AIProvider.health`, `ClinicalSafetyPolicy.classify`. Detecção determinística de urgência aplica texto fixo aprovado e handoff; sem esse texto aprovado não habilitar fluxo automatizado de urgência em produção. A IA nunca diagnostica ou decide tratamento.

Ferramentas candidatas: `list_services`, `find_slots`, `create_hold`, `confirm_appointment`, `cancel_appointment`, `reschedule_appointment`, `request_handoff`. Só expor subconjunto por estado/identidade; toda execução chama os mesmos casos de uso e verificações de domínio. Ferramenta não recebe tenant livre. Resumo e confirmação explícita do usuário são necessários para mutações; resultado não pode ser anunciado antes de commit.

Configuração proposta: `AI_ENABLED`, `AI_PROVIDER`, `AI_MODEL`, segredo `AI_API_KEY`, `AI_TIMEOUT_SECONDS`, `AI_MAX_TOKENS_PER_TURN`, `AI_MAX_TOOL_CALLS_PER_TURN`, `AI_MONTHLY_TENANT_BUDGET`. Host escolhido por allowlist do adaptador, nunca URL vinda da conversa. Validar configuração habilitada e falhar de forma segura sem imprimir valores. Valores monetários/tokens dependem de orçamento e preços verificados em F6.

Antes de chamada: minimizar texto/contexto, pseudonimizar e avaliar possibilidade de dado sensível em texto livre; se não houver aprovação/base definida, usar menu sem IA. Reservar cota atomicamente, limitar tempo e chamadas, retries só para interpretação sem efeitos; estouro/falha → menu/humano. Registrar apenas modelo, latência, contagem e resultado operacional. Suíte de modelo simulado em CI, chamadas reais opcionais sem pacientes e com custo aprovado.

## Atualização F2 — 31/10/2026

Este documento conserva o design completo da F1. O subconjunto implementado e validado nesta fase, com limites e comandos, está em [foundation.md](foundation.md) e no [relatório F2](reports/f2-foundation.md). Funcionalidades futuras aqui descritas não foram declaradas implementadas.


## Continuidade F6 — implementação parcial

Implementados i_boundary.py e i_quota.py, com schema fechado, sem executor de mutação, falha para menu, reservas atômicas conservadoras e ledger sem prompts. Reservas não autorizam chamadas repetidas com a mesma chave. Adaptador de provedor, vinculação ao fluxo, orçamento monetário e texto clínico aprovado não foram implementados/configurados sem D13. Testes usam fornecedor simulado. Ver ADR 0007 e relatório F5–F8; não apresentar isto como IA ativa.
