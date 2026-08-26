"""Estado compartilhado do grafo LangGraph do FinGuard."""

import operator
from typing import Annotated, Any, TypedDict


class FinGuardState(TypedDict, total=False):
    id: str
    canal: str
    produto_original: str | None
    status: str
    texto_original: str
    _usar_llm: bool

    # Preenchidos pelo modo lote (main.py) quando a classificação/risco já foi obtida em
    # uma chamada em lote ao Bedrock; se presentes, os nós correspondentes não chamam o
    # Bedrock individualmente de novo (ver finguard/agentes.py).
    _classificacao_precomputada: dict[str, Any] | None
    _fontes_politica_precomputadas: list[dict[str, Any]] | None
    _risco_nivel_precomputado: str | None
    _risco_justificativa_precomputada: str | None

    bloqueado: bool
    motivo_bloqueio: str | None

    classificacao: dict[str, Any] | None

    risco_nivel: str | None
    risco_justificativa: str | None
    fontes_politica: list[dict[str, Any]]
    politica_contexto_disponivel: bool

    acao_recomendada: str | None

    # Cada nó retorna apenas os logs novos; o operator.add concatena com o histórico.
    logs: Annotated[list[dict[str, Any]], operator.add]
