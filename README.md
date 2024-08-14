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
$ comfy-buildkit -l https://raw.githubusercontent.com/AnyISalIn/comfy-buildkit/main/examples/simple.py
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