import os
import json
import tempfile
import logging
from typing import List, Tuple, Dict, Any

class ComfyC:
    def __init__(self, base_image="nvidia/cuda:12.2.0-devel-ubuntu22.04", 
                 python_version="3.11", 
                 comfyui_repo="https://github.com/comfyanonymous/ComfyUI.git", 
                 comfyui_revision="master",
                 manager_repo="https://github.com/ltdrdata/ComfyUI-Manager.git",
                 manager_revision="8897b9e0f77d85dc02610784e4c357329dd04f4f"):
        self.base_image = base_image
        self.python_version = python_version
        self.user_commands = []
        self.system_commands = []
        self.context_files = {}
        self.custom_nodes = []
        self.comfyui_repo = comfyui_repo
        self.comfyui_revision = comfyui_revision
        self.temp_dir = tempfile.mkdtemp()
        self.comfy_install_data = {
            "comfy_version": comfyui_revision,
            "repo": comfyui_repo,
            "manager_version": manager_revision,
            "manager_repo": manager_repo
        }
        self.project_root = self._find_project_root()

    def _find_project_root(self):
        """Find the project root directory containing the 'template' folder."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        while current_dir != os.path.dirname(current_dir):  # Stop at the root directory
            if os.path.isdir(os.path.join(current_dir, 'template')):
                return current_dir
            current_dir = os.path.dirname(current_dir)
        raise FileNotFoundError("Could not find project root containing 'template' folder")

    # Internal methods for system commands
    def _run(self, command):
        self.system_commands.append(f"RUN {command}")

    def _copy(self, *args):
        if len(args) < 2:
            raise ValueError("COPY requires at least one source and one destination")
        
        sources, dest = args[:-1], args[-1]
        
        if len(sources) == 1 and not dest.endswith('/'):
            # Single file to single target
            source = sources[0]
            full_source_path = os.path.join(self.project_root, source)
            if not os.path.exists(os.path.join(self.temp_dir, os.path.basename(full_source_path))):
                if os.path.exists(full_source_path):
                    import shutil
                    shutil.copy2(full_source_path, os.path.join(self.temp_dir, os.path.basename(full_source_path)))
                else:
                    raise FileNotFoundError(f"Source file not found: {full_source_path}")
            self.system_commands.append(f"COPY {os.path.basename(source)} {dest}")
        else:
            # Multiple files to directory
            for source in sources:
                full_source_path = os.path.join(self.project_root, source)
                if not os.path.exists(os.path.join(self.temp_dir, os.path.basename(full_source_path))):
                    if os.path.exists(full_source_path):
                        import shutil
                        shutil.copy2(full_source_path, os.path.join(self.temp_dir, os.path.basename(full_source_path)))
                    else:
                        raise FileNotFoundError(f"Source file not found: {full_source_path}")
            sources_str = " ".join(os.path.basename(s) for s in sources)
            self.system_commands.append(f"COPY {sources_str} {dest}")

    def _env(self, **kwargs):
        for key, value in kwargs.items():
            self.system_commands.append(f"ENV {key}={value}")

    def _add(self, url, dest):
        self.system_commands.append(f"ADD {url} {dest}")

    def _file_contents(self, content, remote_path, json_dump=False):
        temp_path = os.path.join(self.temp_dir, os.path.basename(remote_path))
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        with open(temp_path, "w") as f:
            if json_dump:
                json.dump(content, f, indent=2)
            else:
                f.write(content)
        self.context_files[os.path.basename(remote_path)] = temp_path
        self._copy(os.path.basename(remote_path), remote_path)

    # Existing methods for user commands (unchanged)
    def run(self, command):
        """Add a RUN command to the Dockerfile."""
        self.user_commands.append(f"RUN {command}")
        return self

    def copy(self, *args):
        """Add a COPY command to the Dockerfile and copy the files to the build context."""
        if len(args) < 2:
            raise ValueError("COPY requires at least one source and one destination")
        
        sources, dest = args[:-1], args[-1]
        
        if len(sources) == 1 and not dest.endswith('/'):
            # Single file to single target
            source = sources[0]
            if not os.path.exists(os.path.join(self.temp_dir, os.path.basename(source))):
                if os.path.exists(source):
                    import shutil
                    shutil.copy2(source, os.path.join(self.temp_dir, os.path.basename(source)))
                else:
                    raise FileNotFoundError(f"Source file not found: {source}")
            self.user_commands.append(f"COPY {os.path.basename(source)} {dest}")
        else:
            # Multiple files to directory
            for source in sources:
                if not os.path.exists(os.path.join(self.temp_dir, os.path.basename(source))):
                    if os.path.exists(source):
                        import shutil
                        shutil.copy2(source, os.path.join(self.temp_dir, os.path.basename(source)))
                    else:
                        raise FileNotFoundError(f"Source file not found: {source}")
            sources_str = " ".join(os.path.basename(s) for s in sources)
            self.user_commands.append(f"COPY {sources_str} {dest}")
        return self

    def env(self, **kwargs):
        """Set environment variables in the Dockerfile."""
        for key, value in kwargs.items():
            self.user_commands.append(f"ENV {key}={value}")
        return self

    def workdir(self, path):
        """Set working directory in the Dockerfile."""
        self.user_commands.append(f"WORKDIR {path}")
        return self

    def entrypoint(self, command):
        """Set the entrypoint for the Dockerfile."""
        self.user_commands.append(f'ENTRYPOINT ["{command}"]')
        return self

    def pip_install(self, *packages):
        """Install Python packages using pip."""
        packages_str = " ".join(packages)
        self.user_commands.append(f"RUN pip install --no-cache-dir {packages_str}")
        return self

    def apt_install(self, *packages):
        """Install system packages using apt-get."""
        packages_str = " ".join(packages)
        self.user_commands.append(f"RUN apt-get update && apt-get install -y {packages_str} && apt-get clean && rm -rf /var/lib/apt/lists/*")
        return self

    def copy_local_file(self, local_path, remote_path):
        """Copy a local file to the Docker context and add a COPY instruction."""
        temp_path = os.path.join(self.temp_dir, os.path.basename(local_path))
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        with open(local_path, "rb") as src, open(temp_path, "wb") as dst:
            dst.write(src.read())
        self.context_files[os.path.basename(local_path)] = temp_path
        self.user_commands.append(f"COPY {os.path.basename(local_path)} {remote_path}")
        return self

    def file_contents(self, content, remote_path, json_dump=False):
        """Create a file with given contents in the Docker context and add a COPY instruction."""
        temp_path = os.path.join(self.temp_dir, os.path.basename(remote_path))
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        with open(temp_path, "w") as f:
            if json_dump:
                json.dump(content, f, indent=2)
            else:
                f.write(content)
        self.context_files[os.path.basename(remote_path)] = temp_path
        self.user_commands.append(f"COPY {os.path.basename(remote_path)} {remote_path}")
        return self

    def custom_node(self, url, revision="main"):
        """Add a custom node to be installed."""
        self.custom_nodes.append((url, revision))
        return self

    def add(self, url, dest):
        """Add an ADD command to download a file to the specified directory or file."""
        self.user_commands.append(f"ADD {url} {dest}")
        return self

    def generate_base_dockerfile(self):
        """Generate the base Dockerfile with system-level installations."""
        self.system_commands = []
        self._env(DEBIAN_FRONTEND="noninteractive", PIP_PREFER_BINARY="1", PYTHONUNBUFFERED="1")
        self._run(f"apt-get update && apt-get install -y python{self.python_version} python3-pip python-is-python3 wget git libgl1-mesa-glx libglib2.0-0 libsm6 libxrender1 libxext6 ffmpeg && apt-get clean && rm -rf /var/lib/apt/lists/*")
        
        self._install_comfyui()
        if self.custom_nodes:
            self._install_custom_nodes()
        
        return f"FROM {self.base_image}\n\n" + "\n".join(self.system_commands) + "\n"

    def _install_comfyui(self):
        self._file_contents(self.comfy_install_data, "/10-install-comfy.json", json_dump=True)
        self._copy("template/10-install-comfy.py", "/10-install-comfy.py")
        self._run("python3 /10-install-comfy.py")

    def _install_custom_nodes(self):
        node_install_data = [
            {"url": url, "hash": revision, "repo_name": url.split('/')[-1].replace('.git', '')}
            for url, revision in self.custom_nodes
        ]
        self._file_contents(node_install_data, "/20-install-nodes.json", json_dump=True)
        self._copy("template/20-install-nodes.py", "/20-install-nodes.py")
        self._run("python3 /20-install-nodes.py")

    def generate_user_dockerfile(self):
        """Generate the Dockerfile with user commands."""
        return "\n".join(self.user_commands) + "\n"

    def generate_dockerfile(self):
        """Generate the final Dockerfile by concatenating base and user Dockerfiles."""
        return self.generate_base_dockerfile() + "\n" + self.generate_user_dockerfile()

    def save_dockerfile(self):
        base_dockerfile_path = os.path.join(self.temp_dir, "Dockerfile.base")
        user_dockerfile_path = os.path.join(self.temp_dir, "Dockerfile.user")
        final_dockerfile_path = os.path.join(self.temp_dir, "Dockerfile")

        with open(base_dockerfile_path, "w") as f:
            f.write(self.generate_base_dockerfile())
        with open(user_dockerfile_path, "w") as f:
            f.write(self.generate_user_dockerfile())
        with open(final_dockerfile_path, "w") as f:
            f.write(self.generate_dockerfile())

        logging.info(f"Base Dockerfile saved to {base_dockerfile_path}")
        logging.info(f"User Dockerfile saved to {user_dockerfile_path}")
        logging.info(f"Final Dockerfile saved to {final_dockerfile_path}")

        if self.context_files:
            logging.info("\nContext files to be copied:")
            for filename, filepath in self.context_files.items():
                logging.info(f"  {filepath} -> {filename}")

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