# ComfyBuildkit

ComfyBuildkit is a Python toolkit for building and customizing ComfyUI Docker images. It provides a flexible and easy-to-use interface for creating Dockerfiles with various configurations and dependencies for ComfyUI.


## Features

- Easy configuration of ComfyUI and custom nodes
- Support for downloading models from Hugging Face and Civitai
- Flexible Docker image customization
- CLI tool for building and deploying images
- Support for local Docker builds and Fly.io deployments

```
$ pip install git+https://github.com/AnyISalIn/comfy-buildkit --upgrade
```

## Usage


### Basic Example

Here's a simple example of how to use ComfyBuildkit:

```shell
$ comfy-buildkit https://raw.githubusercontent.com/AnyISalIn/comfy-buildkit/main/examples/simple.py
```

### YAML Example


Here's an example of a `comfyfile.yaml`:

After creating a `comfyfile.yaml`, you can build the image using the following command:

```shell
$ comfy-buildkit comfyfile.yaml
```

```yaml
comfyui:
  revision: "39fb74c5bd13a1dccf4d7293a2f7a755d9f43cbd"

custom_nodes:
  - url: "https://github.com/jags111/efficiency-nodes-comfyui"
    revision: "b471390b88c9ac8a87c34ad9d882a520296b6fd8"
  - url: "https://github.com/cubiq/ComfyUI_InstantID"
    revision: "6d95aa6758e58dab550725e59dcefbd426c160c7"
  - url: "https://github.com/Fannovel16/comfyui_controlnet_aux"
    revision: "1d7cdce8cb771fbc39a432a6338168c12a338ef4"
  - url: "https://github.com/cubiq/ComfyUI_essentials"
    revision: "87ec9ae07b2b2733839d06c4560b76037d64cc0b"
  - url: "https://github.com/WASasquatch/was-node-suite-comfyui"
    revision: "ee2e31a1e5fd85ad6f5c36831ffda6fea8f249c7"

models:
  - type: wget
    url: "https://huggingface.co/JCTN/JCTN_LORAxl/resolve/f4e83238a4ea5a62f3ff21abdf6ac7b545025731/ClayAnimationRedm.safetensors"
    local_path: "loras/ClayAnimationRedm.safetensors"
  - type: wget
    url: "https://huggingface.co/artificialguybr/PixelArtRedmond/resolve/main/PixelArtRedmond-Lite64.safetensors"
    local_path: "loras/PixelArtRedmond-Lite64.safetensors"
  - type: wget
    url: "https://huggingface.co/diffusers/controlnet-zoe-depth-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors"
    local_path: "controlnet/depth-zoe-xl-v1.0-controlnet.safetensors"
  - type: wget
    url: "https://huggingface.co/InstantX/InstantID/resolve/main/ControlNetModel/diffusion_pytorch_model.safetensors"
    local_path: "controlnet/instantid-controlnet.safetensors"
  - type: wget
    url: "https://huggingface.co/InstantX/InstantID/resolve/main/ip-adapter.bin"
    local_path: "/comfyui/models/instantid/instantid-ip-adapter.bin"
  - type: wget
    url: "https://civitai.com/api/download/models/329420?type=Model&format=SafeTensor&size=pruned&fp=fp16"
    local_path: "checkpoints/albedobaseXL_v13.safetensors"
  - type: wget
    url: "https://huggingface.co/lllyasviel/Annotators/resolve/main/ZoeD_M12_N.pt"
    local_path: "/comfyui/custom_nodes/comfyui_controlnet_aux/ckpts/lllyasviel/Annotators/ZoeD_M12_N.pt"
  - type: hf_snapshot
    repo_id: "DIAMONIK7777/antelopev2"
    local_dir: "insightface/models/antelopev2"

pip_packages:
  - "safetensors"
  - "pybase64==1.3.2"
  - "onnxruntime-gpu@https://huggingface.co/anyisalin/bookmark/resolve/main/onnxruntime_gpu-1.17.0-cp310-cp310-linux_x86_64.whl"
```



### Profile Example

```python
from comfy_buildkit import ComfyBuildkit


b = ComfyBuildkit() \
  .pip_install("numpy<2") \
  .models.hf_file(
    repo_id="Linaqruf/anything-v3.0",
    filename="anything-v3-fp16-pruned.safetensors",
    local_path="checkpoints/anything-v3-fp16-pruned.safetensors"
  )
  # .models.civitai(
  #     model_id=680915,
  #     local_path="checkpoints",
  #     # token=""
  # )
```

### Complex Depends

```python
from comfy_buildkit import ComfyBuildkit

b = ComfyBuildkit() \
  .pip_install("numpy<2") \
  .custom_node("https://github.com/WASasquatch/was-node-suite-comfyui", "-") \
  .custom_node("https://github.com/TencentQQGYLab/ComfyUI-ELLA", "-") \
  .custom_node("https://github.com/yolain/ComfyUI-Easy-Use", "-") \
  .custom_node("https://github.com/huchenlei/ComfyUI-IC-Light-Native", "-") \
  .custom_node("https://github.com/blepping/comfyui_jankhidiffusion", "-") \
  .custom_node("https://github.com/stavsap/comfyui-ollama", "-") \
  .custom_node("https://github.com/cubiq/ComfyUI_essentials", "-") \
  .models.hf_file(
    repo_id="Linaqruf/anything-v3.0",
    filename="anything-v3-fp16-pruned.safetensors",
    local_path="checkpoints/anything-v3-fp16-pruned.safetensors"
  )
```