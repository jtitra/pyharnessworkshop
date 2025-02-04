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

# Standard imports
import os
import subprocess
import json
import random
import hashlib
import string
import secrets

# Third-party imports
import requests
from jinja2 import Template
import yaml

# Library-specific imports
#   None

#### GLOBAL VARIABLES ####
WORKSHOP_REPO = "harness-community/field-workshops"

# PYDOC_RETURN_LABEL = ":return:"
# PYDOC_FOLLOW_PARAM = ":param bool follow:"


def setup_vs_code(service_port, code_server_directory):
    """
    Sets up VS Code server by downloading, installing, and configuring it.

    :param service_port: The port on which the VS Code server will run.
    :param code_server_directory: The directory where the VS Code server will store its files.
    """
    def download_and_install():
        """
        Downloads and installs VS Code server from the official repository.
        """
        url = "https://raw.githubusercontent.com/cdr/code-server/main/install.sh"
        response = requests.get(url)
        with open("/tmp/install.sh", "wb") as f:
            f.write(response.content)
        os.chmod("/tmp/install.sh", 0o755)
        subprocess.run(["bash", "/tmp/install.sh"], check=True)

    # Check if VS Code is already installed
    if subprocess.call(["which", "code-server"], stdout=subprocess.DEVNULL) == 0:
        print("VS Code already installed.")
    else:
        print("Installing VS Code...")
        download_and_install()

    # Setup VS Code
    os.makedirs("/root/.local/share/code-server/User/", exist_ok=True)
    settings_url = f"https://raw.githubusercontent.com/{WORKSHOP_REPO}/main/assets/misc/vs_code/settings.json"
    settings_response = requests.get(settings_url)
    with open("/root/.local/share/code-server/User/settings.json", "wb") as f:
        f.write(settings_response.content)

    service_url = f"https://raw.githubusercontent.com/{WORKSHOP_REPO}/main/assets/misc/vs_code/code-server.service"
    service_response = requests.get(service_url)
    with open("/etc/systemd/system/code-server.service", "wb") as f:
        f.write(service_response.content)

    # Update VS Code service
    with open("/etc/systemd/system/code-server.service", "r") as file:
        service_content = file.read()
    service_content = service_content.replace("EXAMPLEPORT", str(service_port))
    service_content = service_content.replace("EXAMPLEDIRECTORY", code_server_directory)

    create_systemd_service(service_content, "code-server")
    subprocess.run(["code-server", "--install-extension", "hashicorp.terraform"], check=True)


def generate_credentials_html(credentials):
    """
    Fetches the HTML template from a URL, populates it with credentials, and returns the generated HTML content.

    :param credentials: List of credentials to populate the template
    :return: Rendered HTML content as a string
    """
    template_url = f"https://raw.githubusercontent.com/{WORKSHOP_REPO}/main/assets/misc/credential_tab_template.html"
    try:
        # Fetch the HTML template from the URL
        response = requests.get(template_url)
        response.raise_for_status()
        html_template = response.text
        
        # Create a Jinja2 Template instance
        template = Template(html_template)
        
        # Render the template with the credentials data
        rendered_html = template.render(credentials=credentials)
        
        return rendered_html
    
    except requests.RequestException as e:
        print(f"Error fetching the template: {e}")
        return None


def create_systemd_service(service_content, service_name):
    """
    Creates a systemd service file and enables it to start on boot.

    :param service_content: The content to populate the .service file.
    :param service_name: The name of the service to create.
    """
    service_file_path = f"/etc/systemd/system/{service_name}.service"
    with open(service_file_path, "w") as service_file:
        service_file.write(service_content)

    # Reload systemd and enable the service
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", service_name], check=True)
    subprocess.run(["systemctl", "start", service_name], check=True)


def run_command(command):
    """
    Runs a shell command and prints success or failure message.

    :param command: The command to run.
    """
    try:
        subprocess.run(command, shell=True, check=True)
        print(f"Command '{command}' executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to execute command '{command}'. Error: {e}")


