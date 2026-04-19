# SmartOps - Intelligent Report Analysis & Automation System

---

## About Me

### What is SmartOps?

SmartOps is an **intelligent report automation and analysis system** built with Django. It automatically processes, analyzes, and sends reports via email while providing an AI-powered Q&A interface to query your report data in plain English.

### Why Was It Created?

Organizations often struggle with:
- **Manual report processing** - spending hours analyzing CSV data
- **Scattered data sources** - data coming from CSV files, Google Sheets, and Jira
- **Time-consuming insights** - missing important trends without automated analysis
- **Inefficient communication** - reports sent to stakeholders without smart summaries

SmartOps was created to **automate all of this** - from data ingestion to intelligent analysis and delivery.

### How We Achieve This

1. **Data Ingestion**: Users upload CSV files or connect Google Sheets/Jira
2. **Automated Analysis**: AI (Ollama with Qwen model) generates summaries and detects anomalies
3. **Scheduled Delivery**: Celery beats run every 3 minutes to check for new reports
4. **Smart Q&A**: Users ask questions in plain English; RAG-powered AI understands and answers
5. **Email Delivery**: Reports with charts and insights are automatically emailed

### Impact

- **Saves hours** of manual report analysis
- **Real-time insights** via AI-powered Q&A
- **Automated scheduling** ensures no report is missed
- **Multiple data sources** supported in one place
- **PDF/CSV exports** for offline sharing

---

## Project Structure

```
smartops/
├── smartops/               # Django project settings
│   ├── settings.py         # All configuration
│   ├── urls.py              # URL routing
│   └── celery.py            # Celery configuration
├── reports/                # Main application
│   ├── models.py            # Database models
│   ├── views.py             # Web views
│   ├── tasks.py             # Celery background tasks
│   ├── report_agent.py      # AI decision-making agent
│   ├── analytics.py         # KPI extraction & anomaly detection
│   ├── qa.py               # RAG-powered Q&A engine
│   ├── utils.py             # Data fetching utilities
│   └── gdrive.py            # Google Drive upload
└── templates/              # HTML templates
```

---

## Features & How We Built Them

### 1. Report Upload & Management
**What it does**: Users upload CSV files or connect Google Sheets/Jira as data sources.

**How we built it**:
- **Tool**: Django Forms (`forms.py`)
- **File**: `views.py` - `upload_csv()` function
- **Data Sources**:
  - CSV: Direct file upload using `pandas.read_csv()`
  - Google Sheets: `gspread` library with service account credentials
  - Jira: `jira` library with basic authentication

**Where we use it**:
- Upload page at `/reports/upload/`
- Form field accepts `.csv` files, sheet URLs, or Jira credentials

---

### 2. Automated Report Processing
**What it does**: When a report is uploaded, the system automatically:
- Generates statistical summaries
- Creates visualization charts
- Extracts KPIs and detects anomalies
- Saves everything to the database

**How we built it**:
- **Tool**: `matplotlib` for charts, `pandas` for data analysis
- **File**: `views.py` - lines 57-77 for chart generation
- **Analytics**: `analytics.py` - `extract_kpis()` and `detect_anomalies()`

**Where we use it**:
- After CSV upload, charts appear on the report detail page
- KPI cards show total tasks, revenue, blocked counts, etc.

---

### 3. Scheduled Report Emails (Celery Beat)
**What it does**: Every 3 minutes, the system checks for new/updated reports and emails them to stakeholders.

**How we built it**:
- **Tool**: Celery + Redis + django_celery_beat
- **File**: `settings.py` (lines 138-147) - beat schedule configuration
- **File**: `tasks.py` - `send_weekly_report()` shared task

**Schedule**:
```python
CELERY_BEAT_SCHEDULE = {
    "send_weekly_report": {
        "task": "reports.tasks.send_weekly_report",
        "schedule": crontab(minute="*/3"),  # Every 3 minutes
    }
}
```

**Where we use it**:
- Runs automatically in background
- Email sent to `tusharsilotia1@gmail.com`
- Attachments include auto-generated charts

---

