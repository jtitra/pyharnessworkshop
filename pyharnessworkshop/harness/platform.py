# Copyright 2024 Harness Solutions Engineering.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import subprocess
import time
import requests
import jinja2
from pathlib import Path
from urllib.parse import quote
from ..utils.misc import validate_yaml_content

#### GLOBAL VARIABLES ####
HARNESS_API = "https://app.harness.io"
HARNESS_IDP_API = "https://idp.harness.io"

# PYDOC_RETURN_LABEL = ":return:"
# PYDOC_FOLLOW_PARAM = ":param bool follow:"


def verify_harness_login(api_key, account_id, user_name):
    """
    Verifies the login of a user in Harness by checking the audit logs.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param user_name: The user name to verify the login for.
    :return: True if the user has logged in, otherwise False.
    """
    time_filter = int(time.time() * 1000) - 300000  # Current time in milliseconds minus 5 minutes

    print(f"Validating Harness login for user '{user_name}'...")
    url = f"{HARNESS_API}/gateway/audit/api/audits/list?accountIdentifier={account_id}"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }
    payload = {
        "actions": ["LOGIN"],
        "principals": [{
            "type": "USER",
            "identifier": user_name
        }],
        "filterType": "Audit",
        "startTime": str(time_filter)
    }

    response = requests.post(url, headers=headers, json=payload)
    response_data = response.json()
    response_items = response_data.get("data", {}).get("totalItems", 0)

    if response_items >= 1:
        print("Successful login found in audit trail.")
        return True
    else:
        print("No Logins were found in the last 5 minutes")
        return False