def generate_random_suffix(length=10):
    """
    Generates a random suffix by hashing a random number and taking the first 'length' characters.

    :param length: The desired length of the random suffix (default is 10)
    :return: A random suffix string of the specified length.
    """
    if length <= 0:
        raise ValueError("Length must be a positive integer.")
    if length > 15:
        raise ValueError("Length must not exceed 15 characters.")

    random_number = random.randint(0, 2**31 - 1)
    sha256_hash = hashlib.sha256(str(random_number).encode()).hexdigest()
    random_suffix = sha256_hash[:length]
    return random_suffix


def generate_gke_credentials(generator_uri, user_name, output_file, role_name):
    """
    Generate GKE cluster credentials and output to file.

    :param generator_uri: The URL of the GKE Generator API server.
    :param user_name: The user to generate an env/namespace for.
    :param output_file: The file to create for the new kubeconfig yaml.
    :param role_name: The existing K8s ClusterRole to assign to the new user.
    """
    print("Getting GKE cluster credentials...")
    payload = json.dumps({"username": user_name, "rolename": role_name})
    response = requests.post(
        f"{generator_uri}/create-user",
        headers={"Content-Type": "application/json"},
        data=payload,
        stream=True
    )
    with open(output_file, "wb") as f:
        f.write(response.content)
    print(f"HTTP status code: {response.status_code}")


def revoke_gke_credentials(generator_uri, user_name):
    """
    Revoke GKE cluster credentials.

    :param generator_uri: The URL of the GKE Generator API server.
    :param user_name: The user to revoke an env/namespace for.
    """
    print("Revoking GKE cluster credentials...")
    payload = json.dumps({"username": user_name})
    response = requests.post(
        f"{generator_uri}/delete-user",
        headers={"Content-Type": "application/json"},
        data=payload,
        stream=True
    )
    print(f"HTTP status code: {response.status_code}")


def validate_yaml_content(yaml_content):
    """
    Validates provided YAML data.

    :param yaml_content: The YAML data to validate.
    """
    try:
        yaml_data = list(yaml.safe_load_all(yaml_content))
        print("  INFO: Valid YAML provided.")
        return yaml_data
    except yaml.YAMLError as exc:
        print("  ERROR: The provided YAML is not valid.", exc)
        return None


def render_template_from_url(context, template_path):
    """
    Fetches a Jinja2 template from a URL and renders it with the provided context.

    :param context: A dictionary containing the context for rendering the template.
    :param template_path: The path in the repo of the Jinja2 template to fetch.
    :return: The rendered content as a string, or None if an error occurs.
    """
    template_url = f"https://raw.githubusercontent.com/{WORKSHOP_REPO}/main/{template_path}"
    try:
        response = requests.get(template_url)
        response.raise_for_status()
        template_content = response.text
        template = Template(template_content)
        rendered_content = template.render(context)
        return rendered_content
    except requests.RequestException as e:
        print(f"Error fetching the template: {e}")
        return None
    except Exception as e:
        print(f"Error rendering the template: {e}")
        return None


def fetch_template_from_url(template_path, output_file):
    """
    Fetches a Jinja2 template from a URL and outputs it to the specified file.

    :param template_path: The path in the repo of the Jinja2 template to fetch.
    :param output_file: A file to output the template to.
    """
    template_url = f"https://raw.githubusercontent.com/{WORKSHOP_REPO}/main/{template_path}"
    try:
        response = requests.get(template_url)
        response.raise_for_status()
        template_content = response.text
        with open(output_file, 'w') as file:
            file.write(template_content)
    except requests.RequestException as e:
        print(f"Error fetching the template: {e}")
    except Exception as e:
        print(f"Error rendering the template: {e}")


