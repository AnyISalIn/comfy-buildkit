#!/usr/bin/env python3

import json
import os
import subprocess
import time
import sys

COMFYUI_DIR = "/comfyui"

def check_server(url, retries=50, delay=500):
    for i in range(retries):
        try:
            response = requests.head(url)
            if response.status_code == 200:
                print(f"builder - API is reachable")
                return True
        except requests.RequestException:
            pass
        time.sleep(delay / 1000)
    print(f"builder- Failed to connect to server at {url} after {retries} attempts.")
    return False

def run_post_install(repo_path):
    requirements_path = os.path.join(repo_path, 'requirements.txt')
    install_script_path = os.path.join(repo_path, 'install.py')

    if os.path.exists(requirements_path):
        with open(requirements_path, 'r', encoding="UTF-8", errors="ignore") as file:
            for line in file:
                package_name = line.strip()
                if package_name:
                    install_cmd = ["uv", "pip", "install", "--system", package_name]
                    output = subprocess.check_output(install_cmd, cwd=repo_path, text=True)
                    for msg_line in output.split('\n'):
                        if 'Requirement already satisfied:' in msg_line:
                            print('.', end='')
                        else:
                            print(msg_line)

    if os.path.exists(install_script_path):
        install_cmd = [sys.executable, install_script_path]
        output = subprocess.check_output(install_cmd, cwd=repo_path, text=True)
        for msg_line in output.split('\n'):
            if 'Requirement already satisfied:' in msg_line:
                print('.', end='')
            else:
                print(msg_line)

def install_custom_nodes():
    custom_nodes = json.load(open("/20-install-nodes.json"))

    for node in custom_nodes:
        repo_name = node["url"].split("/")[-1]
        print(f"Installing {repo_name}")
        node_dir = f'{COMFYUI_DIR}/custom_nodes/{repo_name}'
        subprocess.run(['git', 'clone', node["url"], node_dir], check=True)
        subprocess.run(['git', 'checkout', node["hash"]], cwd=node_dir, check=True)
        # Second step: Run post-install script
        try:
            repository_name = node["url"].split("/")[-1].strip()
            repo_path = os.path.join(COMFYUI_DIR, 'custom_nodes', repository_name)
            repo_path = os.path.abspath(repo_path)

            run_post_install(repo_path)

        except Exception as e:
            raise Exception(f"Error installing {repo_name}: {str(e)}")

    # clean pip cache
    subprocess.run(['uv', 'clean'], check=True)


if __name__ == "__main__":
    os.chdir(COMFYUI_DIR)
    
    install_custom_nodes()
    
    print("Finished installing dependencies.")