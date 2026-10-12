"""Paket CRUD. Re-export fungsi agar `from app import crud` dapat dipakai."""

from app.crud.schools import (
    create_group,
    create_school,
    delete_group,
    delete_school,
    get_budget_policy,
    get_group,
    get_officer_by_user_id,
    get_school,
    list_budget_policies,
    list_groups,
    list_schools,
    update_budget_policy,
    update_group,
    update_school,
)
from app.crud.users import (
    count_schools_for_officer,
    count_users,
    create_user,
    get_sppg_by_nip,
    get_user_by_email,
    get_user_by_id,
    list_users,
    update_user,
)

__all__ = [
    # users
    "get_user_by_email",
    "get_user_by_id",
    "get_sppg_by_nip",
    "count_users",
    "list_users",
    "count_schools_for_officer",
    "create_user",
    "update_user",
    # schools
    "get_officer_by_user_id",
    "list_schools",
    "get_school",
    "create_school",
    "update_school",
    "delete_school",
    "get_group",
    "list_groups",
    "create_group",
    "update_group",
    "delete_group",
    # budget policies
    "list_budget_policies",
    "get_budget_policy",
    "update_budget_policy",
]
