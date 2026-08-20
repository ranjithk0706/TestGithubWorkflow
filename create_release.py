import os
import sys
import requests
from requests.auth import HTTPBasicAuth

version = os.environ["VERSION"]
tag = os.environ["TAG"]
environment = os.environ["ENVIRONMENT"]
repository = os.environ["REPOSITORY"]
workflow = os.environ["WORKFLOW"]

jira_url = os.environ["JIRA_URL"].rstrip("/")
jira_email = os.environ["JIRA_EMAIL"]
jira_api_token = os.environ["JIRA_API_TOKEN"]
project_key = os.environ["JIRA_PROJECT_KEY"]

auth = HTTPBasicAuth(jira_email, jira_api_token)
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}

project_response = requests.get(
    f"{jira_url}/rest/api/3/project/{project_key}",
    auth=auth,
    headers=headers,
    timeout=30,
)

if not project_response.ok:
    print(f"Failed to find Jira project {project_key}.")
    print(f"HTTP status: {project_response.status_code}")
    print(project_response.text)
    sys.exit(1)

project_id = project_response.json()["id"]

description = f"""GitHub Release

Version: {version}
Tag: {tag}
Environment: {environment}
Repository: {repository}
Workflow: {workflow}
"""

payload = {
    "name": version,
    "description": description,
    "project": int(project_id),
    "released": False,
}

response = requests.post(
    f"{jira_url}/rest/api/3/version",
    json=payload,
    auth=auth,
    headers=headers,
    timeout=30,
)

print(f"Jira response status: {response.status_code}")

if response.ok:
    data = response.json()
    print(f"Jira Release created successfully: {data.get('name')}")
    print(f"Jira Release ID: {data.get('id')}")
else:
    print("Failed to create Jira Release.")
    print(response.text)
    sys.exit(1)
