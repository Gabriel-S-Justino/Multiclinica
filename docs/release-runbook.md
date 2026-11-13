# Release e liberação para produção

O [portal Multiclinica](https://multclinicai.vercel.app) é o endereço atual de demonstração. O [relatório F8](reports/f8-staging.md) registra testes de um ambiente histórico com dados fictícios. Use as evidências do ambiente escolhido para a aprovação de produção.

## Preparação da equipe Multiclinica

1. Confirme o ambiente, o plano, a região, o banco e o responsável pela operação. O uso comercial na Vercel requer um plano que permita essa finalidade. [Política da Vercel](https://vercel.com/docs/limits/fair-use-guidelines)
2. Configure `APP_ENV`, `PUBLIC_ORIGIN` HTTPS, MFA, `DATABASE_URL` do runtime e as chaves `TOKEN_KEY` e `FIELD_KEY`. Use a conexão direta de migração exclusivamente no processo de release. Aplique `alembic upgrade head` antes de publicar alterações de esquema.
3. Publique o commit validado. Confira `/v1/health`, `/v1/ready`, os arquivos estáticos, login e MFA, convites, perfil, permissões por clínica e agenda. Teste tentativas de acesso entre clínicas e de acesso clínico pelo Superadmin.
4. Inicie o [executor de WhatsApp](messaging-implementation.md) em serviço supervisionado. Defina alertas para parada do processo, atraso da fila, entregas desconhecidas e falhas. Verifique que o serviço encontra novos canais sem reiniciar.
5. Teste backup e restauração num destino isolado. Valide chaves, revisão do esquema, permissões, registros cifrados e contagens. Meça a perda de dados admissível e o tempo de recuperação. Faça ensaio de carga autorizado no ambiente de teste, com volume e metas acordados.
6. Defina responsáveis, política de identificação e retenção, acesso, incidentes, contratos e transferência de dados. Use o [guia de privacidade](privacy-operations.md).

## Liberação por clínica

Use o [roteiro de implantação assistida](integration-onboarding.md). Registre as evidências por clínica, com responsável e data. Dados da Meta, chave e modelo de IA, políticas da clínica e validação de entrega entram nessa etapa. Antes de aceitar pacientes reais, confirme também o plano de hospedagem, a execução monitorada das filas e a recuperação no ambiente de destino.

Em caso de incidente, pause o envio pelo comando `disable`. Reverta a aplicação para um artefato compatível com o esquema e restaure em um destino separado quando necessário. Reconcilie as entregas de estado desconhecido com a Meta antes de qualquer reenvio.

Em 13/11/2026, o ensaio de recuperação do banco de demonstração no Neon restaurou um snapshot em branch separado. A revisão `0008` e as contagens de clínicas e usuários coincidiram com o banco de origem. O papel de runtime continuou sujeito às políticas de isolamento e a consulta de vínculos sem contexto retornou zero registros. A janela de histórico informada para o projeto era de seis horas. A aprovação do ambiente comercial exige validar as chaves de cifra, a capacidade e as metas de recuperação no destino escolhido.
