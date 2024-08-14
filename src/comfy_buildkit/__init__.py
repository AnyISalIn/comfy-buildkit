import os
import json
import tempfile
import logging
from shlex import split
from typing import List, Tuple, Dict, Any, Optional, Union
from abc import ABC, abstractmethod
import hashlib
import urllib.parse
import re
import requests
import importlib.resources as pkg_resources
import shutil

class DownloadOperation(ABC):
    @abstractmethod
    def get_dockerfile_commands(self) -> List[str]:
        pass

    @abstractmethod
    def get_output_path(self) -> str:
        pass

class HFFileDownload(DownloadOperation):
    def __init__(self, repo_id: str, filename: str, local_path: str, revision: Optional[str] = None, token: Optional[str] = None):
        self.repo_id = repo_id
        self.filename = filename
        self.local_path = os.path.join('/comfyui/models', local_path) if not local_path.startswith('/') else local_path
        self.revision = revision
        self.token = token

    def get_dockerfile_commands(self) -> List[str]:
        download_args = f"repo_id='{self.repo_id}', filename='{self.filename}', local_dir='{os.path.dirname(self.local_path)}'"
        if self.revision:
            download_args += f", revision='{self.revision}'"
        if self.token:
            download_args += f", token='{self.token}'"
        
        return [f"RUN python -c \"from huggingface_hub import hf_hub_download; hf_hub_download({download_args})\""]

    def get_output_path(self) -> str:
        return self.local_path

class HFSnapshotDownload(DownloadOperation):
    def __init__(self, repo_id: str, local_dir: str, revision: Optional[str] = None, ignore_patterns: Optional[List[str]] = None, token: Optional[str] = None):
        self.repo_id = repo_id
        self.local_dir = os.path.join('/comfy/models', local_dir) if not local_dir.startswith('/') else local_dir
        self.revision = revision
        self.ignore_patterns = ignore_patterns
        self.token = token

    def get_dockerfile_commands(self) -> List[str]:
        download_args = f"repo_id='{self.repo_id}', local_dir='{self.local_dir}'"
        if self.revision:
            download_args += f", revision='{self.revision}'"
        if self.ignore_patterns:
            patterns = ", ".join(f"'{pattern}'" for pattern in self.ignore_patterns)
            download_args += f", ignore_patterns=[{patterns}]"
        if self.token:
            download_args += f", token='{self.token}'"
        
        return [f"RUN python -c \"from huggingface_hub import snapshot_download; snapshot_download({download_args})\""]

    def get_output_path(self) -> str:
        return self.local_dir

class URLDownload(DownloadOperation):
    def __init__(self, url: str, local_path: str):
        self.url = url
        self.local_path = os.path.join('/comfy/models', local_path) if not local_path.startswith('/') else local_path

    def get_dockerfile_commands(self) -> List[str]:
        return [f"ADD {self.url} {self.local_path}"]

    def get_output_path(self) -> str:
        return self.local_path

class CivitaiDownload(DownloadOperation):
    def __init__(self, model_id: str, local_path: str, token: Optional[str] = None, model_name: Optional[str] = None):
        self.model_id = model_id
        self.local_dir = os.path.join('/comfyui/models', os.path.dirname(local_path)) if not local_path.startswith('/') else os.path.dirname(local_path)
        self.token = token
        self.model_name = model_name
        self.file_name = self._get_file_name()
        self.local_path = os.path.join(self.local_dir, self.file_name)

    def _get_file_name(self) -> str:
        if self.model_name:
            return self.model_name

        api_url = f"https://civitai.com/api/download/models/{self.model_id}"
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        # Dry run to get the pre-signed S3 URL
        download_response = requests.head(api_url, headers=headers, allow_redirects=False)
        download_response.raise_for_status()
        
        # Extract filename from the 'location' header
        location = download_response.headers.get('location')
        if location:
            parsed_url = urllib.parse.urlparse(location)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            content_disposition = query_params.get('response-content-disposition', [''])[0]
            if content_disposition:
                filename = re.findall("filename=?(.+)?", content_disposition)[0]
            else:
                filename = os.path.basename(parsed_url.path)
        else:
            filename = os.path.basename(download_response.url)
        
        # Remove leading/trailing quotes and spaces from the filename
        filename = filename.replace('"', "")
        
        return filename

    def get_dockerfile_commands(self) -> List[str]:
        download_url = f"https://civitai.com/api/download/models/{self.model_id}"
        if self.token:
            download_url += f"?token={self.token}"
        return [
            f"RUN mkdir -p {self.local_dir}",
            f"RUN wget -O {self.local_path} '{download_url}' || (echo 'Failed to download model {self.model_id}' && exit 1)"
        ]

    def get_output_path(self) -> str:
        return self.local_path

