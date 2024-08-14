import os
import sys
import subprocess
from pathlib import Path
import click
from comfy_buildkit import ComfyBuildkit
from rich.console import Console
import time
import requests
import tempfile
import shutil

console = Console()

def type_text(text: str, delay: float = 0.03) -> None:
    for char in text:
        console.print(char, end="")
        time.sleep(delay)
    console.print()

def print_command(command: str) -> None:
    console.print("$ ", style="bold green", end="")
    type_text(command, delay=0.008)

def print_output(output: str) -> None:
    type_text(output, delay=0.001)

def print_error(error: str) -> None:
    console.print("Error: ", style="bold red", end="")
    type_text(error, delay=0.03)

def print_comment(comment: str) -> None:
    console.print("# ", style="bold blue", end="")
    type_text(comment, delay=0.03)

def create_fly_toml(temp_dir: Path, app_name: str, primary_region: str, 
                    memory: str, cpu_kind: str, cpus: int) -> None:
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
    fly_toml_path = temp_dir / "fly.toml"
    print_command(f"cat > {fly_toml_path} << EOF")
    print_output(fly_toml_content.strip())
    print_command("EOF")
    with open(fly_toml_path, 'w') as f:
        f.write(fly_toml_content)

def get_build_command(build_tool: str) -> list:
    if build_tool == "docker":
        return ["docker", "build"]
    elif build_tool == "podman":
        return ["podman", "build"]
    elif build_tool == "buildah":
        return ["buildah", "bud"]
    elif build_tool == "fly":
        return ["flyctl", "deploy", "--build-only", "--remote-only", "--push", "--recreate-builder", "--deploy-retries", "0"]
    else:
        raise ValueError(f"Unsupported build tool: {build_tool}")

def run_build(temp_dir: Path, tag: str, build_tool: str) -> bool:
    print_command(f"cd {temp_dir}")
    build_cmd = get_build_command(build_tool)
    
    if build_tool == "fly":
        cmd = build_cmd
    else:
        cmd = [*build_cmd, "--network", "host", "-t", tag, "."]
    
    print_command(f"{' '.join(cmd)}")
    print_output(f"Building image using {build_tool}...")
    result = subprocess.run(cmd, cwd=temp_dir)
    if result.returncode == 0:
        print_output(f"{build_tool.capitalize()} build completed successfully!")
        return True
    else:
        print_error(f"{build_tool.capitalize()} build failed: {result.stderr}")
        return False

def run_docker_container(tag: str, port: int, build_tool: str = "docker") -> None:
    run_cmd = "docker" if build_tool == "docker" else build_tool
    print_command(f"{run_cmd} run -d -p {port}:8188 --gpus all {tag}")
    print_output(f"Starting {build_tool} container...")
    result = subprocess.run([run_cmd, "run", "--rm", "-ti", "-p", f"{port}:8188", "--gpus", "all", tag])
    if result.returncode == 0:
        print_output(f"{build_tool.capitalize()} container started successfully! Access ComfyUI at http://localhost:{port}")
    else:
        print_error(f"Failed to start {build_tool} container: {result.stderr}")

@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.argument('profile', type=str, required=False)
@click.option('--build-tool', '-b', default="docker", type=click.Choice(['docker', 'podman', 'buildah', 'fly']), help="Build tool to use (docker, podman, buildah, or fly)")
@click.option('--tag', '-t', default="comfyui:latest", help="Docker image tag (for local build)")
@click.option('--port', '-p', default=8080, type=int, help="Port to run the Docker container on")
@click.option('--no-cleanup', '-n', is_flag=True, help="Disable auto cleanup after build")
@click.option('--fly-app-name', '-a', default="comfy-builder", help="Fly.io app name")
@click.option('--fly-primary-region', '-r', default="sjc", help="Fly.io primary region")
@click.option('--fly-memory', '-m', default="4gb", help="Fly.io VM memory")
@click.option('--fly-cpu-kind', '-k', default="shared", help="Fly.io CPU kind")
@click.option('--fly-cpus', '-c', default=2, type=int, help="Fly.io number of CPUs")
@click.option('--preview', '-v', is_flag=True, help="Preview Dockerfile without building")
@click.pass_context
def main(ctx: click.Context, profile: str, build_tool: str, tag: str, port: int, no_cleanup: bool, fly_app_name: str,
         fly_primary_region: str, fly_memory: str, fly_cpu_kind: str, fly_cpus: int, preview: bool) -> None:
    """Build ComfyUI Docker image"""
    if not profile:
        click.echo(ctx.get_help())
        ctx.exit()

    try:
        print_command(f"Loading profile: {profile}")
        
        if profile.startswith(('http://', 'https://')):
            # Handle HTTP profile
            print_comment("Downloading profile from URL")
            response = requests.get(profile)
            response.raise_for_status()
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
                temp_file.write(response.text)
                profile_path = Path(temp_file.name)
        else:
            # Handle local file profile
            profile_path = Path(profile).resolve()
        
        print_command(f"cd {profile_path.parent}")
        os.chdir(profile_path.parent)

        sys.path.append(str(profile_path.parent))
        profile_module = profile_path.stem
        module = __import__(profile_module)
        
        builder = next((attr for attr in vars(module).values() if isinstance(attr, ComfyBuildkit)), None)
        
        if not builder:
            print_error("No ComfyBuildkit instance found in the profile module")
            return

        print_comment("Generating Dockerfile")
        dockerfile_content = builder.generate_dockerfile()
        print_command("cat > Dockerfile << EOF")
        print_output(dockerfile_content)
        print_command("EOF")
        
        builder.save_dockerfile()
    
        if preview:
            print_comment("Previewing Dockerfile")
            print_output(dockerfile_content)
        else:
            if build_tool == "fly":
                print_comment("Preparing Fly.io Deployment")
                create_fly_toml(Path(builder.temp_dir), fly_app_name, fly_primary_region, fly_memory, fly_cpu_kind, fly_cpus)
            
            print_comment(f"Building Image using {build_tool}")
            build_success = run_build(Path(builder.temp_dir), tag, build_tool)
            
            if build_success and build_tool in ["docker", "podman", "buildah"]:
                print_comment(f"Running {build_tool.capitalize()} Container")
                run_docker_container(tag, port, build_tool)
            elif build_tool == "fly":
                print_comment("Preparing Fly.io Deployment")
                create_fly_toml(Path(builder.temp_dir), fly_app_name, fly_primary_region, fly_memory, fly_cpu_kind, fly_cpus)
                run_flyctl(Path(builder.temp_dir))
            else:
                print_error(f"No build option specified. Use --local (-l) for {build_tool} build, --fly (-f) for Fly.io build, or --preview (-v) to preview the Dockerfile.")

    except requests.RequestException as e:
        print_error(f"Failed to download profile: {str(e)}")
    except Exception as e:
        print_error(f"An error occurred: {str(e)}")

    finally:
        if not no_cleanup and not preview:
            print_comment("Cleaning up...")
            builder.cleanup()
        elif not preview:
            print_error(f"Skipping cleanup. Temporary files remain in: {builder.temp_dir}")

if __name__ == "__main__":
    main()