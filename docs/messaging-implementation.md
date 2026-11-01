# WhatsApp determinístico — operação local

Canal oficial atrás de `WhatsAppProvider`; [ADR 0006](decisions/0006-whatsapp.md). O adaptador Cloud API usa host fixo, TLS, timeout e nenhum redirecionamento. A versão Graph é configuração obrigatória para envio; nenhuma versão foi presumida. Não houve mensagem real nem validação de conta Meta.

## Configurar

1. Aplicar migrações com credencial direta de migração. Runtime sem owner/BYPASSRLS.
2. Criar fila ativa, atribuir atendentes e configurar expediente/aviso. Configurar políticas de serviço e verificação aprovadas pela clínica.
3. Salvar credenciais WhatsApp na tela de integrações: são cifradas e somente de escrita.
4. Em processo controlado, com URL de migração: `python -m backend.messaging_cli provision --tenant-id UUID --queue-id UUID --phone-number-id ID --account-id ID`. Cria conta técnica não interativa e canal com envio desligado.
5. Webhook: `/v1/webhooks/whatsapp/CHANNEL_UUID`. GET de verificação e POST autenticado por HMAC. Conta e número precisam coincidir com o canal configurado. Assinatura é verificada sobre bytes antes do JSON.
6. Worker limitado por invocação: `python -m backend.messaging_cli process --channel-id UUID --limit 50`; saída: `python -m backend.messaging_cli send --channel-id UUID --limit 50`. Use agendador/worker externo durável. Não executar como background em memória da função HTTP.

Ativar envio exige validação da versão suportada, conta, número, permissões e credenciais reais; alterar o canal por processo privilegiado revisado. `send_enabled=false` preserva mensagens como enfileiradas. A configuração inicial não finge entrega.

## Fluxo e proteção

Menu → serviço → unidade → preferência por profissional → datas por semana → horários paginados → finalidade/cadastro mínimo → revisão → confirmação. Menus de texto usam código opaco completo, válido somente na etapa atual. Consultas existentes exigem vínculo manual vigente; sem ele a resposta é uniforme, sem revelar existência. Cancelamento e remarcação têm seleção e confirmação próprias. O motor F3 revalida disponibilidade e políticas dentro da transação.

`menu`, `reiniciar` e `cancelar fluxo` encerram o fluxo e liberam o hold quando possível, sem cancelar consulta existente. `voltar` retorna à seleção preservando serviço/unidade e liberando o hold. Hold expirado não confirma. Inatividade pede reconfirmação; dados são revalidados antes de uso. `parar` registra opt-out; `retomar` inicia novo atendimento quando não há handoff ativo. Durante handoff o bot fica silencioso, inclusive para mídia; somente liberação explícita do atendente permite retomada. Mídia não é baixada.

Ingestão deduplica por evento de canal. Banco e fila são atômicos; ACK somente após persistência. Ordenação local e lock impedem processamento simultâneo. Eventos externos atrasados não executam ação sensível. Payload, histórico e contexto temporário são cifrados; logs contêm somente metadados.

Outbox revalida contato, opt-out e janela de 24 horas. Fora da janela bloqueia texto livre, inclusive do atendente. Templates proativos não foram implementados. Rede ambígua ou lease expirado vira `unknown`, sem reenvio automático. HTTP429 recebe backoff/jitter limitado; falhas definitivas viram `dead`. Callbacks não regridem `read`/`delivered`.

## Recuperação e limites

Monitorar `inbound_jobs.status/error_code/available_at` e `message_dispatches.status/error_code/lease_until`, sem exportar conteúdo. DLQ exige diagnóstico; reprocessar somente com mesmo evento/idempotência, após corrigir causa. Não reenviar `unknown` sem reconciliação humana com provedor. Rotação de credenciais invalida a configuração anterior; pausa controlada e teste sintético antes de reativar. Não há suporte automático a dois app secrets simultâneos.

Uma clínica é serializada por transação para integridade. O ensaio local de webhook não comprova p95 remoto, escala nem frequência do agendador contratado. Retenção e descarte permanecem pendentes de política aprovada. Não há produção pronta apenas por existir worker e adaptador.
