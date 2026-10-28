"""Correção de redação com LLMs gratuitos.

Cadeia de provedores (o primeiro que responder um JSON válido vence):
    1. Groq          (GROQ_API_KEY)   - llama-3.3-70b-versatile
    2. Google Gemini (GEMINI_API_KEY) - gemini-2.5-flash
    3. Hugging Face  (HF_TOKEN)       - Inference Providers (API compatível com OpenAI)
    4. Pollinations  (sem chave)
    5. Heurística local (sem rede)   - garante que a funcionalidade nunca fica fora do ar
"""
import json
import logging
import re
import time
from typing import Callable

import httpx

from ..config import settings

logger = logging.getLogger("agenda.ai")

COMPETENCIES = [
    ("C1", "Domínio da norma-padrão da língua escrita"),
    ("C2", "Compreensão da proposta e aplicação de conceitos de várias áreas"),
    ("C3", "Seleção e organização de informações e argumentos"),
    ("C4", "Conhecimento dos mecanismos linguísticos de coesão"),
    ("C5", "Proposta de intervenção respeitando os direitos humanos"),
]

SYSTEM_PROMPT = """Você é um corretor experiente e criterioso da redação do ENEM (Brasil).
Avalie o texto dissertativo-argumentativo segundo as 5 competências oficiais do INEP:
C1 - Domínio da modalidade escrita formal da língua portuguesa.
C2 - Compreender a proposta e aplicar conceitos das várias áreas de conhecimento para desenvolver o tema, dentro dos limites do texto dissertativo-argumentativo.
C3 - Selecionar, relacionar, organizar e interpretar informações, fatos, opiniões e argumentos em defesa de um ponto de vista.
C4 - Demonstrar conhecimento dos mecanismos linguísticos necessários para a construção da argumentação (coesão).
C5 - Elaborar proposta de intervenção para o problema abordado, respeitando os direitos humanos (agente, ação, meio/modo, finalidade e detalhamento).

Regras:
- Cada competência recebe exatamente um destes valores: 0, 40, 80, 120, 160 ou 200.
- A nota total é a soma das cinco (0 a 1000).
- Fuga total ao tema, texto com menos de 7 linhas ou desrespeito aos direitos humanos devem ser penalizados conforme o INEP.
- O texto pode ter vindo de OCR; ignore pequenos ruídos óbvios de digitalização ao avaliar a C1.
- Seja específico: cite trechos ou aspectos concretos do texto nos comentários.
- Escreva tudo em português do Brasil.

Responda APENAS com um objeto JSON válido, sem markdown, exatamente neste formato:
{
  "total_score": 0,
  "competencies": [
    {"id": "C1", "name": "Domínio da norma-padrão", "score": 0, "feedback": "..."},
    {"id": "C2", "name": "Compreensão da proposta", "score": 0, "feedback": "..."},
    {"id": "C3", "name": "Argumentação", "score": 0, "feedback": "..."},
    {"id": "C4", "name": "Coesão textual", "score": 0, "feedback": "..."},
    {"id": "C5", "name": "Proposta de intervenção", "score": 0, "feedback": "..."}
  ],
  "strengths": ["...", "..."],
  "improvements": ["...", "..."],
  "summary": "Parecer geral em 2 a 3 frases."
}"""

TIMEOUT = httpx.Timeout(25.0, connect=8.0)
# Orçamento total para tentar provedores (a função na Vercel tem maxDuration = 60s)
TIME_BUDGET_SECONDS = 38.0


def _user_prompt(theme: str, text: str) -> str:
    return f"TEMA DA REDAÇÃO: {theme}\n\nTEXTO DO ALUNO:\n\"\"\"\n{text}\n\"\"\""


def _messages(theme: str, text: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _user_prompt(theme, text)},
    ]


# ------------------------------------------------------------------ provedores
def _openai_compatible(url: str, headers: dict, payload: dict) -> str:
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"]


def call_groq(theme: str, text: str) -> str:
    return _openai_compatible(
        "https://api.groq.com/openai/v1/chat/completions",
        {"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
        {
            "model": settings.GROQ_MODEL,
            "messages": _messages(theme, text),
            "temperature": 0.2,
            "max_tokens": 2048,
            "response_format": {"type": "json_object"},
        },
    )


def call_gemini(theme: str, text: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": _user_prompt(theme, text)}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json", "maxOutputTokens": 4096},
    }
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.post(url, params={"key": settings.GEMINI_API_KEY}, json=payload)
        resp.raise_for_status()
        data = resp.json()
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


def call_huggingface(theme: str, text: str) -> str:
    return _openai_compatible(
        "https://router.huggingface.co/v1/chat/completions",
        {"Authorization": f"Bearer {settings.HF_TOKEN}"},
        {
            "model": settings.HF_MODEL,
            "messages": _messages(theme, text),
            "temperature": 0.2,
            "max_tokens": 2048,
        },
    )


