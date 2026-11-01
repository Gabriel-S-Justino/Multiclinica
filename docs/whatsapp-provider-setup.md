# Contrato WhatsApp

RF-WA-01–10. Proposta: API oficial por `WhatsAppProvider`, número por clínica. Credenciais, assinatura exata, permissões, endpoints/versionamento, janela/templates, limites de listas e retries **não verificados nesta fase**; consultar documentação oficial Meta antes de F5. Nenhum endpoint de envio inventado ou configurado.

Interface: `verify_challenge`, `verify_signature(raw_body, headers)`, `parse_events(verified_body)`, `send_text(destination, text, context)`, `send_menu(destination, menu, context)`, `map_delivery_status`. Payload bruto só é parseado após autenticação; comparação em tempo constante conforme algoritmo documentado pelo provedor. Não presumir timestamp assinado se o provedor não o fornece: replay é mitigado por deduplicação e validação do contexto, nunca por campo não autenticado.

Webhook resolve provider/account/phone_number_id por mapa restrito e rejeita rota desconhecida. Persistir evento mínimo cifrado e job no mesmo commit, responder ACK; falha de persistência retorna falha. Expansão de envelope deduplica cada mensagem/callback. Duplicata autenticada recebe ACK sem efeito adicional.

Outbox: chave por evento/ação, lease e retries com backoff/jitter, timeout e DLQ; erro permanente não é repetido indefinidamente. Timeout no envio pode ter resultado ambíguo: reconciliar usando capacidades oficiais ou registrar entrega desconhecida; não prometer envio exatamente uma vez. Verificar opt-out e janela novamente no envio, inclusive respostas de atendente. Fora da janela não enviar texto livre; templates só quando aprovados e autorizados. Paciente que escreve parar revoga comunicações proativas; tratamento de mensagens iniciadas pelo próprio usuário deve seguir política validada.

Segredos propostos: `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN` e tokens por clínica cifrados; nomes finais dependem do adaptador. UI retorna apenas configured/last_verified_at, nunca segredo. Runbook de rotação deve manter validação durante transição controlada sem expor valores. Mídia não é baixada no MVP.

## Atualização F2 — 31/10/2026

Este documento conserva o design completo da F1. O subconjunto implementado e validado nesta fase, com limites e comandos, está em [foundation.md](foundation.md) e no [relatório F2](reports/f2-foundation.md). Funcionalidades futuras aqui descritas não foram declaradas implementadas.
