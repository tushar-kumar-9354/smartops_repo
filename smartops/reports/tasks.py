# reports/tasks.py
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from celery import shared_task
from django.core.mail import EmailMessage
from django.core.cache import cache
from .models import Report, ReportInsight, ReportLog
from .report_agent import ReportAgent
import pandas as pd
import os
from .analytics import extract_kpis, detect_anomalies
import logging
import hashlib

logger = logging.getLogger(__name__)

def log(report, level, message):
    ReportLog.objects.create(report=report, level=level, message=message)

def get_file_hash(file_path):
    """Generate MD5 hash of file content"""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"❌ Error generating file hash: {e}")
        return f"error_{os.path.basename(file_path)}"

@shared_task(bind=True, max_retries=3)
def send_weekly_report(self, report_id=None):
    try:
        logger.info(f"🚀 Starting weekly report task. Report ID: {report_id}")

        # If no report_id provided, get the most recent one
        if report_id:
            current_report = Report.objects.get(id=report_id)
            logger.info(f"Processing specific report: {current_report.title}")
        else:
            current_report = Report.objects.order_by("-created_at").first()
            if current_report:
                logger.info(f"Processing latest report: {current_report.title}")
            else:
                logger.warning("No reports available")
                return "No reports available."

        if not current_report:
            logger.warning("❌ No reports available.")
            return "No reports available."

        if not current_report.csv_file:
            logger.warning("❌ No CSV file attached to the report.")
            return "No data source found."

        # ✅ CHECK IF THIS CSV FILE HAS ALREADY BEEN PROCESSED
        file_hash = get_file_hash(current_report.csv_file.path)
        lock_id = f"csv_processed_{file_hash}"
        
        if cache.get(lock_id):
            logger.warning(f"⚠️ CSV file already processed previously. Skipping report {current_report.id}.")
            return "CSV file already processed. Skipped."
        
        # Get the previous report (excluding current one)
        previous_report = Report.objects.exclude(id=current_report.id).order_by("-created_at").first()
        if previous_report:
            logger.info(f"Previous report: {previous_report.title}")
        else:
            logger.info("No previous report found")

        # Load current report data
        logger.info(f"📂 Loading data from: {current_report.csv_file.path}")
        try:
            df = pd.read_csv(current_report.csv_file.path)
            logger.info(f"✅ Loaded DataFrame with shape: {df.shape}")
        except Exception as e:
            logger.error(f"❌ Error reading CSV: {e}")
            return f"Error reading CSV: {e}"

        # Run through agent with BOTH current and previous reports
        agent = ReportAgent(last_report=previous_report)
        agent.current_report = current_report
        
        decision = agent.decide_report(df)
        logger.info(f"Agent decision: {decision}")

        if not decision["send"]:
            logger.warning(f"⏸ Report skipped: {decision['reason']}")
            return f"Report skipped: {decision['reason']}"

        # Generate chart
        report_title = current_report.title
        chart_path = os.path.join("media", f"auto_chart_{report_title.replace(' ', '_')}.png")

        logger.info("📊 Generating chart...")
        try:
            plt.figure(figsize=(6, 4))
            numeric_cols = df.select_dtypes(include="number")
            if not numeric_cols.empty:
                numeric_cols.hist()
                plt.tight_layout()
                plt.savefig(chart_path)
                plt.close()
                logger.info(f"✅ Chart saved at {chart_path}")
            else:
                logger.warning("⚠️ No numeric columns for chart")
                chart_path = None
        except Exception as e:
            logger.error(f"❌ Error generating chart: {e}")
            chart_path = None

        # Prepare email
        subject = f"SmartOps Report - {report_title}"
        if decision.get("urgent"):
            subject = "⚠️ URGENT: " + subject

        logger.info(f"📧 Sending email: {subject}")
        try:
            email = EmailMessage(
                subject=subject,
                body=decision["summary"],
                to=["tusharsilotia1@gmail.com"],
            )
            if chart_path and os.path.exists(chart_path):
                email.attach_file(chart_path)
            email.send()
            logger.info("✅ Email sent successfully.")
            print("="*80)
        except Exception as e:
            logger.error(f"❌ Error sending email: {e}")
            return f"Error sending email: {e}"
        
        # Extract KPIs and insights
        try:
            kpis = extract_kpis(df)
            for k, v in kpis.items():
                ReportInsight.objects.create(report=current_report, key=k, value=v, text="")
            
            # Detect anomalies
            anoms = detect_anomalies(df, "revenue")
            if anoms:
                log(current_report, "WARN", f"Anomalies found in revenue rows: {anoms}")
        except Exception as e:
            logger.warning(f"⚠️ Error in analytics: {e}")

        # ✅ MARK THIS CSV FILE AS PROCESSED (PERMANENTLY)
        cache.set(lock_id, True, timeout=None)  # Never expires
        logger.info(f"✅ Permanently marked CSV file as processed: {file_hash}")

        success_message = f"Report for {report_title} sent and file marked as processed!"
        logger.info(success_message)
        return success_message

    except Exception as e:
        logger.error(f"❌ Unexpected error in send_weekly_report: {e}")
        # Retry the task in case of failure
        self.retry(exc=e, countdown=60)
        return f"Task failed: {e}"