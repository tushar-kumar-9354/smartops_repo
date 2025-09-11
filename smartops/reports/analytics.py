# reports/analytics.py
import numpy as np

def extract_kpis(df):
    kpis = {}
    # Example KPIs (adjust to your dataset)
    if "revenue" in df.columns:
        kpis["revenue_total"] = float(df["revenue"].sum())
        kpis["revenue_mean"] = float(df["revenue"].mean())
    if "status" in df.columns:
        totals = df["status"].value_counts().to_dict()
        kpis["total_tasks"] = int(df.shape[0])
        kpis["done"] = int(totals.get("Done", totals.get("done", 0)))
    if "blocked" in df.columns:
        kpis["blocked_count"] = int(df["blocked"].sum())
    return kpis

def detect_anomalies(df, column, threshold=3.0):
    """
    Simple z-score anomaly detection on a numeric column.
    Returns indices (or rows) that are anomalies.
    """
    if column not in df.columns or not np.issubdtype(df[column].dtype, np.number):
        return []
    
    # Handle empty or single-value columns
    if len(df[column]) <= 1:
        return []
        
    col = df[column].fillna(0).astype(float)
    
    # Check if all values are the same (no variance)
    if col.std(ddof=0) == 0:
        return []
        
    zscores = (col - col.mean()) / (col.std(ddof=0) + 1e-9)
    anomalies = list(df.index[np.abs(zscores) > threshold])
    return anomalies