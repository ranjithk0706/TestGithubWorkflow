import os
import sys
import requests


# --------------------------------------------------
# Configuration
# --------------------------------------------------

JIRA_URL = os.environ["JIRA_URL"].rstrip("/")
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = os.environ["JIRA_API_TOKEN"]
JIRA_PROJECT_KEY = os.environ["JIRA_PROJECT_KEY"]

VERSION = os.environ["VERSION"]
TAG = os.environ["TAG"]
ENVIRONMENT = os.environ["ENVIRONMENT"]

AUTH = (JIRA_EMAIL, JIRA_API_TOKEN)

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}


# --------------------------------------------------
# Helper
# --------------------------------------------------

def jira_request(method, url, **kwargs):
    response = requests.request(
        method,
        url,
        auth=AUTH,
        headers=HEADERS,
        timeout=30,
        **kwargs,
    )

    print(f"Jira response status: {response.status_code}")

    if not response.ok:
        print(response.text)
        response.raise_for_status()

    return response


# --------------------------------------------------
# 1. Find Jira project
# --------------------------------------------------

print(f"Looking up Jira project: {JIRA_PROJECT_KEY}")

project_url = (
    f"{JIRA_URL}/rest/api/3/project/{JIRA_PROJECT_KEY}"
)

project_response = jira_request(
    "GET",
    project_url,
)

project = project_response.json()

project_id = project["id"]
project_key = project["key"]
project_name = project["name"]

print(f"Jira project: {project_name}")
print(f"Jira project key: {project_key}")
print(f"Jira project ID: {project_id}")


# --------------------------------------------------
# 2. Check whether version already exists
# --------------------------------------------------

print(f"Checking Jira version: {VERSION}")

versions_url = (
    f"{JIRA_URL}/rest/api/3/project/"
    f"{project_id}/versions"
)

versions_response = jira_request(
    "GET",
    versions_url,
)

versions = versions_response.json()

existing_version = next(
    (
        version
        for version in versions
        if version["name"] == VERSION
    ),
    None,
)


# --------------------------------------------------
# 3. Create Jira version if necessary
# --------------------------------------------------

if existing_version:
    jira_version_id = existing_version["id"]

    print(
        f"Jira version already exists: "
        f"{VERSION} (ID: {jira_version_id})"
    )

else:
    print(f"Creating Jira version: {VERSION}")

    create_version_url = (
        f"{JIRA_URL}/rest/api/3/version"
    )

    payload = {
        "name": VERSION,
        "projectId": int(project_id),
        "description": (
            f"GitHub release {TAG}"
        ),
        "released": False,
        "archived": False,
    }

    create_response = jira_request(
        "POST",
        create_version_url,
        json=payload,
    )

    created_version = create_response.json()

    jira_version_id = created_version["id"]

    print(
        f"Jira version created successfully: "
        f"{VERSION} (ID: {jira_version_id})"
    )


# --------------------------------------------------
# 4. Summary
# --------------------------------------------------

print("")
print("========================================")
print("Release information")
print("========================================")
print(f"Jira project : {project_key}")
print(f"Jira version : {VERSION}")
print(f"Git tag      : {TAG}")
print(f"Environment  : {ENVIRONMENT}")
print(f"Repository   : {os.environ['REPOSITORY']}")
print(f"Workflow     : {os.environ['WORKFLOW']}")
print("========================================")
print("")
print("Jira release step completed successfully.")
