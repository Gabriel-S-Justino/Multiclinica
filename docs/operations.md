# Operação proposta

Sem serviço rodando. Donos operacionais e contatos ainda precisam ser indicados.

Logs estruturados com correlation ID, tenant opaco, ação, duração e resultado; nunca corpo de mensagem ou segredo. Métricas: ACK/p95, erro, atraso de fila, retries/DLQ, conflito de agenda, entrega desconhecida, cota/latência de IA e handoff. Dimensões com cardinalidade limitada; dados pessoais não são labels.

| Evento | Resposta planejada | Recuperação/evidência |
|---|---|---|
| IA indisponível/cota | Circuit breaker e menu determinístico/humano | Monitorar recuperação sem replay de mutações |
| WhatsApp falha | Preservar outbox, retry limitado por classificação | Reconciliar timeout ambíguo; DLQ e reprocessamento auditado |
| Banco indisponível no webhook | Não ACK de sucesso sem persistência | Verificar retries do provedor, restaurar conexão e deduplicar |
| Fila atrasada | Alertar por idade e capacidade, suspender excesso | Reexecutar jobs por ID sem duplicar efeito |
| Hold abandonado | Expiração por consulta, limpeza periódica | Não depende do job para liberar slot |
| Segredo comprometido | Revogar/rotacionar e invalidar sessões afetadas | Verificar versão e registrar incidente sem valor secreto |
| Vazamento/isolamento | Conter integração/tenant afetado, preservar evidência mínima | Responsável avalia impacto e comunicações com prazos validados |
| Falha de release | Reverter código compatível; pausar novas mutações se necessário | Restaurar só por plano aprovado e teste |

Backup: verificar plano/PITR, restaurar em ambiente isolado sem comunicações externas, checar integridade/constraints/contagens, reaplicar descartes e medir perda/tempo. Só registrar RPO/RTO atingidos com evidência real. Audit logs não devem ser alteráveis pelo usuário runtime; exportação imutável, acesso e retenção serão validados em F7.

Antes de produção: health check genérico, alertas e responsáveis definidos, runbook ensaiado, retenção e descarte configurados, credenciais separadas, planos/regiões verificados e restauração testada.

## Atualização F2 — 31/10/2026

Este documento conserva o design completo da F1. O subconjunto implementado e validado nesta fase, com limites e comandos, está em [foundation.md](foundation.md) e no [relatório F2](reports/f2-foundation.md). Funcionalidades futuras aqui descritas não foram declaradas implementadas.


## Atualização F3 — 31/10/2026

Holds expirados não bloqueiam agenda mesmo sem limpeza; limpeza continua pendente operacional. Eventos ficam pending na outbox e ainda não têm dispatcher. Não executar migrations automaticamente por requisição. Ver [limites F3](scheduling-implementation.md).
