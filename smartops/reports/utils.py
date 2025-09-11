import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

def fetch_google_sheet(sheet_url):
    # Define scope
    scope = ["https://www.googleapis.com/auth/spreadsheets.readonly",
             "https://www.googleapis.com/auth/drive.readonly"]

    creds = Credentials.from_service_account_file(
        "smartops/credentials/credentials.json", scopes=scope
    )

    client = gspread.authorize(creds)

    # Open sheet by URL
    sheet = client.open_by_url(sheet_url)
    worksheet = sheet.get_worksheet(0)  # First sheet
    data = worksheet.get_all_records()

    # Convert to Pandas DataFrame
    df = pd.DataFrame(data)
    return df


from jira import JIRA
import pandas as pd

def fetch_jira_issues(server_url, email, api_token, project_key, jql=""):
    """
    Connects to Jira and fetches issues for a given project.
    server_url: e.g. "https://yourcompany.atlassian.net"
    email: your Jira email
    api_token: your Jira API token (generate in Atlassian account)
    project_key: e.g. "SMARTOPS"
    jql: optional filter (default empty -> all project issues)
    """

    options = {"server": server_url}
    jira = JIRA(options, basic_auth=(email, api_token))

    # If no custom JQL given, fetch all project issues
    if not jql:
        jql = f"project={project_key}"

    issues = jira.search_issues(jql, maxResults=50)  # limit for demo

    data = []
    for issue in issues:
        data.append({
            "key": issue.key,
            "summary": issue.fields.summary,
            "status": issue.fields.status.name,
            "assignee": getattr(issue.fields.assignee, "displayName", "Unassigned"),
            "created": issue.fields.created,
        })

    return pd.DataFrame(data)
