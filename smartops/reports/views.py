
# reports/views.py
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Add this line
import matplotlib.pyplot as plt
import os
import ollama
from django.shortcuts import render, redirect, get_object_or_404
from .forms import ReportForm
from .models import Report
from django.conf import settings
from .utils import fetch_google_sheet, fetch_jira_issues
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .qa import answer_query

# reports/views.py - SIMPLIFIED VERSION
@login_required
def upload_csv(request):
    if request.method == "POST":
        form = ReportForm(request.POST, request.FILES)
        sheet_url = request.POST.get("sheet_url")
        jira_server = request.POST.get("jira_server")
        jira_email = request.POST.get("jira_email")
        jira_token = request.POST.get("jira_token")
        jira_project = request.POST.get("jira_project")

        if form.is_valid():
            report = form.save(commit=False)
            report.created_by = request.user

            # 1. Google Sheets
            if sheet_url:
                df = fetch_google_sheet(sheet_url)
                report.source_type = "sheets"
                report.source_value = sheet_url

            # 2. Jira
            elif jira_server and jira_email and jira_token and jira_project:
                df = fetch_jira_issues(jira_server, jira_email, jira_token, jira_project)
                report.source_type = "jira"
                report.source_value = jira_project

            # 3. CSV fallback
            else:
                file = request.FILES['csv_file']
                df = pd.read_csv(file)
                report.source_type = "csv"

            # Stats
            stats = df.describe(include='all').to_string()

            # Chart - with error handling
            chart_path = os.path.join("media", f"chart_{report.title}.png")
            plt.figure(figsize=(6,4))
            
            try:
                # Check if we have numeric columns to plot
                numeric_cols = df.select_dtypes(include='number')
                if not numeric_cols.empty:
                    numeric_cols.hist()
                    plt.tight_layout()
                    plt.savefig(chart_path)
                    plt.close()
                    report.chart_path = chart_path
                else:
                    # No numeric columns, skip chart generation
                    report.chart_path = ""
                    plt.close()
            except Exception as e:
                # If chart generation fails, continue without chart
                report.chart_path = ""
                plt.close()
                print(f"Chart generation failed: {e}")

            # AI Summary
            prompt = f"Summarize the following dataset stats in plain English:\n{stats}"
            try:
                response = ollama.chat(model="qwen:0.5b", messages=[{"role": "user", "content": prompt}])
                report.summary = response['message']['content']
            except Exception as e:
                report.summary = f"Summary generation failed: {str(e)}"
            
            report.save()

            # Trigger the Celery task for this specific report
            from .tasks import send_weekly_report
            send_weekly_report.delay(report.id)

            return redirect("report_detail", pk=report.id)
    else:
        form = ReportForm()

    return render(request, "upload.html", {"form": form})
@login_required
def dashboard(request):
    reports = Report.objects.all()
    return render(request, "reports/dashboard.html", {"reports": reports})

@login_required
def report_detail(request, pk):
    report = get_object_or_404(Report, pk=pk)
    logs = report.logs.all().order_by("-created_at")[:100]
    insights = report.insights.all()
    return render(request, "reports/report_detail.html", {"report": report, "logs": logs, "insights": insights})

@login_required
@require_POST
def manual_generate(request):
    # This triggers the Celery task or agent run immediately
    from .tasks import send_weekly_report
    send_weekly_report.delay()   # immediate async trigger
    return JsonResponse({"status":"queued"})

@login_required
@require_POST
def query_report(request):
    q = request.POST.get("q")
    ans = answer_query(q)
    return JsonResponse({"answer": ans})