"""Model ORM. Impor di sini agar `Base.metadata` mengenali semua tabel."""

from app.models.beneficiary_group import BeneficiaryGroup, BeneficiaryLevel
from app.models.budget_policy import BudgetPolicy
from app.models.catalog import (
    Ingredient,
    LocalAvailability,
    NutritionFact,
    Region,
    SeasonalAvailability,
)
from app.models.content import Article, FoodSafetyInfo, Notification
from app.models.family import FamilyMember, FamilyProfile
from app.models.history import HistoryEntry
from app.models.planning import (
    Favorite,
    LlmExplanation,
    MealPlan,
    Recommendation,
    RecommendationItem,
    ShoppingList,
    ShoppingListItem,
    SystemConfig,
)
from app.models.price import (
    Price,
    PriceHistory,
    PriceVerification,
    ScraperRun,
)
from app.models.recipe import Recipe, RecipeIngredient, RecipeNutrition
from app.models.school import School
from app.models.sppg import SppgOfficer
from app.models.user import User, UserRole

__all__ = [
    # Auth & SPPG
    "User",
    "UserRole",
    "SppgOfficer",
    "School",
    "BeneficiaryGroup",
    "BeneficiaryLevel",
    "BudgetPolicy",
    # Wilayah & bahan
    "Region",
    "Ingredient",
    "NutritionFact",
    "SeasonalAvailability",
    "LocalAvailability",
    # Harga
    "Price",
    "PriceVerification",
    "PriceHistory",
    "ScraperRun",
    # Resep
    "Recipe",
    "RecipeNutrition",
    "RecipeIngredient",
    # Keluarga
    "FamilyProfile",
    "FamilyMember",
    # Riwayat
    "HistoryEntry",
    # Rekomendasi, planner, belanja
    "Recommendation",
    "RecommendationItem",
    "LlmExplanation",
    "MealPlan",
    "ShoppingList",
    "ShoppingListItem",
    "Favorite",
    "SystemConfig",
    # Konten
    "Article",
    "Notification",
    "FoodSafetyInfo",
]
