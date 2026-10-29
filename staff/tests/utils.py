from django.contrib.auth.models import User


def account_state():
    """
    Every account's activation, superuser flag, roles, direct permissions, password hash and
    name fields, so a test can show a refusal changed nothing.
    """
    return {
        user.pk: (
            user.is_active,
            user.is_superuser,
            sorted(user.groups.values_list("name", flat=True)),
            sorted(user.user_permissions.values_list("codename", flat=True)),
            user.password,
            user.first_name,
            user.last_name,
            user.email,
        )
        for user in User.objects.order_by("pk")
    }
