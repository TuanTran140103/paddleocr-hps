# Build args for hardware flexibility
# For CPU-only or non-NVIDIA hardware, override these at build time:
#   docker build --build-arg BASE_IMAGE=<cpu-image> --build-arg DEVICE_TYPE=cpu ...
ARG BASE_IMAGE=ccr-2vdh3abv-pub.cnc.bj.baidubce.com/paddlex/hps:paddlex3.4-gpu
ARG DEVICE_TYPE=gpu

FROM ${BASE_IMAGE}

# Install system dependencies (giống Modal script)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Install PaddleX with NumPy < 2 (compatibility fix)
RUN pip install --no-cache-dir "numpy<2" paddlex>=3.4.0 || true

# Set environment variables
ARG DEVICE_TYPE
ENV PADDLEX_HPS_DEVICE_TYPE=${DEVICE_TYPE}
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=true
ENV PADDLEX_HPS_LOGGING_LEVEL=INFO

WORKDIR /app
COPY paddlex_hps_PaddleOCR-VL-1.5_sdk/server .

# Expose Triton ports
EXPOSE 8000 8001 8002

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/v2/health/ready || exit 1

CMD ["/bin/bash", "server.sh"]
