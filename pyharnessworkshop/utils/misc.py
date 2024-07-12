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
import pwd
import grp
import subprocess
import requests
from jinja2 import Template
import json
import random
import hashlib
import yaml

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
    os.makedirs("/home/harness/.local/share/code-server/User/", exist_ok=True)
    os.chown(
        "/home/harness/.local/share",
        pwd.getpwnam("harness").pw_uid,
        grp.getgrnam("harness").gr_gid
    )

    settings_url = "https://raw.githubusercontent.com/jtitra/field-workshops/main/assets/misc/vs_code/settings.json"
    settings_response = requests.get(settings_url)
    with open("/home/harness/.local/share/code-server/User/settings.json", "wb") as f:
        f.write(settings_response.content)

    service_url = "https://raw.githubusercontent.com/jtitra/field-workshops/main/assets/misc/vs_code/code-server.service"
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
    template_url = "https://raw.githubusercontent.com/jtitra/field-workshops/main/assets/misc/credential_tab_template.html"
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
