# ADR 0002 · Desenho para a fundação

Data: 31/10/2026. Histórico: proposto na F1 e aprovado pelo usuário para F2 em 31/10/2026. D1-D16 continuam como base aprovada na F0, com valores pendentes preservados. Detalhes da fundação e desvios limitados estão no ADR 0003.

## Persistência e isolamento

Propor SQLAlchemy síncrono com psycopg, endpoints síncronos para operações de banco e conexões curtas com NullPool no runtime. O pool remoto fará multiplexação. Evita administrar um segundo pool por invocação; não representa comparação medida de desempenho. Migração usa conexão direta, papel separado e execução controlada. Versões, prepared statements e suporte efetivo do driver serão verificados na F2.

Adotar RLS como segunda barreira, além de filtros explícitos de tenant e autorização por recurso. Runtime não será owner, superuser ou BYPASSRLS. Contexto de tenant por transação com `set_config(..., true)` parametrizado, definido após autenticação; contexto ausente nega acesso. Nenhuma configuração de sessão persistente. Tabelas globais de identidade e roteamento terão repositórios e privilégios restritos, sem SELECT de pacientes para resolver tenant. Verificar FORCE RLS, privilégios e reutilização de conexão em testes reais.

## Resolução das ambiguidades F0

- Hold é a representação do estado `held`; não criar linha de appointment nesse estado. API de reserva projeta esse status a partir do hold. Appointment nasce `scheduled`. Assim há uma única fonte para cada etapa, sem duplicar ocupação.
- Criar hold antes de confirmar em transação própria. A confirmação reúne paciente novo, consumo do hold, appointment, estado da conversa, auditoria e outbox em uma transação. Não criar cadastro definitivo ao apenas consultar horários.
- Durante HUMAN_HANDOFF nenhuma resposta automática de conversa, inclusive para mídia. Callbacks de entrega continuam atualizando metadados.
- Auditoria sem texto de mensagens ou dados clínicos; rotina de retenção separada do runtime. Imutabilidade operacional não equivale a prova criptográfica: exportação protegida e retenção são requisitos de F7.
- `LeastFutureLoad`: janela proposta da data de consulta até o fim da janela pesquisada; somar duração de scheduled/confirmed, desempatar pelo primeiro slot e UUID estável. Validar a regra com a clínica antes de F3.
- Recursos no MVP têm capacidade unitária. Capacidade maior é modelada como sub-recursos individualmente reserváveis; não usar soma não serializada. Confirmar necessidade real com a clínica.

## Filas · D6 ainda em aberto

| Opção | Custo | Latência | Operação e riscos |
|---|---|---|---|
| Serviço de entrega durável + Redis gerenciado para limites | Tarifas por uso, valores não verificados | Pode evitar polling; medir | Verificar assinatura, retries, ordenação, DLQ, região e contrato; deduplicação permanece no banco |
| Jobs PostgreSQL + agendador externo durável | Consome banco e execuções; valores não verificados | Depende da frequência de disparo | `SKIP LOCKED`, lease e retries; sem worker residente; polling e limites de cron podem não atender p95 |

Recomendação provisória: opção gerenciada para F5 se suportar região, privacidade e orçamento. Não escolher provedor sem validação. F2 pode definir o contrato e outbox sem implementar entrega externa. Rate limiting de autenticação em F2 usará contadores PostgreSQL atômicos por janela e chave pseudonimizada; medir contenção e migrar para Redis se necessário. D6 precisa de decisão final antes de F5.

## Frontend

Propor TanStack Query para cache de estado remoto e invalidação, React Router para navegação, SCSS para estilos e catálogo pt-BR centralizado. Formulários tratam UX e formatos; domínio permanece no backend. Versões estáveis e lockfiles serão fixados na F2, sem executar scaffolding nesta fase.