### 4. AI Report Agent (Decision Making)
**What it does**: Decides whether a report is "fresh" (different from last time) and worth sending. Prevents duplicate emails for unchanged data.

**How we built it**:
- **Tool**: Ollama with Qwen 0.5B model
- **File**: `report_agent.py` - `ReportAgent` class
- **Logic**:
  - Checks if data is different from previous report (hash comparison)
  - Checks report age (within 24 hours = fresh)
  - Checks for urgent conditions (high blocked count, errors)

**Where we use it**:
- Called in `tasks.py` line 86: `decision = agent.decide_report(df)`
- If `send: False`, report is skipped to avoid duplicate emails

---

### 5. AI-Powered Q&A Engine (RAG)
**What it does**: Users ask questions like "How many reports do I have?" or "What was the revenue trend?" and get answers from the report data.

**How we built it**:
- **Tool**: LangChain + FAISS vector store + Ollama (Qwen model)
- **File**: `qa.py` - `ReportQAEngine` class
- **Process**:
  1. Reports are converted to text documents
  2. Documents are embedded using `sentence-transformers/all-MiniLM-L6-v2`
  3. Embedded vectors stored in FAISS index
  4. User query retrieves relevant documents ( MMR search)
  5. LLM generates answer from retrieved context

**Key Methods**:
- `build_retriever()` - builds FAISS index from all reports
- `_classify_query_type()` - understands query intent
- `answer_query()` - generates AI response

**Where we use it**:
- Report detail page has Q&A form
- Dashboard has query endpoint at `/reports/query/`

---

### 6. Google Drive Upload
**What it does**: Saves generated PDF reports to Google Drive.

**How we built it**:
- **Tool**: Google Drive API v3 with service account
- **File**: `gdrive.py` - `upload_to_drive()` function

**Where we use it**:
- After email is sent, PDF can optionally be uploaded to Drive

---

### 7. KPI Extraction & Anomaly Detection
**What it does**: Automatically extracts key metrics and flags unusual data points.

**How we built it**:
- **Tool**: NumPy for statistics, Z-score anomaly detection
- **File**: `analytics.py`

**KPIs Extracted**:
- Revenue totals and averages (if `revenue` column exists)
- Task counts by status (if `status` column exists)
- Blocked item counts (if `blocked` column exists)

**Anomaly Detection**:
- Z-score method: values beyond 3 standard deviations flagged
- Applied to numeric columns like `revenue`

**Where we use it**:
- After report processing, insights saved to `ReportInsight` model
- Visible on report detail page

---

### 8. Logging System
**What it does**: Tracks all report processing events for debugging.

**How we built it**:
- **Tool**: Python logging + Django logging_utils
- **File**: `logging_utils.py`
- **Model**: `ReportLog` - stores level, message, timestamp

**Where we use it**:
- Task execution logs appear in Django admin
- Errors are logged with full tracebacks

---

## Technologies & Skills Used

### Backend Framework
| Skill | Used In | Purpose |
|-------|---------|---------|
| **Django 5.2** | Project setup | Web framework |
| **Django Forms** | Upload handling | Form validation |
| **Django ORM** | Models | Database operations |
| **Django Auth** | Login system | User authentication |

### Database
| Skill | Used In | Purpose |
|-------|---------|---------|
| **PostgreSQL** | settings.py | Primary database |
| **JSONField** | Report.data | Raw data storage |

### Background Tasks
| Skill | Used In | Purpose |
|-------|---------|---------|
| **Celery** | tasks.py | Async task execution |
| **Redis** | settings.py | Message broker |
| **django_celery_beat** | settings.py | Scheduled tasks |

### Data Processing
| Skill | Used In | Purpose |
|-------|---------|---------|
| **Pandas** | views.py, tasks.py, analytics.py | CSV/data processing |
| **NumPy** | analytics.py | Statistical calculations |

### Visualization
| Skill | Used In | Purpose |
|-------|---------|---------|
| **Matplotlib** | views.py, tasks.py | Chart generation |

