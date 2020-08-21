cat <<EOF | poetry run python3 manage.py shell
from django.contrib.auth import get_user_model

User = get_user_model()  # get the currently active user model,

User.objects.filter(is_superuser=True).exists() or \
    User.objects.create_superuser('admin', 'root@localhost', 'admin') and print("Created admin user")
EOF
