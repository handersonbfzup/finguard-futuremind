"""Guardrail de entrada (anti-injection/anti-abuso) e guardrail de saída (anti-PII/anti-ofensa).

Camada de defesa em profundidade, independente do Bedrock Guardrails oficial (Nível 3).
Roda localmente, sem custo de LLM, e serve como primeiro filtro antes de qualquer chamada
ao modelo — bloqueia os casos óbvios sem gastar tokens.

Os padrões abaixo foram levantados a partir de tentativas reais de ataque encontradas no
dataset do desafio (extração de system prompt, falsa autoridade, jailbreak/roleplay,
exfiltração de dados via URL/Base64/QR code e ameaças de violência física).
"""

import re
from dataclasses import dataclass

# --- Guardrail de entrada -------------------------------------------------

_PADROES_INJECTION = [
    # Extração de system prompt / instruções internas
    r"\bsystem\s*prompt\b",
    r"prompt\s+de\s+sistema",
    r"instru[cç][õoa]es?\s+(internas?|de\s+configura[cç][ãa]o|de\s+seguran[cç]a|reais|de\s+sistema)",
    r"regras?\s+(internas?|de\s+classifica[cç][ãa]o)\s+(completas?|exatas?)",
    r"repita\s+integralmente|transcreva|cole\s+tudo\s+exatamente",
    r"internamente|estrutura\s+interna|template\s+(exato|interno)",
    # Jailbreak / roleplay / override de instruções
    r"modo\s+desenvolvedor|modo\s+irrestrito|admin[-_]?override",
    r"ignore\s+(completamente\s+)?(todas\s+)?as?\s+instru[cç][õoa]es?",
    r"finja\s+que|vamos\s+jogar\s+um\s+jogo|simule\s+que\s+recebeu",
    r"vamos\s+jogar|assuma\s+o\s+papel|jogo\s+de\s+rpg",
    # Falsa autoridade + pedido de dados em massa/sem mascaramento
    r"(diretor|dr\.?a?|gerente|engenheiro|analista)\s+.{0,40}(compliance|seguran[cç]a|\bti\b|banco\s+central)",
    r"exijo\s+acesso|fiscaliza[cç][ãa]o\s+de\s+rotina|protocolo\s+bacen",
    r"c[oó]digo\s+de\s+acesso",
    r"sem\s+mascarar|n[ãa]o\s+precisa\s+mascarar|sem\s+mascaramento|sem\s+nenhuma\s+reda[cç][ãa]o|sem\s+filtro",
    r"todos?\s+os?\s+cpfs?\b|lista\s+(completa\s+)?de\s+cpfs?",
    r"dados\s+pessoais\s+(d[oe]s?\s+)?(client|reclamante)|texto\s+original\s+completo",
    r"cpf\D{0,20}(telefone|endere[cç]o|conta)",
    # Exfiltração de dados via canal externo
    r"https?://|webhook|base64|qr\s*code",
    r"endpoint\s+externo|api\s+externa|token\s+de\s+autentica[cç][ãa]o|bearer\s+\S+",
    # Ameaça direta a pessoas/instituições
    r"vou\s+mandar\s+gente|violência\s+f[íi]sica|contratar\s+um\s+hacker|dar\s+um\s+susto",
]

_REGEX_INJECTION = re.compile("|".join(_PADROES_INJECTION), re.IGNORECASE)


@dataclass
class ResultadoGuardrail:
    bloqueado: bool
    motivo: str | None = None


def verificar_guardrail_entrada(texto: str) -> ResultadoGuardrail:
    """Detecta tentativas de prompt injection, jailbreak, exfiltração de dados ou ameaças.

    Retorna bloqueado=True se o texto não deve ser processado pelo pipeline de classificação.
    """
    match = _REGEX_INJECTION.search(texto)
    if match:
        return ResultadoGuardrail(
            bloqueado=True,
            motivo=f"padrao_suspeito:{match.group(0)[:40]}",
        )
    return ResultadoGuardrail(bloqueado=False)


RESPOSTA_BLOQUEIO = (
    "Não foi possível processar esta solicitação automaticamente. "
    "Se você tem uma reclamação a registrar, por favor descreva o problema enfrentado "
    "com o produto ou serviço. Para outras demandas, entre em contato com nossos canais "
    "oficiais de atendimento."
)


# --- Guardrail de saída ----------------------------------------------------

_REGEX_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_REGEX_CONTA = re.compile(r"\bconta\s*(n[uú]mero|n[º°.]?)?\s*\d{4,6}-?\d\b", re.IGNORECASE)
_REGEX_TELEFONE = re.compile(r"\b(\(?\d{2}\)?\s?)?\d{4,5}-?\d{4}\b")

_PALAVROES = [
    "porra", "merda", "caralho", "puta", "foda", "cacete", "desgraça", "otário", "idiota",
]
_REGEX_PALAVROES = re.compile("|".join(re.escape(p) for p in _PALAVROES), re.IGNORECASE)


def mascarar_dados_sensiveis(texto: str) -> str:
    """Remove CPF, número de conta e telefone de um texto (usado no resumo final)."""
    texto = _REGEX_CPF.sub("[CPF]", texto)
    texto = _REGEX_CONTA.sub("[CONTA]", texto)
    texto = _REGEX_TELEFONE.sub("[TELEFONE]", texto)
    return texto


def mascarar_linguagem_ofensiva(texto: str) -> str:
    """Mascara palavras ofensivas comuns em português (defesa complementar ao prompt do LLM)."""
    return _REGEX_PALAVROES.sub(lambda m: m.group(0)[0] + "*" * (len(m.group(0)) - 1), texto)


def aplicar_guardrail_saida(texto: str) -> str:
    """Aplica as duas máscaras (dados sensíveis + linguagem ofensiva) num texto de saída."""
    return mascarar_linguagem_ofensiva(mascarar_dados_sensiveis(texto))
