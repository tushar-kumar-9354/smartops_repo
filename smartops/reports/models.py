# reports/models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Report(models.Model):
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    summary = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    chart_path = models.CharField(max_length=600, blank=True)
    csv_file = models.FileField(upload_to="uploads/", null=True, blank=True)
    source_type = models.CharField(max_length=50, choices=[("csv","CSV"),("sheets","Sheets"),("jira","Jira")], default="csv")
    source_value = models.CharField(max_length=1000, blank=True)  # e.g. sheet URL or jira project
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    data=models.JSONField(null=True, blank=True)  # Store raw data as JSON if needed

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.created_at:%Y-%m-%d})"


class ReportLog(models.Model):
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="logs", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    level = models.CharField(max_length=20, default="INFO")
    message = models.TextField()

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.level} - {self.message[:80]}"


class ReportInsight(models.Model):
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="insights")
    key = models.CharField(max_length=200)   # e.g., "total_tasks", "blocked_pct"
    value = models.FloatField(null=True, blank=True)
    text = models.TextField(blank=True)      # free-form explanation
