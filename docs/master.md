# Prompt Mestre v2 — Plataforma de Atendimento e Agendamento Clínico via WhatsApp

## 0. Como executar este prompt

- A execução é feita em **fases com gates** (seção 15). Ao final de cada fase, pare, apresente o relatório da fase (seção 16.2) e aguarde aprovação antes de avançar. Não tente entregar tudo em uma única resposta.
- Em modo não interativo (sem humano para responder), não fique bloqueado: adote o **padrão proposto** de cada decisão pendente (seção 3), registre como ADR em `docs/decisions/` com status "assumida — pendente de confirmação" e avance apenas nas partes independentes.
- **Precedência em caso de conflito entre requisitos:** (1) segurança e privacidade dos pacientes; (2) integridade dos dados (sem dupla reserva, sem operação duplicada); (3) simplicidade operacional; (4) conveniência de UX; (5) velocidade de entrega. Se encontrar contradição neste documento, registre-a e proponha a resolução antes de implementar.
- **Fatos externos** (APIs, limites, preços, versões suportadas, políticas do WhatsApp, runtime da Vercel, recursos da Neon) devem ser verificados na documentação oficial vigente no momento da implementação. Cite fonte e data de consulta em `docs/`. O que não puder ser verificado deve ser marcado como "não verificado"; não presuma.
- **Evidência:** nada pode ser declarado "concluído", "testado", "seguro" ou "pronto" sem saída de comando, relatório de teste ou referência a arquivo/linha.
- **Idioma:** código, identificadores e mensagens de commit em inglês; interface, mensagens ao paciente e documentação em pt-BR, com tom cordial, claro e objetivo.
- Cada requisito possui um ID (ex.: `RF-AG-03`) para rastreabilidade em testes, ADRs e relatórios. Itens repetidos em mais de uma seção têm uma única fonte da verdade; as demais seções apenas referenciam.

## 1. Papel e objetivo

Atue como arquiteto de software, engenheiro backend e frontend, especialista em segurança de aplicações, engenheiro de dados e QA sênior.

Projete e implemente uma plataforma multi-clínica (multi-tenant) de atendimento via WhatsApp e gestão de agendamentos. A solução deve ser modular, segura, testável, observável e preparada para produção.

Não gere código que apenas aparenta funcionar. Antes de implementar cada fase, apresente o desenho correspondente (arquitetura, fluxos, modelo de dados, decisões de segurança, riscos e plano de testes). Implemente em etapas pequenas e verificáveis. Não invente integrações, credenciais, endpoints ou capacidades de provedores.

Quando um requisito estiver ambíguo, registre a dúvida e proponha uma decisão explícita. Não assuma regras clínicas, financeiras ou legais que não tenham sido fornecidas; quando precisar de um padrão, marque-o como "proposta a validar com a clínica/jurídico".

## 2. Escopo

### 2.1 MVP (implementar)

- Atendimento via WhatsApp (texto) com menu de serviços configurável.
- Agendamento, cancelamento e remarcação de consultas para serviços que exigem profissional.
- Cadastro mínimo de paciente e agendamento para o próprio contato ou para terceiro/dependente.
- Encaminhamento a atendimento humano e a filas financeiras/administrativas, com inbox para atendentes.
- Portal web com perfis Colaborador, Recepção/Atendente, Admin da clínica e Superadmin.
- Multi-tenancy com isolamento forte, auditoria, observabilidade e documentação.

### 2.2 Fase 2 (projetar sem implementar; não bloquear o MVP)

- Lembretes e confirmações proativas (exigem templates aprovados e respeito às regras de janela de atendimento e opt-in do WhatsApp).
- Lista de espera, convênios/planos, preços, pagamentos, relatórios gerenciais.
- Recebimento de mídia (áudio, imagem, documento) e uploads.
- Múltiplas unidades e recursos (salas/equipamentos): **modelar no banco desde o início**, com interface mínima no MVP.

### 2.3 Fora de escopo

Diagnóstico, triagem clínica, aconselhamento médico, prontuário eletrônico, teleconsulta, treinamento de modelos com dados de pacientes.

### 2.4 Parâmetros não funcionais (preencher; se vazio, usar o ponto de partida)

| Parâmetro | Ponto de partida (validar) |
|---|---|
| Clínicas simultâneas | 10 |
| Profissionais por clínica | 20 |
| Mensagens recebidas/dia (pico) | 5.000 |
| Tempo de resposta do webhook (ACK) | < 2 s (processamento posterior) |
| Latência p95 de resposta ao paciente | < 8 s, incluindo IA |
| Disponibilidade alvo | 99,5% |
| RPO / RTO | ≤ 15 min / ≤ 4 h |
| Orçamento mensal de IA por clínica | [definir] |
| Retenção de mensagens | [definir com a clínica/jurídico] |