def call_pollinations(theme: str, text: str) -> str:
    payload = {
        "model": settings.POLLINATIONS_MODEL,
        "messages": _messages(theme, text),
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "private": True,
    }
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.post(settings.POLLINATIONS_URL, json=payload)
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            return resp.text
    if isinstance(data, dict) and "choices" in data:
        return data["choices"][0]["message"]["content"]
    return json.dumps(data) if isinstance(data, dict) else str(data)


def active_providers() -> list[tuple[str, Callable[[str, str], str]]]:
    providers: list[tuple[str, Callable[[str, str], str]]] = []
    if settings.GROQ_API_KEY:
        providers.append((f"groq:{settings.GROQ_MODEL}", call_groq))
    if settings.GEMINI_API_KEY:
        providers.append((f"gemini:{settings.GEMINI_MODEL}", call_gemini))
    if settings.HF_TOKEN:
        providers.append((f"huggingface:{settings.HF_MODEL}", call_huggingface))
    if settings.POLLINATIONS_ENABLED:
        providers.append((f"pollinations:{settings.POLLINATIONS_MODEL}", call_pollinations))
    return providers


# ------------------------------------------------------------------ parsing
def _extract_json(raw: str) -> dict:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE | re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("Resposta da IA não contém JSON.")
        return json.loads(cleaned[start : end + 1])


def _snap(score) -> int:
    """Arredonda para o nível válido do ENEM mais próximo (múltiplos de 40, entre 0 e 200)."""
    try:
        value = float(score)
    except (TypeError, ValueError):
        value = 0
    value = max(0.0, min(200.0, value))
    return int(round(value / 40.0) * 40)


def _as_str_list(value) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()][:8]


def normalize_result(data: dict) -> dict:
    raw_comps = data.get("competencies") or data.get("competencias") or []
    by_id: dict[str, dict] = {}
    if isinstance(raw_comps, dict):
        raw_comps = [{"id": k, **(v if isinstance(v, dict) else {"score": v})} for k, v in raw_comps.items()]
    for index, comp in enumerate(raw_comps if isinstance(raw_comps, list) else []):
        if not isinstance(comp, dict):
            continue
        cid = str(comp.get("id") or comp.get("competencia") or f"C{index + 1}").upper().strip()
        match = re.search(r"([1-5])", cid)
        cid = f"C{match.group(1)}" if match else f"C{index + 1}"
        by_id[cid] = comp

    competencies = []
    for cid, default_name in COMPETENCIES:
        comp = by_id.get(cid, {})
        competencies.append(
            {
                "id": cid,
                "name": str(comp.get("name") or comp.get("nome") or default_name),
                "score": _snap(comp.get("score", comp.get("nota", 0))),
                "feedback": str(comp.get("feedback") or comp.get("comentario") or "Sem comentário."),
            }
        )
    if not by_id:
        raise ValueError("JSON sem competências.")

    return {
        "total_score": sum(c["score"] for c in competencies),
        "competencies": competencies,
        "strengths": _as_str_list(data.get("strengths") or data.get("pontos_fortes")),
        "improvements": _as_str_list(data.get("improvements") or data.get("sugestoes")),
        "summary": str(data.get("summary") or data.get("parecer") or "").strip(),
    }


# ------------------------------------------------------------------ fallback local
CONNECTIVES = [
    "além disso", "ademais", "outrossim", "portanto", "logo", "assim", "dessa forma", "desse modo",
    "contudo", "entretanto", "no entanto", "todavia", "porém", "embora", "visto que", "uma vez que",
    "pois", "porque", "consequentemente", "por conseguinte", "em primeiro lugar", "em segundo lugar",
    "por fim", "nesse sentido", "nesse contexto", "diante disso", "sob esse viés", "em suma",
]
INTERVENTION_AGENTS = [
    "governo", "estado", "ministério", "escola", "escolas", "mídia", "família", "sociedade",
    "ong", "ongs", "poder público", "prefeitura", "congresso", "empresas", "instituições",
]
INTERVENTION_ACTIONS = ["deve", "devem", "é necessário", "é preciso", "cabe", "precisa", "urge", "medidas"]
INTERVENTION_PURPOSE = ["a fim de", "para que", "com o objetivo de", "com a finalidade de", "visando", "de modo a"]
REPERTOIRE = [
    "segundo", "de acordo com", "conforme", "constituição", "filósofo", "sociólogo", "pesquisa",
    "dados", "ibge", "oms", "onu", "lei", "artigo", "século", "história", "autor", "obra",
]


