"""Klien LLM untuk penjelasan menu (endpoint OpenAI-compatible).

Satu implementasi dipakai untuk **LLM lokal** (Ollama) maupun **API cloud**
(Grok/xAI, Gemini mode OpenAI-compatible) — cukup mengubah environment:

    LLM_BASE_URL  LLM_API_KEY  LLM_MODEL  LLM_TIMEOUT_SECONDS

Tidak ada dependensi baru: HTTP memakai `urllib.request` dari standard library.
Bila LLM tidak dikonfigurasi / gagal / timeout, fungsi mengembalikan teks
fallback sehingga aplikasi tetap berjalan (source="fallback").
"""

from __future__ import annotations

import http.client
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Literal

from app.core.config import settings

logger = logging.getLogger(__name__)

Source = Literal["llm", "fallback"]

SYSTEM_PROMPT = (
    "Anda ahli gizi untuk program makan bergizi di Kabupaten Madiun. "
    "Tulis SATU paragraf penjelasan (maksimal 70 kata) dalam Bahasa Indonesia "
    "yang ramah dan informatif: jelaskan mengapa menu ini cocok, soroti protein "
    "dan gizinya, biaya, serta bahan lokal. Jangan memakai markdown dan jangan "
    "mengarang angka yang tidak diberikan."
)


@dataclass(frozen=True)
class MenuContext:
    """Konteks ringkas sebuah menu untuk diminta penjelasannya."""

    recipe_name: str
    ingredients: tuple[str, ...] = ()
    calories: float | None = None
    protein: float | None = None
    estimated_cost: float | None = None
    budget: float | None = None
    audience: str | None = None


@dataclass(frozen=True)
class LlmResult:
    text: str
    model: str
    source: Source
    latency_ms: int


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def is_configured() -> bool:
    return bool(settings.llm_base_url.strip())


def _base_url() -> str:
    return settings.llm_base_url.strip().rstrip("/")


def _completion_url() -> str:
    base = _base_url()
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _models_url() -> str:
    base = _base_url()
    if base.endswith("/chat/completions"):
        base = base[: -len("/chat/completions")]
    return f"{base}/models"


def _headers() -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        # Sebagian penyedia (mis. Groq di balik Cloudflare) menolak
        # User-Agent bawaan Python-urllib dengan 403 Forbidden.
        "User-Agent": "NutriVillageAI/1.0",
    }
    if settings.llm_api_key.strip():
        headers["Authorization"] = f"Bearer {settings.llm_api_key.strip()}"
    return headers


def _rupiah(value: float) -> str:
    return "Rp" + f"{value:,.0f}".replace(",", ".")


def _prompt(context: MenuContext) -> str:
    lines = [f"Menu: {context.recipe_name}"]
    if context.ingredients:
        lines.append("Bahan utama: " + ", ".join(context.ingredients[:10]))
    if context.calories is not None:
        lines.append(f"Energi per porsi: {context.calories:.0f} kkal")
    if context.protein is not None:
        lines.append(f"Protein per porsi: {context.protein:.0f} g")
    if context.estimated_cost is not None:
        lines.append(f"Estimasi biaya per porsi: {_rupiah(context.estimated_cost)}")
    if context.budget is not None:
        lines.append(f"Anggaran per porsi: {_rupiah(context.budget)}")
    if context.audience:
        lines.append(f"Sasaran penerima: {context.audience}")
    lines.append("Tulis penjelasan singkat dalam satu paragraf.")
    return "\n".join(lines)


