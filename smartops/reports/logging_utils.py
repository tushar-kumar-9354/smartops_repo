# reports/logging_utils.py
from .models import ReportLog

def log(report=None, level="INFO", message=""):
    # console
    print(f"[{level}] {message}")
    # db
    try:
        ReportLog.objects.create(report=report, level=level, message=message)
    except Exception as e:
        # avoid breaking agent on logging errors
        print("[LOG ERROR]", e)
