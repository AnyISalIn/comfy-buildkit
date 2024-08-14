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
