"""Schemas oficiais do desafio FinGuard (enums e modelo de saída do Nível 1)."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Categoria(str, Enum):
    COBRANCA_INDEVIDA = "Cobrança Indevida"
    ATENDIMENTO = "Atendimento"
    FRAUDE_SEGURANCA = "Fraude/Segurança"
    PRODUTO_SERVICO = "Produto/Serviço"
    CANCELAMENTO = "Cancelamento"
    OUTROS = "Outros"


class Produto(str, Enum):
    CARTAO_CREDITO = "Cartão de Crédito"
    CONTA_CORRENTE = "Conta Corrente"
    EMPRESTIMO = "Empréstimo"
    INVESTIMENTOS = "Investimentos"
    SEGUROS = "Seguros"
    NAO_IDENTIFICADO = "Não Identificado"


class Sentimento(str, Enum):
    POSITIVO = "Positivo"
    NEUTRO = "Neutro"
    NEGATIVO = "Negativo"
    CRITICO = "Crítico"


class Urgencia(str, Enum):
    BAIXA = "Baixa"
    MEDIA = "Média"
    ALTA = "Alta"
    CRITICA = "Crítica"


class ClassificacaoReclamacao(BaseModel):
    """Saída do agente classificador (Nível 1), validada contra os enums oficiais."""

    categoria: Categoria
    produto: Produto
    sentimento: Sentimento
    urgencia: Urgencia
    resumo: str = Field(..., min_length=1, max_length=600)


class ResultadoReclamacao(BaseModel):
    """Um registro do dataset já enriquecido com a classificação (ou bloqueio de guardrail)."""

    id: str
    canal: str
    produto_original: str | None
    status: str
    bloqueado: bool = False
    motivo_bloqueio: str | None = None
    classificacao: ClassificacaoReclamacao | None = None
    risco_nivel: str | None = None
    risco_justificativa: str | None = None
    fontes_politica: list[dict[str, Any]] = Field(default_factory=list)
    politica_contexto_disponivel: bool = False
    acao_recomendada: str | None = None
    logs: list[dict] = Field(default_factory=list)
