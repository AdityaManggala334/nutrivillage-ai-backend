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

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_optional_user
from app.db.session import get_db
from app.models.planning import LlmExplanation
from app.models.recipe import Recipe
from app.models.user import User
from app.schemas.ai import AiExplainRequest, AiExplainResponse, AiHealthResponse
from app.services import llm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


def require_llm_user(user: User | None = Depends(get_optional_user)) -> User | None:
    """Login hanya diwajibkan bila `LLM_REQUIRE_AUTH=true` (mis. pemakaian API cloud)."""
    if settings.llm_require_auth and user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token autentikasi diperlukan untuk memakai endpoint AI.",
            headers={"WWW-Authenticate": "Bearer"},
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