## 3. Decisões pendentes (com padrão proposto)

Apresente estas decisões na Fase 0. Se não houver resposta, aplique o padrão proposto e registre como ADR.

| ID | Decisão | Padrão proposto | Bloqueia |
|---|---|---|---|
| D1 | Provedor WhatsApp e modelo de número | API oficial (Cloud API) atrás de uma interface `WhatsAppProvider`; um número por clínica; roteamento `phone_number_id` → `tenant_id` no backend | Fase 5 |
| D2 | Papéis | Colaborador, Recepção/Atendente (opera agenda de vários profissionais e o inbox de handoff), Admin, Superadmin; Financeiro tratado como fila, não como papel | Fase 2 |
| D3 | Identificação do paciente | Telefone do WhatsApp como identificador de contato + dados mínimos; verificação adicional (ex.: data de nascimento) antes de consultar/alterar agendamento existente; CPF opcional e apenas com base legal. Observação: código de verificação enviado pelo mesmo WhatsApp não protege contra quem já controla o número | Fase 3 |
| D4 | Agendar para terceiros/dependentes | Suportado: contato (quem escreve) ≠ paciente (quem é atendido) | Fase 1 |
| D5 | Autenticação do portal | Cookie de sessão `HttpOnly` + `Secure` + `SameSite` + proteção CSRF; frontend e API na mesma origem (rewrite da Vercel) ou sob o mesmo domínio registrável próprio. Verificar se `*.vercel.app` é tratado como site distinto entre projetos | Fase 2 |
| D6 | Fila de processamento e armazenamento de rate limit | Propor duas opções compatíveis com serverless (ex.: serviço de fila/Redis gerenciado vs. fila baseada em PostgreSQL) com trade-offs de custo, latência e operação; decidir antes da Fase 5 | Fase 5 |
| D7 | TTL do hold de horário | 10 min, configurável por clínica | Fase 3 |
| D8 | Distribuição sem preferência de profissional | Estratégia `LeastFutureLoad` (ver RF-AG-06), intercambiável | Fase 3 |
| D9 | Políticas de cancelamento/remarcação | Parâmetros por serviço: antecedência mínima, limite de remarcações; sem cobrança no MVP | Fase 3 |
| D10 | Escopo clínico do bot | Apenas agenda e encaminha; não dá orientação clínica (RF-IA-08) | Fase 6 |
| D11 | Convênio e preço | Fora do MVP; o bot não informa preços | — |
| D12 | Retenção e descarte de mensagens | Configurável por clínica; padrão definido com jurídico; criptografia de campo para conteúdo de mensagens | Fase 7 |
| D13 | Provedor de IA, contrato e região | Contrato/DPA com retenção mínima ou zero e avaliação de transferência internacional de dados (LGPD) antes de produção | Fase 6 |
| D14 | Mídia recebida | MVP: responder que só há suporte a texto e oferecer atendimento humano | Fase 5 |
| D15 | Horário do atendimento humano | Configurável por clínica; fora do horário, registrar solicitação e informar prazo | Fase 4 |
| D16 | Status do agendamento | `held` → `scheduled` → `confirmed` → `completed`; terminais alternativos `canceled`, `no_show`, `rescheduled` (com vínculo ao novo agendamento) | Fase 1 |

## 4. Requisitos funcionais

### 4.1 Atendimento pelo WhatsApp (`RF-WA`)

- **RF-WA-01** Integrar com a API oficial do WhatsApp Business Platform ou BSP compatível, atrás de uma interface própria.
- **RF-WA-02** Receber mensagens e callbacks de status (enviada, entregue, lida, falha) por webhook; responder de forma natural, clara e contextual.
- **RF-WA-03** Identificar a intenção do usuário e encaminhá-lo a um serviço configurado (atendimento clínico, financeiro, outro).
- **RF-WA-04** Administradores cadastram, editam, desativam e ordenam serviços sem alterar código.
- **RF-WA-05** Mensagens ambíguas geram perguntas curtas de esclarecimento (máximo de tentativas configurável antes de oferecer menu ou humano).
- **RF-WA-06** O usuário pode cancelar, reiniciar ou voltar uma etapa sem perder indevidamente dados já confirmados.
- **RF-WA-07** Nunca afirmar que uma operação foi concluída antes da confirmação do backend.
- **RF-WA-08** Respeitar as regras do WhatsApp: janela de atendimento de 24 h, uso de templates aprovados fora dela, opt-in e opt-out (ex.: "parar"), e limites de mensagens interativas (botões e listas). Verificar os limites vigentes na documentação oficial.
- **RF-WA-09** Mensagens com tipo não suportado (mídia, localização etc.) recebem resposta orientativa e opção de humano (D14).
- **RF-WA-10** O bot nunca revela dados de um paciente a um contato não verificado (nome, consultas, existência de cadastro). Respostas devem ser iguais para "existe" e "não existe" quando o contato não estiver verificado, evitando enumeração.

