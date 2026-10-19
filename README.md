# Gestão de Mandato

Protótipo de sistema de gestão de mandato (demonstração).

Dados de contatos, demandas, agenda e as demais telas do gabinete são simulados. São reais, de fontes públicas:

- resultados eleitorais e candidaturas de 2026 (TSE);
- atuação de deputados e senadores (Câmara dos Deputados e Senado Federal, dados abertos);
- emendas parlamentares e pagamentos por favorecido (Portal da Transparência, CGU). Pessoas físicas e microempreendedores individuais aparecem somados, sem nome.

As telas eleitorais de exemplo municipal (resultados, comparação, eleitorado e mapa de votos) seguem simuladas.

A recepção com check-in por QR code (Atendimento › Recepção) também é simulada: sem servidor, o check-in fica salvo no navegador em que o formulário foi preenchido. O formulário público abre em `#checkin` e preenche o endereço pelo CEP (ViaCEP, com BrasilAPI de reserva); sem conexão com essas consultas, o endereço é digitado à mão.

Resumo de implantação para a diretoria (infraestrutura, custos estimados, etapas e segurança): pasta `implantacao/`, com versão em PDF.
