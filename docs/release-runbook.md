# Release preparado — ambiente remoto pendente

31/10/2026. A aprovação geral autoriza a continuidade; não houve implantação, push ou contratação. Faltam identificação das contas/ambientes, configuração privada, domínio, região/plano e responsáveis clínicos/jurídicos. Não inserir tokens no chat.

## Artefatos

`pyproject.toml` declara entrypoint `backend.asgi:app` e Python 3.12. `vercel.json` prepara frontend em `public/`, configura a mesma origem para portal e API e cabeçalhos de segurança. HashRouter dispensa reescrita de rotas clínicas. `.vercelignore` exclui ferramentas, banco local, fixtures, documentação e arquivos de ambiente. Essas configurações precisam ser verificadas no build Vercel real; build Vite local não prova o empacotamento da função.

## Antes do staging

- Selecionar projetos Vercel/Neon, plano e regiões compatíveis. Confirmar limites atuais de função/payload/cron e PITR/retentiva no plano real.
- Criar banco de staging separado. Provisionar papéis de migração e runtime conforme migração 0001; runtime sem superuser/BYPASSRLS e sem propriedade de tabelas.
- Guardar `DATABASE_URL` pooled apenas no runtime e `MIGRATION_DATABASE_URL` direta somente no processo de release. Chaves HMAC/cifra distintas por ambiente; guardar cópia recuperável em secret manager, separada de backup.
- Definir `APP_ENV=staging`, origem pública HTTPS exata e MFA obrigatório. Não usar credenciais de teste nem dados reais nos smoke tests.
- Executar release checks e `alembic upgrade head` fora de HTTP. Não colocar migração automática por requisição ou ao iniciar função.
- Publicar staging; testar cookies, CSRF, cache, headers, login/MFA, seleção de clínica, IDOR, agenda, handoff, outbox e health/readiness. Verificar conexão pooled real e btree_gist.
- Configurar invocações duráveis de worker compatíveis com latência requerida. Cron minuto a minuto não comprova meta de resposta menor que 8 segundos. Não manter loop residente dentro de função serverless.
- Registrar número de teste Meta, webhook e versão oficial vigente. Fazer teste sintético de recebimento/envio/entrega e janela; somente depois habilitar envio controlado.

## Produção

Exige responsáveis, políticas de identidade/retenção, contratos/DPA/região/transferência, texto fixo clínico aprovado, metas medidas, backup restaurado no destino e revisão dos achados de dependências. A IA permanece desligada sem provedor/modelo e política aprovados. O relatório distingue o que foi testado localmente do que depende do destino.

Rollback de app: promover artefato anterior compatível com schema; não executar downgrade destrutivo em produção. Pausar entrada/envio se integridade ou isolamento estiverem em dúvida. Restaurar em banco separado, verificar schema/RLS/grants/cifra e conciliar eventos/entregas antes de trocar conexão. `unknown` não é seguro para reenvio automático. Reaplicar políticas de descarte aprovadas após recuperação.

Fontes: [FastAPI na Vercel](https://vercel.com/docs/frameworks/backend/fastapi), [runtime Python](https://vercel.com/docs/functions/runtimes/python), [pooling Neon](https://neon.com/docs/connect/connection-pooling), consultadas em 31/10/2026. Referências não certificam o plano ainda não informado.
