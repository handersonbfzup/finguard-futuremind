"""Nós do grafo LangGraph do FinGuard (Nível 2 — Orquestrador de Análise).

Cada nó recebe o FinGuardState e retorna apenas as chaves que atualiza (convenção do
LangGraph). Todos os nós registram um log de execução (agente, entrada, saída, tempo em
ms) para atender ao requisito de rastreabilidade do desafio.
"""

import time
from typing import Any

from finguard.guardrails import (
    aplicar_guardrail_saida,
    verificar_guardrail_entrada,
)
from finguard.logging_config import registrar
from finguard.rag import recuperar_contexto_politica
from finguard.schemas import Categoria, Produto, Sentimento, Urgencia
from finguard.state import FinGuardState

_GATILHOS_RISCO_CRITICO = [
    "fraude", "não autorizada", "nao autorizada", "vazamento", "hacker",
    "boletim de ocorrência", "boletim de ocorrencia", "violência", "violencia", "ameaça", "ameaca",
]

_ACOES_POR_URGENCIA = {
    Urgencia.CRITICA.value: "Contato ativo em até 4h, analista dedicado, notificar coordenador da área (POL-SAC-001 2.3).",
    Urgencia.ALTA.value: "Contato ativo em até 4h, analista dedicado, notificar coordenador da área (POL-SAC-001 2.3).",
    Urgencia.MEDIA.value: "Confirmar recebimento em até 12h; avaliação de analista sênior em até 24h (POL-SAC-001 2.2).",
    Urgencia.BAIXA.value: "Confirmar recebimento em até 24h; encaminhar para fila padrão da área (POL-SAC-001 2.1).",
}


def _log(
    agente: str,
    entrada: str,
    saida: Any,
    inicio: float,
    *,
    reclamacao_id: str | None = None,
    status: str = "ok",
) -> list[dict]:
    duracao_ms = round((time.time() - inicio) * 1000, 1)
    registrar(
        acao=agente,
        status=status,
        duracao_ms=duracao_ms,
        reclamacao_id=reclamacao_id,
        detalhes={"entrada_resumida": str(entrada)[:80], "saida_resumida": str(saida)[:160]},
    )
    return [
        {
            "agente": agente,
            "entrada_resumida": str(entrada)[:80],
            "saida_resumida": str(saida)[:160],
            "tempo_ms": duracao_ms,
        }
    ]


def no_guardrail_entrada(state: FinGuardState) -> dict:
    inicio = time.time()
    resultado = verificar_guardrail_entrada(state["texto_original"])
    logs = _log(
        "guardrail_entrada",
        state["texto_original"],
        resultado,
        inicio,
        reclamacao_id=state.get("id"),
        status="bloqueado" if resultado.bloqueado else "ok",
    )
    return {
        "bloqueado": resultado.bloqueado,
        "motivo_bloqueio": resultado.motivo,
        "logs": logs,
    }


def no_resposta_bloqueio(state: FinGuardState) -> dict:
    inicio = time.time()
    from finguard.guardrails import RESPOSTA_BLOQUEIO

    logs = _log(
        "resposta_bloqueio",
        state.get("motivo_bloqueio", ""),
        RESPOSTA_BLOQUEIO,
        inicio,
        reclamacao_id=state.get("id"),
    )
    return {"acao_recomendada": RESPOSTA_BLOQUEIO, "logs": logs}


def no_agente_triagem(state: FinGuardState) -> dict:
    inicio = time.time()
    texto = state["texto_original"]

    if state.get("_usar_llm", True):
        from finguard.bedrock_client import classificar_reclamacao

        classificacao = classificar_reclamacao(texto, reclamacao_id=state.get("id")).model_dump(mode="json")
    else:
        classificacao = {
            "categoria": Categoria.OUTROS.value,
            "produto": Produto.NAO_IDENTIFICADO.value,
            "sentimento": Sentimento.NEUTRO.value,
            "urgencia": Urgencia.BAIXA.value,
            "resumo": "[modo --sem-llm] classificação não executada.",
        }

    logs = _log("agente_triagem", texto, classificacao, inicio, reclamacao_id=state.get("id"))
    return {"classificacao": classificacao, "logs": logs}


