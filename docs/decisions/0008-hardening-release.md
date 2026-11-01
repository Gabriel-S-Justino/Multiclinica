# ADR 0008 — Hardening e release controlado

31/10/2026. Continuidade autorizada pelo usuário. Executar verificações locais, teste real de restauração com dados sintéticos, auditoria atual de dependências, ensaio de carga com limites explícitos e preparação de release. Esses resultados não equivalem a atestado de conformidade nem desempenho do plano remoto.

Não definir base legal, retenção, contato do encarregado ou papéis contratuais sem clínica/jurídico. Retenção automática destrutiva e exclusão de pacientes permanecem desativadas até política aprovada. Preparar inventário, procedimento de direitos e incidentes com campos pendentes; jamais declarar LGPD concluída por possuir cifragem.

F8: preparar entrada FastAPI, artefatos frontend, contrato OpenAPI, configuração de mesma origem e runbook. A ativação real depende das contas/ambientes, domínio, URLs de banco, chaves, região/plano e configuração de worker que o usuário informar. Não usar conta de terceiro ou publicar ambiente clínico sem esses dados. Migrations são comando controlado fora de HTTP. Webhook ativo e worker exigem configuração própria; um deploy do portal não representa sistema completo operante.

Teste de backup usa `pg_dump`/`pg_restore` e banco descartável separado, sem serviço Windows. Verifica dados cifrados, recuperação com chave e políticas RLS/grants. Não mede PITR, RPO/RTO nem capacidade de restauração da conta Neon, que continuam dependentes do plano.

Fontes oficiais consultadas em 31/10/2026: [PostgreSQL dump/restore](https://www.postgresql.org/docs/current/backup-dump.html), [FastAPI Vercel](https://vercel.com/docs/frameworks/backend/fastapi), [runtime Python](https://vercel.com/docs/functions/runtimes/python), [Neon pooling](https://neon.com/docs/connect/connection-pooling), [LGPD — texto atualizado da Câmara](https://www2.camara.leg.br/legin/fed/lei/2018/lei-13709-14-agosto-2018-787077-normaatualizada-pl.html). Prazos legais e obrigações concretas exigem análise do responsável; não se presume aplicabilidade ou conformidade.
