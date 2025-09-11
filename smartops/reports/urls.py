# reports/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("report/<int:pk>/", views.report_detail, name="report_detail"),
    path("manual_generate/", views.manual_generate, name="manual_generate"),
    path("query/", views.query_report, name="query_report"),
]