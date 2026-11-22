import pytest

from app.services.user_rules import UserRuleError, check_create, check_update

BASE = dict(actor_id=1, actor_is_super=False, target_id=2, target_roles={"Admin"}, new_roles={"Admin"}, target_active=True, new_active=True, other_active_supers=1)


def go(**kw):
    check_update(**{**BASE, **kw})


def test_plain_change_ok():
    go(new_roles={"Order Manager"})


def test_admin_cannot_grant_super():
    with pytest.raises(UserRuleError):
        go(new_roles={"Admin", "Super Admin"})


def test_admin_cannot_modify_or_disable_super():
    with pytest.raises(UserRuleError):
        go(target_roles={"Super Admin"}, new_roles={"Super Admin"}, new_active=False)


def test_cannot_deactivate_self():
    with pytest.raises(UserRuleError):
        go(actor_id=2, actor_is_super=True, new_active=False)


def test_last_super_admin_protected():
    with pytest.raises(UserRuleError):
        go(actor_is_super=True, target_roles={"Super Admin"}, new_roles={"Admin"}, other_active_supers=0)
    go(actor_is_super=True, target_roles={"Super Admin"}, new_roles={"Admin"}, other_active_supers=1)


def test_create_super_needs_super():
    with pytest.raises(UserRuleError):
        check_create(actor_is_super=False, new_roles={"Super Admin"})
    check_create(actor_is_super=True, new_roles={"Super Admin"})
