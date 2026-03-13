"""
Modal script v2 để chạy Triton server với cache tối ưu
Phiên bản dành cho Modal 1.3.x

Cách dùng PowerShell:
  modal run modal_run_v2.py
  modal run modal_run_v2.py --warmup-only    # Chỉ warmup cache
"""

import modal

# Tạo Modal app
app = modal.App("paddleocr-triton-run-v2")

# Tạo volumes để cache
cache_volume = modal.Volume.from_name("paddleocr-cache-v2", create_if_missing=True)
models_volume = modal.Volume.from_name("paddleocr-models-v2", create_if_missing=True)

# Tạo image với dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "git", "curl", "wget",
        "libgl1", "libglib2.0-0", "libsm6", "libxext6", "libxrender-dev"
    )
    .pip_install(
        "paddlex>=3.4.0",
        "requests",
        "Pillow",
        "numpy",
        "opencv-python-headless",
    )
    # Modal 1.3.x: Copy files vào image qua add_local_dir trên Image
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
    
    # Check volumes
    print(f"\n📁 Volumes mounted:")
    print(f"   /cache -> {cache_volume}")
    print(f"   /models -> {models_volume}")
    
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
        # time.sleep(45)
        
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
            
            # Get model status
            try:
                resp = requests.get("http://localhost:8000/v2/repository/index", timeout=5)
                if resp.status_code == 200:
                    models = resp.json()
                    print(f"📦 Loaded models: {len(models)}")
                    for m in models[:5]:
                        print(f"   - {m.get('name', 'unknown')}")
            except Exception as e:
                print(f"⚠️  Could not get model status: {e}")
            
            server_process.terminate()
        else:
            stdout, stderr = server_process.communicate()
            print(f"\n❌ Server exited with code: {server_process.returncode}")
            print(f"\n--- STDOUT (last 500 chars) ---")
            print(stdout[-500:] if len(stdout) > 500 else stdout)
            print(f"\n--- STDERR (last 500 chars) ---")
            print(stderr[-500:] if len(stderr) > 500 else stderr)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Commit volumes
    cache_volume.commit()
    models_volume.commit()
    
    print("\n✅ Test completed!")
    return {"status": "success"}


@app.function(
    image=image,
    volumes={
        "/cache": cache_volume,
        "/models": models_volume,
    },
    gpu="T4",
    timeout=300,
)
def warmup():
    """
    Warmup - preload packages và models vào cache
    """
    import os
    
    print("🔥 Warming up cache...\n")
    
    # Test imports
    print("📦 Testing imports...")
    try:
        import paddlex
        print(f"✅ PaddleX: {paddlex.__version__}")
    except Exception as e:
        print(f"⚠️  PaddleX: {e}")
    
    try:
        import paddle
        print(f"✅ PaddlePaddle: {paddle.__version__}")
        print(f"✅ CUDA available: {paddle.is_compiled_with_cuda()}")
    except Exception as e:
        print(f"⚠️  PaddlePaddle: {e}")
    
    try:
        import cv2
        print(f"✅ OpenCV: {cv2.__version__}")
    except Exception as e:
        print(f"⚠️  OpenCV: {e}")
    
    # Check app files
    print("\n📁 Checking /app files...")
    if os.path.exists("/app"):
        files = os.listdir("/app")
        print(f"   Found: {files}")
    
    # Commit cache
    cache_volume.commit()
    models_volume.commit()
    
    print("\n✅ Warmup complete!")
    return {"status": "warmed"}


@app.local_entrypoint()
def main(warmup_only: bool = False):
    """
    Entry point

    Usage:
        modal run modal_run_v2.py                    # Run server test
        modal run modal_run_v2.py --warmup-only     # Just warmup cache
    """
    print("🚀 Running on Modal GPU v2 with cache...\n")
    
    if warmup_only:
        result = warmup.remote()
    else:
        # Warmup first, then run
        print("🔥 Running warmup first...")
        warmup_result = warmup.remote()
        print(f"✅ Warmup done: {warmup_result}\n")
        
        result = run_triton_server.remote()
    
    print(f"\n✅ Done! Result: {result}")
    return result
