"""Skema endpoint LLM (FR-11: penjelasan menu setelah peringkat SAW)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AiExplainRequest(BaseModel):
    """Konteks menu yang akan dijelaskan.

    Sengaja hanya menerima ringkasan (bukan seluruh objek resep) agar endpoint
    tetap ringan dipakai mesin rekomendasi mana pun — termasuk SAW versi baru.
    """

    recipe_name: str = Field(min_length=1, max_length=120)
    ingredients: list[str] = Field(default_factory=list, max_length=30)
    calories: float | None = Field(default=None, ge=0, le=10000)
    protein: float | None = Field(default=None, ge=0, le=500)
    estimated_cost: float | None = Field(default=None, ge=0)
    budget: float | None = Field(default=None, ge=0)
    audience: str | None = Field(default=None, max_length=80)
    recipe_id: int | None = Field(default=None, gt=0)
    # Simpan hasil ke tabel `llm_explanations` (bisa dimatikan untuk uji cepat).
    save: bool = True

    @field_validator("ingredients")
    @classmethod
    def _batasi_panjang_bahan(cls, nilai: list[str]) -> list[str]:
        """Batas per item, bukan hanya jumlah item: nilai ini masuk ke prompt LLM."""
        if any(len(item) > 80 for item in nilai):
            raise ValueError("Nama bahan maksimal 80 karakter.")
        return [item.strip() for item in nilai]


class AiExplainResponse(BaseModel):
    explanation: str
    model: str
    source: Literal["llm", "fallback"]
    latency_ms: int
    saved_id: int | None = None


class AiHealthResponse(BaseModel):
    status: Literal["ok", "disabled", "unreachable"]
    base_url: str
    model: str
    models: list[str] = Field(default_factory=list)
    latency_ms: int
    detail: str | None = None
