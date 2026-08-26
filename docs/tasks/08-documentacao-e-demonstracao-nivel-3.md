# Tarefa: Atualizar documentação e roteiro de demonstração do nível 3

## Objetivo

Alinhar código, documentação e apresentação para que cada requisito do nível 3 possa ser demonstrado com evidência verificável.

## Contexto atual

O projeto possui ADR, README, processo operacional e dashboards, mas a documentação ainda precisa distinguir claramente guardrail local de Bedrock Guardrails oficial, modo LLM de modo offline e implementação real de recomendações futuras.

## Escopo

- Atualizar `docs/readme.md`, `docs/processo.md` e `adr_finguard.html` após as tarefas técnicas.
- Documentar arquitetura final, fluxo de bloqueio, RAG, sanitização, logs, IAM e custos.
- Criar roteiro de demonstração de 5 minutos com entrada válida, ataque bloqueado, PII mascarada e relatório gerencial.
- Identificar quais artefatos foram gerados com Bedrock e quais foram gerados com `--sem-llm`.
- Incluir comandos de instalação, testes, execução, validação e cleanup.
- Registrar limitações conhecidas sem apresentar componentes não implementados como concluídos.

## Critérios de aceite

- Um novo integrante consegue instalar, testar e executar o projeto seguindo a documentação.
- Cada requisito do nível 3 aponta para código, teste ou artefato de evidência.
- O roteiro de demonstração não depende de dados reais.
- ADR e README têm os mesmos modelos, parâmetros e status de integração.
- Os dashboards e resultados identificam o modo de execução e a versão da configuração.

## Evidências esperadas

- Documentação atualizada e navegável.
- Roteiro de apresentação versionado.
- Checklist final da banca preenchido.

## Dependências

- Conclusão das tarefas de Bedrock Guardrails, RAG, privacidade, testes, resiliência, governança e custos.
