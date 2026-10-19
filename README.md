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
