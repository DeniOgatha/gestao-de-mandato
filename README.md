# Gestão de Mandato

Protótipo de sistema de gestão de mandato (demonstração).

Dados de contatos, demandas, agenda e as demais telas do gabinete são simulados. São reais, de fontes públicas:

- resultados eleitorais e candidaturas de 2026 (TSE);
- atuação de deputados e senadores (Câmara dos Deputados e Senado Federal, dados abertos);
- emendas parlamentares e pagamentos por favorecido (Portal da Transparência, CGU). Pessoas físicas e microempreendedores individuais aparecem somados, sem nome.

As telas eleitorais de exemplo municipal (resultados, comparação, eleitorado e mapa de votos) seguem simuladas.

A recepção com check-in por QR code (Atendimento › Recepção) também é simulada: sem servidor, o check-in fica salvo no navegador em que o formulário foi preenchido. O formulário público abre em `#checkin` e preenche o endereço pelo CEP (ViaCEP, com BrasilAPI de reserva); sem conexão com essas consultas, o endereço é digitado à mão.

Resumo de implantação para a diretoria (infraestrutura, custos estimados, etapas e segurança): pasta `implantacao/`, com versão em PDF.

A página Atendimento › Presença reúne horários de pico, atendidos, quem saiu sem atendimento, mensagens enviadas, consulta por pessoa e declaração de comparecimento, com exportação em Excel e PDF. Cada criação, correção e cancelamento vira um evento numa cadeia com hash SHA-256, e exportações, consultas e mudanças de permissão vão para uma trilha de auditoria separada. No protótipo tudo fica no navegador e o horário é o do aparelho; os CPFs de exemplo são inválidos de propósito.

## Atualização diária do Meu parlamentar

Todo dia às 6h (Brasília), o workflow `atualizar-dados.yml` roda `rotina/atualizar_federal.py`. Ele baixa das fontes públicas as proposições da Câmara (2019 até hoje) e o cadastro dos acompanhados, a cota parlamentar da Câmara e do Senado (2023 até hoje) e as notícias dos últimos 60 dias. O resultado fica no ramo `dados`, que guarda só a última versão. Em seguida o workflow publica os três ambientes, e `rotina/embutir.py` coloca esses dados no `index.html` de cada um. O código continua passando por `develop` → `homologacao` → `main`. Só os dados entram direto.

Se uma fonte vier pela metade (queda de mais de 10% nos totais), a rotina para sem gravar e o site fica com os dados do dia anterior. O GitHub avisa a falha por e-mail. Notícias que não puderem ser buscadas ficam com as anteriores que ainda estão na janela de 60 dias. Para rodar fora de hora: Actions › Atualizar dados do Meu parlamentar › Run workflow.

## Ambientes

O site publica três ambientes a partir de três ramos: `develop` em [/teste/](https://deniogatha.github.io/gestao-de-mandato/teste/), `homologacao` em [/homologacao/](https://deniogatha.github.io/gestao-de-mandato/homologacao/) e `main` na raiz (produção). Uma mudança segue `develop` → pedido de mesclagem → `homologacao` → pedido de mesclagem → `main`. Quem acessa o quê em cada ambiente está em [AMBIENTES.md](AMBIENTES.md) e na tela Configurações › Ambientes e acessos.
