# Configuração do provedor WhatsApp

Use a conta WhatsApp Business da clínica na Cloud API da Meta. A clínica precisa informar WABA ID, Phone Number ID, versão Graph habilitada, Access Token e App Secret. Gere um Verify Token para a verificação do webhook.

O administrador salva e verifica os valores em **Integrações**, vincula o número e usa a URL de webhook exibida no cadastro. Configure o webhook com HTTPS e assine o campo `messages` na Meta. A verificação do portal consulta metadados do número. A homologação confirma o webhook assinado, o processamento e a entrega de resposta.

O executor e a ativação de envio ficam com a equipe Multiclinica. Consulte o [roteiro de implantação assistida](integration-onboarding.md) e o [guia do executor](messaging-implementation.md). O suporte a coexistência com o aplicativo WhatsApp Business depende das opções disponíveis na conta Meta da clínica.

[WhatsApp Business Platform](https://developers.facebook.com/documentation/business-messaging/whatsapp/overview)