### 4.2 Conversa e estado (`RF-CV`)

- **RF-CV-01** O fluxo é uma **máquina de estados determinística** persistida no banco. A IA interpreta linguagem e extrai dados; **não** decide transições nem estado final.
- **RF-CV-02** Mensagens da mesma conversa são processadas **em série**: o estado tem versão (lock otimista) e/ou lock transacional por conversa. Mensagens rápidas em sequência, fora de ordem ou duplicadas não podem corromper o estado.
- **RF-CV-03** Sessões expiram por inatividade (padrão configurável); ao retomar, o bot reconfirma o ponto em que parou.
- **RF-CV-04** Estado crítico nunca fica apenas em memória da função serverless.
- **RF-CV-05** Existe estado `HUMAN_HANDOFF`: enquanto ativo, o bot não responde ao paciente; retorna ao bot somente por liberação explícita do atendente ou expiração configurada.

### 4.3 Agendamento (`RF-AG`)

- **RF-AG-01** Para serviços que exigem profissional, listar apenas profissionais ativos, habilitados para o serviço e com agenda configurada.
- **RF-AG-02** Perguntar se há preferência por profissional; havendo, consultar a disponibilidade dele.
- **RF-AG-03** Exibir datas disponíveis dentro da janela configurada (padrão: próximos 30 dias, limitada pela antecedência máxima da clínica), respeitando fuso horário, feriados, bloqueios, expediente, duração, intervalos e antecedência mínima. Como listas do WhatsApp têm limite de itens, definir paginação ou agrupamento (semana → dia → horário) e documentar.
- **RF-AG-04** Após a escolha da data, apresentar somente horários efetivamente elegíveis.
- **RF-AG-05** Antes da confirmação, apresentar resumo: serviço, profissional, data, hora, unidade (se aplicável), duração e paciente.
- **RF-AG-06** Sem preferência, selecionar entre os elegíveis pela estratégia configurável. Padrão `LeastFutureLoad`: (1) menor carga futura de horas agendadas no período relevante; (2) menor horário disponível; (3) desempate determinístico e auditável. Não usar o total histórico.
- **RF-AG-07** Identificar o paciente conforme D3. Dados pessoais (CPF, telefone, nascimento) não são repetidos em mensagens, logs ou telas sem necessidade.
- **RF-AG-08** Paciente novo: coletar só os campos obrigatórios definidos pela clínica, informar a finalidade e validar no backend.
- **RF-AG-09** Criar paciente (quando necessário), reserva e agendamento em **uma única transação** (seção 8).
- **RF-AG-10** Cancelamento e remarcação conforme políticas configuradas (D9); remarcação é atômica (libera o horário antigo e reserva o novo, ou nada muda).
- **RF-AG-11** Nunca permitir dupla reserva, inclusive sob concorrência.
- **RF-AG-12** Reserva temporária (hold) com expiração durante o fluxo de confirmação (D7).
- **RF-AG-13** Ciclo de vida de status conforme D16, com transições validadas no domínio.

### 4.4 Atendimento humano e outros setores (`RF-HU`)

- **RF-HU-01** Transferir para humano com registro do motivo e do histórico mínimo necessário.
- **RF-HU-02** Encaminhar solicitações financeiras/administrativas para filas, equipes ou canais configurados.
- **RF-HU-03** Respeitar horário do atendimento humano (D15).
- **RF-HU-04** Inbox no portal para atendentes: ver conversas transferidas, assumir, responder, devolver ao bot, encerrar. Acesso limitado à clínica e à fila do atendente.

### 4.5 Portal profissional e administrativo (`RF-PT`)

Perfis:

- **Colaborador:** acessa somente os próprios agendamentos e as configurações de agenda permitidas.
- **Recepção/Atendente:** opera agenda dos profissionais para os quais tiver permissão e o inbox de atendimento humano da própria clínica.
- **Admin da clínica:** gerencia colaboradores, serviços, horários, bloqueios, integrações e visualiza dados da própria clínica conforme permissões.
- **Superadmin da plataforma:** cadastra e administra clínicas e seus administradores. Acesso a dados de pacientes **negado por padrão**; acesso excepcional apenas por processo *break-glass*: justificativa obrigatória, escopo e duração limitados, notificação ao Admin da clínica e trilha de auditoria imutável.