def parse_pipeline(yaml_str):
    """
    Parses a YAML string representing a pipeline configuration and extracts the stages into a dictionary.

    :param yaml_str: A string containing the YAML representation of the pipeline configuration.
    :return: A dictionary with the stage names as keys and their respective details as values. 
    """
    pipeline_data = yaml.safe_load(yaml_str)
    stages_dict = {}
    stages = pipeline_data.get("pipeline", {}).get("stages", [])
    # Flatten the list of stage and parallel stage
    flat_stages = []
    for stage_entry in stages:
        if "stage" in stage_entry:
            flat_stages.append(stage_entry["stage"])
        elif "parallel" in stage_entry:
            for parallel_stage in stage_entry["parallel"]:
                if "stage" in parallel_stage:
                    flat_stages.append(parallel_stage["stage"])
    for stage in flat_stages:
        stage_name = stage.get("name")
        stage_data = {
            "identifier": stage.get("identifier"),
            "description": stage.get("description", ""),
            "type": stage.get("type"),
            "spec": stage.get("spec", {})
        }
        stages_dict[stage_name] = stage_data
    return stages_dict


def validate_steps_in_stage(stages_dict, stage_id, step_context):
    """
    Validates steps in a given stage type against the provided step context.

    :param stages_dict: Dictionary containing stages with their details.
    :param stage_id: The ID of the stage to filter.
    :param step_context: A dictionary of steps and their expected values to validate.
    :return: A dictionary of misconfigured_steps.
    """
    misconfigured_steps = []
    for stage_name, stage_details in stages_dict.items():
        if stage_details.get("identifier", "").lower() == stage_id.lower():
            stage_type = stage_details.get("type")
            execution = stage_details.get("spec", {}).get("execution", {})
            steps = execution.get("steps", [])
            # Flatten the list of steps and parallel steps
            flat_steps = []
            for step_entry in steps:
                if "step" in step_entry:
                    flat_steps.append(step_entry["step"])
                elif "parallel" in step_entry:
                    for parallel_step in step_entry["parallel"]:
                        if "step" in parallel_step:
                            flat_steps.append(parallel_step["step"])
                elif "stepGroup" in step_entry:
                    for group_step in step_entry["stepGroup"]["steps"]:
                        if "step" in group_step:
                            flat_steps.append(group_step["step"])
            # Validate the step context against the found steps
            for step_key, expected_properties in step_context.items():
                matching_steps = [
                    s for s in flat_steps
                    if (s.get("type", "").lower() == step_key.lower() or
                        s.get("name", "").lower() == step_key.lower() or
                        s.get("identifier", "").lower() == step_key.lower())
                ]
                if not matching_steps:
                    print(f"Step '{step_key}' not found in stage '{stage_name}' with type '{stage_type}'.")
                    misconfigured_steps.append({
                        "step_key": step_key,
                        "stage_name": stage_name,
                        "stage_type": stage_type,
                        "property": None,
                        "expected": None,
                        "actual": None,
                        "message": f"Step '{step_key}' not found in stage '{stage_name}' with type '{stage_type}'."
                    })
                    continue
                # Validate the expected properties for each matching step
                for step in matching_steps:
                    for prop_key, expected_value in expected_properties.items():
                        actual_value = step.get(prop_key)
                        if isinstance(expected_value, dict):
                            for sub_key, sub_expected_value in expected_value.items():
                                sub_actual_value = actual_value.get(sub_key) if actual_value else None
                                if sub_actual_value != sub_expected_value:
                                    print(f"Mismatch for step '{step_key}' in property '{prop_key}.{sub_key}': expected '{sub_expected_value}', got '{sub_actual_value}'")
                                    misconfigured_steps.append({
                                        "step_key": step_key,
                                        "stage_name": stage_name,
                                        "stage_type": stage_type,
                                        "property": f"{prop_key}.{sub_key}",
                                        "expected": sub_expected_value,
                                        "actual": sub_actual_value,
                                        "message": f"Mismatch for step '{step_key}' in property '{prop_key}.{sub_key}': expected '{sub_expected_value}', got '{sub_actual_value}'"
                                    })
                        else:
                            if actual_value != expected_value:
                                print(f"Mismatch for step '{step_key}' in property '{prop_key}': expected '{expected_value}', got '{actual_value}'")
                                misconfigured_steps.append({
                                    "step_key": step_key,
                                    "stage_name": stage_name,
                                    "stage_type": stage_type,
                                    "property": prop_key,
                                    "expected": expected_value,
                                    "actual": actual_value,
                                    "message": f"Mismatch for step '{step_key}' in property '{prop_key}': expected '{expected_value}', got '{actual_value}'"
                                })
    return misconfigured_steps


