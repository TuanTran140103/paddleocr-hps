"""
Modal script v3 để chạy Triton server
Dùng NVIDIA Triton base image thay vì custom base image

Cách dùng PowerShell:
  modal run modal_run_v3.py
"""

import modal

# Tạo Modal app
app = modal.App("paddleocr-triton-run-v3")

# Tạo volumes để cache
cache_volume = modal.Volume.from_name("paddleocr-cache-v3", create_if_missing=True)
models_volume = modal.Volume.from_name("paddleocr-models-v3", create_if_missing=True)

# Dùng NVIDIA Triton base image có sẵn tritonserver
# Lưu ý: Base image của bạn (Baidu Cloud) Modal không thể pull được
# Nên dùng NVIDIA Triton base image
image = (
    modal.Image.from_registry(
        "nvcr.io/nvidia/tritonserver:23.05-py3",
        add_python="3.10",
    )
    .apt_install(
        "git", "curl", "wget",
        "libgl1", "libglib2.0-0", "libsm6", "libxext6", "libxrender-dev"
    )
    .pip_install(
        "paddlex>=3.4.0",
        "paddlepaddle-gpu",
        "requests",
        "Pillow",
        "numpy",
        "opencv-python-headless",
    )
    # Copy server files vào image
    .add_local_dir(
        local_path="paddlex_hps_PaddleOCR-VL-1.5_sdk/server",
        remote_path="/app",
    )
)


@app.function(
    image=image,
    volumes={
        "/cache": cache_volume,
        "/models": models_volume,
    },
    gpu="T4",
    timeout=600,
)
def run_triton_server():
    """
    Chạy Triton server trên GPU của Modal
    """
    import subprocess
    import time
    import os
    
    print("🚀 Starting Triton server on Modal GPU...\n")
    
    # Test GPU
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print(f"✅ GPU: {result.stdout.strip()}")
    
    # Test tritonserver binary
    print("\n📦 Checking tritonserver...")
    triton_result = subprocess.run(
        ["which", "tritonserver"],
        capture_output=True,
        text=True
    )
    if triton_result.returncode == 0:
        print(f"✅ tritonserver found: {triton_result.stdout.strip()}")
    else:
        print("❌ tritonserver NOT found!")
    
    # Check /app contents
    print(f"\n📁 /app contents:")
    if os.path.exists("/app"):
        app_files = os.listdir("/app")
        print(f"   {app_files[:15]}")
    
    # Chạy server
    print("\n📦 Starting Triton server...")
    
    try:
        server_process = subprocess.Popen(
            ["/bin/bash", "/app/server.sh"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd="/app",
            env={**os.environ, "PADDLEX_HPS_DEVICE_TYPE": "gpu"}
        )
        
        # Đợi server startup (45 giây cho model loading)
        print("⏳ Waiting for server startup...")
        time.sleep(45)
        
        if server_process.poll() is None:
            print("✅ Server is running!")
            
            # Test health endpoint
            import requests
            try:
                resp = requests.get("http://localhost:8000/v2/health/ready", timeout=5)
                print(f"✅ Health check: {resp.status_code}")
                if resp.status_code == 200:
                    print("✅ Triton server is READY!")
            except Exception as e:
                print(f"⚠️  Health check failed: {e}")
            
            server_process.terminate()
        else:
            stdout, stderr = server_process.communicate()
            print(f"\n❌ Server exited with code: {server_process.returncode}")
            print(f"\n--- STDOUT (last 1000 chars) ---")
            print(stdout[-1000:] if len(stdout) > 1000 else stdout)
            print(f"\n--- STDERR (last 1000 chars) ---")
            print(stderr[-1000:] if len(stderr) > 1000 else stderr)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Commit volumes
    cache_volume.commit()
    models_volume.commit()
    
    print("\n✅ Test completed!")
    return {"status": "success"}


@app.local_entrypoint()
def main():
    """
    Entry point

    Usage:
        modal run modal_run_v3.py
    """
    print("🚀 Running on Modal GPU v3 with NVIDIA Triton base image...\n")
    
    result = run_triton_server.remote()
    
    print(f"\n✅ Done! Result: {result}")
    return result
