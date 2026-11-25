"""Контекстный процессор ролей пользователя для навигации в шаблонах."""
from .models import UserProfile


def user_roles(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {
            'is_staff_or_operator': False,
            'is_actor': False,
        }
    profile = getattr(user, 'profile', None)
    role = profile.role if profile else None
    is_staff_or_op = bool(
        user.is_staff
        or user.is_superuser
        or role in (UserProfile.ROLE_OPERATOR, UserProfile.ROLE_ADMIN)
    )
    is_actor = bool(is_staff_or_op or role == UserProfile.ROLE_ACTOR)
    return {
        'is_staff_or_operator': is_staff_or_op,
        'is_actor': is_actor,
    }