### AI & NLP
| Skill | Used In | Purpose |
|-------|---------|---------|
| **Ollama (Qwen 0.5B)** | views.py, report_agent.py, qa.py | AI summaries & Q&A |
| **LangChain** | qa.py | RAG framework |
| **FAISS** | qa.py | Vector similarity search |
| **HuggingFace Embeddings** | qa.py | Document embedding |

### External Integrations
| Skill | Used In | Purpose |
|-------|---------|---------|
| **gspread** | utils.py | Google Sheets access |
| **Jira Python library** | utils.py | Jira issue fetching |
| **Google Drive API** | gdrive.py | File uploads |
| **ReportLab** | views.py | PDF generation |

### Email
| Skill | Used In | Purpose |
|-------|---------|---------|
| **Django SMTP** | tasks.py | Email delivery |

---

## Database Models

### Report
Main model storing report metadata and data.
```python
title              # Report name
created_at         # Auto timestamp
summary            # AI-generated summary
chart_path         # Path to chart image
csv_file           # Uploaded CSV file
source_type        # csv, sheets, or jira
source_value       # URL or project name
created_by         # ForeignKey to User
data               # JSON field for raw data
updated_at         # Auto timestamp on update
```

### ReportLog
Tracks processing events.
```python
level      # INFO, WARNING, ERROR
message    # Log message
created_at # Timestamp
report     # ForeignKey to Report
```

### ReportInsight
Stores extracted KPIs.
```python
key        # e.g., "revenue_total"
value      # Numeric value
text       # Description
report     # ForeignKey to Report
```

---

## API Endpoints

| URL | View | Purpose |
|-----|------|---------|
| `/reports/dashboard/` | `dashboard` | Main dashboard |
| `/reports/upload/` | `upload_csv` | Upload CSV/sheets/jira |
| `/reports/<pk>/` | `report_detail` | View report details |
| `/reports/<pk>/download_csv/` | `download_csv` | Export CSV |
| `/reports/<pk>/download_pdf/` | `download_pdf` | Export PDF |
| `/reports/query/` | `query_report` | AI Q&A endpoint |
| `/reports/manual_generate/` | `manual_generate` | Trigger report generation |
| `/accounts/login/` | Django auth | User login |

---

## Configuration

### Environment Variables (in settings.py)
```python
SECRET_KEY              # Django secret key
DEBUG                   # True for development
DATABASE_URL            # PostgreSQL connection
CELERY_BROKER_URL       # Redis URL (localhost:6379)
EMAIL_HOST_USER         # Gmail for sending emails
EMAIL_HOST_PASSWORD     # App-specific password
GOOGLE_CREDENTIALS_PATH # Path to service account JSON
```

### Celery Beat Schedule
- **Interval**: Every 3 minutes
- **Task**: `reports.tasks.send_weekly_report`
- **Broker**: Redis

---

## Quick Commands

> **Start all services in separate terminals for the full system to work**

### 1. Redis (Required for Celery)
```bash
# Start Redis server
redis-server
```
- Runs on `localhost:6379` by default
- Must be running before Celery worker starts

---

### 2. Ollama (Required for AI Features)
```bash
# Pull the AI model (one-time setup)
ollama pull qwen:0.5b

# Start Ollama server (keep running)
ollama serve
```
- Runs on `localhost:11434` by default
- Make sure the model is pulled before using AI features

---

### 3. Celery Worker (Processes Background Tasks)
```bash
# Navigate to project directory
cd C:\Users\hp\smart_ops\smartops

# Start Celery worker
celery -A smartops worker -l info
```
- Processes tasks like sending emails, generating reports
- Keep running while the server is active

---

### 4. Celery Beat (Schedules Automated Tasks)
```bash
# Navigate to project directory
cd C:\Users\hp\smart_ops\smartops

# Start Celery Beat scheduler
celery -A smartops beat -l info
```
- Runs every 3 minutes to check for new reports
- Automatically sends emails for fresh reports

---

### 5. Django Development Server
```bash
# Navigate to project directory
cd C:\Users\hp\smart_ops\smartops

# Run migrations first (if new setup)
python manage.py migrate

# Start the web server
python manage.py runserver
```
- Runs on `http://127.0.0.1:8000/` by default
- Access the app at `http://127.0.0.1:8000/reports/dashboard/`