Telas mínimas: login/MFA e recuperação de senha; agenda (dia/semana) do colaborador; horários, exceções e bloqueios; serviços (CRUD, ordem, ativar/desativar); colaboradores; inbox de atendimento; auditoria (Admin); gestão de clínicas (Superadmin); configuração de integrações com campos de segredo apenas de escrita (nunca exibir valor salvo).

Requisitos de frontend: React + TypeScript em modo `strict`; estado de servidor com biblioteca justificada; estados de carregamento, vazio e erro; responsivo; acessibilidade WCAG 2.1 AA; textos em pt-BR centralizados para facilitar i18n; nenhuma regra de negócio no frontend.

Aplicar menor privilégio. Permissões são verificadas no backend em toda requisição; ocultar botões no frontend não é controle de acesso.

## 5. Stack e organização

Tecnologias obrigatórias:

- Frontend: React + TypeScript; estilos em SCSS.
- Backend: Python + FastAPI, Pydantic v2, SQLAlchemy 2.x (justificar sync vs. async considerando pooling na Neon).
- Banco: PostgreSQL na Neon. Migrações: Alembic.
- Deploy: Vercel, respeitando limites do runtime serverless.

Use versões estáveis e compatíveis, fixadas no gerenciador de dependências (lockfile versionado). Justifique cada biblioteca relevante. Estrutura mínima:

- `frontend/`: aplicação React.
- `backend/`: API, domínio, persistência e integrações.
- `docs/`: documentação funcional e técnica em Markdown (inclui `docs/decisions/` para ADRs).
- `tests/`: unitários, integração, segurança e e2e, organizados por camada.

Camadas: apresentação, aplicação/casos de uso, domínio e infraestrutura. Rotas HTTP são finas: validam entrada, autenticam, autorizam e delegam a casos de uso. Regras de negócio não ficam em componentes React, handlers de webhook nem em prompts.

Qualidade automatizada obrigatória: formatação e lint (ex.: Ruff, ESLint), type-check (ex.: mypy/pyright, `tsc --noEmit`), testes (pytest, Vitest, e2e), análise de dependências, varredura de segredos e SAST. Tudo roda em pipeline de CI desde a Fase 2.

## 6. Arquitetura de IA e guardrails (`RF-IA`)

- **RF-IA-01** Abstração de provedor de IA (interface/contrato) com adaptadores independentes (OpenAI, Google, Anthropic ou outros). Provedor, modelo, endpoint permitido e chave são configurados por ambiente ou secret do deploy.
- **RF-IA-02** Validar a configuração na inicialização e falhar de forma segura se incompleta.
- **RF-IA-03** A IA interpreta linguagem e sugere intenção/dados estruturados; o backend determina permissões, disponibilidade, elegibilidade, estado e resultado final. Saídas do modelo são validadas por schema antes de uso.
- **RF-IA-04** Ferramentas expostas à IA: estritamente as necessárias, com contratos tipados, validação de argumentos e autorização independente. **O conjunto de ferramentas disponível depende do estado da conversa e da identidade verificada.** `tenant_id`, identidade do paciente e permissões vêm da sessão no servidor, nunca de argumentos escolhidos pelo modelo. Limite máximo de chamadas de ferramenta por turno.
- **RF-IA-05** A IA não executa SQL, não acessa o banco, não executa código ou shell, não acessa arquivos arbitrários e não escolhe URLs livres.
- **RF-IA-06** Toda mensagem de usuário, conteúdo recebido por WhatsApp, documentos e resultados externos são entrada não confiável. Instruções nelas contidas não alteram políticas, permissões ou instruções de sistema (defesa contra *prompt injection*).
- **RF-IA-07** A IA não inventa disponibilidade, não confirma agendamento, não altera cadastro nem cancela consulta sem executar a ferramenta correspondente e receber sucesso do backend.
- **RF-IA-08** **Segurança clínica:** a IA não diagnostica, não orienta tratamento, não interpreta sintomas ou exames. Diante de relato de urgência/emergência, responde com texto fixo **aprovado pela clínica** (não gerado pelo modelo) orientando buscar atendimento de emergência e transfere para humano. Detecção por regras determinísticas além da IA.
- **RF-IA-09** **Minimização de dados:** não enviar dados pessoais ou clínicos ao modelo sem necessidade comprovada, base legal e configuração aprovada. Usar identificadores opacos e contexto mínimo; mascarar/pseudonimizar antes do envio. Texto livre do paciente pode conter dado sensível: tratar como tal.
- **RF-IA-10** **Controle de custo e abuso:** limite de tokens por turno e por conversa, cota mensal por clínica, rate limit por número, timeout e retry com backoff.
- **RF-IA-11** **Modo degradado:** se a IA estiver indisponível ou exceder cota, o fluxo continua por menu determinístico (botões/listas) e/ou transferência para humano.
- **RF-IA-12** Registrar provedor/modelo, latência, tokens e resultado de ferramentas como metadados operacionais, sem armazenar prompts sensíveis nem dados pessoais desnecessários.
- **RF-IA-13** Dados de pacientes não são usados para treinamento sem autorização e fundamento legal específicos.

