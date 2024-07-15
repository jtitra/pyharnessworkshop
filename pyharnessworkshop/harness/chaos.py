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
from ..utils.misc import validate_yaml_content

#### GLOBAL VARIABLES ####
HARNESS_API = "https://app.harness.io"

# PYDOC_RETURN_LABEL = ":return:"
# PYDOC_FOLLOW_PARAM = ":param bool follow:"


def generate_hce_id(name):
    """
    Generates a probe ID based on the provided name by replacing spaces with underscores and removing dashes.

    :param name: The name to be used for generating the probe ID
    :return: The generated probe ID as a string
    """
    return name.replace(" ", "_").replace("-", "")


def supported_api_methods(request_type, account_id, org_id, project_id, request_variables=None):
    """
    Returns the payload for the specified request type.

    :param request_type: The type of request (e.g., 'register_infra', 'add_probe', 'stop_all_chaos')
    :param account_id: The account identifier
    :param org_id: The organization identifier
    :param project_id: The project identifier
    :param request_variables: The variables to be included in the request payload
    :return: A dictionary containing the complete payload for the specified request type
    :raises ValueError: If the request type is unsupported
    """
    if request_variables is None:
        request_variables = {}

    match request_type:
        case "register_infra":
            query_data = {
                "operation": "mutation",
                "type": "registerInfra",
                "variables": {"key": "request", "value": "RegisterInfraRequest!"},
                "return": "{ manifest }"
            }
        case "add_probe":
            query_data = {
                "operation": "mutation",
                "type": "addProbe",
                "variables": {"key": "request", "value": "ProbeRequest!"},
                "return": "{ name type }"
            }
        case "list_infra":
            query_data = {
                "operation": "query",
                "type": "listInfrasV2",
                "variables": {"key": "request", "value": "ListInfraRequest"},
                "return": "{ totalNoOfInfras infras {infraID name environmentID platformName infraNamespace serviceAccount infraScope installationType} }"
            }
        case "get_infra_manifest":
            query_data = {
                "operation": "query",
                "type": "getInfraManifest",
                "variables": {"key": "infraID", "value": "String!"},
                "return": ""
            }
        case "stop_all_chaos":
            query_data = {
                "operation": "mutation",
                "type": "stopAllWorkflowRuns",
                "variables": {},
                "return": ""
            }
        case _:
            raise ValueError(f"Unsupported request type: {request_type}")

    identifiers = {
        "accountIdentifier": account_id,
        "orgIdentifier": org_id,
        "projectIdentifier": project_id
    }

    if query_data["variables"] == {}:
        query = f"""
        {query_data['operation']} {query_data['type']}($identifiers: IdentifiersRequest!) {{
            {query_data['type']}(identifiers: $identifiers) {query_data['return']}
        }}
        """
    else:
        query = f"""
        {query_data['operation']} {query_data['type']}(${query_data['variables']['key']}: {query_data['variables']['value']}, $identifiers: IdentifiersRequest!) {{
            {query_data['type']}({query_data['variables']['key']}: ${query_data['variables']['key']}, identifiers: $identifiers) {query_data['return']}
        }}
        """
        request_variables = {query_data['variables']['key']: request_variables}
        
    variables = {
        "identifiers": identifiers,
        **request_variables
    }

    payload = {
        "query": query,
        "variables": variables
    }

    return payload


def make_api_call(api_key, account_id, org_id, project_id, query_type, request_variables=None):
    """
    Makes an API call to the Chaos API with the specified query type and variables.

    :param api_key: The access token for authentication
    :param account_id: The account identifier
    :param org_id: The organization identifier
    :param project_id: The project identifier
    :param query_type: The type of query to be executed (e.g., 'register_infra', 'add_probe', 'stop_all_chaos')
    :param request_variables: The variables to be included in the request payload
    :return: The response from the Chaos API as a JSON object
    :raises SystemError: If an HTTP error or other error occurs during the API call
    """
    payload = supported_api_methods(query_type, account_id, org_id, project_id, request_variables)
    chaos_uri = f"{HARNESS_API}/gateway/chaos/manager/api/query"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }

    response = requests.post(chaos_uri, headers=headers, json=payload)
    try:
        response.raise_for_status()  # Raises HTTPError if the response status is 4xx/5xx
        json_response = response.json()
        if 'errors' in json_response:
            raise ValueError(f"GraphQL errors: {json_response['errors']}")
        return json_response
    except requests.exceptions.HTTPError as http_err:
        raise SystemError(f"HTTP error occurred: {http_err}")
    except Exception as err:
        raise SystemError(f"Other error occurred: {err}")


