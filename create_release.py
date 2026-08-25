import os
import sys
import requests
import yaml
from requests.auth import HTTPBasicAuth


# --------------------------------------------------
# GitHub release information
# --------------------------------------------------

version = os.environ["VERSION"]
tag = os.environ["TAG"]
environment = os.environ["ENVIRONMENT"]
repository = os.environ["REPOSITORY"]
workflow = os.environ["WORKFLOW"]


# --------------------------------------------------
# Jira configuration
# --------------------------------------------------

jira_url = os.environ["JIRA_URL"].rstrip("/")
jira_email = os.environ["JIRA_EMAIL"]
jira_api_token = os.environ["JIRA_API_TOKEN"]


# --------------------------------------------------
# Read central Jira project configuration
# --------------------------------------------------

config_file = "jira-projects.yml"

if not os.path.exists(config_file):
    print(f"ERROR: {config_file} not found.")
    sys.exit(1)

with open(config_file, "r") as file:
    config = yaml.safe_load(file)


repositories = config.get("repositories", {})

if repository not in repositories:
    print(f"ERROR: Repository '{repository}' is not configured.")
    sys.exit(1)


jira_projects = repositories[repository].get("jira_projects", [])

if not jira_projects:
    print(f"ERROR: No Jira projects configured for '{repository}'.")
    sys.exit(1)


print("========================================")
print("Release Configuration")
print("========================================")
print(f"Repository: {repository}")
print(f"Version: {version}")
print(f"Tag: {tag}")
print(f"Environment: {environment}")
print(f"Workflow: {workflow}")
print(f"Jira Projects: {jira_projects}")
print("========================================")


# --------------------------------------------------
# Jira Release description
# --------------------------------------------------

description = f"{version}_{tag}_{environment}_{repository}_{workflow}"

print(f"Release description: {description}")


# --------------------------------------------------
# Jira authentication
# --------------------------------------------------

auth = HTTPBasicAuth(
    jira_email,
    jira_api_token
)

headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}


# --------------------------------------------------
# Create Release in each configured Jira project
# --------------------------------------------------

for project_key in jira_projects:

    print("")
    print("========================================")
    print(f"Creating Release in Jira project: {project_key}")
    print("========================================")

    # Get Jira project
    project_url = f"{jira_url}/rest/api/3/project/{project_key}"

    project_response = requests.get(
        project_url,
        auth=auth,
        headers=headers,
        timeout=30
    )

    print(
        f"Project lookup status for {project_key}: "
        f"{project_response.status_code}"
    )

    if not project_response.ok:
        print(
            f"Failed to retrieve Jira project {project_key}."
        )
        print(project_response.text)
        sys.exit(1)

    project = project_response.json()

    project_id = project["id"]

    print(f"Jira project: {project.get('name')}")
    print(f"Jira project key: {project.get('key')}")
    print(f"Jira project ID: {project_id}")


    # --------------------------------------------------
    # Create Jira Release / Version
    # --------------------------------------------------

    payload = {
        "name": version,
        "description": description,
        "projectId": int(project_id),
        "released": False
    }

    version_url = f"{jira_url}/rest/api/3/version"

    response = requests.post(
        version_url,
        json=payload,
        auth=auth,
        headers=headers,
        timeout=30
    )

    print(
        f"Jira Release creation status for "
        f"{project_key}: {response.status_code}"
    )

    if response.ok:

        release = response.json()

        print("Release created successfully!")
        print(f"Project: {project_key}")
        print(f"Release name: {release.get('name')}")
        print(f"Release ID: {release.get('id')}")
        print(f"Description: {release.get('description')}")

    else:

        print(
            f"Failed to create Release in "
            f"project {project_key}."
        )

        print(response.text)
        sys.exit(1)


print("")
print("========================================")
print("All Jira Releases created successfully!")
print("========================================")
