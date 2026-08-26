"""Ingestao e recuperacao local da politica interna do FinGuard."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

RAIZ = Path(__file__).resolve().parent.parent
PDF_POLITICA_PADRAO = RAIZ / "docs" / "KS_POLITICA_INTERNA (4).pdf"
TAMANHO_CHUNK_CARACTERES = 2400
SOBREPOSICAO_CHARS = 300
LIMIAR_RELEVANCIA = 0.08

# Titulos numerados sao preservados como metadado mesmo quando o PDF quebra linhas.
_PADRAO_SECAO = re.compile(r"^\s*((?:\d+\.)+\d*\s+.+|[A-Z][A-Z0-9ÁÀÃÂÉÊÍÓÔÕÚÇ /-]{8,})\s*$")


@dataclass(frozen=True)
class PoliticaChunk:
    chunk_id: str
    document_id: str
    page: int
    section: str
    text: str

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


def _normalizar_texto(texto: str) -> str:
    return re.sub(r"[ \t]+", " ", texto.replace("\r", "")).strip()


def _extrair_secao(linha: str, atual: str) -> str:
    linha_normalizada = _normalizar_texto(linha)
    numerada = re.match(
        r"^((?:\d+\.)+\d*\s+[A-ZÁÀÃÂÉÊÍÓÔÕÚÇ][^:|]{0,100}?)(?=\s+(?:Definição|Prazo|Ações|Canal|Esta)|\s+-|$)",
        linha_normalizada,
    )
    if numerada:
        return numerada.group(1).strip()
    if _PADRAO_SECAO.match(linha_normalizada):
        return linha_normalizada[:120]
    return atual


def extrair_chunks_pdf(
    caminho_pdf: str | Path = PDF_POLITICA_PADRAO,
    *,
    tamanho_chunk: int = TAMANHO_CHUNK_CARACTERES,
    sobreposicao: int = SOBREPOSICAO_CHARS,
    document_id: str = "POL-SAC-001",
) -> list[PoliticaChunk]:
    """Extrai chunks somente da politica, preservando pagina e secao."""
    if tamanho_chunk <= sobreposicao:
        raise ValueError("tamanho_chunk deve ser maior que sobreposicao")

    reader = PdfReader(str(caminho_pdf))
    chunks: list[PoliticaChunk] = []
    for numero_pagina, pagina in enumerate(reader.pages, start=1):
        texto_pagina = pagina.extract_text() or ""
        secao = f"Página {numero_pagina}"
        texto = _normalizar_texto(texto_pagina)
        partes = re.split(r"(?=(?:\d+\.)+\d*\s+)", texto)
        segmentos: list[tuple[str, str]] = []
        for parte_texto in partes:
            parte_texto = parte_texto.strip()
            if not parte_texto:
                continue
            primeira_linha = parte_texto.split("  ", 1)[0]
            secao_parte = _extrair_secao(primeira_linha, secao)
            segmentos.append((secao_parte, parte_texto))

        parte = 0
        for secao_segmento, texto in segmentos:
            inicio = 0
            while inicio < len(texto):
                fim = min(inicio + tamanho_chunk, len(texto))
                trecho = texto[inicio:fim].strip()
                if trecho:
                    chunks.append(
                        PoliticaChunk(
                            chunk_id=f"{document_id}-p{numero_pagina:02d}-c{parte:02d}",
                            document_id=document_id,
                            page=numero_pagina,
                            section=secao_segmento,
                            text=trecho,
                        )
                    )
                if fim == len(texto):
                    break
                inicio = fim - sobreposicao
                parte += 1
            parte += 1
    return chunks


class PoliticaRetriever:
    """Retriever lexical offline; o indice contem apenas chunks da politica."""

    def __init__(self, chunks: Iterable[PoliticaChunk]):
        self.chunks = list(chunks)
        if not self.chunks:
            raise ValueError("A politica nao possui chunks indexaveis")
        self.vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), sublinear_tf=True)
        self.matriz = self.vectorizer.fit_transform([chunk.text for chunk in self.chunks])

    @classmethod
    def from_pdf(cls, caminho_pdf: str | Path = PDF_POLITICA_PADRAO) -> "PoliticaRetriever":
        return cls(extrair_chunks_pdf(caminho_pdf))

    def recuperar(self, consulta: str, *, top_k: int = 4, limiar: float = LIMIAR_RELEVANCIA) -> list[dict]:
        if not consulta.strip():
            return []
        vetor_consulta = self.vectorizer.transform([consulta])
        similaridades = cosine_similarity(vetor_consulta, self.matriz)[0]
        indices = similaridades.argsort()[::-1]
        resultados = []
        for indice in indices[:top_k]:
            score = float(similaridades[indice])
            if score < limiar:
                continue
            resultado = self.chunks[indice].to_dict()
            resultado["score"] = round(score, 6)
            resultados.append(resultado)
        return resultados


@lru_cache(maxsize=1)
def obter_retriever_politica(caminho_pdf: str | Path = PDF_POLITICA_PADRAO) -> PoliticaRetriever:
    """Carrega o indice uma vez por processo para evitar reprocessar o PDF por linha."""
    return PoliticaRetriever.from_pdf(str(caminho_pdf))


def recuperar_contexto_politica(
    texto: str,
    classificacao: dict | None = None,
    canal: str = "",
    *,
    top_k: int = 4,
) -> list[dict]:
    consulta = " ".join(parte for parte in [texto, canal, str(classificacao or "")] if parte)
    return obter_retriever_politica().recuperar(consulta, top_k=top_k)


def formatar_contexto_politica(chunks: list[dict]) -> str:
    """Serializa fontes como dados delimitados, nunca como instrucoes do sistema."""
    if not chunks:
        return "[NENHUM CONTEXTO RELEVANTE DA POLITICA FOI RECUPERADO]"
    blocos = []
    for chunk in chunks:
        blocos.append(
            "<fonte "
            f'chunk_id="{escape(str(chunk["chunk_id"]))}" pagina="{escape(str(chunk["page"]))}" '
            f'secao="{escape(str(chunk["section"]))}">\n{escape(str(chunk["text"]))}\n</fonte>'
        )
    return "\n\n".join(blocos)