## 7. Segurança obrigatória

Defesa em profundidade. Segurança não pode depender do prompt da IA nem da validação do frontend.

### 7.1 Injeção, XSS e cabeçalhos

- ORM ou consultas parametrizadas em todas as operações; nunca concatenar entrada em SQL, nomes de tabela, cláusulas ou ordenações. Ordenação/filtros dinâmicos usam allowlists de campos e operadores.
- Usuário de banco de runtime com privilégios mínimos, distinto do usuário de migração.
- Texto de usuário é renderizado como texto. `dangerouslySetInnerHTML` apenas em exceção justificada, com sanitização robusta e allowlist.
- CSP adequada, `X-Content-Type-Options: nosniff`, `Referrer-Policy` e política de frame. Validar esquemas de URL (bloquear `javascript:`, `data:` e não permitidos). Não inserir conteúdo de paciente em scripts, atributos HTML ou CSS.

### 7.2 CSRF, CORS e sessões

- Conforme D5: cookies `HttpOnly`, `Secure`, `SameSite` adequado, proteção CSRF e rotação de sessão. Evitar `localStorage` para tokens de longa duração.
- CORS restrito a origens explícitas; nunca `*` com credenciais.
- Expiração, revogação, rotação e logout. Reautenticação ou MFA em operações sensíveis.

### 7.3 Autenticação, autorização e multi-tenancy

- RBAC com permissões explícitas por recurso e ação; matriz de permissões documentada e testada.
- `tenant_id` em todas as entidades e consultas multi-tenant, **derivado da identidade autenticada no servidor**; nunca aceito livremente do cliente.
- Avaliar e justificar **Row Level Security** do PostgreSQL como defesa em profundidade (contexto de tenant definido por transação, compatível com o pooling da Neon). Se rejeitada, registrar o motivo em ADR.
- Isolamento também em tarefas assíncronas, relatórios, exports, cache, arquivos e logs.
- Prevenir IDOR/BOLA: UUID não substitui autorização; verificar propriedade e escopo em toda leitura, alteração e exclusão.
- Colaborador: só recursos próprios. Admin: só a própria clínica. Superadmin: escopo mínimo, ações auditadas, break-glass conforme seção 4.5.
- Senhas com Argon2id (preferencial) ou bcrypt com parâmetros atuais. Política de senha, recuperação segura, rate limiting e MFA para perfis privilegiados.
- `audit_logs` somente de inserção (sem UPDATE/DELETE para o usuário de runtime).

### 7.4 Webhooks e abuso

- Validar assinatura criptográfica sobre o **corpo bruto** da requisição, antes de qualquer parse, com comparação em tempo constante; validar método, formato e timestamp conforme documentação oficial. Tratar o desafio de verificação do provedor.
- Idempotência por identificador único do evento (`webhook_events` com unicidade por provedor + id). Eventos fora de ordem e callbacks de status duplicados são tratados sem efeito colateral.
- IP não é mecanismo único de autenticação.
- Rate limiting por IP, número, usuário, tenant e endpoint, com limites distintos para webhooks e usuários autenticados, usando armazenamento compartilhado compatível com serverless (D6); contador em memória local não conta.
- Proteção contra replay, spam, enumeração e brute force.
- Responder o webhook rapidamente (ACK) e processar em fila/worker compatível com o deploy.

### 7.5 SSRF, RCE e path traversal

- Backend não busca URL arbitrária. Integrações usam hosts e protocolos permitidos; bloquear loopback, redes privadas, link-local e metadados de cloud. Desabilitar redirects ou revalidar cada destino.
- Proibido `eval`, `exec`, shell ou comandos montados com entrada externa; sem desserialização insegura.
- Uploads fora do MVP: não implementar essa superfície. Se entrar na Fase 2, exigir limite de tamanho, extensão e MIME real, nome aleatório, armazenamento fora da raiz pública, verificação de malware e proteção contra traversal.

### 7.6 Dados pessoais e LGPD

