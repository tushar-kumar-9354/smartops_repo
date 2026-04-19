
# reports/views.py
import pandas as pd
import matplotlib
from sklearn import logger
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
            print(prompt)
            try:
                response = ollama.chat(model="qwen:0.5b", messages=[{"role": "user", "content": prompt}])
                print(response)
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
# reports/views.py - UPDATE DASHBOARD VIEW
@login_required
def dashboard(request):
    from .models import Report
    reports = Report.objects.all().order_by("-created_at")[:10]
    total_reports = Report.objects.count()
    
    context = {
        "reports": reports,
        "total_reports": total_reports,  # This was missing!
    }
    return render(request, "reports/dashboard.html", context)


@login_required
def report_detail(request, pk):
    report = get_object_or_404(Report, pk=pk)
    logs = report.logs.all().order_by("-created_at")[:100]
    insights = report.insights.all()
    answer = None

    if request.method == "POST":
        query = request.POST.get("query")
        if query:
            contextual_query = f"Report titled '{report.title}': {query}"
            answer = answer_query(contextual_query)

    context = {
        "report": report,
        "logs": logs,
        "insights": insights,
        "answer": answer,
    }
    return render(request, "reports/report_detail.html", context)
# reports/views.py
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages

@login_required
@require_POST
def manual_generate(request):
    """
    Trigger manual report generation for the latest report
    """
    try:
        from .tasks import send_weekly_report
        from .models import Report
        
        # Get the latest report
        latest_report = Report.objects.order_by("-created_at").first()
        
        if not latest_report:
            return JsonResponse({
                "status": "error", 
                "message": "No reports available. Please upload a CSV first."
            }, status=400)
        
        if not latest_report.csv_file:
            return JsonResponse({
                "status": "error",
                "message": "Latest report has no CSV file attached."
            }, status=400)
        
        # Trigger task for the specific latest report
        send_weekly_report.delay(latest_report.id)
        
        return JsonResponse({
            "status": "queued",
            "message": f"Report generation started for '{latest_report.title}'",
            "report_id": latest_report.id,
            "report_title": latest_report.title
        })
        
    except Exception as e:
        logger.error(f"Error in manual_generate: {e}")
        return JsonResponse({
            "status": "error",
            "message": "Internal server error"
        }, status=500)
# reports/views.py - ADD THIS IMPORT
from django.contrib import messages
# reports/views.py - ENHANCE THE QUERY VIEW
@login_required
@require_POST
def query_report(request):
    """
    Handle report queries with better response handling
    """
    try:
        query = request.POST.get("q", "").strip()
        
        if not query:
            return JsonResponse({"error": "Please enter a question"}, status=400)
        
        from .qa import answer_query, get_report_count, get_recent_reports
        
        # Handle specific common queries directly for better accuracy
        query_lower = query.lower()
        
        if "how many reports" in query_lower:
            count = get_report_count()
            recent_reports = get_recent_reports(5)
            report_list = "\n".join([f"- {report.title} ({report.created_at.date()})" 
                                   for report in recent_reports])
            
            answer = f"There are {count} reports in total.\n\nMost recent reports:\n{report_list}"
            
        elif "list reports" in query_lower or "recent reports" in query_lower:
            recent_reports = get_recent_reports(10)
            if "alphabetical" in query_lower or "alphabet" in query_lower:
                recent_reports = sorted(recent_reports, key=lambda x: x.title.lower())
            
            report_list = "\n".join([f"- {report.title} ({report.created_at.date()})" 
                                   for report in recent_reports])
            
            answer = f"Recent reports:\n{report_list}"
            
        else:
            # Use the AI for other queries
            answer = answer_query(query)
        
        return JsonResponse({
            "answer": answer,
            "query": query
        })
        
    except Exception as e:
        logger.error(f"Error in query_report: {e}")
        return JsonResponse({"error": "Internal server error"}, status=500)
    
import os
import pandas as pd
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from .models import Report

# CSV Download
def download_csv(request, pk):
    report = get_object_or_404(Report, pk=pk)
    if not report.csv_file:
        return HttpResponse("No CSV file attached.", status=404)
    return FileResponse(open(report.csv_file.path, "rb"), as_attachment=True, filename=os.path.basename(report.csv_file.path))

# PDF Download
def download_pdf(request, pk):
    report = get_object_or_404(Report, pk=pk)

    pdf_path = f"media/report_{report.id}.pdf"
    doc = SimpleDocTemplate(pdf_path)
    styles = getSampleStyleSheet()
    story = []

    # Title
    story.append(Paragraph(f"SmartOps Report - {report.title}", styles["Heading1"]))
    story.append(Spacer(1, 12))

    # Summary
    story.append(Paragraph("Summary", styles["Heading2"]))
    story.append(Paragraph(report.summary or "No summary available", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Chart
    if report.chart_path and os.path.exists(report.chart_path):
        story.append(Paragraph("Chart", styles["Heading2"]))
        from reportlab.platypus import Image
        story.append(Image(report.chart_path, width=400, height=250))
        story.append(Spacer(1, 12))

    doc.build(story)

    return FileResponse(open(pdf_path, "rb"), as_attachment=True, filename=os.path.basename(pdf_path))
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .qa import answer_query

@require_POST
@csrf_exempt
def ask_question(request, report_id):
    try:
        query = request.POST.get('query', '')
        if not query:
            return JsonResponse({'error': 'Query is required'}, status=400)
        
        # Process the query using your QA engine
        answer = answer_query(query)
        
        return JsonResponse({'answer': answer})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)