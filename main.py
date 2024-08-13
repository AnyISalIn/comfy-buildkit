from comfyc import ComfyC
import subprocess
import os
import argparse

def create_fly_toml(temp_dir: str, app_name: str, primary_region: str = 'sjc', 
                    memory: str = '1gb', cpu_kind: str = 'shared', cpus: int = 1):
    fly_toml_content = f"""
app = '{app_name}'
primary_region = '{primary_region}'

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = 'stop'
  auto_start_machines = true
  min_machines_running = 0
  processes = ['app']

[[vm]]
  memory = '{memory}'
  cpu_kind = '{cpu_kind}'
  cpus = {cpus}
"""
    fly_toml_path = os.path.join(temp_dir, "fly.toml")
    with open(fly_toml_path, "w") as f:
        f.write(fly_toml_content.strip())

def run_flyctl(temp_dir: str):
    current_dir = os.getcwd()
    os.chdir(temp_dir)
    try:
        subprocess.run("flyctl deploy --build-only --push", shell=True, check=True)
    finally:
        os.chdir(current_dir)

def run_docker_build(temp_dir: str, tag: str):
    current_dir = os.getcwd()
    os.chdir(temp_dir)
    try:
        subprocess.run(f"docker build -t {tag} .", shell=True, check=True)
    finally:
        os.chdir(current_dir)

# Usage example
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build ComfyUI Docker image")
    parser.add_argument("--local", action="store_true", help="Build locally using Docker")
    parser.add_argument("--fly", action="store_true", help="Build using Fly.io")
    parser.add_argument("--tag", default="comfyui:latest", help="Docker image tag (for local build)")
    args = parser.parse_args()

    builder = ComfyC()

    print(builder \
        .custom_node("https://github.com/jags111/efficiency-nodes-comfyui", "b471390b88c9ac8a87c34ad9d882a520296b6fd8") \
        .custom_node("https://github.com/cubiq/ComfyUI_InstantID", "6d95aa6758e58dab550725e59dcefbd426c160c7") \
        .custom_node("https://github.com/Fannovel16/comfyui_controlnet_aux", "1d7cdce8cb771fbc39a432a6338168c12a338ef4") \
        .custom_node("https://github.com/cubiq/ComfyUI_essentials", "87ec9ae07b2b2733839d06c4560b76037d64cc0b") \
        .custom_node("https://github.com/WASasquatch/was-node-suite-comfyui", "ee2e31a1e5fd85ad6f5c36831ffda6fea8f249c7") \
        .add("https://huggingface.co/JCTN/JCTN_LORAxl/resolve/f4e83238a4ea5a62f3ff21abdf6ac7b545025731/ClayAnimationRedm.safetensors", "/comfyui/models/lora/ClayAnimationRedm.safetensors") \
        .add("https://huggingface.co/diffusers/controlnet-zoe-depth-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors", "/comfyui/models/controlnet/depth-zoe-xl-v1.0-controlnet.safetensors") \
        .add("https://huggingface.co/InstantX/InstantID/resolve/main/ControlNetModel/diffusion_pytorch_model.safetensors", "/comfyui/models/controlnet/instantid-controlnet.safetensors") \
        .add("https://huggingface.co/InstantX/InstantID/resolve/main/ip-adapter.bin", "/comfyui/models/instantid/instantid-ip-adapter.bin") \
        .add("https://civitai.com/api/download/models/329420?type=Model&format=SafeTensor&size=pruned&fp=fp16", "/comfyui/models/checkpoints/albedobaseXL_v13.safetensors")
        .generate_dockerfile())

    try:
        builder.save_dockerfile()
        
        if args.local:
            print(f"Building Docker image locally with tag: {args.tag}")
            run_docker_build(builder.temp_dir, args.tag)
        
        if args.fly:
            print("Building on Fly.io")
            create_fly_toml(builder.temp_dir, "tmp4vlhq0ve", memory="2gb", cpus=2)
            print(f"Temporary directory: {builder.temp_dir}")
            run_flyctl(builder.temp_dir)
        
        if not args.local and not args.fly:
            print("No build option specified. Use --local for Docker build or --fly for Fly.io build.")
    
    finally:
        # Uncomment the following line to clean up the temporary directory
        # builder.cleanup()
        pass