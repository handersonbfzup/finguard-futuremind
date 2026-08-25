#!/usr/bin/env python3
"""Script de validação dos logs da execução."""

import json
from pathlib import Path
from collections import defaultdict

log_file = Path('logs/execucao_20260825-191134.jsonl')

# Variáveis de aggregação
total_acoes = 0
acoes_erro = 0
tokens_entrada_total = 0
tokens_saida_total = 0
agentes_stats = defaultdict(lambda: {"count": 0, "tokens_in": 0, "tokens_out": 0})
chamadas_bedrock = 0
modelos_usados = defaultdict(lambda: {"count": 0, "tokens_in": 0, "tokens_out": 0})

with open(log_file) as f:
    for linha in f:
        try:
            registro = json.loads(linha)
            total_acoes += 1
            
            acao = registro.get('acao', '')
            detalhes = registro.get('detalhes', {})
            
            # Contar erros
            if registro.get('status') == 'erro':
                acoes_erro += 1
            
            # Contar chamadas Bedrock
            if 'bedrock' in acao.lower():
                chamadas_bedrock += 1
                tokens_in = detalhes.get('tokens_entrada', 0)
                tokens_out = detalhes.get('tokens_saida', 0)
                tokens_entrada_total += tokens_in
                tokens_saida_total += tokens_out
                
                # Track modelo
                modelo = detalhes.get('modelo', 'unknown')
                modelos_usados[modelo]["count"] += 1
                modelos_usados[modelo]["tokens_in"] += tokens_in
                modelos_usados[modelo]["tokens_out"] += tokens_out
            
            # Stats por agente
            agentes_stats[acao]["count"] += 1
        except:
            pass

print("=" * 70)
print("VALIDAÇÃO DE MÉTRICAS DO DASHBOARD - FinGuard")
print("=" * 70)
print()
print("RESUMO GERAL")
print("-" * 70)
print(f"Total de ações registradas:     {total_acoes:>6}")
print(f"Ações com erro:                 {acoes_erro:>6}")
print(f"Taxa de erro:                   {(acoes_erro/total_acoes*100):>6.1f}%")
print()
print("TOKENS (Bedrock)")
print("-" * 70)
print(f"Chamadas Bedrock:               {chamadas_bedrock:>6}")
print(f"Tokens de entrada:              {tokens_entrada_total:>6}")
print(f"Tokens de saída:                {tokens_saida_total:>6}")
print(f"Tokens totais:                  {tokens_entrada_total + tokens_saida_total:>6}")
print()
print("MODELOS UTILIZADOS")
print("-" * 70)
for modelo in sorted(modelos_usados.keys()):
    stats = modelos_usados[modelo]
    print(f"{modelo:30} chamadas: {stats['count']:3d}  entrada: {stats['tokens_in']:6d}  saída: {stats['tokens_out']:6d}")
print()
print("AGENTES (contagem de ações)")
print("-" * 70)
for agente in sorted(agentes_stats.keys()):
    stats = agentes_stats[agente]
    print(f"  {agente:40} {stats['count']:4d}")