class Models:
    def __init__(self, buildkit: 'ComfyBuildkit'):
        self.buildkit = buildkit

    def hf_file(self, repo_id: str, filename: str, local_path: str, revision: Optional[str] = None, token: Optional[str] = None) -> 'ComfyBuildkit':
        """Add a Hugging Face file download to the build process."""
        self.buildkit.download_operations.append(HFFileDownload(repo_id, filename, local_path, revision, token))
        return self.buildkit

    def hf_snapshot(self, repo_id: str, local_dir: str, revision: Optional[str] = None, ignore_patterns: Optional[List[str]] = None, token: Optional[str] = None) -> 'ComfyBuildkit':
        """Add a Hugging Face model snapshot download to the build process."""
        self.buildkit.download_operations.append(HFSnapshotDownload(repo_id, local_dir, revision, ignore_patterns, token))
        return self.buildkit

    def wget(self, url: str, local_path: str) -> 'ComfyBuildkit':
        """Add a direct URL download to the build process."""
        self.buildkit.download_operations.append(URLDownload(url, local_path))
        return self.buildkit

    def civitai(self, model_id: int, local_path: str, token: Optional[str] = None, model_name: Optional[str] = None) -> 'ComfyBuildkit':
        """Add a Civitai model download to the build process."""
        self.buildkit.download_operations.append(CivitaiDownload(model_id, local_path, token, model_name))
        return self.buildkit

