# Escopo e rastreabilidade inicial

Status: F2 entrega autenticação/RBAC/RLS; F3 entrega o motor RF-AG, preservando apresentação/canais para F4/F5. A matriz abaixo conserva a distribuição planejada; resultados concretos estão nos relatórios de fase, sem indicar conclusão do MVP.

## MVP

Atendimento WhatsApp por texto, menu configurável, agendamento/cancelamento/remarcação com profissional, cadastro mínimo, dependentes, filas humanas, portal por perfil, isolamento multi-clínica, auditoria e observabilidade.

## Posterior ao MVP

Lembretes proativos, lista de espera, convênios, preços, pagamentos, relatórios e mídia/uploads. Unidades e recursos serão modelados desde o início com interface mínima.

## Fora do escopo

Diagnóstico, triagem ou orientação clínica, prontuário, teleconsulta e treinamento de modelos com dados de pacientes.

## Matriz inicial

Os IDs abaixo seguem o Master.md. A F1 detalhará cada requisito em critérios e contratos; esta matriz não substitui seu conteúdo integral.

| IDs | Entrega prevista | Evidência de aceite planejada | Estado |
|---|---|---|---|
| RF-WA-01 a RF-WA-10 | F5; linguagem natural em F6 | Assinatura, idempotência, janela, opt-out, mídia e não enumeração | Não implementado |
| RF-CV-01 a RF-CV-05 | F5 | Máquina persistida, serialização, expiração e silêncio em handoff | Não implementado |
| RF-AG-01 a RF-AG-13 | F3; exposição em F4/F5 | Domínio, fuso, hold, remarcação; 50 disputas no mesmo horário em PostgreSQL real → 1 sucesso | Motor e portal verificados; canal F5 validado com transporte simulado, ativação real pendente |
| RF-HU-01 a RF-HU-04 | F4/F5 | Filas, permissões, expediente, assumir e devolver ao bot | Não implementado |
| RF-PT (seção 4.5, sem sub-IDs na fonte) | F2/F4 | RBAC por endpoint, isolamento e e2e acessível | Portal F4 verificado localmente e aprovado |
| RF-IA-01 a RF-IA-13 | F6 | Schemas, ferramentas autorizadas, minimização, cotas e zero violações na suíte adversária | Não implementado |
| Segurança (seção 7) | F2–F7 | Autenticação, RLS avaliada, CSRF, IDOR, injeções, scans | Controles F2/F3 verificados localmente; hardening F7 pendente |
| Integridade (seção 8) | F1/F3 | Constraints, transações e concorrência em PostgreSQL real | F3 verificada; pool Neon real e carga pendentes |
| Operação/deploy (seções 11–12) | F7/F8 | Restauração, build, staging e observação real | Não implementado |

Os requisitos sem ID individual na fonte receberão IDs complementares na F1 sem renomear os IDs existentes.

## Atualização F2 — 31/10/2026

Este documento conserva o design completo da F1. O subconjunto implementado e validado nesta fase, com limites e comandos, está em [foundation.md](foundation.md) e no [relatório F2](reports/f2-foundation.md). Funcionalidades futuras aqui descritas não foram declaradas implementadas.


## Continuidade F5–F8 — 31/10/2026

A matriz inicial conserva o plano histórico. Estado atual e evidências: [relatório de continuidade](reports/continuation-f5-f8.md). RF-WA/RF-CV/RF-HU possuem implementação determinística local; conta Meta e entrega real pendentes. RF-IA possui fronteira e cotas testadas; adaptador escolhido, ligação ao fluxo e configuração aprovadas pendentes, IA desligada. Hardening local e empacotamento preparados; direitos/retentiva, conformidade e staging/produção não concluídos.
