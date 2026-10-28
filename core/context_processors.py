from core.roles import ADMIN, role_name


def roles(request):
    """Expose the signed-in user's role to every template (sidebar and Admin-only controls)."""
    user = getattr(request, "user", None)
    if user is None:
        return {}
    role = role_name(user)
    return {"user_role": role, "user_is_admin": role == ADMIN}
