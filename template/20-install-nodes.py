#!/usr/bin/env python3

import json
import os
import subprocess
import time

COMFYUI_DIR = "/comfyui"

def start_comfyui_server():
    print("Starting ComfyUI")
    command = ["python", "main.py", "--disable-auto-launch", "--disable-metadata", "--cpu"]
    return subprocess.Popen(command, cwd=COMFYUI_DIR)

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

def install_custom_nodes():
    custom_nodes = json.load(open("/20-install-nodes.json"))

    for node in custom_nodes:
        repo_name = node["url"].split("/")[-1]
        print(f"Installing {repo_name}")
        node_dir = f'{COMFYUI_DIR}/custom_nodes/{repo_name}'
        subprocess.run(['git', 'clone', node["url"], node_dir], check=True)
        subprocess.run(['git', 'checkout', node["hash"]], cwd=node_dir, check=True)
        # Second step: Run post-install script
        subprocess.run(['python', './custom_nodes/ComfyUI-Manager/cm-cli.py', 'post-install', node_dir], cwd=COMFYUI_DIR, check=True)

    # clean pip cache
    subprocess.run(['pip', 'cache', 'purge'], check=True)


if __name__ == "__main__":
    os.chdir(COMFYUI_DIR)
    
    install_custom_nodes()
    
    print("Finished installing dependencies.")