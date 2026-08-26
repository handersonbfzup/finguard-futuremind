# Tarefa: Implementar RAG da política interna

## Objetivo

Disponibilizar a política interna como contexto recuperável para os agentes de risco e relatório, substituindo regras dependentes apenas de texto fixo no prompt.

## Contexto atual

O arquivo `docs/KS_POLITICA_INTERNA (4).pdf` existe no projeto, mas as regras `POL-SAC-001` estão atualmente embutidas em `finguard/bedrock_client.py`. O desafio espera RAG local ou via API.

## Escopo

- Extrair o texto do PDF preservando página e seção.
- Dividir o conteúdo em chunks com tamanho e sobreposição documentados.
- Criar índice/retriever local compatível com execução offline ou definir o serviço AWS utilizado.
- Recuperar os trechos relevantes para cada análise de risco.
- Inserir contexto recuperado em prompt delimitado, sem permitir que o documento altere as instruções do sistema.
- Retornar fontes, páginas ou identificadores dos chunks usados.
- Definir comportamento quando não houver contexto relevante.

## Critérios de aceite

- A execução do agente de risco usa contexto recuperado da política, e não somente constante hard-coded.
- Cada justificativa de risco pode ser rastreada até uma página/chunk da política.
- O contexto recuperado não contém dados de outras reclamações.
- O pipeline permanece executável localmente com uma configuração documentada.
- Testes verificam chunking, recuperação, metadados, ausência de contexto e delimitação contra prompt injection.
- O relatório final identifica a fonte normativa usada na decisão.

## Evidências esperadas

- Módulo de ingestão e recuperação.
- Índice ou artefato local reproduzível, sem dados de produção.
- Testes do retriever.
- Atualização do ADR e da documentação operacional.

## Dependências

- PDF da política interna fornecido pelo desafio.
- Biblioteca de extração/indexação aprovada no ambiente.
- Decisão de persistência local versus serviço AWS.
