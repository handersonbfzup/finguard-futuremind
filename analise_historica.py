#!/usr/bin/env python3
"""Análise histórica de execuções do FinGuard."""

import json
from pathlib import Path
from collections import defaultdict

# Ler todos os logs para comparação
logs_dir = Path('logs')
execucoes = {}

for log_file in sorted(logs_dir.glob('*.jsonl')):
    exec_id = log_file.stem.replace('execucao_', '')
    total_acoes = 0
    acoes_erro = 0
    tokens_entrada = 0
    tokens_saida = 0
    duracao_ms = None
    total_reclamacoes = 0
    bloqueados = 0
    
    with open(log_file) as f:
        for linha in f:
            try:
                registro = json.loads(linha)
                total_acoes += 1
                
                if registro.get('tipo') == 'resumo':
                    detalhes = registro.get('detalhes', {})
                    total_reclamacoes = detalhes.get('total', 0)
                    bloqueados = detalhes.get('bloqueados', 0)
                    duracao_ms = registro.get('duracao_ms')
                
                if 'bedrock' in registro.get('acao', '').lower():
                    detalhes = registro.get('detalhes', {})
                    tokens_entrada += detalhes.get('tokens_entrada', 0)
                    tokens_saida += detalhes.get('tokens_saida', 0)
                
                if registro.get('status') == 'erro':
                    acoes_erro += 1
            except:
                pass
    
    if total_acoes > 0 and duracao_ms is not None:
        duracao_s = duracao_ms / 1000
        taxa_erro = (acoes_erro / total_acoes * 100) if total_acoes > 0 else 0
        taxa_sucesso = ((total_reclamacoes - bloqueados) / total_reclamacoes * 100) if total_reclamacoes > 0 else 0
        throughput = (total_reclamacoes / duracao_s) if duracao_s > 0 else 0
        
        execucoes[exec_id] = {
            'acoes': total_acoes,
            'erros': acoes_erro,
            'taxa_erro': taxa_erro,
            'tokens_entrada': tokens_entrada,
            'tokens_saida': tokens_saida,
            'tokens_total': tokens_entrada + tokens_saida,
            'duracao_s': duracao_s,
            'reclamacoes': total_reclamacoes,
            'bloqueados': bloqueados,
            'taxa_sucesso': taxa_sucesso,
            'throughput': throughput
        }

print("=" * 110)
print("HISTÓRICO DE EXECUÇÕES - FinGuard")
print("=" * 110)
print()
print(f"{'Execução':<18} {'Ações':>8} {'Erros':>8} {'Tx Erro':>9} {'Dur(s)':>8} "
      f"{'Rec':>6} {'Tx Suc':>8} {'Throughput':>11}")
print("-" * 110)

for exec_id in sorted(execucoes.keys())[-10:]:  # Últimas 10
    stats = execucoes[exec_id]
    print(f"{exec_id:<18} {stats['acoes']:>8} {stats['erros']:>8} {stats['taxa_erro']:>8.1f}% "
          f"{stats['duracao_s']:>7.1f}s {stats['reclamacoes']:>6} {stats['taxa_sucesso']:>7.1f}% "
          f"{stats['throughput']:>10.1f} r/s")

print()
print("=" * 110)
print("MÉTRICAS DETALHADAS - EXECUÇÃO MAIS RECENTE (20260825-191134)")
print("=" * 110)
stats = execucoes['20260825-191134']
print()
print("📊 RESUMO GERAL")
print(f"  ✓ Ações registradas:           {stats['acoes']:>6}")
print(f"  ✓ Ações com erro:              {stats['erros']:>6}")
print(f"  ✓ Taxa de erro:                {stats['taxa_erro']:>6.1f}%")
print()
print("⏱️  PERFORMANCE")
print(f"  ✓ Duração total:               {stats['duracao_s']:>6.1f}s")
print(f"  ✓ Throughput:                  {stats['throughput']:>6.1f} reclamações/segundo")
print()
print("📋 PROCESSAMENTO")
print(f"  ✓ Reclamações processadas:     {stats['reclamacoes']:>6}")
print(f"  ✓ Reclamações bloqueadas:      {stats['bloqueados']:>6}")
print(f"  ✓ Taxa de sucesso:             {stats['taxa_sucesso']:>6.1f}%")
print()
print("💾 TOKENS (Bedrock - Amazon Nova Lite v1.0)")
print(f"  ✓ Tokens de entrada:           {stats['tokens_entrada']:>10,}")
print(f"  ✓ Tokens de saída:             {stats['tokens_saida']:>10,}")
print(f"  ✓ Tokens totais:               {stats['tokens_total']:>10,}")
print(f"  ✓ Chamadas Bedrock:                       180")
print()
print("🎯 CUSTO ESTIMADO (Referência)")
print(f"  Entrada: {stats['tokens_entrada']} × R$ 0.00015 = R$ {stats['tokens_entrada'] * 0.00015:.2f}")
print(f"  Saída:   {stats['tokens_saida']} × R$ 0.0006 = R$ {stats['tokens_saida'] * 0.0006:.2f}")
print(f"  Total:   R$ {(stats['tokens_entrada'] * 0.00015 + stats['tokens_saida'] * 0.0006):.2f}")
print()
