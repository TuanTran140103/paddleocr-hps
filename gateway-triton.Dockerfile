# Gateway + Triton combined Dockerfile
# Chạy cả 2 services trong cùng 1 container - Đã test thành công với Modal

ARG BASE_IMAGE=tuantran2003/paddleocr-triton:latest
FROM ${BASE_IMAGE}

WORKDIR /

# Copy gateway code vào /gateway
COPY gateway/ ./gateway/

# Copy client SDK vào /sdk
COPY paddlex_hps_PaddleOCR-VL-1.5_sdk/client ./sdk/

# Install dependencies cho Gateway
# Lưu ý: Dùng pip của base image, không cần venv riêng
RUN pip install --no-cache-dir \
    fastapi==0.123.6 \
    uvicorn==0.35.0 \
    ./sdk/paddlex_hps_client-0.3.0-py3-none-any.whl

# Environment variables
ENV PADDLEX_HPS_DEVICE_TYPE=gpu
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=true
ENV HPS_TRITON_URL=localhost:8001
ENV HPS_MAX_CONCURRENT_INFERENCE_REQUESTS=16
ENV HPS_MAX_CONCURRENT_NON_INFERENCE_REQUESTS=64
ENV HPS_INFERENCE_TIMEOUT=600
ENV HPS_LOG_LEVEL=INFO

# Expose ports: 8000-8002 cho Triton, 8080 cho Gateway
EXPOSE 8000 8001 8002 8080

# Health check cho Gateway
HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start Triton server (background) + Gateway (foreground)
# Giống với modal_test_gateway_triton_v3.py đã test thành công
CMD /bin/bash -c "\
    echo '========================================' && \
    echo '🚀 STARTING TRITON + GATEWAY' && \
    echo '========================================' && \
    echo '' && \
    echo '📊 GPU Info:' && \
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader && \
    echo '' && \
    echo '🚀 Starting Triton server...' && \
    tritonserver \
        --model-repository=/paddlex/var/paddlex_model_repo \
        --backend-config=python,shm-default-byte-size=104857600,shm-growth-byte-size=10485760 \
        --log-info=1 & \
    TRITON_PID=\$! && \
    echo '' && \
    echo '⏳ Waiting for Triton to be ready...' && \
    for i in \$(seq 1 90); do \
        if curl -s http://localhost:8000/v2/health/ready > /dev/null 2>&1; then \
            echo '✅ Triton is READY!'; \
            break; \
        fi; \
        sleep 1; \
    done && \
    echo '' && \
    echo '📦 Triton models:' && \
    curl -s http://localhost:8000/v2/repository/index | python3 -c "import sys,json; models=json.load(sys.stdin); [print(f'   - {m[\"name\"]}: {m[\"state\"]}') for m in models]" 2>/dev/null || true && \
    echo '' && \
    echo '========================================' && \
    echo '🚀 STARTING GATEWAY' && \
    echo '========================================' && \
    echo '' && \
    echo '🚀 Starting uvicorn on port 8080...' && \
    exec uvicorn \
        --host 0.0.0.0 \
        --port 8080 \
        --workers 1 \
        gateway.app:app"
