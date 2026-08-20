import os
import sys
import requests
from requests.auth import HTTPBasicAuth

# Values supplied by GitHub Actions
version = os.environ["VERSION"]
tag = os.environ["TAG"]
environment = os.environ["ENVIRONMENT"]
repository = os.environ["REPOSITORY"]
workflow = os.environ["WORKFLOW"]

# Jira configuration supplied by GitHub Actions
jira_url = os.environ["JIRA_URL"].rstrip("/")
jira_email = os.environ["JIRA_EMAIL"]
jira_api_token = os.environ["JIRA_API_TOKEN"]
project_key = os.environ["JIRA_PROJECT_KEY"]

auth = HTTPBasicAuth(jira_email, jira_api_token)

headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# Jira Release description
description = f"""Version: {version}
Tag: {tag}
Environment: {environment}
Repository: {repository}
Workflow: {workflow}
"""

print("Creating Jira Release...")
print(f"Release name: {version}")
print("Release description:")
print(description)

# Get Jira project information
project_url = f"{jira_url}/rest/api/3/project/{project_key}"

project_response = requests.get(
    project_url,
    auth=auth,
    headers=headers,
    timeout=30,
)

print(f"Project lookup status: {project_response.status_code}")

if not project_response.ok:
    print("Failed to retrieve Jira project.")
    print(project_response.text)
    sys.exit(1)

project = project_response.json()
project_id = project["id"]

print(f"Jira project: {project.get('name')}")
print(f"Jira project key: {project.get('key')}")
print(f"Jira project ID: {project_id}")

# Create Jira Release/Version
payload = {
    "name": version,
    "description": description,
    "project": int(project_id),
    "released": False,
}

version_url = f"{jira_url}/rest/api/3/version"

response = requests.post(
    version_url,
    json=payload,
    auth=auth,
    headers=headers,
    timeout=30,
)

print(f"Jira Release creation status: {response.status_code}")

if response.ok:
    release = response.json()

    print("Jira Release created successfully!")
    print(f"Release name: {release.get('name')}")
    print(f"Release ID: {release.get('id')}")
else:
    print("Failed to create Jira Release.")
    print(response.text)
    sys.exit(1)
