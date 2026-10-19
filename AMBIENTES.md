# Ambientes e acessos

Onde cada versão do sistema roda, que dados ela tem e quem pode fazer o quê em cada uma. Gerado da mesma fonte da tela Gestão › Ambientes e acessos.

## Os três ambientes

| | Teste | Homologação | Produção |
|---|---|---|---|
| Para quê | Onde o desenvolvedor experimenta e confere cada mudança. | Cópia fiel da produção, onde a empresa e o gabinete aprovam a mudança antes de ela valer. | O sistema em uso pelos gabinetes. |
| Ramo | `develop` | `homologacao` | `main` |
| Endereço hoje | https://deniogatha.github.io/gestao-de-mandato/teste/ | https://deniogatha.github.io/gestao-de-mandato/homologacao/ | https://deniogatha.github.io/gestao-de-mandato/ |
| Endereço na versão final | teste.dominio.com.br | homolog.dominio.com.br | app.dominio.com.br |
| Dados | Só fictícios | Fictícios ou cópia anonimizada | Reais (hoje: demonstração com dados fictícios) |
| Como a mudança entra | Cada envio ao ramo develop é publicado sozinho. | Pedido de mesclagem do develop para homologacao. | Pedido de mesclagem da homologacao para main. |
| Quem aprova | Nenhuma: é o rascunho do desenvolvedor. | Diretor da empresa e, quando a mudança foi pedida pelo gabinete, o administrador do gabinete. | Diretor da empresa, depois da homologação. |

Fluxo: `develop` (teste) → pedido de mesclagem → `homologacao` → pedido de mesclagem → `main` (produção). Nada vai direto para `main` ou `homologacao`.

## Quem acessa o quê

| Papel | Teste | Homologação | Produção |
|---|---|---|---|
| **Desenvolvedor** (Quem programa o sistema) | **Total**. Publica direto no ramo develop e cria dados fictícios à vontade. | **Publica**. Só por pedido de mesclagem. Não vê dados de cliente: usa cópia anonimizada. | **Publica**. Só por pedido de mesclagem aprovado. Sem acesso a dados pessoais; acesso emergencial com prazo, motivo e registro na trilha. |
| **Diretor da empresa** (Segundo administrador de todas as contas) | **Leitura**. Acompanha o que está sendo feito. | **Aprova**. Revisa a mudança e aprova a ida para a produção. | **Aprova**. Dono das contas (código, hospedagem, banco), aprova publicações e revoga acessos. |
| **Suporte da empresa** (Atende os chamados dos gabinetes) | **Sem acesso** | **Testa**. Reproduz problemas relatados. | **Emergencial**. Só dentro de um chamado, com registro na trilha. Não exporta dados. |
| **Administrador do gabinete** (Chefe de gabinete ou quem o gabinete indicar) | **Sem acesso** | **Testa**. Aprova as mudanças pedidas pelo gabinete (níveis Profissional e Dedicado). | **Usa**. Administra os acessos da equipe do gabinete. |
| **Equipe do gabinete** (Recepção, atendimento, assessoria) | **Sem acesso** | **Testa**. Só em treinamento combinado. | **Usa**. Conforme o perfil em Gestão › Equipe e permissões. |
| **Visitante** (Quem faz check-in pelo QR code) | **Sem acesso** | **Sem acesso** | **Usa**. Só o formulário de check-in. |
| **Auditoria e jurídico** (Controle interno, DPO, advogado) | **Sem acesso** | **Sem acesso** | **Leitura**. Registro de eventos e trilha de auditoria, sem alterar nada. |

## Infraestrutura por ambiente

| Item | Teste | Homologação | Produção | Como está hoje |
|---|---|---|---|---|
| Ramo do código | develop | homologacao | main | Igual: os três ramos já existem. |
| Como a mudança entra | Envio direto | Pedido de mesclagem do develop | Pedido de mesclagem da homologacao | Igual. A aprovação obrigatória entra quando o diretor for adicionado ao repositório. |
| Endereço | teste.dominio.com.br | homolog.dominio.com.br | app.dominio.com.br | Pastas /teste/, /homologacao/ e a raiz do mesmo site. |
| Hospedagem | Vercel, projeto de teste | Vercel, projeto de homologação | Vercel, projeto de produção | GitHub Pages, um site com os três ambientes. |
| Banco de dados | Supabase gratuito, separado | Supabase de homologação, separado | Supabase Pro em São Paulo | Navegador de cada pessoa, com dados separados por ambiente. |
| Dados | Fictícios | Fictícios ou cópia anonimizada | Reais | Fictícios nos três. |
| Login | Contas de teste | Contas próprias, com segundo fator | Segundo fator obrigatório | Sem login: a página é pública. |
| Cópias de segurança | Não precisa | Não precisa | Diária e a cada 6 horas, ou a qualquer minuto (PITR) | Não há. |
| Registro de eventos e trilha | Pode ser zerado | Guardado | Guardado, sem alteração possível | Cadeias com hash no navegador. |

## Limites de hoje

- Os três endereços são públicos e usam dados fictícios. A “produção” atual é a demonstração do protótipo.
- O repositório tem uma pessoa só. O GitHub não deixa o autor aprovar o próprio pedido de mesclagem, então a aprovação obrigatória fica em 0 até o diretor entrar como colaborador. Aí ela sobe para 1 em `main` e `homologacao`.
- O controle de acesso por papel descrito acima vale para a versão final, com login, segundo fator e banco por ambiente.
