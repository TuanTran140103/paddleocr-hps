"""
Modal script để build Triton Docker image với GPU support
và push lên Docker Hub

Cách dùng:
1. Cài đặt Modal CLI: pip install modal
2. Authenticate: modal setup
3. Chạy build:
   modal run modal_build.py --dockerhub_username YOUR_USERNAME --dockerhub_token YOUR_TOKEN

Lưu ý: Script sẽ clone repository từ GitHub vào Modal container trước khi build
"""

import modal
import os
import shutil
import subprocess

# Tạo Modal app
app = modal.App("paddleocr-triton-builder")

# Tạo image với Docker và Git
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("docker.io", "curl", "git")
    .pip_install("docker", "requests")
)


@app.function(
    image=image,
    gpu="T4",  # GPU Tesla T4 - free tier
    timeout=3600,  # 1 giờ timeout
)
def build_and_push(
    dockerhub_username: str,
    dockerhub_token: str,
    github_repo: str,
    image_name: str = "paddleocr-triton",
    tag: str = "latest",
    branch: str = "main",
):
    """
    Build Docker image với GPU và push lên Docker Hub
    
    Args:
        dockerhub_username: Docker Hub username
        dockerhub_token: Docker Hub token
        github_repo: GitHub repo URL (ví dụ: https://github.com/username/repo.git)
        image_name: Tên Docker image
        tag: Tag cho Docker image
        branch: Branch để clone
    """
    import docker
    import tempfile
    
    # Khởi tạo Docker client
    client = docker.from_env()
    
    # Login vào Docker Hub
    print(f"🔐 Logging into Docker Hub as {dockerhub_username}...")
    client.login(username=dockerhub_username, password=dockerhub_token)
    
    # Clone repository
    work_dir = "/tmp/paddleocr-build"
    print(f"📦 Cloning repository: {github_repo} (branch: {branch})")
    
    try:
        # Xóa thư mục cũ nếu tồn tại
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
        
        # Clone repo
        result = subprocess.run(
            ["git", "clone", "-b", branch, "--depth", "1", github_repo, work_dir],
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        if result.returncode != 0:
            raise Exception(f"Git clone failed: {result.stderr}")
        
        print(f"✅ Cloned to {work_dir}")
        
    except subprocess.TimeoutExpired:
        raise Exception("Git clone timeout")
    except Exception as e:
        raise Exception(f"Failed to clone repo: {str(e)}")
    
    # Build context path
    build_context = work_dir
    
    # Verify required files exist
    dockerfile_path = os.path.join(build_context, "tritonserver.Dockerfile")
    if not os.path.exists(dockerfile_path):
        raise Exception(f"Dockerfile not found: {dockerfile_path}")
    
    server_dir = os.path.join(build_context, "paddlex_hps_PaddleOCR-VL-1.5_sdk/server")
    if not os.path.exists(server_dir):
        raise Exception(f"Server directory not found: {server_dir}")
    
    print(f"✅ Found Dockerfile and server directory")
    
    # Full image name
    image_full_name = f"{dockerhub_username}/{image_name}:{tag}"
    print(f"🔨 Building image: {image_full_name}")
    
    try:
        # Build với build args cho GPU
        build_logs = client.api.build(
            path=build_context,
            dockerfile="tritonserver.Dockerfile",
            tag=image_full_name,
            buildargs={
                "DEVICE_TYPE": "gpu",
            },
            rm=True,
            forcerm=True,
            decode=True,
            stream=True,
        )
        
        for chunk in build_logs:
            if 'stream' in chunk:
                print(chunk['stream'].strip())
            elif 'error' in chunk:
                print(f"❌ ERROR: {chunk['error']}")
                raise Exception(chunk['error'])
        
        # Get built image
        built_image = client.images.get(image_full_name)
        print(f"✅ Build successful! Image ID: {built_image.short_id}")
        
    except Exception as e:
        print(f"❌ Build failed: {str(e)}")
        raise
    
    # Push lên Docker Hub
    print(f"📤 Pushing image to Docker Hub: {image_full_name}")
    try:
        push_logs = client.images.push(
            image_full_name,
            auth_config={
                "username": dockerhub_username,
                "password": dockerhub_token,
            },
            stream=True,
            decode=True,
        )
        
        for progress in push_logs:
            if 'status' in progress:
                status_msg = progress['status']
                if 'progressDetail' in progress:
                    print(f"{status_msg}: {progress['progressDetail']}")
                else:
                    print(status_msg)
        
        print(f"✅ Successfully pushed {image_full_name}")
        
    except Exception as e:
        print(f"❌ Push failed: {str(e)}")
        raise
    
    # Cleanup
    shutil.rmtree(work_dir, ignore_errors=True)
    
    return {"status": "success", "image": image_full_name, "tags": [tag]}


@app.local_entrypoint()
def main(
    dockerhub_username: str,
    dockerhub_token: str,
    github_repo: str,
    image_name: str = "paddleocr-triton",
    tag: str = "latest",
    branch: str = "main",
):
    """
    Entry point để chạy build từ local

    Usage:
        modal run modal_build.py \
          --dockerhub-username YOUR_USERNAME \
          --dockerhub-token YOUR_TOKEN \
          --github-repo https://github.com/yourusername/yourrepo.git

    Hoặc với environment variables:
        export DOCKERHUB_USERNAME=your_username
        export DOCKERHUB_TOKEN=your_token
        modal run modal_build.py --github-repo https://github.com/yourusername/yourrepo.git
    """
    # Lấy từ env nếu không truyền vào
    username = dockerhub_username or os.environ.get("DOCKERHUB_USERNAME")
    token = dockerhub_token or os.environ.get("DOCKERHUB_TOKEN")
    
    if not username or not token:
        raise ValueError("Cần cung cấp Docker Hub username và token")
    
    if not github_repo:
        raise ValueError("Cần cung cấp GitHub repository URL")
    
    print(f"🚀 Starting build on Modal GPU...")
    print(f"   Repo: {github_repo} (branch: {branch})")
    print(f"   Image: {username}/{image_name}:{tag}")
    
    result = build_and_push.remote(
        dockerhub_username=username,
        dockerhub_token=token,
        github_repo=github_repo,
        image_name=image_name,
        tag=tag,
        branch=branch,
    )
    
    print(f"\n✅ Build complete! Result: {result}")
    return result
