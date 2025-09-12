# reports/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("report/<int:pk>/", views.report_detail, name="report_detail"),
    path("manual_generate/", views.manual_generate, name="manual_generate"),
    path("report/<int:pk>/csv/", views.download_csv, name="download_csv"),
    path("report/<int:pk>/pdf/", views.download_pdf, name="download_pdf"),
    path("query/", views.query_report, name="query_report"),
    path("report/<int:report_id>/ask/", views.ask_question, name="ask_question"),
    
]