def create_harness_project(api_key, account_id, org_id, project_name):
    """
    Creates a project in Harness.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_name: The name of the project to create.
    """
    url = f"{HARNESS_API}/gateway/ng/api/projects?accountIdentifier={account_id}&orgIdentifier={org_id}"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }
    payload = {
        "project": {
            "name": project_name,
            "orgIdentifier": org_id,
            "description": "Automated build via Instruqt.",
            "identifier": project_name,
            "tags": {
                "automated": "yes",
                "owner": "instruqt"
            }
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    response_data = response.json()
    response_status = response_data.get("status")

    if response_status == "SUCCESS":
        print(f"Project '{project_name}' created successfully.")
    else:
        print(f"Failed to create project '{project_name}'. Response: {response_data}")
        raise SystemExit(1)


def invite_user_to_harness_project(api_key, account_id, org_id, project_id, user_email):
    """
    Invites a user to a Harness project.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_id: The project ID in Harness.
    :param user_email: The email of the user to invite.
    """
    url = f"{HARNESS_API}/gateway/ng/api/user/users?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }
    payload = {
        "emails": [user_email],
        "userGroups": ["_project_all_users"],
        "roleBindings": [{
            "resourceGroupIdentifier": "_all_project_level_resources",
            "roleIdentifier": "_project_admin",
            "roleName": "Project Admin",
            "resourceGroupName": "All Project Level Resources",
            "managedRole": True
        }]
    }

    response = requests.post(url, headers=headers, json=payload)
    return response.json()


def invite_user_to_harness_project_loop(api_key, account_id, org_id, project_id, user_email):
    """
    Invites a user to a Harness project with retry logic.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_id: The project ID in Harness.
    :param user_email: The email of the user to invite.
    """
    max_attempts = 4
    invite_attempts = 0

    print("Inviting the user to the project...")
    invite_response = invite_user_to_harness_project(api_key, account_id, org_id, project_id, user_email)
    invite_status = invite_response.get("status")
    print(f"  DEBUG: Status: {invite_status}")

    while invite_status != "SUCCESS" and invite_attempts < max_attempts:
        print(f"User invite to project has failed. Retrying... Attempt: {invite_attempts + 1}")
        invite_response = invite_user_to_harness_project(api_key, account_id, org_id, project_id, user_email)
        invite_status = invite_response.get("status")
        print(f"  DEBUG: Status: {invite_status}")
        invite_attempts += 1
        time.sleep(3)

    if invite_status == "SUCCESS":
        print("The API hit worked, your user was invited successfully.")
    else:
        print(f"API hit to invite the user to the project has failed after {max_attempts} attempts. Response: {invite_response}")
        raise SystemExit(1)


def delete_harness_project(api_key, account_id, org_id, project_id, cleanup=False):
    """
    Deletes a project in Harness.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_id: The project ID to delete.
    :param cleanup: Flag to continue the cleanup process on failure.
    """
    url = f"{HARNESS_API}/gateway/ng/api/projects/{project_id}?accountIdentifier={account_id}&orgIdentifier={org_id}"
    headers = {
        "x-api-key": api_key
    }

    response = requests.delete(url, headers=headers)
    response_data = response.json()
    response_status = response_data.get("status")

    if response_status == "SUCCESS":
        print(f"Project '{project_id}' deleted successfully.")
    else:
        print(f"Failed to delete project '{project_id}'. Response: {response_data}")
        if cleanup:
            print("Attempting to continue the cleanup process...")
        else:
            raise SystemExit(1)


def get_harness_user_id(api_key, account_id, search_term):
    """
    Gets the Harness user ID based on the search term.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param search_term: The term to search for the user.
    :return: The user ID if found, otherwise None.
    """
    url = f"{HARNESS_API}/gateway/ng/api/user/aggregate?accountIdentifier={account_id}&searchTerm={search_term}"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }

    try:
        response = requests.post(url, headers=headers)
        response.raise_for_status()  # Raises HTTPError for bad responses
        response_data = response.json()
        user_id = response_data.get('data', {}).get('content', [{}])[0].get('user', {}).get('uuid')
    except (requests.RequestException, ValueError, KeyError, IndexError) as e:
        print(f"Error occurred: {e}")
        user_id = None

    print(f"Harness User ID: {user_id}")
    return user_id


def delete_harness_user(api_key, account_id, user_email, cleanup=False):
    """
    Deletes a user from Harness based on their email.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param user_email: The email of the user to delete.
    :param cleanup: Flag to continue the cleanup process on failure.
    """
    user_id = get_harness_user_id(api_key, account_id, user_email)
    if user_id is None:
        print("Failed to determine the User ID. They may not have logged in. Nothing to delete.")
    else:
        print(f"Deleting Harness User ID: {user_id}")
        url = f"{HARNESS_API}/gateway/ng/api/user/{user_id}?accountIdentifier={account_id}"
        headers = {
            "x-api-key": api_key
        }

        response = requests.delete(url, headers=headers)
        response_data = response.json()
        response_status = response_data.get("status")

        if response_status == "SUCCESS":
            print("User deleted successfully.")
        else:
            print(f"Failed to delete user. Response: {response_data}")
            if cleanup:
                print("Attempting to continue the cleanup process...")
            else:
                raise SystemExit(1)


def create_harness_delegate(api_key, account_id, org_id, project_id):
    """
    Creates a project-level delegate in Harness.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_id: The project ID in Harness.
    """
    url = f"{HARNESS_API}/gateway/ng/api/download-delegates/kubernetes?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }
    payload = {
        "name": "instruqt-workshop-delegate",
        "description": "Automatically created for this lab",
        "clusterPermissionType": "CLUSTER_ADMIN"
    }

    response = requests.post(url, headers=headers, json=payload, stream=True)
    response_code = response.status_code

    with open("instruqt-delegate.yaml", "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)

    if 200 <= response_code < 300:
        with open("instruqt-delegate.yaml", 'r') as file:
            validate_yaml_content(file)

        try:
            subprocess.run(["kubectl", "apply", "-f", "instruqt-delegate.yaml"], check=True)
        except subprocess.CalledProcessError:
            print("  ERROR: Failed to apply the provided YAML.")
    else:
        print(f"  ERROR: Request failed. Status Code: {response_code}")


def create_harness_pipeline(api_key, account_id, org_id, project_id, pipeline_yaml):
    """
    Creates a pipeline in the provided Harness project.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_id: The project ID in Harness.
    :param pipeline_yaml: The Harness pipeline YAML payload.
    """
    url = f"{HARNESS_API}/pipeline/api/pipelines/v2?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}"
    headers = {
        "Content-Type": "application/yaml",
        "x-api-key": api_key
    }

    validate_yaml_content(pipeline_yaml)
    response = requests.post(url, headers=headers, data=pipeline_yaml, stream=True)
    response_code = response.status_code

    if 200 <= response_code < 300:
        print("  INFO: Successfully created Harness pipeline.")
    else:
        print(f"  ERROR: Request failed. Status Code: {response_code}")
        print(f"  Response Content: {response.content.decode('utf-8')}")


def update_pipeline(api_key, account_id, org_id, project_id, pipeline_id, pipeline_yaml):
    """
    Updates an existing pipeline in the provided Harness project.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_id: The project ID in Harness.
    :param pipeline_id: The identifier of the pipeline to update.
    :param pipeline_yaml: The Harness pipeline YAML payload.
    """
    url = f"{HARNESS_API}/pipeline/api/pipelines/v2/{pipeline_id}?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}"
    headers = {
        "Content-Type": "application/yaml",
        "x-api-key": api_key
    }

    validate_yaml_content(pipeline_yaml)
    response = requests.put(url, headers=headers, data=pipeline_yaml, stream=True)
    response_code = response.status_code

    if 200 <= response_code < 300:
        print("  INFO: Successfully updated Harness pipeline.")
    else:
        print(f"  ERROR: Request failed. Status Code: {response_code}")
        print(f"  Response Content: {response.content.decode('utf-8')}")


def list_pipelines(api_key, account_id, org_id, project_id):
    """
    Lists all pipelines in the provided Harness project.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_id: The project ID in Harness.
    :return: A JSON response containing the list of pipelines.
    """
    url = f"{HARNESS_API}/pipeline/api/pipelines/list?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }
    payload = {
        "filterType": "PipelineSetup"
    }

    response = requests.post(url, headers=headers, json=payload)
    try:
        response.raise_for_status()  # Raises HTTPError if the response status is 4xx/5xx
        json_response = response.json()
        if json_response.get('status') != "SUCCESS":
            raise ValueError(f"API errors: {json_response['errors']}")
        return json_response
    except requests.exceptions.HTTPError as http_err:
        raise SystemError(f"HTTP error occurred: {http_err}")
    except Exception as err:
        raise SystemError(f"Other error occurred: {err}")


def get_pipeline_by_id(json_response, pipeline_id):
    """
    Retrieves a pipeline from the provided JSON response by its identifier.

    :param json_response: The JSON response containing the list of pipelines.
    :param pipeline_id: The identifier of the pipeline to retrieve.
    :return: The pipeline data if found, otherwise None.
    """
    if json_response.get("status") == "SUCCESS":
        content = json_response.get("data", {}).get("content", [])
        if len(content) == 1:
            print("Project only contains a single pipeline.")
            identifier = content[0].get("identifier")
            print(f"Single pipeline identifier: {identifier}")
            return content[0]
        elif len(content) > 1:
            print("Project contains multiple pipelines.")
            target_pipeline = None
            for pipeline in content:
                if pipeline.get("identifier", "").lower() == pipeline_id.lower():
                    target_pipeline = pipeline
                    break
            if target_pipeline:
                print(f"Found pipeline: {target_pipeline.get('identifier')}")
                return target_pipeline
            else:
                print(f"No pipeline with identifier '{pipeline_id}' found.")
                return None
    else:
        print("API call failed or returned an unsuccessful status.")


def create_project_secret(api_key, account_id, org_id, project_id, input_yaml):
    """
    Creates a secret in the provided Harness project.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_id: The project ID in Harness.
    :param input_yaml: The Harness secret YAML payload.
    """
    url = f"{HARNESS_API}/v1/orgs/{org_id}/projects/{project_id}/secrets"
    headers = {
        "Content-Type": "application/yaml",
        "x-api-key": api_key,
        "Harness-Account": account_id
    }

    validate_yaml_content(input_yaml)
    response = requests.post(url, headers=headers, data=input_yaml, stream=True)
    response_code = response.status_code

    if 200 <= response_code < 300:
        print("  INFO: Successfully created Harness secret.")
    else:
        print(f"  ERROR: Request failed. Status Code: {response_code}")
        print(f"  Response Content: {response.content.decode('utf-8')}")


def create_project_connector(api_key, account_id, org_id, project_id, input_yaml):
    """
    Creates a connector in the provided Harness project.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_id: The project ID in Harness.
    :param input_yaml: The Harness connector YAML payload.
    """
    url = f"{HARNESS_API}/gateway/ng/api/connectors/?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}"
    headers = {
        "Content-Type": "text/yaml",
        "x-api-key": api_key
    }

    validate_yaml_content(input_yaml)
    response = requests.post(url, headers=headers, data=input_yaml, stream=True)
    response_code = response.status_code

    if 200 <= response_code < 300:
        print("  INFO: Successfully created Harness connector.")
    else:
        print(f"  ERROR: Request failed. Status Code: {response_code}")
        print(f"  Response Content: {response.content.decode('utf-8')}")


def deploy_harness_delegate(api_key, account_id, org_id, project_id, template_path, delegate_name):
    """
    Deploys a Harness delegate using the provided template.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_id: The project ID in Harness.
    :param template_path: The path to the delegate template file.
    :param delegate_name: The name to assign to the delegate.
    """
    input_path = Path(template_path)
    output_file = f"{input_path.parent}/harness-delegate.yaml"
    delegate_token = generate_delegate_token(api_key, account_id, org_id, project_id, f"{delegate_name}-token")
    delegate_image = get_latest_delegate_tag(api_key, account_id)
    with open(template_path, "r") as file:
        template = jinja2.Template(file.read())
    rendered_content = template.render(
        delegate_name=delegate_name,
        account_id=account_id,
        delegate_token=delegate_token,
        delegate_image=delegate_image
    )
    with open(output_file, 'w') as file:
        file.write(rendered_content)
    with open(output_file, 'r') as file:
        validate_yaml_content(file)
    try:
        subprocess.run(["kubectl", "apply", "-f", output_file], check=True)
    except subprocess.CalledProcessError:
        print("  ERROR: Failed to apply the provided YAML.")


def generate_delegate_token(api_key, account_id, org_id, project_id, token_name):
    """
    Generates a delegate token for the specified Harness project.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_id: The project ID in Harness.
    :param token_name: The name to assign to the generated token.
    :return: The generated delegate token.
    """
    headers = {
        "x-api-key": api_key
    }
    url = f"{HARNESS_API}/ng/api/delegate-token-ng?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}&tokenName={token_name}"
    response = requests.post(url, headers=headers)
    if response.status_code == 200:
        response_json = response.json()
        return response_json.get("resource", {}).get("value")
    else:
        response.raise_for_status()


def get_latest_docker_delegate_tag(latest=0):
    """
    Retrieves the latest tag for the Harness delegate image from Docker Hub.

    :return: The latest full tag for the Harness delegate image.
    :raises ValueError: If no full tags are found in the repository.
    """
    url = "https://hub.docker.com/v2/repositories/harness/delegate/tags"
    params = {
        "page_size": 1000,
        "ordering": "last_updated"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    tags = response.json()["results"]
    full_tags = [tag["name"] for tag in tags if "minimal" not in tag["name"].lower()]
    if not full_tags:
        raise ValueError("No full tags found in the repository.")
    return full_tags[latest]


def get_latest_delegate_tag(api_key, account_id):
    """
    Retrieves the latest supported version for the Harness delegate image for the given account.

    :return: The latest supported version for the Harness delegate image.
    :raises ValueError: If the latest supported version is not found in the response.
    """
    url = f"{HARNESS_API}/ng/api/delegate-setup/latest-supported-version?accountIdentifier={account_id}"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()

    latest_version = data.get("resource", {}).get("latestSupportedVersion")
    if not latest_version:
        raise ValueError("Latest supported version not found in the response.")

    return latest_version


def update_repo_security_settings(api_key, account_id, org_id, project_id, repo_identifier, secret_scanning_enabled=True, vulnerability_scanning_mode="disabled"):
    """
    Updates the security settings for a repository in the provided Harness project.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_id: The project ID in Harness.
    :param repo_identifier: The identifier for the repository.
    :param secret_scanning_enabled: Boolean flag to enable/disable secret scanning.
    :param vulnerability_scanning_mode: Mode for vulnerability scanning.
    """
    url = f"{HARNESS_API}/code/api/v1/repos/{repo_identifier}/settings/security?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }
    payload = {
        "secret_scanning_enabled": secret_scanning_enabled,
        "vulnerability_scanning_mode": vulnerability_scanning_mode
    }

    response = requests.patch(url, headers=headers, json=payload)
    response_code = response.status_code

    if 200 <= response_code < 300:
        print("INFO: Successfully updated repository security settings.")
    else:
        print(f"ERROR: Request failed. Status Code: {response_code}")
        print(f"Response Content: {response.content.decode('utf-8')}")


def create_service(api_key, account_id, org_id, project_id, service_yaml):
    """
    Creates a service in the provided Harness project.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_id: The project ID in Harness.
    :param service_yaml: The Harness service YAML payload.
    """
    url = f"{HARNESS_API}/ng/api/servicesV2?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }
    response = requests.post(url, headers=headers, json=service_yaml, stream=True)
    response_code = response.status_code
    if 200 <= response_code < 300:
        print("  INFO: Successfully created Harness service.")
    else:
        print(f"  ERROR: Request failed. Status Code: {response_code}")
        print(f"  Response Content: {response.content.decode('utf-8')}")


def list_services(api_key, account_id, org_id, project_id):
    """
    Lists all services in the provided Harness project.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_id: The project ID in Harness.
    :return: A JSON response containing the list of services.
    """
    url = f"{HARNESS_API}/ng/api/servicesV2?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }
    response = requests.get(url, headers=headers)
    try:
        response.raise_for_status()  # Raises HTTPError if the response status is 4xx/5xx
        json_response = response.json()
        if json_response.get('status') != "SUCCESS":
            raise ValueError(f"API errors: {json_response['errors']}")
        return json_response
    except requests.exceptions.HTTPError as http_err:
        raise SystemError(f"HTTP error occurred: {http_err}")
    except Exception as err:
        raise SystemError(f"Other error occurred: {err}")


def update_service(api_key, account_id, org_id, project_id, service_id, service_yaml):
    """
    Updates an existing service in the provided Harness project.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_id: The project ID in Harness.
    :param service_id: The identifier of the service to update.
    :param service_yaml: The Harness service YAML payload.
    """
    url = f"{HARNESS_API}/ng/api/servicesV2?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }
    response = requests.put(url, headers=headers, json=service_yaml, stream=True)
    response_code = response.status_code
    if 200 <= response_code < 300:
        print("  INFO: Successfully updated Harness service.")
    else:
        print(f"  ERROR: Request failed. Status Code: {response_code}")
        print(f"  Response Content: {response.content.decode('utf-8')}")


def get_service_by_id(json_response, service_id):
    """
    Retrieves a service from the provided JSON response by its identifier.

    :param json_response: The JSON response containing the list of services.
    :param service_id: The identifier of the service to retrieve.
    :return: The service data if found, otherwise None.
    """
    if json_response.get("status") == "SUCCESS":
        content = json_response.get("data", {}).get("content", [])
        if len(content) == 1:
            print("Project only contains a single service.")
            identifier = content[0].get("service").get("identifier")
            print(f"Single service identifier: {identifier}")
            if identifier.lower() == service_id.lower():
                return content[0]
            else:
                return None
        elif len(content) > 1:
            print("Project contains multiple services.")
            target_service = None
            for service_data in content:
                service = service_data.get("service", {})
                if service.get("identifier", "").lower() == service_id.lower():
                    target_service = service
                    break
            if target_service:
                print(f"Found service: {target_service.get('identifier')}")
                return target_service
            else:
                print(f"No service with identifier '{service_id}' found.")
                return None
    else:
        print("API call failed or returned an unsuccessful status.")


def create_user_group(api_key, account_id, org_id, project_id, group_name, users=None):
    """
    Creates a user group in the provided Harness project.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_id: The project ID in Harness.
    :param group_name: The name of the group to create.
    :param users: Array of user IDs to add to the group.
    """
    if users is None:
        users = []
    url = f"{HARNESS_API}/ng/api/user-groups?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}"
    group_identifer = group_name.replace(" ", "_").replace("-", "")
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }
    payload = {
        "identifier": f"{group_identifer}",
        "name": f"{group_name}",
        "users": users
    }
    response = requests.post(url, headers=headers, json=payload)
    response_code = response.status_code
    if 200 <= response_code < 300:
        print("  INFO: Successfully created Harness Group.")
    else:
        print(f"  ERROR: Request failed. Status Code: {response_code}")
        print(f"  Response Content: {response.content.decode('utf-8')}")


def execute_pipeline(api_key, account_id, org_id, project_id, pipeline_id, execution_yaml, execution_notes=None):
    """
    Executes a Harness pipeline with the specified parameters.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_id: The project ID in Harness.
    :param pipeline_id: The identifier of the pipeline to execute.
    :param execution_yaml: The YAML content for the pipeline execution.
    :param execution_notes: Notes for the pipeline execution.
    :return: The response from the API call.
    """
    base_url = f"{HARNESS_API}/gateway/pipeline/api/pipeline/execute/{pipeline_id}"
    query_params = (
        f"accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}"
    )
    if execution_notes:
        encoded_execution_notes = quote(execution_notes)
        query_params += f"&notesForPipelineExecution={encoded_execution_notes}"
    url = f"{base_url}?{query_params}"
    headers = {
        "Content-Type": "application/yaml",
        "x-api-key": api_key
    }
    response = requests.post(url, headers=headers, data=execution_yaml)
    response_code = response.status_code
    if 200 <= response_code < 300:
        print("  INFO: Pipeline execution started successfully.")
    else:
        print(f"  ERROR: Request failed. Status Code: {response_code}")
        print(f"  Response Content: {response.content.decode('utf-8')}")


def get_pipeline_yaml(api_key, account_id, org_id, project_id, pipeline_id):
    """
    Retrieves the YAML content of a specified Harness pipeline.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param org_id: The organization ID in Harness.
    :param project_id: The project ID in Harness.
    :param pipeline_id: The identifier of the pipeline to retrieve.
    :return: The YAML content of the pipeline.
    """
    url = (
        f"{HARNESS_API}/gateway/pipeline/api/pipelines/{pipeline_id}"
        f"?accountIdentifier={account_id}&orgIdentifier={org_id}&projectIdentifier={project_id}"
    )
    headers = {
        "Load-From-Cache": "false",
        "x-api-key": api_key
    }
    response = requests.get(url, headers=headers)
    response_code = response.status_code
    if 200 <= response_code < 300:
        data = response.json().get("data", {})
        pipeline_yaml = data.get("yamlPipeline", "")
        return pipeline_yaml
    else:
        print(f"ERROR: Request failed. Status Code: {response_code}")
        print(f"Response Content: {response.content.decode('utf-8')}")
        return None


def add_user_to_user_group(api_key, account_id, user_email, user_group_id):
    """
    Adds a user to a Harness user group based on their email.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param user_email: The email of the user to add to the group.
    :param user_group_id: The ID of the user group in Harness.
    """
    print(f"Getting Harness User ID for user: {user_email}")
    user_id = get_harness_user_id(api_key, account_id, user_email)
    if user_id is None:
        print("  ERROR: Failed to determine the User ID.")
        raise SystemExit(1)
    else:
        print(f"  Got Harness User ID: {user_id}")
        print(f"  Adding ID: {user_id} to Group: {user_group_id}")
        url = f"{HARNESS_API}/gateway/ng/api/user-groups/{user_group_id}/member/{user_id}?accountIdentifier={account_id}"
        headers = {
            "x-api-key": api_key
        }

        response = requests.put(url, headers=headers)
        response_data = response.json()
        response_status = response_data.get("status")

        if response_status == "SUCCESS":
            print("  User was successfully added to group.")
        else:
            print(f"  ERROR: Failed to add user to group. Response: {response_data}")
            raise SystemExit(1)


def remove_user_from_user_group(api_key, account_id, user_email, user_group_id):
    """
    Removes a user to a Harness user group based on their email.

    :param api_key: The API key for accessing Harness API.
    :param account_id: The account ID in Harness.
    :param user_email: The email of the user to remove from the group.
    :param user_group_id: The ID of the user group in Harness.
    """
    print(f"Getting Harness User ID for user: {user_email}")
    user_id = get_harness_user_id(api_key, account_id, user_email)
    if user_id is None:
        print("  ERROR: Failed to determine the User ID.")
        raise SystemExit(1)
    else:
        print(f"  Got Harness User ID: {user_id}")
        print(f"  Removing ID: {user_id} from Group: {user_group_id}")
        url = f"{HARNESS_API}/gateway/ng/api/user-groups/{user_group_id}/member/{user_id}?accountIdentifier={account_id}"
        headers = {
            "x-api-key": api_key
        }

        response = requests.delete(url, headers=headers)
        response_data = response.json()
        response_status = response_data.get("status")

        if response_status == "SUCCESS":
            print("  User was successfully removed from group.")
        else:
            print(f"  ERROR: Failed to remove user from group. Response: {response_data}")
            raise SystemExit(1)


def get_all_idp_catalog_items(api_key, idp_account_id):
    """
    Retrieves all items from the IDP catalog.

    :param api_key: The API key for accessing Harness API.
    :param idp_account_id: The IDP account/instance ID. Different from the Harness account ID.
    :return: List of items (JSON).
    """
    url = f"{HARNESS_IDP_API}/{idp_account_id}/idp/api/catalog/locations"
    headers = {
        "x-api-key": api_key
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching catalog item: {e}")
        return []


def delete_matching_idp_catalog_ids(api_key, idp_account_id, matching_ids):
    """
    Iterates over matching IDs and deletes them via the API.

    :param api_key: The API key for accessing Harness API.
    :param idp_account_id: The IDP account/instance ID. Different from the Harness account ID.
    :param matching_ids: List of IDs to delete.
    """
    for location_id in matching_ids:
        print(f"Attempting to delete catalog item with ID: {location_id}")
        url = f"{HARNESS_IDP_API}/{idp_account_id}/idp/api/catalog/locations/{location_id}"
        headers = {
            "x-api-key": api_key
        }
        try:
            response = requests.delete(url, headers=headers)
            if response.status_code == 204:  # HTTP 204: No Content (successful deletion)
                print(f"  Successfully deleted catalog item with ID: {location_id}")
            else:
                print(f"  Failed to delete catalog item with ID: {location_id}. Status code: {response.status_code}")
        except requests.RequestException as e:
            print(f"  Error deleting catalog item with ID {location_id}: {e}")


def find_ids_with_target(data, search_string):
    """
    Finds all IDs where the target field contains the specified search string.

    :param data: List of dictionaries containing target data.
    :param search_string: String to search for in the target field.
    :return: List of IDs matching the search criteria.
    """
    return [item['data']['id'] for item in data if search_string in item['data']['target']]
