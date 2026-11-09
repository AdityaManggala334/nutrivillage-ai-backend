"""Router LLM (FR-11) — penjelasan menu berbasis local LLM / API cloud.

- `GET  /ai/health`  : status endpoint LLM (untuk uji integrasi Docker/Ollama).
- `POST /ai/explain` : minta penjelasan satu menu, sekaligus menyimpannya ke
  tabel `llm_explanations` (kolom `model` mencatat model yang dipakai).

Alur rekomendasi tidak diubah: endpoint ini hanya menghasilkan narasi.
Bila LLM tidak tersedia, balasan memakai teks fallback (`source="fallback"`)
sehingga demo/aplikasi tidak pernah gagal.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_optional_user
from app.core.ratelimit import client_ip, consume
from app.db.session import get_db
from app.models.planning import LlmExplanation
from app.models.recipe import Recipe
from app.models.user import User
from app.schemas.ai import AiExplainRequest, AiExplainResponse, AiHealthResponse
from app.services import llm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


LLM_PER_HOUR = 30


def require_llm_user(
    request: Request,
    user: User | None = Depends(get_optional_user),
) -> User | None:
    """Login diwajibkan bila `LLM_REQUIRE_AUTH=true`, plus kuota per pemakai.

    Tanpa kuota, endpoint ini bisa dipakai mengirim panggilan ke API cloud
    berbayar dan menulis `llm_explanations` tanpa batas (K-02).
    """
    if settings.llm_require_auth and user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token autentikasi diperlukan untuk memakai endpoint AI.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    kunci = f"llm:user:{user.id}" if user else f"llm:ip:{client_ip(request)}"
    kuota = consume(kunci, limit=LLM_PER_HOUR, window_seconds=3600)
    if not kuota.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Kuota AI {LLM_PER_HOUR}x per jam tercapai. Coba lagi nanti.",
            headers={"Retry-After": str(kuota.retry_after)},
        )
    return user


def _save_explanation(
    db: Session,
    recipe_id: int | None,
    text: str,
    model: str,
) -> int | None:
    """Simpan ke `llm_explanations`; kegagalan DB tidak membatalkan respons."""
    try:
        valid_recipe_id = recipe_id if recipe_id and db.get(Recipe, recipe_id) else None
        row = LlmExplanation(
            recipe_id=valid_recipe_id,
            explanation_text=text,
            model=model,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return int(row.id)
    except Exception:  # noqa: BLE001 - jaring pengaman agar endpoint tetap sukses
        db.rollback()
        logger.warning("Gagal menyimpan penjelasan LLM ke database", exc_info=True)
        return None


@router.get("/health", response_model=AiHealthResponse)
def ai_health() -> AiHealthResponse:
    return AiHealthResponse(**llm.check_health())


@router.post("/explain", response_model=AiExplainResponse)
def explain_menu(
    payload: AiExplainRequest,
    db: Session = Depends(get_db),
    _: User | None = Depends(require_llm_user),
) -> AiExplainResponse:
    context = llm.MenuContext(
        recipe_name=payload.recipe_name,
        ingredients=tuple(payload.ingredients),
        calories=payload.calories,
        protein=payload.protein,
        estimated_cost=payload.estimated_cost,
        budget=payload.budget,
        audience=payload.audience,
    )
    result = llm.generate_explanation(context)

    saved_id = (
        _save_explanation(db, payload.recipe_id, result.text, result.model)
        if payload.save
        else None
    )

    return AiExplainResponse(
        explanation=result.text,
        model=result.model,
        source=result.source,
        latency_ms=result.latency_ms,
        saved_id=saved_id,
    )
