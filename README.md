# Comfy Buildkit

A CLI tool for building ComfyUI with Docker and Fly.io.


```
pip install comfy-buildkit

from comfy_buildkit import ComfyBuildkit

builder = ComfyBuildkit(comfyui_revision="master")

# Custom nodes
builder.custom_node("https://github.com/jags111/efficiency-nodes-comfyui", "b471390b88c9ac8a87c34ad9d882a520296b6fd8")
builder.custom_node("https://github.com/cubiq/ComfyUI_InstantID", "6d95aa6758e58dab550725e59dcefbd426c160c7")
builder.custom_node("https://github.com/Fannovel16/comfyui_controlnet_aux", "1d7cdce8cb771fbc39a432a6338168c12a338ef4")
builder.custom_node("https://github.com/cubiq/ComfyUI_essentials", "87ec9ae07b2b2733839d06c4560b76037d64cc0b")
builder.custom_node("https://github.com/WASasquatch/was-node-suite-comfyui", "ee2e31a1e5fd85ad6f5c36831ffda6fea8f249c7")

# Additional files
builder.add("https://huggingface.co/JCTN/JCTN_LORAxl/resolve/f4e83238a4ea5a62f3ff21abdf6ac7b545025731/ClayAnimationRedm.safetensors",
            "/comfyui/models/loras/ClayAnimationRedm.safetensors")
builder.add("https://huggingface.co/artificialguybr/PixelArtRedmond/resolve/main/PixelArtRedmond-Lite64.safetensors",
            "/comfyui/models/loras/PixelArtRedmond-Lite64.safetensors")
builder.add("https://huggingface.co/diffusers/controlnet-zoe-depth-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors",
            "/comfyui/models/controlnet/depth-zoe-xl-v1.0-controlnet.safetensors")
builder.add("https://huggingface.co/InstantX/InstantID/resolve/main/ControlNetModel/diffusion_pytorch_model.safetensors",
            "/comfyui/models/controlnet/instantid-controlnet.safetensors")
builder.add("https://huggingface.co/InstantX/InstantID/resolve/main/ip-adapter.bin",
            "/comfyui/models/instantid/instantid-ip-adapter.bin")
builder.add("https://civitai.com/api/download/models/329420?type=Model&format=SafeTensor&size=pruned&fp=fp16",
            "/comfyui/models/checkpoints/albedobaseXL_v13.safetensors")
builder.add("https://huggingface.co/lllyasviel/Annotators/resolve/main/ZoeD_M12_N.pt",
            "/comfyui/custom_nodes/comfyui_controlnet_aux/ckpts/lllyasviel/Annotators/ZoeD_M12_N.pt")

# Final configuration
builder.hf_snapshot_download("DIAMONIK7777/antelopev2", "/comfyui/models/insightface/models/antelopev2")
# builder.run("mkdir -p /comfyui/models/insightface/models/antelopev2")
# builder.run("wget -P /comfyui/models/insightface/models/antelopev2 https://huggingface.co/DIAMONIK7777/antelopev2/resolve/main/1k3d68.onnx")
# builder.run("wget -P /comfyui/models/insightface/models/antelopev2 https://huggingface.co/DIAMONIK7777/antelopev2/resolve/main/2d106det.onnx")
# builder.run("wget -P /comfyui/models/insightface/models/antelopev2 https://huggingface.co/DIAMONIK7777/antelopev2/resolve/main/genderage.onnx")
# builder.run("wget -P /comfyui/models/insightface/models/antelopev2 https://huggingface.co/DIAMONIK7777/antelopev2/resolve/main/glintr100.onnx")
# builder.run("wget -P /comfyui/models/insightface/models/antelopev2 https://huggingface.co/DIAMONIK7777/antelopev2/resolve/main/scrfd_10g_bnkps.onnx")
builder.pip_install("runpod", "requests", "safetensors", "pybase64==1.3.2")
builder.pip_install('onnxruntime-gpu@https://huggingface.co/anyisalin/bookmark/resolve/main/onnxruntime_gpu-1.17.0-cp310-cp310-linux_x86_64.whl')
builder.copy("src/start.sh", "src/rp_handler.py", "/")
builder.run("chmod +x /start.sh")
builder.cmd("/start.sh")
builder.save_dockerfile()
```