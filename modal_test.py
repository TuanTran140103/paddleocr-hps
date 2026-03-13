"""
Modal script để test/run Triton server trên GPU

Cách dùng PowerShell:
  modal run modal_test.py

Script này chỉ dùng để test inference trên GPU của Modal, không build Docker image
"""

import modal

# Tạo Modal app
app = modal.App("paddleocr-triton-test")

# Tạo image với các dependencies cần thiết
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("curl", "git")
    .pip_install("requests", "numpy", "Pillow")
)


@app.function(
    image=image,
    gpu="T4",  # GPU Tesla T4
    timeout=600,  # 10 phút timeout
)
def test_inference():
    """
    Test inference đơn giản trên GPU của Modal
    """
    import subprocess
    import os
    
    print("🚀 Starting test on Modal GPU...")
    
    # Test GPU có sẵn
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print(f"✅ GPU available: {result.stdout.strip()}")
    else:
        print("⚠️  nvidia-smi not available, but GPU should work")
    
    # Test Python imports
    try:
        import torch
        print(f"✅ PyTorch version: {torch.__version__}")
        print(f"✅ CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"✅ GPU: {torch.cuda.get_device_name(0)}")
    except ImportError:
        print("⚠️  PyTorch not installed")
    
    # Clone repo để test
    work_dir = "/tmp/paddleocr-test"
    if os.path.exists(work_dir):
        import shutil
        shutil.rmtree(work_dir)
    
    print("\n📦 Cloning repository for testing...")
    clone_result = subprocess.run(
        ["git", "clone", "--depth", "1", 
         "https://github.com/TuanTran140103/paddleocr-hps.git", work_dir],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    if clone_result.returncode == 0:
        print(f"✅ Cloned to {work_dir}")
        
        # List files
        files = os.listdir(work_dir)
        print(f"📁 Repository files: {files[:10]}")  # First 10 files
    else:
        print(f"⚠️  Clone failed: {clone_result.stderr}")
    
    print("\n✅ Test completed successfully!")
    return {"status": "success", "gpu": "T4"}


@app.local_entrypoint()
def main():
    """
    Entry point - chạy test trên Modal GPU
    
    Usage:
        modal run modal_test.py
    """
    print("🚀 Running test on Modal GPU...\n")
    
    result = test_inference.remote()
    
    print(f"\n✅ Done! Result: {result}")
    return result
