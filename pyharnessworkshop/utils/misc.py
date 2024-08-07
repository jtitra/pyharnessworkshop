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

import os
import subprocess
import requests
from jinja2 import Template
import json
import random
import hashlib
import yaml

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


def generate_random_suffix():
    """
    Generates a random suffix by hashing a random number and taking the first 10 characters.

    :return: A random suffix string of 10 characters.
    """
    random_number = random.randint(0, 32767)
    md5_hash = hashlib.md5(str(random_number).encode()).hexdigest()
    random_suffix = md5_hash[:10]
    return random_suffix


def generate_gke_credentials(generator_uri, user_name, output_file):
    """
    Generate GKE cluster credentials and output to file.

    :param generator_uri: The URL of the GKE Generator API server.
    :param user_name: The user to generate an env/namespace for.
    :param output_file: The file to create for the new kubeconfig yaml.
    """
    print("Getting GKE cluster credentials...")
    payload = json.dumps({"username": user_name})
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