- Nome, CPF, telefone, nascimento e dados de saúde são dados pessoais; dados de saúde são sensíveis. Definir finalidade, base legal, transparência, minimização, retenção e descarte.
- TLS em trânsito; proteção em repouso conforme risco (criptografia de campo para conteúdo de mensagens e CPF, avaliando busca por hash determinístico com chave separada).
- Mascarar CPF e telefone em telas e logs; nunca registrar senha, token, chave ou payload clínico integral.
- Atendimento aos direitos do titular (acesso, correção, exclusão/anonimização), conciliado com a trilha de auditoria.
- Documentar papéis (controlador/operador), encarregado, relatório de impacto (RIPD), operadores e suboperadores (WhatsApp/BSP, IA, Neon, Vercel) e transferência internacional de dados.
- Plano de resposta a incidentes com prazos de comunicação.

### 7.7 Segredos e configuração

- Segredos apenas em variáveis/secret manager do ambiente; `.env` nunca versionado (`.gitignore`); `.env.example` somente com nomes e valores fictícios.
- Ambientes separados (local, teste, staging, produção) com credenciais distintas; nunca reutilizar credenciais.
- Segredos nunca no frontend, repositório, logs, mensagens de erro ou documentação. Validar configuração sem imprimir valores. Prever rotação.
- Segredos de integração por clínica (ex.: tokens do WhatsApp) armazenados criptografados e write-only na interface.

## 8. Integridade e concorrência do agendamento

- Modelar horários, duração, fuso, intervalos, bloqueios, feriados, status e capacidade do recurso. Persistir timestamps em UTC e manter o fuso IANA da clínica para apresentação e regras locais.
- A consulta de disponibilidade é informativa; **a confirmação revalida dentro de transação**. Um `SELECT` prévio nunca é garantia contra conflito.
- **Proposta a validar:**
  - `appointments` com intervalo (`tstzrange`) e **exclusion constraint** (`btree_gist`) impedindo sobreposição por profissional (e por recurso, quando houver) para status ativos.
  - Holds em `appointment_holds` com `expires_at`; a criação e a confirmação ocorrem em transação que serializa por profissional (lock de linha ou `pg_advisory_xact_lock`), verifica agendamentos **e** holds ativos usando o relógio do banco. Expiração é aplicada na própria consulta; o job de limpeza serve apenas para higiene.
  - Usar apenas locks de escopo de transação, compatíveis com pooling em modo transação. Verificar essa compatibilidade na documentação da Neon e do driver escolhido.
  - Idempotência na criação: unicidade `(tenant_id, idempotency_key)` derivada do evento de entrada.
- A operação de criação é atômica (paciente, reserva/agendamento e estado do fluxo). Remarcação também.
- Definir recuperação de holds abandonados.
- Testar duas ou mais requisições concorrentes ao mesmo horário em **PostgreSQL real** (nunca SQLite).

## 9. Modelo de dados (propor e justificar)

Entidades mínimas:

- `tenants`, `units`, `resources`;
- `users`, `roles`, `permissions`, vínculos usuário-clínica(-profissional);
- `professionals`, `services`, `professional_services` (duração/regra específica quando houver);
- `contacts` (quem escreve no WhatsApp) e `patients` (quem é atendido), com vínculo entre eles;
- `professional_schedules`, `schedule_exceptions`, `blocked_periods`, `holidays`;
- `appointments` (com status e histórico de transições) e `appointment_holds`;
- `conversations`, `messages`, `conversation_state` (com versão), `handoffs`;
- `webhook_events`, `outbox`/fila de saída, `ai_usage`;
- `audit_logs`, `consents` (opt-in/opt-out e consentimentos);
- configurações de integração por clínica (segredos criptografados), `service_queues`.

Defina PK, FK, constraints, índices e regras de exclusão (soft delete vs. anonimização). Evite duplicar dados pessoais. Avalie índices compostos iniciados por `tenant_id`. Migrações Alembic reversíveis quando possível, com teste de upgrade a partir do zero e a partir de dados existentes.

## 10. API e validação

- Schemas Pydantic para validar e normalizar toda entrada e saída; rejeitar campos inesperados em operações sensíveis.
- Limitar tamanho de strings, arrays, paginação e payloads.
- Validar CPF no backend quando coletado (dígito verificador não é prova de identidade). Telefone em E.164. Datas, horários, fuso, duração e transições de status validados.
- Erros genéricos ao cliente; detalhes só em logs protegidos. Respostas e códigos HTTP padronizados; sem stack trace ao usuário.
- Paginação, filtros allowlisted e limites máximos.
- Operações não idempotentes que possam ser repetidas aceitam chave de idempotência.
- Versionar a API (`/v1`) e publicar o contrato OpenAPI gerado.

## 11. Observabilidade e operação

