# Privacidade e incidentes — procedimento para revisão

Este é um procedimento técnico pendente de validação pelo controlador e jurídico. Não declara conformidade LGPD. Fonte legal consultada em 31/10/2026: [texto atualizado da Lei 13.709/2018 na Câmara](https://www2.camara.leg.br/legin/fed/lei/2018/lei-13709-14-agosto-2018-787077-normaatualizada-pl.html). Regras e prazos aplicáveis devem ser confirmados pelos responsáveis com a regulamentação vigente.

## Pendências de ativação

Preencher: controlador e operador, encarregado/canal de contato, finalidades e bases por tratamento, política para menores/dependentes, retenção e preservação por categoria, contratos/suboperadores, regiões/transferência, texto clínico fixo, política de incidentes e responsáveis de plantão. Aprovação de implementação não preenche esses dados. IA não recebe texto de paciente até aprovação específica e configuração.

## Solicitação de titular

Registrar protocolo sem conteúdo clínico em log. Verificar identidade por procedimento aprovado e escopo do solicitante; posse do WhatsApp não basta para todos os riscos. Responsável analisa restrições de preservação antes de exportar, corrigir ou anonimizar. Entregar somente dados autorizados por canal seguro, com prazo e acesso controlados. Registrar evento de auditoria sem o conteúdo exportado. Não criar export público, envio por e-mail automático ou exclusão em massa a partir de número informado.

O sistema ainda não implementa exportação/anonimização automatizada nem retenção destrutiva. Essas ações dependem da política ausente; não marcar direitos/descartes como concluídos. A equipe deve manter procedimento operacional restrito e validar a implementação correspondente antes de produção.

## Incidente

1. Abrir registro restrito com responsável e horário; preservar metadados, sem copiar payloads para chats/logs públicos.
2. Conter: desativar canal/envio, revogar sessões e chaves afetadas, bloquear acesso comprometido. Não apagar evidência antes de orientação do responsável.
3. Avaliar escopo, tipos de dados, titulares, período, possível acesso indevido e operadores envolvidos. Correlacionar IDs de auditoria, sem ampliar a exposição.
4. O controlador/encarregado decide comunicações e prazos conforme risco e regras vigentes. Não presumir que este runbook cumpre as obrigações legais.
5. Recuperar em ambiente separado; validar schema, permissões, cifragem e estado da fila. Conciliar entregas `unknown` antes de reenviar. Reaplicar descartes/preservações aprovados.
6. Registrar causa, correção, verificações, comunicação e prevenção; validar retorno controlado à operação.

## Backup e retenção

Dump e chave são necessários para recuperação dos campos cifrados. Guardá-los separadamente com controle de acesso e teste de restauração. Dump não substitui PITR. A política precisa abranger backups, provedores externos, mensagens, jobs, contextos temporários e trilha de auditoria. Recuperação pode reintroduzir dados eliminados; conciliação e tombstones aprovados precisam ser implementados antes de descarte automático.
