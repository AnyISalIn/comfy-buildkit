#!/usr/bin/env python3

import json
import os
import subprocess
import time
import sys
from pathlib import Path
from typing import List, Dict, Any
import requests

COMFYUI_DIR = Path("/comfyui")

def run_post_install(repo_path: Path) -> None:
    requirements_path = repo_path / 'requirements.txt'
    install_script_path = repo_path / 'install.py'

    if requirements_path.exists():
        with requirements_path.open('r', encoding="UTF-8", errors="ignore") as file:
            for package_name in file:
                package_name = package_name.strip()
                if package_name:
                    install_cmd = ["uv", "pip", "install", "--system", package_name]
                    process = subprocess.Popen(install_cmd, cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    for line in process.stdout:
                        print('.' if 'Requirement already satisfied:' in line else line, end='')
                    process.wait()
                    if process.returncode != 0:
                        raise subprocess.CalledProcessError(process.returncode, install_cmd)

    if install_script_path.exists():
        install_cmd = [sys.executable, str(install_script_path)]
        process = subprocess.Popen(install_cmd, cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print('.' if 'Requirement already satisfied:' in line else line, end='')
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, install_cmd)

def install_custom_nodes() -> None:
    with open("/20-install-nodes.json", "r") as f:
        custom_nodes: List[Dict[str, Any]] = json.load(f)

    for node in custom_nodes:
        repo_name = Path(node["url"]).name
        print(f"Installing {repo_name}")
        node_dir = COMFYUI_DIR / 'custom_nodes' / repo_name
        subprocess.run(['git', 'clone', node["url"], str(node_dir)], check=True)
        subprocess.run(['git', 'checkout', node["hash"]], cwd=node_dir, check=True)
        
        try:
            run_post_install(node_dir)
        except Exception as e:
            print(f"Error installing {repo_name}: {str(e)}")

    # clean pip cache
    subprocess.run(['uv', 'clean'], check=True)

if __name__ == "__main__":
    os.chdir(COMFYUI_DIR)
    install_custom_nodes()
    print("Finished installing dependencies.")