def fallback_explanation(context: MenuContext) -> str:
    """Teks pengganti bila LLM tidak tersedia (tetap informatif)."""
    parts: list[str] = [f"{context.recipe_name} cocok dipilih"]
    if context.audience:
        parts.append(f"untuk {context.audience}")
    parts.append("karena gizinya seimbang")

    nutrition: list[str] = []
    if context.calories is not None:
        nutrition.append(f"sekitar {context.calories:.0f} kkal")
    if context.protein is not None:
        nutrition.append(f"{context.protein:.0f} g protein")
    if nutrition:
        parts.append("dengan " + " dan ".join(nutrition) + " per porsi")

    sentence = " ".join(parts) + "."

    if context.estimated_cost is not None:
        money = f"Estimasi biayanya {_rupiah(context.estimated_cost)} per porsi"
        if context.budget is not None:
            status = "masih dalam" if context.estimated_cost <= context.budget else "sedikit di atas"
            money += f", {status} anggaran {_rupiah(context.budget)} per porsi"
        sentence += " " + money + "."

    sentence += (
        " Bahannya mudah ditemukan di sekitar Madiun sehingga mendukung pangan lokal"
        " sekaligus menekan biaya."
    )
    return sentence


def _extract_text(body: object) -> str:
    """Ambil teks dari respons OpenAI-compatible (Ollama/xAI/Gemini)."""
    if not isinstance(body, dict):
        raise ValueError("Respons LLM bukan objek JSON")
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("Respons LLM tidak memiliki 'choices'")
    first = choices[0]
    if not isinstance(first, dict):
        raise ValueError("Format 'choices' tidak dikenali")
    message = first.get("message")
    if not isinstance(message, dict):
        raise ValueError("Respons LLM tidak memiliki 'message'")
    content = message.get("content")

    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        # Sebagian penyedia mengirim bagian-bagian (multimodal).
        texts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
        return "".join(texts).strip()
    return ""


