# 🔧 Tối ưu hóa HPS - PaddleOCR-VL-1.5

## 📊 Phân tích瓶颈 (Bottleneck Analysis)

### Kiến trúc HPS:

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│   Client    │ ──► │  FastAPI Gateway │ ──► │Triton Server│
│  (100 req)  │     │  (UVICORN×4)     │     │             │
└─────────────┘     └──────────────────┘     └──────┬──────┘
                                                    │
                    ┌───────────────────────────────┼───────────────────────────────┐
                    │                               │                               │
                    ▼                               ▼                               ▼
        ┌───────────────────┐          ┌───────────────────┐          ┌───────────────────┐
        │ layout-parsing    │          │ restructure-pages │          │ VLM Server (vLLM) │
        │ GPU: PP-DocLayout │          │ CPU: Post-process │          │ PaddleOCR-VL-1.5  │
        │ max_batch=32 ✓    │          │ max_batch=1       │          │                   │
        │ instances=2 ✓     │          │ instances=1       │          │                   │
        │ ✅ OPTIMIZED      │          │ ⚠️ KHÔNG DÙNG     │          │ ✅ Fast           │
        └───────────────────┘          └───────────────────┘          └───────────────────┘
```

### ⚠️ Lưu ý quan trọng về `restructure-pages`:

**`restructure-pages` là gì?**
- Post-processing tùy chọn cho **multi-page documents**
- Nhiệm vụ: Merge tables across pages, relevel titles, concatenate pages
- **KHÔNG phải** là một phần bắt buộc của pipeline OCR

**Khi nào KHÔNG cần:**
```python
# Trong layout-parsing/model.py, dòng 237-242:
if input.restructurePages:  # ← Chỉ chạy nếu client yêu cầu
    preds = self.pipeline.restructure_pages(...)
```

**→ Nếu bạn OCR từng trang PDF riêng lẻ (single-page), `restructure-pages` KHÔNG bao giờ được gọi!**

### Vấn đề nghẽn cổ chai:

| Thành phần | Vấn đề | Giải pháp |
|------------|--------|-----------|
| **layout-parsing** | `max_batch_size=8` quá nhỏ | ✅ Tăng lên 32 |
| **layout-parsing** | `instance_count=1` | ✅ Tăng lên 2 |
| **layout-parsing** | `dynamic_batching` mặc định | ✅ Tối ưu queue delay 100ms |
| **Gateway** | `MAX_CONCURRENT=16` | ✅ Tăng lên 48 |
| **restructure-pages** | Không dùng đến | ✅ Giữ count=1 (tối thiểu) |

---

## 🚀 Giải pháp tối ưu

### 1. **Tối ưu layout-parsing (GPU)**

**Thay đổi:**
```pbtxt
# Trước:
max_batch_size: 8
instance_group { count: 1 }
dynamic_batching { }

# Sau:
max_batch_size: 32
instance_group { count: 2 }
dynamic_batching {
  preferred_batch_size: [ 16, 32 ]
  max_queue_delay_microseconds: 100000  # 100ms
}
```

**Lý do:**
- **batch_size 32**: Tăng 4x, cho phép GPU xử lý nhiều ảnh cùng lúc
- **2 instances**: Song song 2 model instances, mỗi instance có thể batch 32 → 64 requests đồng thời
- **preferred_batch_size [16, 32]**: Triton sẽ cố gắng gom đủ 16 hoặc 32 requests trước khi inference
- **max_queue_delay 100ms**: Chờ tối đa 100ms để gom batch, cân bằng giữa latency và throughput

**Hiệu năng dự kiến:**
- **Throughput**: Tăng 3-4x (từ ~50 img/s → ~150-200 img/s trên L40S)
- **Latency trung bình**: Có thể tăng nhẹ (~50-100ms) do chờ gom batch
- **GPU Utilization**: Tăng từ ~40% → ~80-90%

---

### 2. **Tối ưu restructure-pages (CPU)**

**Thay đổi:**
```pbtxt
# Trước:
instance_group { count: 1 }

# Sau:
instance_group { count: 4 }
```

**Lý do:**
- Post-processing không cần GPU, chạy trên CPU
- Tăng 4 instances để tận dụng đa core CPU
- Mỗi instance xử lý độc lập, không cần batching

**Hiệu năng dự kiến:**
- **Throughput**: Tăng 3-4x (tùy số CPU cores)
- **CPU Utilization**: Phân bổ đều trên các cores

---

### 3. **Tối ưu Gateway**

**File `.env.optimized`:**
```bash
HPS_MAX_CONCURRENT_INFERENCE_REQUESTS=48    # Tăng từ 16 → 48
HPS_MAX_CONCURRENT_NON_INFERENCE_REQUESTS=128  # Tăng từ 64 → 128
HPS_INFERENCE_TIMEOUT=900                   # Tăng từ 600 → 900s
UVICORN_WORKERS=4                           # Giữ nguyên
```

**Lý do:**
- **48 concurrent inference**: Phù hợp với 2 instances × batch_size 32 = 64 capacity
- **128 non-inference**: CPU có thể xử lý nhiều request đồng thời
- **900s timeout**: Dự phòng cho document rất phức tạp

---

## 📈 Cách áp dụng

### Option 1: Tự động (khuyến nghị)

```bash
cd deploy/paddleocr_vl_docker/hps

# 1. Chạy script tối ưu
bash optimize_triton.sh

# 2. Áp dụng cấu hình gateway
cp .env.optimized .env

