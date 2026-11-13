# Relatório F3 · Agendamento

Data: 31/10/2026. F2 aprovada pelo usuário nesta sessão. F3 implementada por casos de uso, aguardando gate. Nenhum push, contratação, deploy ou mensagem externa.

## Entrega e decisões

Disponibilidade com fuso/expediente/exceções/feriados/bloqueios/buffers; elegibilidade e seleção intercambiável LeastFutureLoad; hold expirável; confirmação/cancelamento/remarcação/status; identidade mínima cifrada; vínculos verificados manualmente; idempotência; auditoria e outbox; atualização atômica da conversa mínima.

[ADR 0004](../decisions/0004-scheduling.md) registra a granularidade por clínica do lock, defesa no banco, remarcação sobreposta ao original, limites das regras clínicas e testes. Essa escolha substitui o plano de lock por profissional enquanto o volume não justificar maior paralelismo. A aprovação F2 não foi tratada como definição de políticas clínicas.

## Arquivos

Novos: `backend/domain/scheduling.py`, `domain/selection.py`, `application/contracts.py`, `application/scheduling_commands.py`, `application/scheduling.py`, `infrastructure/fields.py`, `infrastructure/scheduling_models.py`, migração `0002_scheduling.py`, testes unitários/integrados de agenda, ADR 0004, guia e evidências F3.

Alterados: env Alembic para registrar metadata nova; runner para upgrade 0001→0002 com dados; schemas de autenticação usam contrato base da aplicação; pyproject/uv.lock adicionam Hypothesis; `.gitignore`, script de verificação por fase e documentação. Migração 0001 e evidências F2 preservadas.

## Verificações

Resultados finais: **77 testes Python aprovados (49 integração + 28 unitários)**, **2 testes de componente** e **1 regressão e2e Chromium** aprovados. Ruff/formatação, mypy, Bandit, ESLint, build e scan de segredos passaram. Auditoria Python: **72 dependências, nenhuma vulnerabilidade conhecida**. As duas propriedades Hypothesis geraram 100 exemplos válidos cada, sem falhas.

Evidências: `f3-validation.txt`, `f3-integration.txt`, `f3-pytest.xml`, `f3-hypothesis.txt` e `f3-python-audit.json`. O XML foi formatado e suas estatísticas Hypothesis originalmente codificadas em base64 foram extraídas para texto legível em `f3-hypothesis.txt`; casos/resultados foram preservados. Não foi criada exclusão ampla de scanner para XML.

A suíte inclui:

- 50 holds simultâneos no mesmo horário → exatamente 1 vencedor;
- 50 confirmações concorrentes do mesmo hold → exatamente 1 appointment e 1 evento;
- 50 INSERTs SQL diretos concorrentes → exatamente 1 hold ativo aceito pelo trigger;
- remarcação parcialmente sobreposta, recursos compartilhados/obrigatórios, TTL vencido sem limpeza, configuração alterada após hold;
- falha injetada **após gravações**: rollback de paciente/appointment/conversa/outbox e rollback de remarcação preservando o original;
- perfis/tenant/IDOR/dono do hold, MFA no caso de uso e paciente não verificado;
- parâmetros clínicos explícitos, override de duração, buffers, histórico concluído ignorado na seleção;
- Hypothesis: simetria de sobreposição e propriedades de slots com durações/buffers/bloqueios variáveis; DST ambíguo/inexistente;
- cifra vinculada ao tenant/linha/campo e comandos sensíveis sem tenant livre;
- migrations e regressão do portal da fundação.

Os testes são locais em PostgreSQL 18.6; nenhum uso de SQLite. O primeiro ciclo identificou alias SQL `old` ambíguo com a variável do trigger; corrigido antes da rodada final. Sem alegação de cobertura percentual, benchmark ou garantia de segurança de produção.

A revisão também corrigiu a validação de nascimento para usar o dia local da clínica. O teste `birth_date_uses_clinic_day_at_utc_midnight_boundary` cobre a virada do dia em UTC sem aceitar uma data futura na clínica.

## Rastreabilidade RF-AG

| Requisito | Evidência de teste |
|---|---|
| 01-04 | availability_and_pagination, holiday_exception_and_block, duration_override_and_buffers, scheduling_professional_permissions |
| 05 | DTO com IDs/horários; apresentação do resumo ao paciente fica para API/portal F4 e WhatsApp F5 |
| 06 | least_future_load_orders_load_then_time_then_stable_id, uses_future_active_duration, does_not_penalize_completed_history |
| 07-08 | new_patient_is_encrypted_and_not_automatically_verified, rls_idor_and_unverified_patient, register_contact_is_minimal_encrypted_and_idempotent |
| 09 | confirm_consumes_hold_and_atomically_finishes_conversation, failure_after_booking_writes_rolls_back_every_effect |
| 10 | overlapping_reschedule_is_atomic_and_transfers_resource, reschedule_failure_after_writes_preserves_old_and_hold, clinic_policy_limits |
| 11 | fifty_simultaneous_holds, fifty_simultaneous_confirmations, fifty_direct_sql_inserts, runtime_sql_resource_overlap |
| 12 | expired_hold_does_not_require_cleanup_job, direct_sql_cannot_create_overlapping_hold_or_extend_ttl |
| 13 | terminal_or_backward_transition, completion_before_start, cancel_releases_slot_and_terminal_transition_is_denied |

Os nomes são prefixos dos casos versionados nos arquivos de teste; observar relatório de execução para resultado efetivo. RF-AG-05 e fluxos de canais não estão concluídos nesta fase.

## Riscos e pendências

- D3/D9 e evidência de autorização de dependentes ainda dependem da clínica; sem valores produtivos inventados. Serviços reais não foram ativados.
- API/telas de agenda, paginação por canal e resumo de confirmação são F4/F5. Não há agendamento ponta a ponta por WhatsApp.
- Lock por clínica pode limitar throughput. Não há teste de carga/SLA, nem verificação Neon/Vercel real.
- D6 permanece aberto; outbox não envia nada. Políticas de retenção, descarte, rotação de chaves e restauração são F7.
- CI configurado acompanha a suíte nova, mas não foi executado remotamente. Scans não substituem revisão de segurança; alertas moderados de tooling frontend da F2 continuam documentados.

O lockfile frontend permaneceu inalterado nesta fase; o relatório npm da F2 registra 11 alertas moderados, sem altos/críticos, e não foi apresentado como nova auditoria F3. Há aviso de depreciação do TestClient/httpx herdado da fundação; testes finais passaram. Nenhum check remoto ou deploy foi declarado executado.

## Gate

Solicitar aprovação da F3 para iniciar F4 (API e Portal). Valores de negócio pendentes devem continuar bloqueando apenas funcionalidades dependentes, sem impedir telas/configuração e partes independentes. A pausa segue a seção 0 do Master.md.
