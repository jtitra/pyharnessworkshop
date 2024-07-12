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
from ..utils.misc import validate_yaml_content

#### GLOBAL VARIABLES ####
HARNESS_API = "https://app.harness.io"

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
