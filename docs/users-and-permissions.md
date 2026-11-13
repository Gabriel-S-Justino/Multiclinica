# Permissões e identidade

O login identifica a conta. O vínculo ativo determina a clínica, o cargo e as permissões aplicadas em cada requisição. Uma conta pode ter vínculos diferentes em mais de uma clínica.

| Cargo | Acesso |
|---|---|
| Colaborador | Agenda própria e dados mínimos associados. Edita horários quando autorizado. |
| Recepção | Agenda dos profissionais atribuídos e conversas das filas atribuídas. Edita horários quando autorizado. |
| Admin da clínica | Agenda e configurações da clínica, serviços, equipe, filas, integrações e auditoria. Administra cargo, estado do vínculo, horários, profissionais e filas da própria clínica. |
| Superadmin | Administração de clínicas e contas, convites e permissões dos vínculos de todas as clínicas. O perfil de plataforma tem acesso aos dados administrativos. Agendas, pacientes, conversas e credenciais são restritos aos vínculos clínicos autorizados. |

O Admin gera convites na clínica ativa. O Superadmin escolhe uma clínica existente e gera o convite naquela clínica. O destinatário ativa a conta ou aceita com uma conta existente. O vínculo é gravado após o aceite. Alterações de permissões são auditadas, invalidam sessões do vínculo e protegem o último administrador ativo.

A conta do Superadmin exige um registro global de operador ativo e MFA. Após entrar, o Superadmin abre **Administração da plataforma** e pode consultar os indicadores e a auditoria com exportação CSV. A auditoria reúne metadados de eventos da plataforma e das clínicas. Uma conta técnica de mensageria tem acesso limitado às operações de seu canal.

O Superadmin pode excluir clínicas e contas de outros usuários. O Admin pode excluir um vínculo da própria clínica. A exclusão revoga acesso, remove o registro da operação e preserva o histórico. O último administrador ativo de uma clínica é protegido contra remoção pelo Admin.

Em **Minha conta**, a pessoa atualiza os dados de contato e a foto. Senhas são protegidas com Argon2id. Sessões usam cookies seguros e mutações verificam CSRF e origem. A API exige MFA recente em operações administrativas sensíveis.
