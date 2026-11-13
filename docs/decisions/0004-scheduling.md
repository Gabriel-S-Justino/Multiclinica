# ADR 0004 · Execução da F3

Data: 31/10/2026. F2 aprovada pelo usuário; decisões de implementação submetidas ao gate F3.

Antes de implementar, desenho: manter holds e appointments separados, serializar mutações de agenda com advisory lock **transacional por clínica**, usar exclusão GiST de intervalos ativos por profissional e triggers que verificam conflitos entre holds/agendamentos/recursos. Sem locks de sessão. Essa granularidade é mais conservadora que o lock por profissional da F1: protege recursos compartilhados e simplifica a ordem de locks. Custo: mutações de uma clínica são sequenciais; não há garantia de throughput sem teste de carga. Clínicas distintas têm chaves diferentes; colisão de hash apenas reduz paralelismo.

Recursos são associações relacionais com FK composta por tenant e destino exclusivo (hold ou appointment). Triggers repetem o lock/checagem inclusive para escrita SQL direta pelo runtime. Exclusão entre appointments é defesa adicional. Expiração usa clock_timestamp do banco após obter lock, independente de limpeza. Confirmação consome hold antes de inserir appointment dentro da mesma transação.

Regras clínicas D3/D9 continuam pendentes: não inventar durações ou antecedências de produção. Serviços exigem política validada explicitamente. Testes usam serviços sintéticos. Vínculos de pacientes existentes exigem verificação manual registrada pela clínica, com finalidade, validade e revogação; não implementar reconhecimento automático por telefone/nascimento. Nenhuma coleta de CPF nesta fase. Paciente novo é criado somente na confirmação, sem busca por nome/data para vinculação.

Dados pessoais de contato/paciente cifrados com AES-GCM da biblioteca cryptography, nonces aleatórios e AAD por tenant/entidade/campo; chave derivada de FIELD_KEY via HKDF com domínio próprio. Índice de telefone usa HMAC com TOKEN_KEY (chave distinta da cifra). Sem nomes/telefones nos eventos, auditoria ou resultados idempotentes.

Contratos F3 são casos de uso tipados no backend; endpoints e telas de agenda ficam para F4. Confirmação e remarcação gravam eventos na outbox no commit, sem integrar WhatsApp/IA. Estado de conversa mínimo entra nesta fase para testar atomicidade; o fluxo completo é F5.

Plano de testes: propriedades de intervalos/fuso; feriados, exceções, buffers e bloqueios; 50 holds simultâneos para um slot → 1 vencedor; 50 confirmações do mesmo hold → 1 efeito; replay idempotente; recursos entre profissionais; hold vencido; remarcação com falha sem alterações parciais; RLS/IDOR e escrita direta; migrations 0001→0002 com dados. Nenhum teste pode ser substituído por SQLite.
