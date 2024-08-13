#!/usr/bin/env python3

import json
import os
import subprocess
import time

COMFYUI_DIR = "/comfyui"

def install_comfyui(comfy_repo="https://github.com/comfyanonymous/ComfyUI.git", comfy_revision="74e124f4d784b859465e751a7b361c20f192f0f9"):
    print("Cloning ComfyUI repository")
    subprocess.run(['git', 'clone', comfy_repo, COMFYUI_DIR], check=True)
    
    os.chdir(COMFYUI_DIR)
    
    print("Checking out specific commit")
    subprocess.run(['git', 'checkout', comfy_revision], check=True)
    
    print("Installing dependencies")
    subprocess.run(['pip', 'install', 'torch==2.2.1', 'torchvision', 'torchaudio', 'xformers'], check=True)
    subprocess.run(['pip', 'install', '-r', 'requirements.txt'], check=True)
    subprocess.run(['pip', 'install', 'onnxruntime-gpu@https://huggingface.co/anyisalin/bookmark/resolve/main/onnxruntime_gpu-1.17.0-cp310-cp310-linux_x86_64.whl'], check=True)
    
    # clean pip cache
    subprocess.run(['pip', 'cache', 'purge'], check=True)
    
    os.chdir('..')  # Return to the original directory

def install_comfyui_manager(manager_repo="https://github.com/ltdrdata/ComfyUI-Manager.git", manager_revision="0.24.9"):
    print("Installing ComfyUI-Manager")
    subprocess.run(['git', 'clone', manager_repo, f'{COMFYUI_DIR}/custom_nodes/ComfyUI-Manager'], check=True)
    os.chdir(f'{COMFYUI_DIR}/custom_nodes/ComfyUI-Manager')
    subprocess.run(['git', 'checkout', manager_revision], check=True)
    subprocess.run(['pip', 'install', '-r', 'requirements.txt'], check=True)
    
    os.chdir(COMFYUI_DIR)  # Return to the ComfyUI directory
    os.chdir('..')  # Return to the original directory

if __name__ == "__main__":
    with open('/10-install-comfy.json', 'r') as f:
        config = json.load(f)
    
    comfy_repo = config.get('repo', "https://github.com/comfyanonymous/ComfyUI.git")
    comfy_revision = config.get('comfy_version', "74e124f4d784b859465e751a7b361c20f192f0f9")
    manager_repo = config.get('manager_repo', "https://github.com/ltdrdata/ComfyUI-Manager.git")
    manager_revision = config.get('manager_version', "8897b9e0f77d85dc02610784e4c357329dd04f4f")
    
    install_comfyui(comfy_repo, comfy_revision)
    install_comfyui_manager(manager_repo, manager_revision)