class ComfyBuildkit:
    def __init__(self, base_image: str = "ubuntu:22.04", 
                 python_version: str = "3.11", 
                 comfyui_repo: str = "https://github.com/comfyanonymous/ComfyUI.git", 
                 comfyui_revision: str = "master",
                 manager_repo: str = "https://github.com/ltdrdata/ComfyUI-Manager.git",
                 manager_revision: str = "8897b9e0f77d85dc02610784e4c357329dd04f4f") -> None:
        self.base_image: str = base_image
        self.python_version: str = python_version
        self.custom_nodes: List[Tuple[str, str]] = []
        self.comfyui_repo: str = comfyui_repo
        self.comfyui_revision: str = comfyui_revision
        self.temp_dir: str = tempfile.mkdtemp()
        self.comfy_install_data: Dict[str, str] = {
            "comfy_version": comfyui_revision,
            "repo": comfyui_repo,
            "manager_version": manager_revision,
            "manager_repo": manager_repo
        }
        self.project_root: str = os.getcwd()  # Current working directory
        self.hf_hub_installed: bool = False
        self.system_stage: List[str] = []
        self.user_stage: List[str] = []
        self.download_operations: List[DownloadOperation] = []
        self.models = Models(self)
        self._copy_template_to_temp()

    def _find_template_dir(self) -> str:
        """Find the directory containing the 'template' folder within the package."""
        try:
            # Get the directory containing the template files
            template_dir = pkg_resources.files('comfy_buildkit').joinpath('template')
            return str(template_dir)
        except ImportError:
            raise FileNotFoundError("Could not find 'template' folder in the package")

    def _copy_template_to_temp(self):
        """Copy all template files to the temporary directory."""
        template_dir = self._find_template_dir()
        import pdb; pdb.set_trace()
        for item in os.listdir(template_dir):
            s = os.path.join(template_dir, item)
            d = os.path.join(self.temp_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)

    # Internal methods for system commands
    def _run(self, command: str) -> None:
        self.system_stage.append(f"RUN {command}")

    def _copy(self, *args: str) -> None:
        if len(args) < 2:
            raise ValueError("COPY requires at least one source and one destination")
        
        sources: Tuple[str, ...] = args[:-1]
        dest: str = args[-1]
        
        for source in sources:
            temp_path = os.path.join(self.temp_dir, source)
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            
            try:
                # Try to get the file from the package resources
                template_path = pkg_resources.files('comfy_buildkit').joinpath('template', source)
                if template_path.is_file():
                    shutil.copy2(str(template_path), temp_path)
                else:
                    raise FileNotFoundError(f"Source file not found in template: {source}")
            except ImportError:
                # If pkg_resources.files() is not available, fall back to the old method
                template_dir = self._find_template_dir()
                template_path = os.path.join(template_dir, source)
                if os.path.exists(template_path):
                    shutil.copy2(template_path, temp_path)
                else:
                    raise FileNotFoundError(f"Source file not found in template: {source}")
        
        self.system_stage.append(f"COPY {' '.join(sources)} {dest}")

    def _env(self, **kwargs: str) -> None:
        for key, value in kwargs.items():
            self.system_stage.append(f"ENV {key}={value}")

    def _add(self, url: str, dest: str) -> None:
        self.system_stage.append(f"ADD {url} {dest}")

    def _cmd(self, command: Union[str, List[str]]) -> None:
        if isinstance(command, list):
            cmd_str: str = ', '.join(f'"{item}"' for item in command)
            self.system_stage.append(f"CMD [{cmd_str}]")
        else:
            cmd_list: List[str] = split(command)
            cmd_str: str = ', '.join(f'"{item}"' for item in cmd_list)
            self.system_stage.append(f"CMD [{cmd_str}]")

    def _entrypoint(self, command: Union[str, List[str]]) -> None:
        if isinstance(command, list):
            entrypoint_str: str = ', '.join(f'"{item}"' for item in command)
            self.system_stage.append(f"ENTRYPOINT [{entrypoint_str}]")
        else:
            self.system_stage.append(f'ENTRYPOINT ["{command}"]')

    def _file_contents(self, content: Union[str, Dict[str, Any]], remote_path: str, json_dump: bool = False) -> None:
        temp_path: str = os.path.join(self.temp_dir, remote_path.lstrip('/'))
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        with open(temp_path, "w") as f:
            if json_dump:
                json.dump(content, f, indent=2)
            else:
                f.write(content)
        self._copy(remote_path, remote_path)

    # Existing methods for user commands (unchanged)
    def run(self, command: str) -> 'ComfyBuildkit':
        """Add a RUN command to the Dockerfile."""
        self.user_stage.append(f"RUN {command}")
        return self

    def copy(self, *args: str) -> 'ComfyBuildkit':
        """Add a COPY command to the Dockerfile and copy the files to the build context."""
        if len(args) < 2:
            raise ValueError("COPY requires at least one source and one destination")
        
        sources: Tuple[str, ...] = args[:-1]
        dest: str = args[-1]
        
        for source in sources:
            source_path = os.path.join(self.project_root, source)
            if os.path.exists(source_path):
                import shutil
                shutil.copy2(source_path, os.path.join(self.temp_dir, os.path.basename(source)))
            else:
                raise FileNotFoundError(f"Source file not found: {source}")
        
        sources_str: str = " ".join(os.path.basename(s) for s in sources)
        self.user_stage.append(f"COPY {sources_str} {dest}")
        return self

    def env(self, **kwargs: str) -> 'ComfyBuildkit':
        """Set environment variables in the Dockerfile."""
        for key, value in kwargs.items():
            self.user_stage.append(f"ENV {key}={value}")
        return self

    def workdir(self, path: str) -> 'ComfyBuildkit':
        """Set working directory in the Dockerfile."""
        self.user_stage.append(f"WORKDIR {path}")
        return self

    def entrypoint(self, command: Union[str, List[str]]) -> 'ComfyBuildkit':
        """Set the entrypoint for the Dockerfile."""
        if isinstance(command, list):
            entrypoint_str: str = ', '.join(f'"{item}"' for item in command)
            self.user_stage.append(f"ENTRYPOINT [{entrypoint_str}]")
        else:
            self.user_stage.append(f'ENTRYPOINT ["{command}"]')
        return self

    def cmd(self, command: Union[str, List[str]]) -> 'ComfyBuildkit':
        """Set the default command for the Dockerfile."""
        if isinstance(command, list):
            cmd_str: str = ', '.join(f'"{item}"' for item in command)
            self.user_stage.append(f"CMD [{cmd_str}]")
        else:
            self.user_stage.append(f'CMD ["{command}"]')
        return self

    def pip_install(self, *packages: str) -> 'ComfyBuildkit':
        """Install Python packages using pip."""
        packages_str: str = " ".join(f"'{pkg}'" for pkg in packages)
        self.user_stage.append(f"RUN uv pip install --system --no-cache-dir {packages_str}")
        return self

    def apt_install(self, *packages: str) -> 'ComfyBuildkit':
        """Install system packages using apt-get."""
        packages_str: str = " ".join(packages)
        self.user_stage.append(f"RUN apt-get update && apt-get install -y {packages_str} && apt-get clean && rm -rf /var/lib/apt/lists/*")
        return self

    def copy_local_file(self, local_path: str, remote_path: str) -> 'ComfyBuildkit':
        """Copy a local file to the Docker context and add a COPY instruction."""
        temp_path: str = os.path.join(self.temp_dir, remote_path.lstrip('/'))
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        shutil.copy2(local_path, temp_path)
        self.user_stage.append(f"COPY {remote_path} {remote_path}")
        return self

    def file_contents(self, content: Union[str, Dict[str, Any]], remote_path: str, json_dump: bool = False) -> 'ComfyBuildkit':
        """Create a file with given contents in the Docker context and add a COPY instruction."""
        temp_path: str = os.path.join(self.temp_dir, remote_path.lstrip('/'))
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        with open(temp_path, "w") as f:
            if json_dump:
                json.dump(content, f, indent=2)
            else:
                f.write(content)
        self.user_stage.append(f"COPY {remote_path} {remote_path}")
        return self
    
    def custom_node_from_depends(self, depends_data: Union[str, Dict[str, Any]]) -> 'ComfyBuildkit':
        """Add custom nodes from a depends.json-like structure."""
        if isinstance(depends_data, str):
            # If it's a file path, read the JSON file
            with open(depends_data, 'r') as f:
                depends_data = json.load(f)
        elif not isinstance(depends_data, dict):
            # If it's not a dict, try to parse it as JSON
            depends_data = json.loads(depends_data)

        custom_nodes = depends_data.get("custom_nodes", {})
        for url, node_info in custom_nodes.items():
            if node_info.get("state") == "installed":
                revision = node_info.get("hash", "-")
                if revision == "-" or not revision:
                    revision = "main"  # Use default revision if hash is invalid or missing
                self.custom_nodes.append((url, revision))
        return self

    def custom_node(self, url: str, revision: str = "main") -> 'ComfyBuildkit':
        """Add a custom node to be installed."""
        self.custom_nodes.append((url, revision))
        return self

    def add(self, url: str, dest: str) -> 'ComfyBuildkit':
        """Add an ADD command to download a file to the specified directory or file."""
        self.user_stage.append(f"ADD {url} {dest}")
        return self

    def generate_base_dockerfile(self) -> str:
        """Generate the base Dockerfile with system-level installations."""
        self.system_stage = [f"FROM {self.base_image} AS system_stage"]
        self._env(DEBIAN_FRONTEND="noninteractive", PIP_PREFER_BINARY="1", PYTHONUNBUFFERED="1")
        self._run(f"apt-get update && apt-get install -y python{self.python_version} python3-pip python-is-python3 wget git libgl1-mesa-glx libglib2.0-0 libsm6 libxrender1 libxext6 ffmpeg && apt-get clean && rm -rf /var/lib/apt/lists/*")
        self._run(f"pip install uv")
        
        self._install_comfyui()
        if self.custom_nodes:
            self._install_custom_nodes()
        
        self._cmd("python /comfyui/main.py --listen 0.0.0.0")
        
        return "\n\n".join(self.system_stage) + "\n"

    def _install_comfyui(self) -> None:
        self._file_contents(self.comfy_install_data, "10-install-comfy.json", json_dump=True)
        self._copy("10-install-comfy.py", "/10-install-comfy.py")
        self._run("python3 /10-install-comfy.py")

    def _install_custom_nodes(self) -> None:
        node_install_data: List[Dict[str, str]] = [
            {"url": url, "hash": revision, "repo_name": url.split('/')[-1].replace('.git', '')}
            for url, revision in self.custom_nodes
        ]
        self._file_contents(node_install_data, "20-install-nodes.json", json_dump=True)
        self._copy("20-install-nodes.py", "/20-install-nodes.py")
        self._run("python3 /20-install-nodes.py")

    def generate_download_dockerfile(self) -> str:
        """Generate the Dockerfile for the download layers."""
        download_stages = []
        
        if self.download_operations:
            download_stages.append("RUN pip install huggingface_hub")
            
            for operation in self.download_operations:
                # Generate a unique hash for this operation
                operation_hash = hashlib.md5(str(operation.__dict__).encode()).hexdigest()[:8]
                stage_name = f"download_{operation_hash}"
                
                download_stages.append(f"FROM system_stage AS {stage_name}")
                download_stages.extend(operation.get_dockerfile_commands())
        
        return "\n".join(download_stages) + "\n"

    def generate_user_dockerfile(self) -> str:
        """Generate the Dockerfile with user commands."""
        return "\n".join(self.user_stage) + "\n"

    def generate_dockerfile(self):
        """Generate the final Dockerfile by concatenating all stages."""
        stages = [
            self.generate_base_dockerfile(),
            self.generate_download_dockerfile(),
            "FROM system_stage AS user_stage\n" + self.generate_user_dockerfile(),
            "FROM user_stage AS final_stage\n"
        ]

        for operation in self.download_operations:
            operation_hash = hashlib.md5(str(operation.__dict__).encode()).hexdigest()[:8]
            stage_name = f"download_{operation_hash}"
            output_path = operation.get_output_path()
            stages[-1] += f"COPY --from={stage_name} {output_path} {output_path}\n"

        return "\n".join(stages)

    def save_dockerfile(self):
        system_dockerfile_path = os.path.join(self.temp_dir, "Dockerfile.system")
        user_dockerfile_path = os.path.join(self.temp_dir, "Dockerfile.user")
        download_dockerfile_path = os.path.join(self.temp_dir, "Dockerfile.download")
        final_dockerfile_path = os.path.join(self.temp_dir, "Dockerfile")

        with open(system_dockerfile_path, "w") as f:
            f.write(self.generate_base_dockerfile())
        with open(user_dockerfile_path, "w") as f:
            f.write(self.generate_user_dockerfile())
        with open(download_dockerfile_path, "w") as f:
            f.write(self.generate_download_dockerfile())
        with open(final_dockerfile_path, "w") as f:
            f.write(self.generate_dockerfile())

        logging.info(f"System stage Dockerfile saved to {system_dockerfile_path}")
        logging.info(f"User stage Dockerfile saved to {user_dockerfile_path}")
        logging.info(f"Download stage Dockerfile saved to {download_dockerfile_path}")
        logging.info(f"Final multi-stage Dockerfile saved to {final_dockerfile_path}")

        logging.info(f"\nTemporary directory used: {self.temp_dir}")
        logging.info("Remember to clean up this directory after building the Docker image.")

    def cleanup(self):
        """Clean up the temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir)
        logging.info(f"Cleaned up temporary directory: {self.temp_dir}")

    def enter_context(self):
        """Enter the Docker build context."""
        return self.temp_dir

    def get_context_dir(self):
        """Return the Docker build context directory."""
import os
import json
import tempfile
import logging
from shlex import split
from typing import List, Tuple, Dict, Any, Optional, Union
from abc import ABC, abstractmethod
import hashlib
import urllib.parse
import re
import requests
import importlib.resources as pkg_resources
import shutil

class DownloadOperation(ABC):
    @abstractmethod
    def get_dockerfile_commands(self) -> List[str]:
        pass

    @abstractmethod
    def get_output_path(self) -> str:
        pass

class HFFileDownload(DownloadOperation):
    def __init__(self, repo_id: str, filename: str, local_path: str, revision: Optional[str] = None, token: Optional[str] = None):
        self.repo_id = repo_id
        self.filename = filename
        self.local_path = os.path.join('/comfyui/models', local_path) if not local_path.startswith('/') else local_path
        self.revision = revision
        self.token = token

    def get_dockerfile_commands(self) -> List[str]:
        download_args = f"repo_id='{self.repo_id}', filename='{self.filename}', local_dir='{os.path.dirname(self.local_path)}'"
        if self.revision:
            download_args += f", revision='{self.revision}'"
        if self.token:
            download_args += f", token='{self.token}'"
        
        return [f"RUN python -c \"from huggingface_hub import hf_hub_download; hf_hub_download({download_args})\""]

    def get_output_path(self) -> str:
        return self.local_path

class HFSnapshotDownload(DownloadOperation):
    def __init__(self, repo_id: str, local_dir: str, revision: Optional[str] = None, ignore_patterns: Optional[List[str]] = None, token: Optional[str] = None):
        self.repo_id = repo_id
        self.local_dir = os.path.join('/comfy/models', local_dir) if not local_dir.startswith('/') else local_dir
        self.revision = revision
        self.ignore_patterns = ignore_patterns
        self.token = token

    def get_dockerfile_commands(self) -> List[str]:
        download_args = f"repo_id='{self.repo_id}', local_dir='{self.local_dir}'"
        if self.revision:
            download_args += f", revision='{self.revision}'"
        if self.ignore_patterns:
            patterns = ", ".join(f"'{pattern}'" for pattern in self.ignore_patterns)
            download_args += f", ignore_patterns=[{patterns}]"
        if self.token:
            download_args += f", token='{self.token}'"
        
        return [f"RUN python -c \"from huggingface_hub import snapshot_download; snapshot_download({download_args})\""]

    def get_output_path(self) -> str:
        return self.local_dir

class URLDownload(DownloadOperation):
    def __init__(self, url: str, local_path: str):
        self.url = url
        self.local_path = os.path.join('/comfy/models', local_path) if not local_path.startswith('/') else local_path

    def get_dockerfile_commands(self) -> List[str]:
        return [f"ADD {self.url} {self.local_path}"]

    def get_output_path(self) -> str:
        return self.local_path

class CivitaiDownload(DownloadOperation):
    def __init__(self, model_id: str, local_path: str, token: Optional[str] = None, model_name: Optional[str] = None):
        self.model_id = model_id
        self.local_dir = os.path.join('/comfyui/models', os.path.dirname(local_path)) if not local_path.startswith('/') else os.path.dirname(local_path)
        self.token = token
        self.model_name = model_name
        self.file_name = self._get_file_name()
        self.local_path = os.path.join(self.local_dir, self.file_name)

    def _get_file_name(self) -> str:
        if self.model_name:
            return self.model_name

        api_url = f"https://civitai.com/api/download/models/{self.model_id}"
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        # Dry run to get the pre-signed S3 URL
        download_response = requests.head(api_url, headers=headers, allow_redirects=False)
        download_response.raise_for_status()
        
        # Extract filename from the 'location' header
        location = download_response.headers.get('location')
        if location:
            parsed_url = urllib.parse.urlparse(location)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            content_disposition = query_params.get('response-content-disposition', [''])[0]
            if content_disposition:
                filename = re.findall("filename=?(.+)?", content_disposition)[0]
            else:
                filename = os.path.basename(parsed_url.path)
        else:
            filename = os.path.basename(download_response.url)
        
        # Remove leading/trailing quotes and spaces from the filename
        filename = filename.replace('"', "")
        
        return filename

    def get_dockerfile_commands(self) -> List[str]:
        download_url = f"https://civitai.com/api/download/models/{self.model_id}"
        if self.token:
            download_url += f"?token={self.token}"
        return [
            f"RUN mkdir -p {self.local_dir}",
            f"RUN wget -O {self.local_path} '{download_url}' || (echo 'Failed to download model {self.model_id}' && exit 1)"
        ]

    def get_output_path(self) -> str:
        return self.local_path

class Models:
    def __init__(self, buildkit: 'ComfyBuildkit'):
        self.buildkit = buildkit

    def hf_file(self, repo_id: str, filename: str, local_path: str, revision: Optional[str] = None, token: Optional[str] = None) -> 'ComfyBuildkit':
        """Add a Hugging Face file download to the build process."""
        self.buildkit.download_operations.append(HFFileDownload(repo_id, filename, local_path, revision, token))
        return self.buildkit

    def hf_snapshot(self, repo_id: str, local_dir: str, revision: Optional[str] = None, ignore_patterns: Optional[List[str]] = None, token: Optional[str] = None) -> 'ComfyBuildkit':
        """Add a Hugging Face model snapshot download to the build process."""
        self.buildkit.download_operations.append(HFSnapshotDownload(repo_id, local_dir, revision, ignore_patterns, token))
        return self.buildkit

    def wget(self, url: str, local_path: str) -> 'ComfyBuildkit':
        """Add a direct URL download to the build process."""
        self.buildkit.download_operations.append(URLDownload(url, local_path))
        return self.buildkit

    def civitai(self, model_id: int, local_path: str, token: Optional[str] = None, model_name: Optional[str] = None) -> 'ComfyBuildkit':
        """Add a Civitai model download to the build process."""
        self.buildkit.download_operations.append(CivitaiDownload(model_id, local_path, token, model_name))
        return self.buildkit

class ComfyBuildkit:
    def __init__(self, base_image: str = "ubuntu:22.04", 
                 python_version: str = "3.11", 
                 comfyui_repo: str = "https://github.com/comfyanonymous/ComfyUI.git", 
                 comfyui_revision: str = "master",
                 manager_repo: str = "https://github.com/ltdrdata/ComfyUI-Manager.git",
                 manager_revision: str = "8897b9e0f77d85dc02610784e4c357329dd04f4f") -> None:
        self.base_image: str = base_image
        self.python_version: str = python_version
        self.custom_nodes: List[Tuple[str, str]] = []
        self.comfyui_repo: str = comfyui_repo
        self.comfyui_revision: str = comfyui_revision
        self.temp_dir: str = tempfile.mkdtemp()
        self.comfy_install_data: Dict[str, str] = {
            "comfy_version": comfyui_revision,
            "repo": comfyui_repo,
            "manager_version": manager_revision,
            "manager_repo": manager_repo
        }
        self.project_root: str = os.getcwd()  # Current working directory
        self.hf_hub_installed: bool = False
        self.system_stage: List[str] = []
        self.user_stage: List[str] = []
        self.download_operations: List[DownloadOperation] = []
        self.models = Models(self)

    def _find_template_dir(self) -> str:
        """Find the directory containing the 'template' folder within the package."""
        try:
            # Get the directory containing the template files
            template_dir = pkg_resources.files('comfy_buildkit').joinpath('template')
            return str(template_dir)
        except ImportError:
            raise FileNotFoundError("Could not find 'template' folder in the package")

    # Internal methods for system commands
    def _run(self, command: str) -> None:
        self.system_stage.append(f"RUN {command}")

    def _copy(self, *args: str) -> None:
        if len(args) < 2:
            raise ValueError("COPY requires at least one source and one destination")
        
        sources: Tuple[str, ...] = args[:-1]
        dest: str = args[-1]
        
        for source in sources:
            temp_path = os.path.join(self.temp_dir, source)
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            
            try:
                # Try to get the file from the package resources
                template_path = pkg_resources.files('comfy_buildkit').joinpath('template', source)
                if template_path.is_file():
                    shutil.copy2(str(template_path), temp_path)
                else:
                    raise FileNotFoundError(f"Source file not found in template: {source}")
            except ImportError:
                # If pkg_resources.files() is not available, fall back to the old method
                template_dir = self._find_template_dir()
                template_path = os.path.join(template_dir, source)
                if os.path.exists(template_path):
                    shutil.copy2(template_path, temp_path)
                else:
                    raise FileNotFoundError(f"Source file not found in template: {source}")
        
        self.system_stage.append(f"COPY {' '.join(sources)} {dest}")

    def _env(self, **kwargs: str) -> None:
        for key, value in kwargs.items():
            self.system_stage.append(f"ENV {key}={value}")

    def _add(self, url: str, dest: str) -> None:
        self.system_stage.append(f"ADD {url} {dest}")

    def _cmd(self, command: Union[str, List[str]]) -> None:
        if isinstance(command, list):
            cmd_str: str = ', '.join(f'"{item}"' for item in command)
            self.system_stage.append(f"CMD [{cmd_str}]")
        else:
            cmd_list: List[str] = split(command)
            cmd_str: str = ', '.join(f'"{item}"' for item in cmd_list)
            self.system_stage.append(f"CMD [{cmd_str}]")

    def _entrypoint(self, command: Union[str, List[str]]) -> None:
        if isinstance(command, list):
            entrypoint_str: str = ', '.join(f'"{item}"' for item in command)
            self.system_stage.append(f"ENTRYPOINT [{entrypoint_str}]")
        else:
            self.system_stage.append(f'ENTRYPOINT ["{command}"]')

    def _file_contents(self, content: Union[str, Dict[str, Any]], remote_path: str, json_dump: bool = False) -> None:
        temp_path: str = os.path.join(self.temp_dir, remote_path.lstrip('/'))
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        with open(temp_path, "w") as f:
            if json_dump:
                json.dump(content, f, indent=2)
            else:
                f.write(content)
        self._copy(remote_path, remote_path)

    # Existing methods for user commands (unchanged)
    def run(self, command: str) -> 'ComfyBuildkit':
        """Add a RUN command to the Dockerfile."""
        self.user_stage.append(f"RUN {command}")
        return self

    def copy(self, *args: str) -> 'ComfyBuildkit':
        """Add a COPY command to the Dockerfile and copy the files to the build context."""
        if len(args) < 2:
            raise ValueError("COPY requires at least one source and one destination")
        
        sources: Tuple[str, ...] = args[:-1]
        dest: str = args[-1]
        
        for source in sources:
            source_path = os.path.join(self.project_root, source)
            if os.path.exists(source_path):
                import shutil
                shutil.copy2(source_path, os.path.join(self.temp_dir, os.path.basename(source)))
            else:
                raise FileNotFoundError(f"Source file not found: {source}")
        
        sources_str: str = " ".join(os.path.basename(s) for s in sources)
        self.user_stage.append(f"COPY {sources_str} {dest}")
        return self

    def env(self, **kwargs: str) -> 'ComfyBuildkit':
        """Set environment variables in the Dockerfile."""
        for key, value in kwargs.items():
            self.user_stage.append(f"ENV {key}={value}")
        return self

    def workdir(self, path: str) -> 'ComfyBuildkit':
        """Set working directory in the Dockerfile."""
        self.user_stage.append(f"WORKDIR {path}")
        return self

    def entrypoint(self, command: Union[str, List[str]]) -> 'ComfyBuildkit':
        """Set the entrypoint for the Dockerfile."""
        if isinstance(command, list):
            entrypoint_str: str = ', '.join(f'"{item}"' for item in command)
            self.user_stage.append(f"ENTRYPOINT [{entrypoint_str}]")
        else:
            self.user_stage.append(f'ENTRYPOINT ["{command}"]')
        return self

    def cmd(self, command: Union[str, List[str]]) -> 'ComfyBuildkit':
        """Set the default command for the Dockerfile."""
        if isinstance(command, list):
            cmd_str: str = ', '.join(f'"{item}"' for item in command)
            self.user_stage.append(f"CMD [{cmd_str}]")
        else:
            self.user_stage.append(f'CMD ["{command}"]')
        return self

    def pip_install(self, *packages: str) -> 'ComfyBuildkit':
        """Install Python packages using pip."""
        packages_str: str = " ".join(f"'{pkg}'" for pkg in packages)
        self.user_stage.append(f"RUN uv pip install --system --no-cache-dir {packages_str}")
        return self

    def apt_install(self, *packages: str) -> 'ComfyBuildkit':
        """Install system packages using apt-get."""
        packages_str: str = " ".join(packages)
        self.user_stage.append(f"RUN apt-get update && apt-get install -y {packages_str} && apt-get clean && rm -rf /var/lib/apt/lists/*")
        return self

    def copy_local_file(self, local_path: str, remote_path: str) -> 'ComfyBuildkit':
        """Copy a local file to the Docker context and add a COPY instruction."""
        temp_path: str = os.path.join(self.temp_dir, remote_path.lstrip('/'))
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        shutil.copy2(local_path, temp_path)
        self.user_stage.append(f"COPY {remote_path} {remote_path}")
        return self

    def file_contents(self, content: Union[str, Dict[str, Any]], remote_path: str, json_dump: bool = False) -> 'ComfyBuildkit':
        """Create a file with given contents in the Docker context and add a COPY instruction."""
        temp_path: str = os.path.join(self.temp_dir, remote_path.lstrip('/'))
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        with open(temp_path, "w") as f:
            if json_dump:
                json.dump(content, f, indent=2)
            else:
                f.write(content)
        self.user_stage.append(f"COPY {remote_path} {remote_path}")
        return self
    
    def custom_node_from_depends(self, depends_data: Union[str, Dict[str, Any]]) -> 'ComfyBuildkit':
        """Add custom nodes from a depends.json-like structure."""
        if isinstance(depends_data, str):
            # If it's a file path, read the JSON file
            with open(depends_data, 'r') as f:
                depends_data = json.load(f)
        elif not isinstance(depends_data, dict):
            # If it's not a dict, try to parse it as JSON
            depends_data = json.loads(depends_data)

        custom_nodes = depends_data.get("custom_nodes", {})
        for url, node_info in custom_nodes.items():
            if node_info.get("state") == "installed":
                revision = node_info.get("hash", "-")
                if revision == "-" or not revision:
                    revision = "main"  # Use default revision if hash is invalid or missing
                self.custom_nodes.append((url, revision))
        return self

    def custom_node(self, url: str, revision: str = "main") -> 'ComfyBuildkit':
        """Add a custom node to be installed."""
        self.custom_nodes.append((url, revision))
        return self

    def add(self, url: str, dest: str) -> 'ComfyBuildkit':
        """Add an ADD command to download a file to the specified directory or file."""
        self.user_stage.append(f"ADD {url} {dest}")
        return self

    def generate_base_dockerfile(self) -> str:
        """Generate the base Dockerfile with system-level installations."""
        self.system_stage = [f"FROM {self.base_image} AS system_stage"]
        self._env(DEBIAN_FRONTEND="noninteractive", PIP_PREFER_BINARY="1", PYTHONUNBUFFERED="1")
        self._run(f"apt-get update && apt-get install -y python{self.python_version} python3-pip python-is-python3 wget git libgl1-mesa-glx libglib2.0-0 libsm6 libxrender1 libxext6 ffmpeg && apt-get clean && rm -rf /var/lib/apt/lists/*")
        self._run(f"pip install uv")
        
        self._install_comfyui()
        if self.custom_nodes:
            self._install_custom_nodes()
        
        self._cmd("python /comfyui/main.py --listen 0.0.0.0")
        
        return "\n\n".join(self.system_stage) + "\n"

    def _install_comfyui(self) -> None:
        self._file_contents(self.comfy_install_data, "10-install-comfy.json", json_dump=True)
        self._copy("10-install-comfy.py", "/10-install-comfy.py")
        self._run("python3 /10-install-comfy.py")

    def _install_custom_nodes(self) -> None:
        node_install_data: List[Dict[str, str]] = [
            {"url": url, "hash": revision, "repo_name": url.split('/')[-1].replace('.git', '')}
            for url, revision in self.custom_nodes
        ]
        self._file_contents(node_install_data, "20-install-nodes.json", json_dump=True)
        self._copy("20-install-nodes.py", "/20-install-nodes.py")
        self._run("python3 /20-install-nodes.py")

    def generate_download_dockerfile(self) -> str:
        """Generate the Dockerfile for the download layers."""
        download_stages = []
        
        if self.download_operations:
            download_stages.append("RUN pip install huggingface_hub")
            
            for operation in self.download_operations:
                # Generate a unique hash for this operation
                operation_hash = hashlib.md5(str(operation.__dict__).encode()).hexdigest()[:8]
                stage_name = f"download_{operation_hash}"
                
                download_stages.append(f"FROM system_stage AS {stage_name}")
                download_stages.extend(operation.get_dockerfile_commands())
        
        return "\n".join(download_stages) + "\n"

    def generate_user_dockerfile(self) -> str:
        """Generate the Dockerfile with user commands."""
        return "\n".join(self.user_stage) + "\n"

    def generate_dockerfile(self):
        """Generate the final Dockerfile by concatenating all stages."""
        stages = [
            self.generate_base_dockerfile(),
            self.generate_download_dockerfile(),
            "FROM system_stage AS user_stage\n" + self.generate_user_dockerfile(),
            "FROM user_stage AS final_stage\n"
        ]

        for operation in self.download_operations:
            operation_hash = hashlib.md5(str(operation.__dict__).encode()).hexdigest()[:8]
            stage_name = f"download_{operation_hash}"
            output_path = operation.get_output_path()
            stages[-1] += f"COPY --from={stage_name} {output_path} {output_path}\n"

        return "\n".join(stages)

    def save_dockerfile(self):
        system_dockerfile_path = os.path.join(self.temp_dir, "Dockerfile.system")
        user_dockerfile_path = os.path.join(self.temp_dir, "Dockerfile.user")
        download_dockerfile_path = os.path.join(self.temp_dir, "Dockerfile.download")
        final_dockerfile_path = os.path.join(self.temp_dir, "Dockerfile")

        with open(system_dockerfile_path, "w") as f:
            f.write(self.generate_base_dockerfile())
        with open(user_dockerfile_path, "w") as f:
            f.write(self.generate_user_dockerfile())
        with open(download_dockerfile_path, "w") as f:
            f.write(self.generate_download_dockerfile())
        with open(final_dockerfile_path, "w") as f:
            f.write(self.generate_dockerfile())

        logging.info(f"System stage Dockerfile saved to {system_dockerfile_path}")
        logging.info(f"User stage Dockerfile saved to {user_dockerfile_path}")
        logging.info(f"Download stage Dockerfile saved to {download_dockerfile_path}")
        logging.info(f"Final multi-stage Dockerfile saved to {final_dockerfile_path}")

        logging.info(f"\nTemporary directory used: {self.temp_dir}")
        logging.info("Remember to clean up this directory after building the Docker image.")

    def cleanup(self):
        """Clean up the temporary directory."""
        import shutil
        shutil.rmtree(self.temp_dir)
        logging.info(f"Cleaned up temporary directory: {self.temp_dir}")

    def enter_context(self):
        """Enter the Docker build context."""
        return self.temp_dir

    def get_context_dir(self):
        """Return the Docker build context directory."""
        return self.temp_dir