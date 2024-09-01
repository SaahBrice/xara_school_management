from django.core.exceptions import PermissionDenied

class SecretaryRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'S':
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)