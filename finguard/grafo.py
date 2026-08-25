"""Montagem do grafo LangGraph do FinGuard (Nível 3 — Guardrails completos).

Fluxo: __start__ -> guardrail_entrada -> [bloqueado: resposta_bloqueio | livre: agente_triagem]
       -> agente_risco -> agente_relatorio -> guardrail_saida -> __end__

O guardrail de entrada já foi implementado na Fase 1 (finguard/guardrails.py) e é
reaproveitado aqui como primeiro nó. O guardrail de saída (Fase 3) roda como último nó,
antes do fim do grafo, e é a barreira final contra vazamento de dados sensíveis/linguagem
imprópria em qualquer campo textual produzido pelos agentes anteriores — esse é o desenho
de grafo recomendado pelo próprio enunciado oficial.
"""

from langgraph.graph import END, StateGraph

from finguard.agentes import (
    no_agente_relatorio,
    no_agente_risco,
    no_agente_triagem,
    no_guardrail_entrada,
    no_guardrail_saida,
    no_resposta_bloqueio,
)
from finguard.state import FinGuardState


def _rotear_apos_guardrail(state: FinGuardState) -> str:
    return "resposta_bloqueio" if state.get("bloqueado") else "agente_triagem"


def construir_grafo():
    grafo = StateGraph(FinGuardState)

    grafo.add_node("guardrail_entrada", no_guardrail_entrada)
    grafo.add_node("resposta_bloqueio", no_resposta_bloqueio)
    grafo.add_node("agente_triagem", no_agente_triagem)
    grafo.add_node("agente_risco", no_agente_risco)
    grafo.add_node("agente_relatorio", no_agente_relatorio)
    grafo.add_node("guardrail_saida", no_guardrail_saida)

    grafo.set_entry_point("guardrail_entrada")
    grafo.add_conditional_edges(
        "guardrail_entrada",
        _rotear_apos_guardrail,
        {"resposta_bloqueio": "resposta_bloqueio", "agente_triagem": "agente_triagem"},
    )
    grafo.add_edge("agente_triagem", "agente_risco")
    grafo.add_edge("agente_risco", "agente_relatorio")
    grafo.add_edge("agente_relatorio", "guardrail_saida")
    grafo.add_edge("guardrail_saida", END)
    grafo.add_edge("resposta_bloqueio", END)

    return grafo.compile()
