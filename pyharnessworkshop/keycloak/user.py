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

import requests

# PYDOC_RETURN_LABEL = ":return:"
# PYDOC_FOLLOW_PARAM = ":param bool follow:"


def create_keycloak_user(keycloak_endpoint, keycloak_realm, keycloak_token, user_email, user_name, user_pwd):
    """
    Creates a user in Keycloak.

    :param keycloak_endpoint: The Keycloak endpoint.
    :param keycloak_realm: The Keycloak realm.
    :param keycloak_token: The Keycloak token.
    :param user_email: The email of the user to create.
    :param user_name: The name of the user to create.
    :param user_pwd: The password of the user to create.
    """
    url = f"{keycloak_endpoint}/admin/realms/{keycloak_realm}/users"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {keycloak_token}"
    }
    payload = {
        "email": user_email,
        "username": user_email,
        "firstName": user_name,
        "lastName": "Student",
        "emailVerified": True,
        "enabled": True,
        "requiredActions": [],
        "groups": [],
        "credentials": [
            {
                "type": "password",
                "value": user_pwd,
                "temporary": False
            }
        ]
    }

    response = requests.post(url, headers=headers, json=payload)
    response_code = response.status_code

    print(f"HTTP status code: {response_code}")

    if response_code != 201:
        print(f"The user creation API is not returning 201... this was the response: {response_code}")
        raise SystemExit(1)


def get_keycloak_user_id(keycloak_endpoint, keycloak_realm, keycloak_token, search_term):
    """
    Gets the Keycloak user ID based on the search term.

    :param keycloak_endpoint: The Keycloak endpoint.
    :param keycloak_realm: The Keycloak realm.
    :param keycloak_token: The Keycloak token.
    :param search_term: The term to search for the user.
    :return: The user ID if found, otherwise None.
    """
    url = f"{keycloak_endpoint}/admin/realms/{keycloak_realm}/users?briefRepresentation=true&first=0&max=11&search={search_term}"
    headers = {
        "Authorization": f"Bearer {keycloak_token}"
    }

    response = requests.get(url, headers=headers)
    response_data = response.json()
    user_id = response_data[0].get("id") if response_data else None

    print(f"Keycloak User ID: {user_id}")
    return user_id


def delete_keycloak_user(keycloak_endpoint, keycloak_realm, keycloak_token, user_email, cleanup=False):
    """
    Deletes a user from Keycloak based on their email.

    :param keycloak_endpoint: The Keycloak endpoint.
    :param keycloak_realm: The Keycloak realm.
    :param keycloak_token: The Keycloak token.
    :param user_email: The email of the user to delete.
    :param cleanup: Flag to continue the cleanup process on failure.
    """
    user_id = get_keycloak_user_id(keycloak_endpoint, keycloak_realm, keycloak_token, user_email)
    if not user_id:
        print("Failed to determine the User ID.")
    else:
        print(f"Deleting Keycloak User ID: {user_id}")
        url = f"{keycloak_endpoint}/admin/realms/{keycloak_realm}/users/{user_id}"
        headers = {
            "Authorization": f"Bearer {keycloak_token}"
        }

        response = requests.delete(url, headers=headers)
        response_code = response.status_code

        print(f"HTTP status code: {response_code}")

        if response_code != 204:
            print(f"The user deletion API is not returning 204... this was the response: {response_code}")
            if cleanup:
                print("Attempting to continue the cleanup process...")
            else:
                raise SystemExit(1)
