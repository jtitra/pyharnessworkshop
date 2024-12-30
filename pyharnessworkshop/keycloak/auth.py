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


def generate_keycloak_token(keycloak_endpoint, keycloak_admin_user, keycloak_admin_pwd, cleanup=False):
    """
    Generates a Keycloak bearer token.

    :param keycloak_endpoint: The Keycloak endpoint.
    :param keycloak_admin_user: The Keycloak admin username.
    :param keycloak_admin_pwd: The Keycloak admin password.
    :param cleanup: Flag to continue the cleanup process on failure.
    :return: The Keycloak token if successful, otherwise None.
    """
    url = f"{keycloak_endpoint}/realms/master/protocol/openid-connect/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "username": keycloak_admin_user,
        "password": keycloak_admin_pwd,
        "grant_type": "password",
        "client_id": "admin-cli"
    }

    response = requests.post(url, headers=headers, data=payload)

    if response.status_code != 200:
        print("API call failed.")
        if cleanup:
            print("Attempting to continue the cleanup process...")
        else:
            raise SystemExit(1)

    response_data = response.json()
    keycloak_token = response_data.get("access_token")

    if not keycloak_token:
        print("Token generation has failed. Response was:")
        print(response_data)
        if cleanup:
            print("Attempting to continue the cleanup process...")
        else:
            raise SystemExit(1)
    else:
        print("Token generation complete")
        return keycloak_token
