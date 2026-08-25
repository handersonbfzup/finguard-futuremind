"""Logging estruturado (JSONL) do FinGuard.

Cada ação relevante do sistema (nó do grafo, chamada ao Bedrock, execução de CLI, script
de cluster/cleanup) grava uma linha de log via `registrar(...)`. O arquivo gerado por
execução alimenta o dashboard de rastreabilidade (finguard/dashboard_logs.py).
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

RAIZ_LOGS = Path(__file__).parent.parent / "logs"

_lock_arquivo = threading.Lock()
_arquivo_execucao: Path | None = None
_execucao_id: str | None = None


def iniciar_execucao(prefixo: str = "execucao") -> str:
    """Abre um novo arquivo JSONL para a execução atual (chamado uma vez por rodada)."""
    global _arquivo_execucao, _execucao_id
    RAIZ_LOGS.mkdir(exist_ok=True)
    _execucao_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    _arquivo_execucao = RAIZ_LOGS / f"{prefixo}_{_execucao_id}.jsonl"
    return _execucao_id


def caminho_arquivo_atual() -> Path | None:
    return _arquivo_execucao


def registrar(
    acao: str,
    status: str = "ok",
    duracao_ms: float | None = None,
    reclamacao_id: str | None = None,
    detalhes: dict | None = None,
    nivel: str = "INFO",
) -> None:
    """Grava uma linha de log estruturado para uma ação executada (thread-safe)."""
    if _arquivo_execucao is None:
        iniciar_execucao()

    linha = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "execucao_id": _execucao_id,
        "nivel": nivel,
        "acao": acao,
        "reclamacao_id": reclamacao_id,
        "status": status,
        "duracao_ms": duracao_ms,
        "detalhes": detalhes or {},
    }
    with _lock_arquivo, open(_arquivo_execucao, "a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(linha, ensure_ascii=False) + "\n")
