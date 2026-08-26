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