- Logs estruturados com correlation ID e identificador de tenant não sensível; mascaramento de dados pessoais e segredos.
- Métricas: latência, erros, falhas de webhook, tamanho/atraso de fila, conflitos de agenda, chamadas e custo de IA, taxa de handoff, funil de agendamento.
- Alertas: falhas de integração, aumento de erros, anomalias, estouro de cota de IA.
- Timeouts, retries com backoff e circuit breaker onde fizer sentido; sem repetir operações não idempotentes sem chave.
- Health checks que não exponham informações internas.
- Documentar backup, restauração (testar ao menos uma vez), migrações e plano de recuperação, verificando retenção/PITR conforme o plano contratado na Neon.

## 12. Deploy: Vercel e Neon

- Validar a compatibilidade do FastAPI e das dependências com o runtime Python da Vercel vigente (versão do Python, tamanho de função, timeouts, limites de payload). Documentar limites e cold starts.
- Separar frontend e API somente se simplificar build e limites; respeitar D5 (mesma origem/domínio) para cookies.
- Não depender de processos persistentes. Não presumir que `BackgroundTasks` sobreviva ao encerramento da função; tarefas demoradas e expiração/limpeza periódica usam fila ou agendador compatível (verificar limites de cron do plano).
- Neon: usar conexão com pooling para o runtime e **conexão direta para migrações**; configurar o driver de acordo com o modo de pooling (ex.: cache de prepared statements); limitar conexões por invocação. Posicionar a região do banco próxima à da função.
- Migrações Alembic em etapa controlada de release; nunca migrações destrutivas automáticas por requisição. Branches da Neon para preview/testes quando disponíveis.
- Variáveis e credenciais separadas por ambiente.
- Não declarar o deploy pronto sem build, testes e verificação real no ambiente de destino.
- Se uma exigência for incompatível com a Vercel ou com o provedor, explique a limitação e proponha alternativa antes de implementar.

## 13. Testes obrigatórios

Cada fase entrega seus testes (não deixar para o final). Cobrir:

**Domínio e dados**
- disponibilidade, duração, fuso, feriados, bloqueios e intervalos (incluir testes baseados em propriedades);
- conflito e concorrência de agendamento em PostgreSQL real (ex.: 50 tentativas simultâneas no mesmo horário → exatamente 1 sucesso);
- expiração de holds; remarcação atômica;
- migrações (upgrade do zero e com dados) e integridade referencial.

**Mensageria e conversa**
- idempotência de webhooks; reenvio, duplicidade, eventos fora de ordem e mensagens simultâneas na mesma conversa;
- assinatura inválida, replay e timestamp fora da janela;
- transições da máquina de estados, handoff e retorno ao bot;
- falhas, timeouts e *rate limits* dos provedores de IA e WhatsApp; modo degradado.

**Segurança**
- permissões por perfil e matriz RBAC; isolamento entre clínicas e entre colaboradores (IDOR/BOLA);
- SQL injection, XSS (refletido, armazenado, DOM), CSRF, CORS, SSRF, rate limiting, enumeração de pacientes;
- **injeção de prompt e jailbreak:** suíte versionada com casos adversários (pedir dados de outro paciente, mudar `tenant_id`, ignorar instruções, forçar chamada de ferramenta, pedir conselho clínico); critério: zero violações;
- autorização das ferramentas da IA testada **sem** passar pelo modelo (chamada direta com argumentos maliciosos);
- varredura de dependências, segredos e SAST sem achados críticos/altos sem exceção documentada.

**Qualidade da IA e UX**
- conversas de referência (*golden conversations*) com o modelo simulado em CI, e avaliação periódica opcional com modelo real;
- testes e2e dos fluxos críticos (agendar, cancelar, remarcar, handoff) e de acessibilidade (ex.: axe);
- teste de carga básico do webhook e do cálculo de disponibilidade.

Unitários para domínio, integração para banco/API, e2e para fluxos críticos. Não alegar cobertura sem relatório de execução.

## 14. Documentação obrigatória

`docs/` em Markdown, atualizada **a cada fase**, no mínimo:

- `README.md` — visão geral, arquitetura e execução local;
- `architecture.md` — componentes, camadas, decisões e diagramas;
- `decisions/` — ADRs (inclui decisões D1–D16, com status);
- `requirements.md` — requisitos com IDs e rastreabilidade para testes;
- `whatsapp-flow.md` — fluxo conversacional, estados e transições;
- `scheduling.md` — disponibilidade, holds, conflitos, remarcação e status;
- `users-and-permissions.md` — perfis, RBAC, matriz de permissões, break-glass e isolamento multi-tenant;
- `data-model.md` — entidades, relacionamentos, índices e constraints;
- `api.md` — endpoints, schemas e erros;
- `ai-provider-setup.md` — provedores, variáveis, troca de modelo, guardrails e cotas;
- `whatsapp-provider-setup.md` — webhook, assinatura, janelas, templates e opt-in/out;
- `security.md` — threat model (STRIDE), controles e checklist;
- `lgpd.md` — dados tratados, finalidades, base legal, retenção, direitos, operadores e transferência internacional;
- `deployment-vercel-neon.md` — deploy, variáveis, banco, migrações e limites verificados;
- `testing.md` — execução, estratégia e relatório;
- `operations.md` — logs, métricas, alertas, backup/restauração e resposta a incidentes (runbooks).