def register_infra(api_key, account_id, org_id, project_id, name, env_id, properties=None):
    """
    Registers infrastructure with the specified details using the Chaos API.

    :param api_key: The access token for authentication
    :param account_id: The account identifier
    :param org_id: The organization identifier
    :param project_id: The project identifier
    :param name: The name of the chaos infrastructure
    :param env_id: The environment identifier the chaos infrastructure will be enabled in
    :param properties: Optional dictionary of properties to configure the infrastructure. Defaults are used if not provided.
    :return: The response from the Chaos API as a JSON object
    """
    if properties is None:
        properties = {}
    
    # Set default values for properties if not provided
    default_properties = {
        "platformName": "Kubernetes",
        "infraNamespace": "hce",
        "serviceAccount": "hce",
        "infraScope": "namespace",
        "infraNsExists": True,
        "installationType": "MANIFEST",
        "isAutoUpgradeEnabled": False
    }

    # Update default properties with any provided properties
    request_variables = {**default_properties, **properties}
    request_variables["name"] = name
    request_variables["environmentID"] = env_id

    response = make_api_call(api_key, account_id, org_id, project_id, "register_infra", request_variables)

    # Extract the YAML manifest from the response
    manifest_yaml = response["data"]["registerInfra"]["manifest"]

    # Save the YAML manifest to a file
    file_name = f"/tmp/{name}_manifest.yaml"
    with open(file_name, "w") as file:
        file.write(manifest_yaml)

    return response


def add_probe(api_key, account_id, org_id, project_id, name, properties=None):
    """
    Adds a probe to the specified infrastructure using the Chaos API.

    :param api_key: The access token for authentication
    :param account_id: The account identifier
    :param org_id: The organization identifier
    :param project_id: The project identifier
    :param name: The name of the probe
    :param properties: Optional dictionary of properties to configure the probe. Defaults are used if not provided.
    :return: The response from the Chaos API as a JSON object
    """
    if properties is None:
        properties = {}
    
    hce_id = generate_hce_id(name)
    
    # Set default values for properties if not provided
    default_properties = {
        "probeTimeout": "10s",
        "interval": "5s",
        "retry": 3,
        "attempt": 3,
        "probePollingInterval": "1s",
        "initialDelay": "2s",
        "stopOnFailure": False,
        "url": "http://example.com",
        "method": {
            "get": {
                "criteria": "==",
                "responseCode": "200"
            }
        }
    }
    
    # Update default properties with any provided properties
    kubernetes_http_properties = {**default_properties, **properties}
    
    request_variables = {
        "name": name,
        "probeID": hce_id,
        "type": "httpProbe",
        "infrastructureType": "Kubernetes",
        "kubernetesHTTPProperties": kubernetes_http_properties
    }
    
    return make_api_call(api_key, account_id, org_id, project_id, "add_probe", request_variables)


def get_manifest_for_infra(api_key, account_id, org_id, project_id, name):
    """
    Creates a manifest file for the chaos infrastructure specified using the Chaos API.

    :param api_key: The access token for authentication
    :param account_id: The account identifier
    :param org_id: The organization identifier
    :param project_id: The project identifier
    :param name: The name of the chaos infrastructure
    """
    infra_id = None
    yaml_file = f"{name}-harness-chaos-enable.yml"
    chaos_infra = make_api_call(api_key, account_id, org_id, project_id, "list_infra")

    for infra in chaos_infra["data"]["listInfrasV2"]["infras"]:
        if infra["name"] == name:
            infra_id = infra["infraID"]
            break

    if infra_id:
        print(f"InfraID for '{name}': {infra_id}")
        chaos_manifest_raw = make_api_call(api_key, account_id, org_id, project_id, "get_infra_manifest", infra_id)
        with open(yaml_file, "wb") as file:
            file.write(chaos_manifest_raw["data"]["getInfraManifest"].encode('utf-8'))
        with open(yaml_file, "r") as file:
            validate_yaml_content(file)
    else:
        print(f"No infrastructure found with the name '{name}'")
