#!/usr/bin/env python3

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Any

COMFYUI_DIR = Path("/comfyui")

def install_comfyui(comfy_repo: str, comfy_revision: str) -> None:
    print("Cloning ComfyUI repository")
    subprocess.run(['git', 'clone', comfy_repo, str(COMFYUI_DIR)], check=True)
    
    os.chdir(COMFYUI_DIR)
    
    print(f"Checking out revision: {comfy_revision}")
    subprocess.run(['git', 'checkout', comfy_revision], check=True)
    
    print("Installing dependencies")
    subprocess.run(['uv', 'pip', 'install', '--system', 'torch==2.2.1', 'torchvision', 'torchaudio', 'xformers'], check=True)
    subprocess.run(['uv', 'pip', 'install', '--system', '-r', 'requirements.txt'], check=True)
    
    print("Cleaning pip cache")
    subprocess.run(['uv', 'clean'], check=True)
    
    os.chdir(Path.cwd().parent)

def install_comfyui_manager(manager_repo: str, manager_revision: str) -> None:
    print("Installing ComfyUI-Manager")
    manager_path = COMFYUI_DIR / "custom_nodes" / "ComfyUI-Manager"
    subprocess.run(['git', 'clone', manager_repo, str(manager_path)], check=True)
    os.chdir(manager_path)
    subprocess.run(['git', 'checkout', manager_revision], check=True)
    subprocess.run(['uv', 'pip', 'install', '--system', '-r', 'requirements.txt'], check=True)
    
    os.chdir(Path.cwd().parents[2])

def load_config(config_path: str = '/10-install-comfy.json') -> Dict[str, Any]:
    with open(config_path, 'r') as f:
        return json.load(f)

if __name__ == "__main__":
    config = load_config()
    
    comfy_repo = config.get('repo', "https://github.com/comfyanonymous/ComfyUI.git")
    comfy_revision = config.get('comfy_version', "74e124f4d784b859465e751a7b361c20f192f0f9")
    manager_repo = config.get('manager_repo', "https://github.com/ltdrdata/ComfyUI-Manager.git")
    manager_revision = config.get('manager_version', "8897b9e0f77d85dc02610784e4c357329dd04f4f")
    
    install_comfyui(comfy_repo, comfy_revision)
    # TODO: Uncomment the following line when ready to install the manager
    # install_comfyui_manager(manager_repo, manager_revision)