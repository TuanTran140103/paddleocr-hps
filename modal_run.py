"""
Modal script để chạy Triton server với Baidu base image
Thử pull image từ Baidu Cloud registry

Cách dùng PowerShell:
  modal run modal_run.py
"""

import modal

# Tạo Modal app
app = modal.App("paddleocr-triton-run")

# Tạo volumes để cache
cache_volume = modal.Volume.from_name("paddleocr-cache", create_if_missing=True)
models_volume = modal.Volume.from_name("paddleocr-models", create_if_missing=True)

# Dùng base image từ Baidu Cloud
# Modal sẽ thử pull image này
image = (
    modal.Image.from_registry(
        "ccr-2vdh3abv-pub.cnc.bj.baidubce.com/paddlex/hps:paddlex3.4-gpu",
        add_python="3.11",
    )
    .apt_install(
        "git", "curl", "wget",
        "libgl1", "libglib2.0-0", "libsm6", "libxext6", "libxrender-dev"
    )
    .pip_install(
        "requests",
        "Pillow",
        "numpy<2",  # PaddleX yêu cầu NumPy 1.x
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
        
        # Get version
        version_result = subprocess.run(
            ["tritonserver", "--version"],
            capture_output=True,
            text=True
        )
        print(f"   Version: {version_result.stdout[:200] if version_result.stdout else 'N/A'}")
    else:
        print("❌ tritonserver NOT found!")
        print(f"   STDERR: {triton_result.stderr}")
    
    # Check Python packages
    print("\n📦 Checking Python packages...")
    try:
        import paddlex
        print(f"✅ PaddleX: {paddlex.__version__}")
    except Exception as e:
        print(f"⚠️  PaddleX: {e}")
    
    try:
        import paddle
        print(f"✅ PaddlePaddle: {paddle.__version__}")
    except Exception as e:
        print(f"⚠️  PaddlePaddle: {e}")
    
    # Check /app contents
    print(f"\n📁 /app contents:")
    if os.path.exists("/app"):
        app_files = os.listdir("/app")
        print(f"   {app_files[:15]}")
    
    # Chạy server
    print("\n📦 Starting Triton server...")
    print("📋 Server logs:\n")
    
    try:
        server_process = subprocess.Popen(
            ["/bin/bash", "/app/server.sh"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd="/app",
            env={
                **os.environ,
                "PADDLEX_HPS_DEVICE_TYPE": "gpu",
                "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "true",
            }
        )
        
        # Đọc log từ server (streaming)
        import select
        import sys
        
        print("⏳ Waiting for server startup...\n")
        
        # Đọc log trong 90 giây
        start_time = time.time()
        server_ready = False
        
        while server_process.poll() is None:
            elapsed = time.time() - start_time
            
            # Đọc output
            line = server_process.stdout.readline()
            if line:
                print(line.rstrip())
                
                # Check nếu server đã ready
                if "listening at" in line.lower() or "ready for inference" in line.lower():
                    server_ready = True
                    print("\n✅ Server is UP and RUNNING!")
            
            # Timeout sau 90 giây
            if elapsed > 90:
                print("\n⏱️  Startup timeout (90s)")
                break
        
        # Đợi thêm 10 giây để xem log cuối
        time.sleep(10)
        
        # Kill server
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()
            
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
        modal run modal_run.py
    """
    print("🚀 Running on Modal GPU with Baidu base image...\n")
    
    result = run_triton_server.remote()
    
    print(f"\n✅ Done! Result: {result}")
    return result
