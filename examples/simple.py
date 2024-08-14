from comfy_buildkit import ComfyBuildkit


# generate depends 
# python3 ./custom_nodes/ComfyUI-Manager/cm-cli.py  deps-in-workflow --workflow ./workflow.json  --output depends.json --mode local
b = ComfyBuildkit() \
  .pip_install("numpy<2") \
  .custom_node_from_depends( # also can pass ./depends.json
    {
    "custom_nodes": {
        "https://github.com/WASasquatch/was-node-suite-comfyui": {
            "state": "installed",
            "hash": "-"
        },
        "https://github.com/TencentQQGYLab/ComfyUI-ELLA": {
            "state": "installed",
            "hash": "-"
        },
        "https://github.com/KoreTeknology/ComfyUI-Universal-Styler": {
            "state": "not-installed",
            "hash": "-"
        },
        "https://github.com/yolain/ComfyUI-Easy-Use": {
            "state": "installed",
            "hash": "-"
        },
        "https://github.com/huchenlei/ComfyUI-IC-Light-Native": {
            "state": "installed",
            "hash": "-"
        },
        "https://github.com/blepping/comfyui_jankhidiffusion": {
            "state": "installed",
            "hash": "-"
        },
        "https://github.com/stavsap/comfyui-ollama": {
            "state": "installed",
            "hash": "-"
        },
        "https://github.com/cubiq/ComfyUI_essentials": {
            "state": "installed",
            "hash": "-"
        }
    },
      "unknown_nodes": []
    }
  ) \
  .models.hf_file(
    repo_id="Linaqruf/anything-v3.0",
    filename="anything-v3-fp16-pruned.safetensors",
    local_path="checkpoints/anything-v3-fp16-pruned.safetensors"
  )