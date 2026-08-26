# Tarefa: Implementar governança operacional e segurança AWS

## Objetivo

Documentar e automatizar os controles necessários para operar o FinGuard sem expor dados nem gerar recursos/custos esquecidos.

## Contexto atual

O ADR recomenda IAM mínimo, credenciais temporárias, Budgets, alarmes, criptografia e retenção, mas esses controles não estão implementados no projeto.

## Escopo

- Definir permissões IAM mínimas para Bedrock Guardrails, Converse, embeddings e, se aplicável, SageMaker.
- Preferir roles/STS e impedir credenciais estáticas no código ou em arquivos versionados.
- Definir retenção, acesso e criptografia dos logs locais ou AWS.
- Criar orçamento/alarme para uso do Bedrock e procedimento de resposta a picos.
- Definir identificação/prefixo de recursos e responsável pelo desprovisionamento.
- Automatizar ou documentar checklist de encerramento, incluindo endpoints, buckets, guardrails e arquivos temporários.
- Registrar versão de configuração, região, modelo e modo de execução.

## Critérios de aceite

- Nenhum segredo aparece no repositório ou nos logs.
- Há matriz de permissões por operação e ambiente.
- Existe política de retenção e descarte aprovada.
- O procedimento de encerramento identifica e remove recursos criados para o desafio.
- O custo estimado e os limites são visíveis para a equipe.
- Uma execução de validação demonstra o uso do perfil/região corretos.

## Evidências esperadas

- Documento de IAM/governança.
- Configuração de orçamento/alarme ou instruções reproduzíveis.
- Checklist de desprovisionamento atualizado.
- Logs de cleanup sem dados sensíveis.

## Dependências

- Acesso à conta AWS de desenvolvimento.
- Definição dos serviços efetivamente usados pelo pipeline.