def validate_stage_configuration(stages_dict, stage_id, stage_context):
    """
    Validates the configuration of a given stage against the provided stage context.

    :param stages_dict: Dictionary containing stages with their details.
    :param stage_id: The ID of the stage to filter.
    :param stage_context: A dictionary of stage configurations and their expected values to validate.
    :return: A list of mismatches, where each mismatch is a dictionary containing the path and details of the discrepancy.
    """
    mismatches = []
    for stage_name, stage_details in stages_dict.items():
        if stage_details.get("identifier", "").lower() == stage_id.lower():
            stage_type = stage_details.get("type")
            for key, expected_value in stage_context.items():
                if key not in stage_details.get("spec", {}):
                    print(f"Configuration '{key}' not found in stage '{stage_name}'.")
                    mismatches.append({
                        "path": f"{stage_name}.{key}",
                        "stage_name": stage_name,
                        "stage_type": stage_type,
                        "expected": expected_value,
                        "actual": None,
                        "message": f"Configuration '{key}' not found in stage '{stage_name}'."
                    })
                else:
                    actual_value = stage_details["spec"][key]
                    if isinstance(expected_value, dict):
                        for sub_key, sub_expected_value in expected_value.items():
                            if sub_key not in actual_value:
                                print(f"Configuration key '{key}.{sub_key}' not found in stage '{stage_name}'.")
                                mismatches.append({
                                    "path": f"{stage_name}.{key}.{sub_key}",
                                    "stage_name": stage_name,
                                    "stage_type": stage_type,
                                    "expected": sub_expected_value,
                                    "actual": None,
                                    "message": f"Configuration key '{key}.{sub_key}' not found in stage '{stage_name}'."
                                })
                            elif actual_value[sub_key] != sub_expected_value:
                                print(f"Mismatch in '{key}.{sub_key}' for stage '{stage_name}': expected '{sub_expected_value}', found '{actual_value.get(sub_key)}'.")
                                mismatches.append({
                                    "path": f"{stage_name}.{key}.{sub_key}",
                                    "stage_name": stage_name,
                                    "stage_type": stage_type,
                                    "expected": sub_expected_value,
                                    "actual": actual_value[sub_key],
                                    "message": f"Mismatch in '{key}.{sub_key}' for stage '{stage_name}': expected '{sub_expected_value}', found '{actual_value.get(sub_key)}'."
                                })
                    elif isinstance(expected_value, list):
                        for item in expected_value:
                            if item not in actual_value:
                                print(f"Expected list item '{item}' not found in '{key}' for stage '{stage_name}'.")
                                mismatches.append({
                                    "path": f"{stage_name}.{key}",
                                    "stage_name": stage_name,
                                    "stage_type": stage_type,
                                    "expected": item,
                                    "actual": None,
                                    "message": f"Expected list item '{item}' not found in '{key}' for stage '{stage_name}'."
                                })
                    elif actual_value != expected_value:
                        print(f"Mismatch in '{key}' for stage '{stage_name}': expected '{expected_value}', found '{actual_value}'.")
                        mismatches.append({
                            "path": f"{stage_name}.{key}",
                            "stage_name": stage_name,
                            "stage_type": stage_type,
                            "expected": expected_value,
                            "actual": actual_value,
                            "message": f"Mismatch in '{key}' for stage '{stage_name}': expected '{expected_value}', found '{actual_value}'."
                        })
    return mismatches


def get_stage_identifier_from_dict(pipeline_dict, stage_type, service_name=None):
    """
    Retrieves the identifier of a stage based on the stage type and an optional service name.

    :param pipeline_dict: Dictionary containing stages with their details.
    :param stage_type: The type of the stage to filter.
    :param service_name: (Optional) The name of the service to filter within the stage type.
    :return: The identifier of the matching stage, or None if no match is found.
    """
    for key, value in pipeline_dict.items():
        if value.get('type') == stage_type:
            if service_name:
                service_ref = value.get('spec', {}).get('service', {}).get('serviceRef')
                if service_ref.lower() == service_name.lower():
                    return value['identifier']
            else:
                return value['identifier']
    return None


