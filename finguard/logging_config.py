"""Logging estruturado (JSONL) do FinGuard.

Cada ação relevante do sistema (nó do grafo, chamada ao Bedrock, execução de CLI, script
de cluster/cleanup) grava uma linha de log via `registrar(...)`. O arquivo gerado por
execução alimenta o dashboard de rastreabilidade (finguard/dashboard_logs.py).
"""

import atexit
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

RAIZ_LOGS = Path(__file__).parent.parent / "logs"

_lock_arquivo = threading.Lock()
_arquivo_execucao: Path | None = None
_execucao_id: str | None = None
# Handle mantido aberto durante toda a execução (em vez de abrir/fechar a cada linha) —
# com muitas chamadas concorrentes (--workers alto, chamadas em lote) o open/close por
# linha vira um gargalo real, pois serializa todas as threads no lock do sistema de arquivos.
_handle_arquivo: TextIO | None = None


def iniciar_execucao(prefixo: str = "execucao") -> str:
    """Abre um novo arquivo JSONL para a execução atual (chamado uma vez por rodada)."""
    global _arquivo_execucao, _execucao_id, _handle_arquivo
    encerrar_execucao()
    RAIZ_LOGS.mkdir(exist_ok=True)
    _execucao_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    _arquivo_execucao = RAIZ_LOGS / f"{prefixo}_{_execucao_id}.jsonl"
    _handle_arquivo = open(_arquivo_execucao, "a", encoding="utf-8")
    return _execucao_id


def encerrar_execucao() -> None:
    """Fecha o handle do arquivo de log atual, se houver (chamado automaticamente ao
    reiniciar a execução ou ao final do processo via atexit)."""
    global _handle_arquivo
    with _lock_arquivo:
        if _handle_arquivo is not None:
            _handle_arquivo.close()
            _handle_arquivo = None


atexit.register(encerrar_execucao)


def caminho_arquivo_atual() -> Path | None:
    return _arquivo_execucao


def registrar(
    acao: str,
    status: str = "ok",
    duracao_ms: float | None = None,
    reclamacao_id: str | None = None,
    detalhes: dict | None = None,
    nivel: str = "INFO",
    tipo: str = "acao",
) -> None:
    """Grava uma linha de log estruturado para uma ação executada (thread-safe).

    `tipo="resumo"` identifica eventos agregados (ex.: duração total da execução), que
    não devem ser comparados/rankeados junto com latências de ações individuais.
    """
    if _handle_arquivo is None:
        iniciar_execucao()

    linha = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "execucao_id": _execucao_id,
        "nivel": nivel,
        "acao": acao,
        "tipo": tipo,
        "reclamacao_id": reclamacao_id,
        "status": status,
        "duracao_ms": duracao_ms,
        "detalhes": detalhes or {},
    }
    with _lock_arquivo:
        _handle_arquivo.write(json.dumps(linha, ensure_ascii=False) + "\n")
        _handle_arquivo.flush()
