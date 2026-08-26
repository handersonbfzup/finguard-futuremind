# Tarefa: Criar testes automatizados e avaliação de qualidade

## Objetivo

Substituir a validação manual por uma suíte reproduzível que prove o atendimento funcional e de segurança do nível 3.

## Contexto atual

Não há arquivos-fonte de testes versionados em `tests/`; existe apenas artefato compilado. Também não há ground truth formal para medir a qualidade da classificação, risco, resumo ou bloqueios.

## Escopo

- Criar testes unitários para schemas, guardrails, sanitização, logging e parsing Bedrock.
- Criar testes do grafo com clientes LLM e AWS mockados.
- Cobrir roteamento PASS/BLOCK, resposta de bloqueio e garantia de que entradas bloqueadas não chegam aos agentes.
- Criar fixtures para reclamações válidas, prompt injection, ameaça, conteúdo fora do domínio e PII fictícia.
- Criar conjunto rotulado ou casos esperados para categoria, produto, sentimento, urgência e risco.
- Medir acurácia/F1 quando houver rótulos, cobertura de bloqueio, falsos positivos, validade JSON e qualidade mínima do resumo.
- Automatizar execução com um comando documentado.

## Critérios de aceite

- `pytest` executa sem depender de credenciais AWS.
- A suíte cobre os caminhos principais e falhas dos agentes.
- Existe relatório de métricas com dataset/casos usados e limitações.
- O pipeline falha de forma explícita quando um contrato Pydantic não é atendido.
- Os testes não usam dados reais nem persistem credenciais.
- O CI ou procedimento local impede regressões no guardrail e na sanitização.

## Evidências esperadas

- Arquivos `.py` em `tests/`.
- Fixtures e conjunto de casos esperados.
- Saída reproduzível do comando de testes.
- Relatório de qualidade versionado ou gerado em artefato de execução.

## Dependências

- Contratos finais dos guardrails e do RAG.
- Definição dos critérios de qualidade aceitos pela equipe.