def validate_password(password, upper, lower, digits):
    """
    Validate that the password contains at least one of each required character type.

    :param password: str, the password to validate
    :param upper: str, uppercase character pool
    :param lower: str, lowercase character pool
    :param digits: str, digit character pool
    :return: bool, True if the password is valid, otherwise False
    """
    return (
        any(char in upper for char in password) and
        any(char in lower for char in password) and
        any(char in digits for char in password)
    )


def generate_password(length=12):
    """
    Generate a random password with the specified length.

    :param length: int, length of the password (default is 12)
    :return: str, randomly generated password
    """
    if length < 4:
        raise ValueError("Password length must be at least 4 to include all character types.")
    if length > 50:
        raise ValueError("Password length must not exceed 50 characters to avoid performance issues.")

    upper = string.ascii_uppercase
    lower = string.ascii_lowercase
    digits = string.digits
    all_characters = upper + lower + digits
    while True:
        password = [
            secrets.choice(upper),
            secrets.choice(lower),
            secrets.choice(digits),
        ]

        password += [secrets.choice(all_characters) for _ in range(length - len(password))]
        random.shuffle(password)  # Shuffle the password to make it random
        if validate_password(password, upper, lower, digits):
            return ''.join(password)


def validate_workspace_configuration(workspace_config, workspace_context):
    """
    Validates the workspace configuration against the provided workspace context.

    :param workspace_config: Dictionary containing the workspace configuration details.
    :param workspace_context: A dictionary of expected workspace configurations and their expected values.
    :return: A list of mismatches, where each mismatch is a dictionary containing the path and details 
             of the discrepancy.
    """
    mismatches = []

    def compare_values(path, expected, actual):
        local_mismatches = []
        # Handle dictionary values recursively.
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                local_mismatches.append({
                    "path": path,
                    "expected": expected,
                    "actual": actual,
                    "message": f"Expected a dictionary at '{path}', but found {type(actual).__name__}."
                })
            else:
                for sub_key, sub_expected in expected.items():
                    new_path = f"{path}.{sub_key}" if path else sub_key
                    if sub_key not in actual:
                        local_mismatches.append({
                            "path": new_path,
                            "expected": sub_expected,
                            "actual": None,
                            "message": f"Configuration key '{new_path}' not found in workspace."
                        })
                    else:
                        sub_actual = actual[sub_key]
                        local_mismatches.extend(compare_values(new_path, sub_expected, sub_actual))
        # Handle lists by checking that each expected item exists in the actual list.
        elif isinstance(expected, list):
            if not isinstance(actual, list):
                local_mismatches.append({
                    "path": path,
                    "expected": expected,
                    "actual": actual,
                    "message": f"Expected a list at '{path}', but found {type(actual).__name__}."
                })
            else:
                for item in expected:
                    if item not in actual:
                        local_mismatches.append({
                            "path": path,
                            "expected": item,
                            "actual": None,
                            "message": f"Expected list item '{item}' not found in '{path}'."
                        })
        # For simple types, compare directly (with special handling for booleans represented as strings).
        else:
            if isinstance(actual, bool) and isinstance(expected, str):
                # Convert the expected value to a boolean.
                expected_bool = True if expected.lower() == "true" else False
                if actual != expected_bool:
                    local_mismatches.append({
                        "path": path,
                        "expected": expected_bool,
                        "actual": actual,
                        "message": f"Mismatch in '{path}': expected '{expected_bool}', found '{actual}'."
                    })
            elif actual != expected:
                local_mismatches.append({
                    "path": path,
                    "expected": expected,
                    "actual": actual,
                    "message": f"Mismatch in '{path}': expected '{expected}', found '{actual}'."
                })

        return local_mismatches

    # Iterate over every expected key in the workspace_context.
    for key, expected_value in workspace_context.items():
        if key not in workspace_config:
            mismatches.append({
                "path": key,
                "expected": expected_value,
                "actual": None,
                "message": f"Configuration '{key}' not found in workspace."
            })
        else:
            actual_value = workspace_config[key]
            mismatches.extend(compare_values(key, expected_value, actual_value))

    return mismatches
