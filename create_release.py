"""Create Jira releases for configured GitHub repositories."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import requests
import yaml
from requests import Response
from requests.auth import HTTPBasicAuth


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIG_FILE = Path("jira-projects.yml")
REQUEST_TIMEOUT = 30
CONFIG_REPOSITORIES_KEY = "repositories"

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def configure_logging() -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )


# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------


def get_required_environment_variable(name: str) -> str:
    """Get a required environment variable.

    Args:
        name: Environment variable name.

    Returns:
        Environment variable value.

    Raises:
        ValueError: If the variable is missing or empty.
    """
    value = os.getenv(name)

    if value is None or not value.strip():
        raise ValueError(
            f"Required environment variable '{name}' "
            "is missing or empty."
        )

    return value.strip()


def load_environment() -> dict[str, str]:
    """Load and validate required environment variables.

    Returns:
        Dictionary containing environment configuration.

    Raises:
        ValueError: If a required variable is missing.
    """
    variable_names = (
        "VERSION",
        "TAG",
        "ENVIRONMENT",
        "REPOSITORY",
        "WORKFLOW",
        "JIRA_URL",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
    )

    environment = {
        name: get_required_environment_variable(name)
        for name in variable_names
    }

    environment["JIRA_URL"] = environment["JIRA_URL"].rstrip("/")

    return environment


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def load_configuration(
    config_file: Path,
) -> dict[str, Any]:
    """Load the central Jira project configuration.

    Args:
        config_file: Configuration file path.

    Returns:
        Parsed YAML configuration.

    Raises:
        FileNotFoundError: If the configuration file is missing.
        ValueError: If the configuration structure is invalid.
        yaml.YAMLError: If YAML parsing fails.
    """
    if not config_file.is_file():
        raise FileNotFoundError(
            f"Configuration file '{config_file}' was not found."
        )

    try:
        with config_file.open(
            "r",
            encoding="utf-8",
        ) as file:
            config = yaml.safe_load(file)
    except yaml.YAMLError:
        LOGGER.exception(
            "Unable to parse configuration file '%s'.",
            config_file,
        )
        raise

    if not isinstance(config, dict):
        raise ValueError(
            f"Configuration file '{config_file}' "
            "must contain a YAML mapping."
        )

    repositories = config.get(
        CONFIG_REPOSITORIES_KEY
    )

    if not isinstance(repositories, dict):
        raise ValueError(
            f"'{CONFIG_REPOSITORIES_KEY}' must be a mapping "
            f"in '{config_file}'."
        )

    return config


def get_jira_projects(
    config: dict[str, Any],
    repository: str,
) -> list[str]:
    """Get Jira projects configured for a repository.

    Args:
        config: Central configuration.
        repository: GitHub repository.

    Returns:
        List of Jira project keys.

    Raises:
        ValueError: If repository configuration is invalid.
    """
    repositories = config.get(
        CONFIG_REPOSITORIES_KEY,
        {},
    )

    repository_config = repositories.get(repository)

    if repository_config is None:
        raise ValueError(
            f"Repository '{repository}' is not configured."
        )

    if not isinstance(repository_config, dict):
        raise ValueError(
            f"Configuration for repository '{repository}' "
            "must be a mapping."
        )

    jira_projects = repository_config.get(
        "jira_projects",
        [],
    )

    if not isinstance(jira_projects, list):
        raise ValueError(
            f"'jira_projects' for repository '{repository}' "
            "must be a list."
        )

    projects = [
        str(project).strip()
        for project in jira_projects
        if str(project).strip()
    ]

    if not projects:
        raise ValueError(
            f"No Jira projects configured for '{repository}'."
        )

    return projects


# ---------------------------------------------------------------------------
# Jira session
# ---------------------------------------------------------------------------


def create_jira_session(
    jira_email: str,
    jira_api_token: str,
) -> requests.Session:
    """Create an authenticated Jira HTTP session.

    Args:
        jira_email: Jira account email.
        jira_api_token: Jira API token.

    Returns:
        Configured requests session.
    """
    session = requests.Session()

    session.auth = HTTPBasicAuth(
        jira_email,
        jira_api_token,
    )

    session.headers.update(
        {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    )

    return session


# ---------------------------------------------------------------------------
# Jira API helpers
# ---------------------------------------------------------------------------


def log_api_error(
    response: Response,
    operation: str,
) -> None:
    """Log details for a failed Jira API request.

    Args:
        response: Jira response.
        operation: API operation description.
    """
    LOGGER.error(
        "%s failed with HTTP status %s.",
        operation,
        response.status_code,
    )

    response_text = response.text.strip()

    if response_text:
        LOGGER.error(
            "Jira API response: %s",
            response_text,
        )


def get_jira_project(
    session: requests.Session,
    jira_url: str,
    project_key: str,
) -> dict[str, Any]:
    """Retrieve a Jira project.

    Args:
        session: Authenticated Jira session.
        jira_url: Jira base URL.
        project_key: Jira project key.

    Returns:
        Jira project information.

    Raises:
        requests.RequestException: If the API request fails.
        ValueError: If the response is invalid.
    """
    project_url = (
        f"{jira_url}/rest/api/3/project/{project_key}"
    )

    try:
        response = session.get(
            project_url,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        LOGGER.exception(
            "Unable to retrieve Jira project '%s'.",
            project_key,
        )
        raise

    LOGGER.info(
        "Project lookup status for %s: %s",
        project_key,
        response.status_code,
    )

    if not response.ok:
        log_api_error(
            response,
            f"Jira project lookup for '{project_key}'",
        )
        response.raise_for_status()

    try:
        project = response.json()
    except ValueError as exc:
        raise ValueError(
            f"Invalid JSON returned for Jira project "
            f"'{project_key}'."
        ) from exc

    if not isinstance(project, dict):
        raise ValueError(
            f"Unexpected Jira project response for "
            f"'{project_key}'."
        )

    return project


def is_duplicate_version_response(
    response: Response,
) -> bool:
    """Determine whether a Jira response indicates a duplicate version.

    Args:
        response: Jira API response.

    Returns:
        True when the response indicates the version already exists.
    """
    if response.status_code != 400:
        return False

    response_text = response.text.lower()

    duplicate_indicators = (
        "already exists",
        "version already exists",
        "a version with this name already exists",
        "name already exists",
    )

    return any(
        indicator in response_text
        for indicator in duplicate_indicators
    )


def create_jira_version(
    session: requests.Session,
    jira_url: str,
    project_id: int,
    project_key: str,
    version: str,
    description: str,
) -> tuple[str, dict[str, Any] | None]:
    """Create a Jira release/version.

    Args:
        session: Authenticated Jira session.
        jira_url: Jira base URL.
        project_id: Jira project ID.
        project_key: Jira project key.
        version: Release version.
        description: Release description.

    Returns:
        Tuple containing the result status and release information.

    Raises:
        requests.RequestException: For non-duplicate API failures.
        ValueError: If the response is invalid.
    """
    version_url = f"{jira_url}/rest/api/3/version"

    payload = {
        "name": version,
        "description": description,
        "projectId": project_id,
        "released": False,
    }

    try:
        response = session.post(
            version_url,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        LOGGER.exception(
            "Unable to create Jira Release for project '%s'.",
            project_key,
        )
        raise

    LOGGER.info(
        "Jira Release creation status for %s: %s",
        project_key,
        response.status_code,
    )

    if response.ok:
        try:
            release = response.json()
        except ValueError as exc:
            raise ValueError(
                f"Invalid JSON returned while creating "
                f"Jira Release for '{project_key}'."
            ) from exc

        if not isinstance(release, dict):
            raise ValueError(
                f"Unexpected Jira Release response for "
                f"'{project_key}'."
            )

        return "created", release

    if is_duplicate_version_response(response):
        LOGGER.warning(
            "Release '%s' already exists in Jira project '%s'. "
            "Skipping this project and continuing.",
            version,
            project_key,
        )

        return "exists", None

    log_api_error(
        response,
        f"Jira Release creation for '{project_key}'",
    )

    response.raise_for_status()

    return "failed", None


# ---------------------------------------------------------------------------
# Release processing
# ---------------------------------------------------------------------------


def build_release_description(
    version: str,
    tag: str,
    environment: str,
    repository: str,
    workflow: str,
) -> str:
    """Build the Jira Release description.

    Args:
        version: Release version.
        tag: Git tag.
        environment: Deployment environment.
        repository: GitHub repository.
        workflow: GitHub Actions workflow.

    Returns:
        Release description.
    """
    return (
        f"{version}_{tag}_{environment}_"
        f"{repository}_{workflow}"
    )


def print_release_configuration(
    environment: dict[str, str],
    jira_projects: list[str],
) -> None:
    """Print release configuration."""
    LOGGER.info("========================================")
    LOGGER.info("Release Configuration")
    LOGGER.info("========================================")
    LOGGER.info(
        "Repository: %s",
        environment["REPOSITORY"],
    )
    LOGGER.info(
        "Version: %s",
        environment["VERSION"],
    )
    LOGGER.info(
        "Tag: %s",
        environment["TAG"],
    )
    LOGGER.info(
        "Environment: %s",
        environment["ENVIRONMENT"],
    )
    LOGGER.info(
        "Workflow: %s",
        environment["WORKFLOW"],
    )
    LOGGER.info(
        "Jira Projects: %s",
        jira_projects,
    )
    LOGGER.info("========================================")


def process_jira_project(
    session: requests.Session,
    jira_url: str,
    project_key: str,
    version: str,
    description: str,
) -> str:
    """Process release creation for one Jira project.

    Args:
        session: Authenticated Jira session.
        jira_url: Jira base URL.
        project_key: Jira project key.
        version: Release version.
        description: Release description.

    Returns:
        'created' when created.
        'exists' when already exists.
    """
    LOGGER.info("")
    LOGGER.info("========================================")
    LOGGER.info(
        "Creating Release in Jira project: %s",
        project_key,
    )
    LOGGER.info("========================================")

    project = get_jira_project(
        session=session,
        jira_url=jira_url,
        project_key=project_key,
    )

    project_id_value = project.get("id")

    if project_id_value is None:
        raise ValueError(
            f"Jira project '{project_key}' response does not "
            "contain a project ID."
        )

    try:
        project_id = int(project_id_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid Jira project ID '{project_id_value}' "
            f"for project '{project_key}'."
        ) from exc

    LOGGER.info(
        "Jira project: %s",
        project.get("name", "Unknown"),
    )
    LOGGER.info(
        "Jira project key: %s",
        project.get("key", project_key),
    )
    LOGGER.info(
        "Jira project ID: %s",
        project_id,
    )

    status, release = create_jira_version(
        session=session,
        jira_url=jira_url,
        project_id=project_id,
        project_key=project_key,
        version=version,
        description=description,
    )

    if status == "exists":
        return "exists"

    LOGGER.info("Release created successfully!")
    LOGGER.info(
        "Project: %s",
        project_key,
    )
    LOGGER.info(
        "Release name: %s",
        release.get("name", version),
    )
    LOGGER.info(
        "Release ID: %s",
        release.get("id", "Unknown"),
    )
    LOGGER.info(
        "Description: %s",
        release.get("description", description),
    )

    return "created"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the Jira release creation process.

    Returns:
        Process exit code.
    """
    configure_logging()

    created_projects: list[str] = []
    existing_projects: list[str] = []

    try:
        environment = load_environment()

        config = load_configuration(CONFIG_FILE)

        jira_projects = get_jira_projects(
            config=config,
            repository=environment["REPOSITORY"],
        )

        print_release_configuration(
            environment=environment,
            jira_projects=jira_projects,
        )

        description = build_release_description(
            version=environment["VERSION"],
            tag=environment["TAG"],
            environment=environment["ENVIRONMENT"],
            repository=environment["REPOSITORY"],
            workflow=environment["WORKFLOW"],
        )

        LOGGER.info(
            "Release description: %s",
            description,
        )

        session = create_jira_session(
            jira_email=environment["JIRA_EMAIL"],
            jira_api_token=environment["JIRA_API_TOKEN"],
        )

        for project_key in jira_projects:
            status = process_jira_project(
                session=session,
                jira_url=environment["JIRA_URL"],
                project_key=project_key,
                version=environment["VERSION"],
                description=description,
            )

            if status == "created":
                created_projects.append(project_key)

            elif status == "exists":
                existing_projects.append(project_key)

        LOGGER.info("")
        LOGGER.info("========================================")
        LOGGER.info("Release Processing Summary")
        LOGGER.info("========================================")

        if created_projects:
            LOGGER.info(
                "Releases created: %s",
                ", ".join(created_projects),
            )
        else:
            LOGGER.info("Releases created: None")

        if existing_projects:
            LOGGER.warning(
                "Releases already existed: %s",
                ", ".join(existing_projects),
            )
        else:
            LOGGER.info(
                "Releases already existed: None"
            )

        LOGGER.info("========================================")

        LOGGER.info(
            "Jira Release processing completed successfully."
        )

        return 0

    except FileNotFoundError as exc:
        LOGGER.error("%s", exc)
        return 1

    except ValueError as exc:
        LOGGER.error("%s", exc)
        return 1

    except yaml.YAMLError:
        LOGGER.error(
            "The central Jira configuration contains invalid YAML."
        )
        return 1

    except requests.HTTPError as exc:
        LOGGER.error(
            "Jira API request failed: %s",
            exc,
        )
        return 1

    except requests.RequestException as exc:
        LOGGER.error(
            "Jira API connection failed: %s",
            exc,
        )
        return 1

    except KeyboardInterrupt:
        LOGGER.error(
            "Process interrupted by user."
        )
        return 130

    except Exception:
        LOGGER.exception(
            "Unexpected error while creating Jira Releases."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