def _risco_heuristico(texto: str, canal: str) -> tuple[str, str]:
    texto_lower = texto.lower()
    if canal in ("Banco Central", "Procon"):
        return "Crítico", "Canal regulatório identificado; urgência elevada pelo piso determinístico."
    gatilho = next((g for g in _GATILHOS_RISCO_CRITICO if g in texto_lower), None)
    if gatilho:
        return "Alto", f'Indício textual de risco elevado detectado ("{gatilho}").'
    return "Baixo", "Nenhum indicador de risco elevado identificado pela análise heurística."


def no_agente_risco(state: FinGuardState) -> dict:
    inicio = time.time()
    texto = state["texto_original"]
    nivel_heuristico, justificativa_heuristica = _risco_heuristico(texto, state["canal"])
    fontes_politica = recuperar_contexto_politica(
        texto, state.get("classificacao"), state["canal"]
    )

    if state.get("_usar_llm", True):
        from finguard.bedrock_client import analisar_risco

        nivel, justificativa = analisar_risco(
            texto,
            state.get("classificacao") or {},
            nivel_heuristico,
            fontes_politica,
            reclamacao_id=state.get("id"),
        )
    else:
        nivel, justificativa = nivel_heuristico, justificativa_heuristica

    saida = {"nivel": nivel, "justificativa": justificativa}
    logs = _log("agente_risco", texto, saida, inicio, reclamacao_id=state.get("id"))
    return {
        "risco_nivel": nivel,
        "risco_justificativa": justificativa,
        "fontes_politica": fontes_politica,
        "politica_contexto_disponivel": bool(fontes_politica),
        "logs": logs,
    }


def no_agente_relatorio(state: FinGuardState) -> dict:
    inicio = time.time()
    classificacao = dict(state.get("classificacao") or {})
    urgencia = classificacao.get("urgencia", Urgencia.BAIXA.value)

    acao = _ACOES_POR_URGENCIA.get(urgencia, "Encaminhar para fila padrão da área responsável.")
    fontes = state.get("fontes_politica", [])
    if fontes:
        acao += " Fonte normativa: " + ", ".join(fonte["chunk_id"] for fonte in fontes) + "."
    else:
        acao += " Fonte normativa não recuperada; requer validação manual."
    if state.get("risco_nivel") in ("Alto", "Crítico"):
        acao += " Escalar para compliance/jurídico dado o nível de risco identificado pelo agente de risco."

    logs = _log("agente_relatorio", str(classificacao), acao, inicio, reclamacao_id=state.get("id"))
    return {"classificacao": classificacao, "acao_recomendada": acao, "logs": logs}


def no_guardrail_saida(state: FinGuardState) -> dict:
    """Última barreira antes do relatório final: garante que nenhum dado sensível (CPF,
    conta, telefone) nem linguagem ofensiva escape em qualquer campo textual gerado pelos
    agentes anteriores — mesmo que a sanitização do agente_triagem já tenha tentado evitar isso.
    """
    inicio = time.time()
    classificacao = dict(state.get("classificacao") or {})
    if "resumo" in classificacao:
        classificacao["resumo"] = aplicar_guardrail_saida(classificacao["resumo"])

    risco_justificativa = state.get("risco_justificativa")
    if risco_justificativa:
        risco_justificativa = aplicar_guardrail_saida(risco_justificativa)

    acao_recomendada = state.get("acao_recomendada")
    if acao_recomendada:
        acao_recomendada = aplicar_guardrail_saida(acao_recomendada)

    logs = _log(
        "guardrail_saida",
        str(classificacao),
        classificacao.get("resumo", ""),
        inicio,
        reclamacao_id=state.get("id"),
    )
    return {
        "classificacao": classificacao,
        "risco_justificativa": risco_justificativa,
        "acao_recomendada": acao_recomendada,
        "logs": logs,
    }