def heuristic_evaluation(theme: str, text: str) -> dict:
    lower = text.lower()
    words = re.findall(r"\w+", lower, flags=re.UNICODE)
    word_count = len(words)
    paragraphs = [p for p in re.split(r"\n\s*\n|\n", text) if len(p.strip()) > 40]
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    avg_sentence = word_count / max(1, len(sentences))

    theme_words = {w for w in re.findall(r"\w+", theme.lower()) if len(w) > 4}
    theme_hits = sum(1 for w in theme_words if w in lower)
    theme_ratio = theme_hits / max(1, len(theme_words))

    conn_hits = sum(1 for c in CONNECTIVES if c in lower)
    agent_hits = sum(1 for a in INTERVENTION_AGENTS if re.search(rf"\b{re.escape(a)}\b", lower))
    action_hits = sum(1 for a in INTERVENTION_ACTIONS if a in lower)
    purpose_hits = sum(1 for a in INTERVENTION_PURPOSE if a in lower)
    rep_hits = sum(1 for r in REPERTOIRE if r in lower)

    if word_count < 70:
        comps = [40, 0, 0, 40, 0]
    else:
        c1 = 160 if 12 <= avg_sentence <= 35 else 120
        if word_count < 200:
            c1 -= 40
        c2 = 80 + (40 if theme_ratio >= 0.4 else 0) + (40 if rep_hits >= 2 else 0) + (40 if len(paragraphs) >= 4 else 0)
        c3 = 80 + (40 if len(paragraphs) >= 4 else 0) + (40 if word_count >= 250 else 0) + (40 if rep_hits >= 3 else 0)
        c4 = 80 + min(120, conn_hits * 20)
        c5_elements = sum([agent_hits > 0, action_hits > 0, purpose_hits > 0, ("por meio de" in lower or "através de" in lower or "mediante" in lower)])
        c5 = min(200, c5_elements * 40 + (40 if agent_hits >= 2 else 0))
        comps = [c1, c2, c3, c4, c5]

    comps = [_snap(c) for c in comps]
    names = ["Domínio da norma-padrão", "Compreensão da proposta", "Argumentação", "Coesão textual", "Proposta de intervenção"]
    feedbacks = [
        f"Frases com média de {avg_sentence:.0f} palavras. Revise acentuação, concordância e pontuação; períodos muito longos dificultam a leitura.",
        f"O texto retoma {theme_hits} de {len(theme_words) or 0} palavras-chave do tema e apresenta {rep_hits} marca(s) de repertório sociocultural.",
        f"Foram identificados {len(paragraphs)} parágrafo(s) e {word_count} palavras. O ideal são 4 parágrafos (introdução, 2 desenvolvimentos e conclusão) com argumentos aprofundados.",
        f"Foram encontrados {conn_hits} conectivo(s) diferentes. Varie os elementos coesivos entre e dentro dos parágrafos.",
        f"Elementos da intervenção detectados: agente ({agent_hits}), ação ({action_hits}), finalidade ({purpose_hits}). Garanta agente, ação, meio, finalidade e detalhamento.",
    ]
    competencies = [
        {"id": cid, "name": names[i], "score": comps[i], "feedback": feedbacks[i]}
        for i, (cid, _) in enumerate(COMPETENCIES)
    ]
    strengths, improvements = [], []
    if len(paragraphs) >= 4:
        strengths.append("Estrutura em parágrafos bem definida.")
    if conn_hits >= 4:
        strengths.append("Bom uso de conectivos para articular as ideias.")
    if rep_hits >= 2:
        strengths.append("Presença de repertório sociocultural.")
    if agent_hits and action_hits:
        strengths.append("A conclusão apresenta indícios de proposta de intervenção.")
    if not strengths:
        strengths.append("O texto aborda o tema proposto e pode ser desenvolvido.")
    if word_count < 250:
        improvements.append("Desenvolva mais os argumentos: redações nota alta costumam ter entre 25 e 30 linhas.")
    if rep_hits < 2:
        improvements.append("Inclua repertório legitimado (dados, leis, autores, fatos históricos) e relacione-o ao tema.")
    if purpose_hits == 0:
        improvements.append("Explicite a finalidade da proposta de intervenção (\"a fim de...\", \"para que...\").")
    if conn_hits < 4:
        improvements.append("Use mais conectivos variados (\"além disso\", \"portanto\", \"nesse sentido\").")
    improvements.append("Para uma correção mais precisa, configure uma chave gratuita do Groq ou do Gemini no servidor.")
    return {
        "total_score": sum(comps),
        "competencies": competencies,
        "strengths": strengths,
        "improvements": improvements,
        "summary": "Avaliação estimada por análise heurística automática (os provedores de IA não estavam disponíveis no momento). Use como orientação, não como nota oficial.",
    }


# ------------------------------------------------------------------ orquestração
def evaluate_essay(theme: str, text: str) -> dict:
    errors: list[str] = []
    started = time.monotonic()
    for name, fn in active_providers():
        if time.monotonic() - started > TIME_BUDGET_SECONDS:
            errors.append(f"{name}: pulado (tempo esgotado)")
            continue
        try:
            raw = fn(theme, text)
            result = normalize_result(_extract_json(raw))
            result["provider"] = name
            return result
        except Exception as exc:  # noqa: BLE001 - qualquer falha passa para o próximo provedor
            logger.warning("Provedor %s falhou: %s", name, exc)
            errors.append(f"{name}: {type(exc).__name__}")
    result = heuristic_evaluation(theme, text)
    result["provider"] = "heuristica-local"
    result["provider_errors"] = errors
    return result