# 3. Restart services
docker compose down
docker compose up --build
```

### Option 2: Thủ công

1. **Cập nhật `layout-parsing/config_gpu.pbtxt`:**
   ```bash
   cp model_repo/layout-parsing/config_gpu_optimized.pbtxt \
      model_repo/layout-parsing/config_gpu.pbtxt
   ```

2. **Cập nhật `restructure-pages/config.pbtxt`:**
   ```bash
   cp model_repo/restructure-pages/config_optimized.pbtxt \
      model_repo/restructure-pages/config.pbtxt
   ```

3. **Cập nhật `.env`:**
   ```bash
   cp .env.optimized .env
   ```

4. **Rebuild và restart:**
   ```bash
   docker compose down
   docker compose up --build
   ```

---

## 🔍 Giám sát hiệu năng

### Kiểm tra Triton metrics:

```bash
# Xem log Triton
docker logs paddleocr-vl-tritonserver -f

# Kiểm tra model status
curl http://localhost:8000/v2/repository/models/layout-parsing

# Xem GPU utilization
nvidia-smi dmon -i 0
```

### Metrics quan trọng:

| Metric | Trước | Sau (kỳ vọng) | Cách đo |
|--------|-------|---------------|---------|
| **GPU Utilization** | 40-50% | 80-90% | `nvidia-smi` |
| **Throughput (img/s)** | ~50 | ~150-200 | Log gateway |
| **Avg Latency** | 200ms | 250-300ms | Log gateway |
| **P99 Latency** | 500ms | 400ms | Log gateway |
| **Queue Depth** | Cao | Thấp | Triton metrics |

---

## ⚠️ Lưu ý

### Khi tăng `max_batch_size`:

- **显存 (VRAM) usage sẽ tăng**:
  - PP-DocLayoutV3: ~2GB @ batch=8 → ~6-8GB @ batch=32
  - Đảm bảo GPU có đủ VRAM (L40S có 48GB ✅)

### Khi tăng `instance_count`:

- **Mỗi instance nhân đôi VRAM**:
  - 1 instance: ~6GB
  - 2 instances: ~12GB
  - Vẫn an toàn trên L40S (48GB)

### Khi tăng `concurrent requests`:

- **Gateway memory tăng**: Mỗi request tốn ~10-20MB RAM
- **48 requests × 20MB = ~1GB RAM** cho gateway

---

## 🎯 Cấu hình cho các scenario khác

### Scenario A: High Throughput (xử lý hàng loạt)

```bash
# .env.high-throughput
HPS_MAX_CONCURRENT_INFERENCE_REQUESTS=64
HPS_MAX_CONCURRENT_NON_INFERENCE_REQUESTS=256
UVICORN_WORKERS=8

# layout-parsing/config_gpu.pbtxt
max_batch_size: 64
instance_group { count: 4 }
dynamic_batching {
  preferred_batch_size: [ 32, 64 ]
  max_queue_delay_microseconds: 200000  # 200ms
}
```

**Phù hợp:** Xử lý PDF hàng loạt, không quan tâm latency

---

### Scenario B: Low Latency (real-time API)

```bash
# .env.low-latency
HPS_MAX_CONCURRENT_INFERENCE_REQUESTS=8
HPS_MAX_CONCURRENT_NON_INFERENCE_REQUESTS=32
UVICORN_WORKERS=2
HPS_INFERENCE_TIMEOUT=300

# layout-parsing/config_gpu.pbtxt
max_batch_size: 16
instance_group { count: 1 }
dynamic_batching {
  preferred_batch_size: [ 4, 8 ]
  max_queue_delay_microseconds: 50000  # 50ms
}
```

**Phù hợp:** API real-time, ưu tiên response time nhanh

---

### Scenario C: Balanced (default - khuyến nghị)

```bash
# .env.optimized (như đã tạo)
HPS_MAX_CONCURRENT_INFERENCE_REQUESTS=48
HPS_MAX_CONCURRENT_NON_INFERENCE_REQUESTS=128
UVICORN_WORKERS=4

# layout-parsing/config_gpu.pbtxt
max_batch_size: 32
instance_group { count: 2 }
dynamic_batching {
  preferred_batch_size: [ 16, 32 ]
  max_queue_delay_microseconds: 100000  # 100ms
}
```

**Phù hợp:** Hầu hết các use case, cân bằng throughput và latency

---

## 📊 Benchmark kết quả (dự kiến)

### Test với 100 requests (10 trang PDF × 10 files):

| Cấu hình | Tổng thời gian | Throughput | Avg Latency | P99 Latency |
|----------|----------------|------------|-------------|-------------|
| **Default** | ~120s | ~0.8 req/s | 250ms | 800ms |
| **Optimized** | ~35s | ~2.8 req/s | 300ms | 500ms |
| **Cải thiện** | **3.4x nhanh hơn** | **3.5x** | +20% | **-37%** |

---

## 🔮 Nâng cao: Multi-GPU (nếu có)

Nếu có 2 GPUs, có thể mở rộng:

```pbtxt
# layout-parsing/config_gpu.pbtxt
instance_group [
  {
    count: 2
    kind: KIND_GPU
    gpus: [ 0, 1 ]
  }
]
```

Và cập nhật `compose.yaml`:
```yaml
paddleocr-vl-tritonserver:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            device_ids: ["0", "1"]
            capabilities: [gpu]
```

---

## 📚 Tài liệu tham khảo

- [Triton Dynamic Batching](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_configuration.html#dynamic-batcher)
- [Triton Instance Groups](https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/user_guide/model_configuration.html#instance-groups)
- [NVIDIA Best Practices](https://docs.nvidia.com/deeplearning/performance/dl-performance-matrix-multiplication/index.html)
