from celery import Celery
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smartops.settings")

app = Celery("smartops")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Load django-celery-beat scheduler
app.conf.beat_scheduler = "django_celery_beat.schedulers:DatabaseScheduler"
