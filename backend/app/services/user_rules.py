"""Guard rails for staff-user administration (pure, unit-tested)."""
SUPER = "Super Admin"


class UserRuleError(ValueError):
    pass


def check_update(*, actor_id: int, actor_is_super: bool, target_id: int, target_roles: set[str], new_roles: set[str],
                 target_active: bool, new_active: bool, other_active_supers: int) -> None:
    """Raise UserRuleError if this change would let someone escalate privileges or lock the business out."""
    touches_super = (SUPER in target_roles) != (SUPER in new_roles)
    if touches_super and not actor_is_super:
        raise UserRuleError("Only a Super Admin can grant or remove the Super Admin role")
    if SUPER in target_roles and not actor_is_super and (new_roles != target_roles or new_active != target_active):
        raise UserRuleError("Only a Super Admin can modify a Super Admin")
    if target_id == actor_id and not new_active:
        raise UserRuleError("You cannot deactivate your own account")
    was_active_super = SUPER in target_roles and target_active
    still_active_super = SUPER in new_roles and new_active
    if was_active_super and not still_active_super and other_active_supers == 0:
        raise UserRuleError("There must always be at least one active Super Admin")


def check_create(*, actor_is_super: bool, new_roles: set[str]) -> None:
    if SUPER in new_roles and not actor_is_super:
        raise UserRuleError("Only a Super Admin can create a Super Admin")