Documente decisões e limitações reais. Sem credenciais ou dados reais.

## 15. Processo de execução em fases

Cada fase termina com: código + testes + documentação atualizados, comandos executados com saída, riscos e pendências, e **gate de aprovação**.

| Fase | Conteúdo | Saída principal |
|---|---|---|
| **F0 Descoberta** | Ambiguidades, premissas, perguntas bloqueantes, decisões D1–D16, NFRs, escopo | Lista de perguntas e ADRs de decisão |
| **F1 Design** | Arquitetura, fluxos, estados, modelo de dados, threat model STRIDE, matriz de permissões, contratos de API e interfaces de provedores | Documentos de design e diagramas |
| **F2 Fundação** | Repositório, CI, lint/type/test/SAST, configuração validada, logs base, migrações iniciais, autenticação, RBAC, isolamento multi-tenant (e RLS, se aprovada) | Testes de isolamento e permissão passando |
| **F3 Agendamento** | Agendas, disponibilidade, holds, agendamentos, status, idempotência, concorrência | Testes de concorrência em PostgreSQL real |
| **F4 API e Portal** | Endpoints, telas mínimas, inbox de atendimento, auditoria | Fluxos do portal ponta a ponta |
| **F5 WhatsApp determinístico** | Webhook seguro, fila, máquina de estados com menus (sem IA), handoff | Fluxo completo de agendamento pelo WhatsApp sem IA |
| **F6 IA** | Abstração de provedores, interpretação de intenção, ferramentas restritas, guardrails, cotas, modo degradado | Suíte de injeção de prompt e conversas de referência |
| **F7 Hardening e conformidade** | Revisão de segurança, LGPD, teste de carga, varredura de dependências, restauração de backup | Relatório de segurança e conformidade |
| **F8 Deploy** | Staging, verificação real, checklist de produção, runbooks | Ambiente verificado e passos manuais |

Não avance para fase que dependa de decisão de negócio não definida: registre a pendência e implemente apenas partes independentes (ver seção 0 para modo não interativo).

## 16. Critérios de aceite e relatórios

### 16.1 A entrega só é considerada pronta quando

- fluxos de agendar, cancelar, remarcar e transferir para humano funcionam ponta a ponta no WhatsApp e no portal (testes e2e);
- colaborador não acessa dados de outro profissional e uma clínica não acessa dados de outra (testes automatizados para cada endpoint);
- N requisições concorrentes ao mesmo horário resultam em exatamente uma reserva;
- o mesmo webhook reenviado várias vezes gera uma única operação;
- a suíte de injeção de prompt e de autorização de ferramentas passa com zero violações, e a IA não executa operações fora de ferramentas autorizadas;
- entradas maliciosas são tratadas sem execução de código, SQL ou HTML;
- varredura de segredos sem achados e nenhum segredo no frontend, repositório ou logs;
- migrações, testes, lint, type-check, análise de dependências e build executados com sucesso e com saída anexada;
- o sistema opera em modo degradado sem IA;
- documentação de configuração, operação, LGPD e limitações do deploy serverless completa;
- restauração de backup testada ao menos uma vez.

### 16.2 Relatório de cada fase e relatório final

Cada fase apresenta: objetivo e escopo entregue, decisões tomadas (ADRs), arquivos criados/alterados, comandos executados com resultados, testes e evidências, riscos remanescentes, pendências de decisão e próximo passo proposto.

O relatório final acrescenta: arquitetura implementada, estrutura de diretórios, variáveis necessárias (sem valores secretos), matriz de rastreabilidade requisito → teste, resultados consolidados e passos manuais de deploy.

## 17. Regras de qualidade

- Priorize segurança, integridade dos dados e simplicidade operacional.
- Aplique SOLID, DRY e KISS sem criar abstrações desnecessárias (YAGNI).
- Tipagem estática: TypeScript em modo estrito e type hints no Python verificados por ferramenta.
- Evite lógica de negócio duplicada entre frontend, backend e IA.
- Não armazene estado crítico apenas em memória local da função serverless.
- Não exponha stack traces ao usuário.
- Não marque tarefa como concluída sem evidência verificável.