---

## Quick Start Summary (Copy-Paste)

Open **4 separate terminals** and run these commands:

| Terminal | Command |
|----------|---------|
| **1. Redis** | `redis-server` |
| **2. Ollama** | `ollama serve` |
| **3. Celery** | `cd C:\Users\hp\smart_ops\smartops && celery -A smartops worker -l info` |
| **4. Celery Beat** | `cd C:\Users\hp\smart_ops\smartops && celery -A smartops beat -l info` |
| **5. Django** | `cd C:\Users\hp\smart_ops\smartops && python manage.py runserver` |

---

## One-Time Setup Commands

```bash
# Install all dependencies
pip install django celery redis pandas matplotlib numpy
pip install gspread jira reportlab langchain-huggingface
pip install faiss-cpu langchain-community psycopg2-binary

# Pull Ollama model (once)
ollama pull qwen:0.5b

# Run database migrations (once)
cd C:\Users\hp\smart_ops\smartops
python manage.py migrate

# Create superuser (for admin access)
python manage.py createsuperuser
```

---

## Check Running Services

```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG

# Check if Ollama is running
curl http://localhost:11434/api/tags
# Should return JSON with model info
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Celery worker won't start | Make sure Redis is running first |
| AI features not working | Check if `ollama serve` is running and model is pulled |
| No emails being sent | Check email credentials in settings.py |
| Database errors | Run `python manage.py migrate` |

---

## Setup & Installation

```bash
# Install dependencies
pip install django celery redis pandas matplotlib numpy
pip install gspread jira reportlab langchain-huggingface
pip install faiss-cpu langchain-community

# Start Redis
redis-server

# Run migrations
python manage.py migrate

# Start Celery worker
celery -A smartops worker -l info

# Start Celery beat
celery -A smartops beat -l info

# Run Django server
python manage.py runserver
```

---

## How a Typical Flow Works

1. **User uploads CSV** → `upload_csv()` saves report
2. **Charts generated** via matplotlib
3. **AI summary** created via Ollama
4. **Celery task triggered** for email processing
5. **Agent checks** if data is fresh vs previous
6. **If fresh**: Email sent with chart + summary
7. **KPIs extracted** and saved as ReportInsight
8. **Anomalies detected** and logged
9. **User can ask questions** via Q&A interface
10. **RAG retrieves** relevant context from reports
11. **Ollama generates** natural language answer

---

## Email Configuration

Emails are sent via Gmail SMTP:
- **Host**: smtp.gmail.com
- **Port**: 587
- **TLS**: Enabled
- **Recipient**: tusharsilotia1@gmail.com (configurable in tasks.py)

For Gmail, use an **App Password** (16 characters) instead of your actual password.

---

## Files Summary

| File | Purpose |
|------|---------|
| `models.py` | Database schema |
| `views.py` | Web request handling |
| `tasks.py` | Background job processing |
| `forms.py` | Form validation |
| `report_agent.py` | AI decision logic |
| `analytics.py` | KPI extraction |
| `qa.py` | RAG-powered Q&A engine |
| `utils.py` | Google Sheets & Jira integration |
| `gdrive.py` | Google Drive upload |
| `urls.py` | URL routing |
| `admin.py` | Django admin configuration |
| `logging_utils.py` | Custom logging setup |
| `decorators.py` | Custom decorators |
| `ollama_wrapper.py` | Ollama API wrapper |

---

## Security Notes

- **Credentials**: Google service account JSON stored in `credentials/credentials.json`
- **Database**: PostgreSQL with password authentication
- **CSRF**: Enabled on all POST forms
- **Authentication**: Login required for all report views
- **Email**: Uses app-specific password, not main password

---

## Future Enhancements

- Add more data source integrations (Excel, API endpoints)
- Support for scheduled report templates
- Real-time WebSocket-based Q&A
- Dashboard customization options
- Export to more formats (Excel, Google Sheets)