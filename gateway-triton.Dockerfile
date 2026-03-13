# Gateway + Triton combined Dockerfile
# Tái sử dụng image Triton đã build, install thêm gateway dependencies

FROM tuantran2003/paddleocr-triton:latest

WORKDIR /app

# Copy gateway code
COPY gateway/ ./gateway/

# Install web dependencies (chưa có trong base Triton image)
RUN pip install --no-cache-dir \
    fastapi==0.123.6 \
    uvicorn==0.35.0 \
    tritonclient[grpc]

# Install paddlex_hps_client từ SDK
COPY paddlex_hps_PaddleOCR-VL-1.5_sdk/client ./sdk/
RUN pip install --no-cache-dir \
    -r ./sdk/requirements.txt \
    ./sdk/paddlex_hps_client-0.3.0-py3-none-any.whl

# Environment variables cho Gateway
ENV HPS_TRITON_URL=localhost:8001
ENV HPS_MAX_CONCURRENT_INFERENCE_REQUESTS=16
ENV HPS_MAX_CONCURRENT_NON_INFERENCE_REQUESTS=64
ENV HPS_INFERENCE_TIMEOUT=600
ENV HPS_LOG_LEVEL=INFO
ENV UVICORN_WORKERS=4

# Expose ports: 8000-8002 cho Triton, 8080 cho Gateway
EXPOSE 8000 8001 8002 8080

# Start Triton server (background) + Gateway (main process)
CMD /bin/bash -c "\
    echo '🚀 Starting Triton + Gateway...' && \
    tritonserver \
        --model-repository=/paddlex/var/paddlex_model_repo \
        --backend-config=python,shm-default-byte-size=104857600,shm-growth-byte-size=10485760 \
        --log-info=1 & \
    TRITON_PID=\$! && \
    echo '⏳ Waiting for Triton to be ready...' && \
    for i in \$(seq 1 30); do \
        if curl -s http://localhost:8000/v2/health/ready > /dev/null 2>&1; then \
            echo '✅ Triton is ready!'; \
            break; \
        fi; \
        sleep 1; \
    done && \
    echo '🚀 Starting Gateway...' && \
    exec uvicorn \
        --host 0.0.0.0 \
        --port 8080 \
        --workers \${UVICORN_WORKERS} \
        gateway.app:app"
