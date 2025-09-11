# reports/decorators.py (create this new file)
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import get_user_model

User = get_user_model()

def is_manager(user):
    return user.groups.filter(name="managers").exists()

manager_required = user_passes_test(is_manager)