# Vincular o WhatsApp da clínica

Tenha à mão o acesso de administrador ao portal, uma fila de atendimento ativa e acesso ao app da clínica na Meta com o número cadastrado na Cloud API. Deixe o portal e o [painel de aplicativos da Meta](https://developers.facebook.com/apps/) abertos em abas separadas.

1. **Localize o número na Meta.** Selecione o app da clínica, abra WhatsApp → Configuração da API e escolha o telefone que receberá as mensagens. Copie o *Phone Number ID* (identificador do telefone) e o *WhatsApp Business Account ID* (identificador da conta, também chamado WABA ID).
2. **Preencha Integrações no portal.** Cole os dois IDs nos campos correspondentes. Nas configurações empresariais da Meta, use um token de usuário do sistema com acesso à conta e permissões whatsapp_business_messaging e whatsapp_business_management. Cole-o em **Token de acesso**. Em Configurações do app → Básico, revele a chave secreta e cole-a no campo correspondente. Escolha a fila e clique em **Salvar e verificar**. Se a verificação falhar, confira se os IDs e as credenciais pertencem à mesma conta e ao mesmo app.
3. **Vincule o número.** No passo seguinte do portal, confirme o vínculo. O portal exibirá uma URL de retorno e um token de verificação gerado para esse canal.
4. **Conecte as mensagens.** Volte aos Webhooks do WhatsApp Business na Meta. Cole a URL e o token de verificação e clique em **Verificar e salvar**. Assine o campo **messages**. O portal atualiza a confirmação do endereço automaticamente.
5. **Ative e faça o primeiro teste.** Clique em **Ativar envio**. De outro celular, envie “Olá” para o número vinculado e confirme o recebimento do menu. Se o endereço já foi confirmado mas o menu não chega, confira a assinatura de **messages**, o envio ativo e o indicador do executor no portal.

Se o portal confirmar a URL e continuar sem receber eventos, peça à equipe para conferir se o app está inscrito na conta empresarial do número. [Aplicativos inscritos na WABA](https://developers.facebook.com/docs/graph-api/reference/whats-app-business-account/subscribed_apps/)

A equipe Multiclinica acompanha o processamento e a entrega durante a homologação. [Guia do executor](worker-deployment.md) · [Implantação assistida](integration-onboarding.md)
