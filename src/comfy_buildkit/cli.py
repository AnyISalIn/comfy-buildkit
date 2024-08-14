import os
import sys
import subprocess
from pathlib import Path
import click
from comfy_buildkit import ComfyBuildkit
from rich.console import Console
import time

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
def run_flyctl(temp_dir: Path) -> None:
    print_command(f"cd {temp_dir}")
    print_command("flyctl deploy --build-only --remote-only --push --recreate-builder --deploy-retries 0")
    print_output("Deploying app...")
    result = subprocess.run(["flyctl", "deploy", "--build-only", "--remote-only", "--push", "--recreate-builder", "--deploy-retries", "0"], 
                            cwd=temp_dir)
    if result.returncode == 0:
        print_output("App deployed successfully!")
    else:
        print_error(f"Deployment failed: {result.stderr}")
    print_command(f"cd {os.getcwd()}")

def run_docker_build(temp_dir: Path, tag: str) -> None:
    print_command(f"cd {temp_dir}")
    print_command(f"docker build --network host -t {tag} .")
    print_output("Building Docker image...")
    result = subprocess.run(["docker", "build", "--network", "host", "-t", tag, "."], 
                            cwd=temp_dir)
    if result.returncode == 0:
        print_output("Docker image built successfully!")
    else:
        print_error(f"Docker build failed: {result.stderr}")
    print_command(f"cd {os.getcwd()}")

@click.command()
@click.argument('profile', type=click.Path(exists=True))
@click.option('--local', '-l', is_flag=True, help="Build locally using Docker")
@click.option('--fly', '-f', is_flag=True, help="Build using Fly.io")
@click.option('--tag', '-t', default="comfyui:latest", help="Docker image tag (for local build)")
@click.option('--no-cleanup', '-n', is_flag=True, help="Disable auto cleanup after build")
@click.option('--fly-app-name', '-a', default="comfy-builder", help="Fly.io app name")
@click.option('--fly-primary-region', '-r', default="sjc", help="Fly.io primary region")
@click.option('--fly-memory', '-m', default="4gb", help="Fly.io VM memory")
@click.option('--fly-cpu-kind', '-k', default="shared", help="Fly.io CPU kind")
@click.option('--fly-cpus', '-c', default=2, type=int, help="Fly.io number of CPUs")
def main(profile: str, local: bool, fly: bool, tag: str, no_cleanup: bool, fly_app_name: str,
         fly_primary_region: str, fly_memory: str, fly_cpu_kind: str, fly_cpus: int) -> None:
    """Build ComfyUI Docker image"""
    try:
        print_command(f"Loading profile: {profile}")
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
    
        if local:
            print_comment("Building Docker Image")
            run_docker_build(Path(builder.temp_dir), tag)
    
        if fly:
            print_comment("Preparing Fly.io Deployment")
            create_fly_toml(Path(builder.temp_dir), fly_app_name, fly_primary_region, fly_memory, fly_cpu_kind, fly_cpus)
            run_flyctl(Path(builder.temp_dir))
    
        if not (local or fly):
            print_error("No build option specified. Use --local (-l) for Docker build or --fly (-f) for Fly.io build.")

    except Exception as e:
        print_error(f"An error occurred: {str(e)}")

    finally:
        if not no_cleanup:
            print_comment("Cleaning up...")
            builder.cleanup()
        else:
            print_error(f"Skipping cleanup. Temporary files remain in: {builder.temp_dir}")

if __name__ == "__main__":
    main()