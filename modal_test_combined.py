"""
Modal script để test combined Gateway + Triton server

Cách dùng:
  modal run modal_test_combined.py

Yêu cầu:
  - Docker image: tuantran2003/paddleocr-gateway-triton:latest
  - Modal account đã setup
"""

import modal
import os

# Tạo Modal app
app = modal.App("paddleocr-gateway-triton-test")

# Build image từ Docker Hub
image = (
    modal.Image.from_registry(
        "tuantran2003/paddleocr-gateway-triton:latest",
        add_python="3.11",
    )
    .pip_install("requests")
)


@app.cls(
    image=image,
    gpu="T4",
    timeout=600,
    scaledown_window=30 * 60,
)
class GatewayTritonTester:
    @modal.enter()
    def start_services(self):
        """
        Khởi động Gateway + Triton khi container start
        CMD trong Dockerfile sẽ tự động chạy cả 2
        """
        import subprocess
        import time

        print("🚀 Starting Gateway + Triton services...\n")

        # Check GPU
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"✅ GPU: {result.stdout.strip()}\n")

        # Check /app contents
        print(f"📁 /app contents:")
        if os.path.exists("/app"):
            app_files = os.listdir("/app")
            print(f"   {sorted(app_files)}\n")

        # Wait for services to start (CMD đã chạy từ đầu)
        print("⏳ Waiting for services to be ready...\n")
        time.sleep(20)

        # Check if processes are running
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True
        )
        print("📋 Running processes:")
        for line in result.stdout.split('\n'):
            if 'triton' in line.lower() or 'uvicorn' in line.lower():
                print(f"   {line}")
        print()

    @modal.method()
    def check_triton_health(self):
        """
        Check Triton server health (port 8000)

        Returns:
            dict: Health status
        """
        import requests

        endpoints = [
            ("Health Ready", "http://localhost:8000/v2/health/ready"),
            ("Health Live", "http://localhost:8000/v2/health/live"),
            ("Repository Index", "http://localhost:8000/v2/repository/index"),
        ]

        results = {}

        for name, endpoint in endpoints:
            try:
                response = requests.get(endpoint, timeout=10)
                results[name] = {
                    "status": response.status_code,
                    "healthy": response.status_code == 200
                }
                if response.status_code == 200:
                    print(f"✅ Triton - {name}: {response.status_code}")
                else:
                    print(f"⚠️ Triton - {name}: {response.status_code}")
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "healthy": False,
                    "error": str(e)
                }
                print(f"❌ Triton - {name}: {e}")

        return results

    @modal.method()
    def check_gateway_health(self):
        """
        Check Gateway health (port 8080)

        Returns:
            dict: Health status
        """
        import requests

        endpoints = [
            ("Health", "http://localhost:8080/health"),
            ("Health Ready", "http://localhost:8080/health/ready"),
        ]

        results = {}

        for name, endpoint in endpoints:
            try:
                response = requests.get(endpoint, timeout=10)
                results[name] = {
                    "status": response.status_code,
                    "healthy": response.status_code == 200
                }
                if response.status_code == 200:
                    print(f"✅ Gateway - {name}: {response.status_code}")
                else:
                    print(f"⚠️ Gateway - {name}: {response.status_code}")
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "healthy": False,
                    "error": str(e)
                }
                print(f"❌ Gateway - {name}: {e}")

        return results

    @modal.method()
    def test_gateway_inference(self, image_url: str = "https://picsum.photos/800/600"):
        """
        Test inference qua Gateway

        Args:
            image_url: URL của image cần test

        Returns:
            dict: Kết quả inference
        """
        import requests
        import base64
        import io
        from PIL import Image

        print(f"\n📸 Testing Gateway inference with image: {image_url}")

        # Download image
        response = requests.get(image_url)
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content))

        # Convert to base64
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        # Send request to Gateway
        gateway_url = "http://localhost:8080/layout-parsing"

        payload = {
            "image": image_base64
        }

        print(f"📤 Sending request to {gateway_url}...")

        try:
            response = requests.post(gateway_url, json=payload, timeout=120)
            response.raise_for_status()

            result = response.json()
            print("✅ Gateway inference successful!")
            print(f"📊 Result status: {result.get('errorCode', 'N/A')}")

            return {
                "status": "success",
                "result": result
            }

        except requests.exceptions.Timeout:
            print("❌ Inference timeout")
            return {"status": "timeout"}
        except Exception as e:
            print(f"❌ Inference failed: {e}")
            return {"status": "error", "error": str(e)}

    @modal.method()
    def list_triton_models(self):
        """
        List all models in Triton repository

        Returns:
            list: Model names
        """
        import requests

        try:
            response = requests.get("http://localhost:8000/v2/repository/index", timeout=10)
            response.raise_for_status()
            models = response.json()
            
            print("\n📦 Triton models:")
            for model in models:
                model_name = model.get("name", "unknown")
                state = model.get("state", "unknown")
                version = model.get("version", "unknown")
                print(f"   - {model_name} (v{version}): {state}")
            
            return models
        except Exception as e:
            print(f"❌ Failed to list models: {e}")
            return []


@app.local_entrypoint()
def main():
    """
    Entry point - chạy test từ local

    Usage:
        modal run modal_test_combined.py
    """
    print("🚀 Starting Gateway + Triton test on Modal...\n")

    tester = GatewayTritonTester()

    # Check Triton health
    print("🏥 Checking Triton health...\n")
    triton_health = tester.check_triton_health.remote()

    # Check Gateway health
    print("\n🏥 Checking Gateway health...\n")
    gateway_health = tester.check_gateway_health.remote()

    # List models
    print("\n📦 Listing Triton models...\n")
    models = tester.list_triton_models.remote()

    print(f"\n✅ Test completed!")
    return {
        "triton_health": triton_health,
        "gateway_health": gateway_health,
        "models": models
    }
