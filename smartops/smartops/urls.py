# smartops/urls.py
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from reports import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("upload/", views.upload_csv, name="upload_csv"),
    path("report/<int:pk>/", views.report_detail, name="report_detail"),
    path("reports/", include("reports.urls")),
    # Redirect root to dashboard
    path("", lambda request: redirect('dashboard'), name='root_redirect'),
]

from django.conf import settings
from django.conf.urls.static import static

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)