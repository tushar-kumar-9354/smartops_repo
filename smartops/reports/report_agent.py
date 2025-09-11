# reports/report_agent.py
import pandas as pd
import ollama
import hashlib
from django.core.cache import cache
from django.utils.timezone import now
from datetime import timedelta

class ReportAgent:
    def __init__(self, last_report=None):
        self.last_report = last_report
        
    def is_fresh_data(self, df: pd.DataFrame) -> bool:
        """
        Freshness detection based on report creation time, not just data content
        """
        # Method 1: Always consider data fresh if it's a new report (different from last)
        if not self.last_report:
            print("🟡 No previous report → treating as fresh data")
            return True
            
        # Method 2: Check if current report is different from last report
        # (This assumes you're passing the current report, not just the data)
        current_report = getattr(self, 'current_report', None)
        if current_report and current_report.id != self.last_report.id:
            print("🟡 Different report → treating as fresh data")
            return True
            
        # Method 3: Check if report was created recently (last 24 hours)
        if self.last_report.created_at > now() - timedelta(hours=24):
            print("🟡 Recent report → treating as fresh data")
            return True
            
        # Method 4: Manual override
        if cache.get('force_fresh_report'):
            print("🟡 Manual freshness override → treating as fresh data")
            cache.delete('force_fresh_report')
            return True

        # Method 5: Basic data comparison (fallback)
        try:
            last_df = pd.read_csv(self.last_report.csv_file.path)
            
            # Quick comparison - check if files are exactly the same
            current_hash = hashlib.md5(df.to_string().encode()).hexdigest()
            last_hash = hashlib.md5(last_df.to_string().encode()).hexdigest()
            
            if current_hash != last_hash:
                print("✅ Data content changed → fresh data")
                return True
                
        except Exception as e:
            print(f"🟡 Error comparing data: {e} → treating as fresh data")
            return True

        print("❌ Data appears to be the same as last report")
        return False

    # ... rest of the methods remain the same

    def generate_summary(self, df: pd.DataFrame) -> str:
        """Generate summary with Ollama"""
        print("📝 Generating summary with Ollama...")
        
        # Get basic stats
        stats = df.describe(include="all").to_string()
        
        # Get sample data for context
        sample_info = f"Dataset shape: {df.shape}, Columns: {list(df.columns)}"
        sample_data = df.head(3).to_string()
        
        prompt = f"""You are an AI reporting assistant analyzing dataset changes.

Dataset info:
{sample_info}

Sample data:
{sample_data}

Basic statistics:
{stats}

Provide a concise summary highlighting key insights, trends, or notable patterns in this data."""

        try:
            response = ollama.chat(
                model="qwen:0.5b",
                messages=[{"role": "user", "content": prompt}]
            )
            summary = response["message"]["content"]
            print("✅ Summary generated.")
            return summary
        except Exception as e:
            print(f"❌ Error generating summary: {e}")
            return f"Summary generation failed: {str(e)}"

    def decide_report(self, df: pd.DataFrame) -> dict:
        """Core agent decision logic"""
        print("🤖 Running agent decision logic...")

        fresh = self.is_fresh_data(df)

        if not fresh:
            print("⚠️ Latest data is not fresh.")
            return {
                "send": False,
                "reason": "Data is stale, no significant changes.",
            }

        summary = self.generate_summary(df)

        # Check for urgent conditions
        urgent = False
        urgent_reasons = []
        
        # Check for blocked items if column exists
        if "blocked" in df.columns and df["blocked"].sum() > 5:
            urgent_reasons.append(f"High blocked count: {df['blocked'].sum()}")
            urgent = True
            
        # Check for other potential issues
        numeric_cols = df.select_dtypes(include='number')
        if not numeric_cols.empty:
            for col in numeric_cols.columns:
                if col.lower() in ['error', 'failure', 'issue'] and df[col].sum() > 10:
                    urgent_reasons.append(f"High {col} count: {df[col].sum()}")
                    urgent = True

        return {
            "send": True,
            "urgent": urgent,
            "summary": summary,
            "reasons": urgent_reasons if urgent else []
        }