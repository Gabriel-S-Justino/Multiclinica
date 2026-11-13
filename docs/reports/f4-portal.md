# Relatório F4 · API e portal

Data: 31/10/2026. F3 aprovada pelo usuário. Implementação local da F4; validação local concluída, aguardando gate. Não foi iniciado o WhatsApp F5, nem realizado push ou deploy.

## Entrega

API e portal com agenda diária/semanal, cadastro mínimo, disponibilidade, hold/revisão/confirmação, cancelamento e remarcação; configuração de serviços, profissionais, habilitações, horários/exceções/bloqueios, unidades e recursos; equipe, convites com aceite, filas e atendimento humano; auditoria, credenciais somente de escrita e operação de plataforma com aprovação para leitura excepcional.

Arquitetura e decisões: [ADR 0005](../decisions/0005-api-portal.md). Operação, contratos e fontes oficiais: [guia F4](../portal-implementation.md). Foram usadas orientações da skill Sites para implementação/preview local; publicação permanece na F8 conforme o escopo autorizado.

## Evidências e limites

94 testes Python passaram com PostgreSQL 18.6 real: 66 de integração e 28 unitários. Incluem regressões F2/F3, matriz de perfis, IDOR, cursores vinculados ao ator, fluxo HTTP de agendar/verificar/remarcar/cancelar, concorrência de tomada da conversa, cifragem e idempotência de respostas, convites e acesso excepcional aprovado/expirado. A cobertura não equivale a teste exaustivo de todas as combinações de endpoint e perfil.

3 testes de componente passaram. Ruff/formatação, mypy, Bandit, scan de segredos, ESLint, TypeScript e build passaram em `f4-validation.txt`. Um teste Chromium com API real valida login/seleção e o fluxo de agendamento com revisão; **1 e2e aprovado**, com zero violações axe nas telas verificadas (agenda desktop, revisão modal e agenda móvel). Capturas `f4-review.png` e `f4-mobile.png` inspecionadas visualmente. Evidências: `f4-integration.txt`, `f4-pytest.xml`, `f4-hypothesis.txt` e `f4-browser.txt`. Estatísticas Hypothesis foram extraídas de base64 para texto legível, preservando resultados no XML. Upgrade com dados e ciclo downgrade/upgrade passaram; servidores de teste foram encerrados.

Auditoria npm: 11 achados moderados, zero altos/críticos (`f4-npm-audit.json`). Permanecem pendentes de resolução na revisão de dependências/hardening; não se declara ausência de vulnerabilidades. Não foram adicionadas dependências Python nesta fase; a auditoria F3 continua histórica, não representa nova consulta.

O envio WhatsApp e a IA não são ativados: mensagens do inbox ficam na outbox. Guardar credenciais não confirma uma conexão com o provedor. Convites não enviam e-mail. Políticas clínicas/identidade precisam ser aprovadas pelos responsáveis antes de uso real. Nenhum dado real de paciente foi usado nos testes. Acessibilidade automatizada não substitui avaliação manual com tecnologia assistiva. Sem produção, carga, restauração ou conformidade final verificadas; F7/F8 continuam pendentes.

## Gate

Apresentar o resultado final da validação F4 e aguardar aprovação antes de iniciar F5, conforme seção 0 de `Master.md`.

## Aprovação registrada

F4 aprovada pelo usuário em 31/10/2026 com autorização geral de continuidade (aprove tudo). Os próximos gates não exigem nova confirmação genérica; ver relatório F5-F8.