def generate_explanation(context: MenuContext) -> LlmResult:
    """Minta penjelasan ke LLM; selalu mengembalikan hasil (fallback bila gagal)."""
    started = time.perf_counter()

    if not is_configured():
        return LlmResult(
            text=fallback_explanation(context),
            model="fallback",
            source="fallback",
            latency_ms=_elapsed_ms(started),
        )

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _prompt(context)},
        ],
        "temperature": 0.3,
        "max_tokens": 120,
        "stream": False,
    }
    request = urllib.request.Request(
        _completion_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(),
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.llm_timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        text = _extract_text(body)
        if not text:
            raise ValueError("Teks penjelasan kosong")
        return LlmResult(
            text=text,
            model=settings.llm_model,
            source="llm",
            latency_ms=_elapsed_ms(started),
        )
    except (OSError, ValueError, http.client.HTTPException) as exc:
        logger.warning("LLM tidak dapat dipakai (%s) — memakai teks fallback", exc)
        return LlmResult(
            text=fallback_explanation(context),
            model="fallback",
            source="fallback",
            latency_ms=_elapsed_ms(started),
        )


def check_health() -> dict[str, object]:
    """Cek apakah endpoint LLM dapat dijangkau (untuk bukti integrasi)."""
    started = time.perf_counter()

    if not is_configured():
        return {
            "status": "disabled",
            "base_url": "",
            "model": settings.llm_model,
            "models": [],
            "latency_ms": _elapsed_ms(started),
            "detail": "LLM_BASE_URL belum diisi — endpoint memakai teks fallback.",
        }

    request = urllib.request.Request(_models_url(), headers=_headers(), method="GET")
    try:
        timeout = min(settings.llm_timeout_seconds, 10.0)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        raw_models = body.get("data") if isinstance(body, dict) else None
        if not isinstance(raw_models, list):
            # Ollama mengembalikan `data: null` saat belum ada model terunduh.
            raw_models = []
        models = [
            str(item.get("id"))
            for item in raw_models
            if isinstance(item, dict) and item.get("id")
        ]
        return {
            "status": "ok",
            "base_url": _base_url(),
            "model": settings.llm_model,
            "models": models,
            "latency_ms": _elapsed_ms(started),
            "detail": None,
        }
    except (OSError, ValueError, http.client.HTTPException) as exc:
        return {
            "status": "unreachable",
            "base_url": _base_url(),
            "model": settings.llm_model,
            "models": [],
            "latency_ms": _elapsed_ms(started),
            "detail": str(exc)[:200],
        }

@dataclass(frozen=True)
class PlanContext:
    """Konteks ringkas satu paket makan penuh (FR-03: narasi hasil engine)."""
    total_biaya: float | None = None
    anggaran: float | None = None
    energi_pct: float | None = None
    protein_pct: float | None = None
    daftar_menu: tuple[str, ...] = ()
    n_waktu_makan: int = 0


def _plan_prompt(context: PlanContext) -> str:
    lines = [
        f"Paket makan {context.n_waktu_makan} waktu untuk satu hari keluarga.",
        "Menu per waktu makan:",
    ]
    lines.extend(f"- {row}" for row in context.daftar_menu[:6])
    if context.energi_pct is not None:
        lines.append(f"Pemenuhan energi: {context.energi_pct:.0f}% dari target harian")
    if context.protein_pct is not None:
        lines.append(f"Pemenuhan protein: {context.protein_pct:.0f}% dari target harian")
    if context.total_biaya is not None:
        lines.append(f"Total biaya: {_rupiah(context.total_biaya)}")
    if context.anggaran is not None:
        lines.append(f"Anggaran harian: {_rupiah(context.anggaran)}")
    lines.append(
        "Tulis 2-3 kalimat: mengapa kombinasi ini cocok untuk kebutuhan gizi "
        "dan anggaran pengguna. Sebutkan kekuatan utamanya (misal protein hewani "
        "atau sayur lokal) tanpa mengarang angka di luar data di atas."
    )
    return "\n".join(lines)


def plan_fallback(context: PlanContext) -> str:
    """Narasi pengganti bila LLM tidak tersedia (tetap informatif)."""
    kalimat = [
        f"Paket {context.n_waktu_makan} waktu makan ini disusun agar memenuhi "
        "kebutuhan gizi harian keluarga dengan biaya terkendali."
    ]
    if context.total_biaya is not None and context.anggaran is not None:
        status = "masih dalam" if context.total_biaya <= context.anggaran else "sedikit di atas"
        kalimat.append(
            f"Total biayanya {_rupiah(context.total_biaya)}, {status} anggaran "
            f"{_rupiah(context.anggaran)}."
        )
    if context.energi_pct is not None:
        kalimat.append(
            f"Paket ini memenuhi sekitar {context.energi_pct:.0f}% kebutuhan energi "
            f"dan {context.protein_pct or 0:.0f}% protein harian."
        )
    if context.daftar_menu:
        kunci = ", ".join(
            context.daftar_menu[0].split(": ")[-1].split(", ")[:3]
        )
        kalimat.append(f"Menu utamanya antara lain {kunci}.")
    kalimat.append("Semua bahan mudah ditemukan di pasar lokal Madiun.")
    return " ".join(kalimat)


def generate_plan_explanation(context: PlanContext) -> LlmResult:
    """Narasi satu paket makan penuh; fallback bila LLM tidak tersedia."""
    started = time.perf_counter()
    if not is_configured():
        return LlmResult(
            text=plan_fallback(context),
            model="fallback",
            source="fallback",
            latency_ms=_elapsed_ms(started),
        )
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _plan_prompt(context)},
        ],
        "temperature": 0.3,
        "max_tokens": 160,
        "stream": False,
    }
    request = urllib.request.Request(
        _completion_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.llm_timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        text = _extract_text(body)
        if not text:
            raise ValueError("Teks penjelasan kosong")
        return LlmResult(
            text=text,
            model=settings.llm_model,
            source="llm",
            latency_ms=_elapsed_ms(started),
        )
    except (OSError, ValueError, http.client.HTTPException) as exc:
        logger.warning("LLM tidak dapat dipakai (%s) - memakai teks fallback", exc)
        return LlmResult(
            text=plan_fallback(context),
            model="fallback",
            source="fallback",
            latency_ms=_elapsed_ms(started),
        )
