# Hướng dẫn setup Modal GPU Build

Hướng dẫn này giúp bạn build Triton Docker image với GPU trên Modal và push lên Docker Hub.

## 📋 Yêu cầu

1. **Tài khoản Modal** - Đăng ký tại https://modal.com/
2. **Tài khoản Docker Hub**
3. **GitHub repository** của bạn

---

## 🔧 Setup Modal (Local)

### Bước 1: Cài đặt Modal CLI

```bash
pip install modal
```

### Bước 2: Authenticate với Modal

```bash
modal setup
```

Làm theo hướng dẫn để lấy token từ https://modal.com/settings

### Bước 3: Chạy build thủ công (optional)

```bash
# Cách 1: Truyền tham số trực tiếp
modal run modal_build.py \
  --dockerhub_username YOUR_DOCKERHUB_USERNAME \
  --dockerhub_token YOUR_DOCKERHUB_TOKEN \
  --image_name paddleocr-triton \
  --tag latest

# Cách 2: Dùng environment variables
export DOCKERHUB_USERNAME=your_username
export DOCKERHUB_TOKEN=your_token
modal run modal_build.py
```

---

## 🔐 Setup GitHub Secrets

Để workflow tự động chạy, bạn cần thêm các secrets sau vào GitHub repository:

1. Vào **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

2. Thêm các secrets:

| Secret Name | Giá trị |
|-------------|---------|
| `MODAL_TOKEN_ID` | Token ID từ Modal settings |
| `MODAL_TOKEN_SECRET` | Token Secret từ Modal settings |
| `DOCKERHUB_USERNAME` | Docker Hub username của bạn |
| `DOCKERHUB_TOKEN` | Docker Hub access token (Personal access token) |

### Lấy Modal Tokens:

1. Truy cập https://modal.com/settings
2. Copy **Token ID** và **Token Secret**

### Tạo Docker Hub Token:

1. Truy cập https://hub.docker.com/settings/security
2. Click **New Access Token**
3. Đặt tên (ví dụ: `github-actions`)
4. Copy token và lưu vào GitHub Secrets

---

## 🚀 Chạy Workflow

### Tự động (Auto-trigger)

Workflow sẽ tự động chạy khi:
- Push commit thay đổi `tritonserver.Dockerfile`
- Push commit thay đổi files trong `paddlex_hps_PaddleOCR-VL-1.5_sdk/server/`

### Thủ công (Manual)

1. Vào tab **Actions** của repository
2. Chọn workflow **Build and Push Triton Docker Image (via Modal)**
3. Click **Run workflow**
4. (Optional) Nhập tag custom hoặc để `latest`
5. Click **Run workflow**

---

## 📦 Docker Image Tags

Workflow tự động tạo tags:

| Tag | Mô tả |
|-----|-------|
| `latest` | Tag mặc định (khi chạy manual) |
| `<short-sha>` | Tag từ commit SHA (ví dụ: `a1b2c3d`) |

---

## 💰 Chi phí Modal

Modal cung cấp:
- **Free tier**: ~$30 credit/tháng cho tài khoản mới
- **GPU T4**: ~$0.0003/giây (~$1/giờ)

Mỗi build thường tốn ~5-15 phút tùy vào:
- Thời gian pull base image
- Thời gian build
- Thời gian push lên Docker Hub

**Ước tính**: ~$0.05 - $0.15/build

---

## 🐛 Troubleshooting

### Lỗi: "Modal token is invalid"
- Kiểm tra lại tokens trong GitHub Secrets
- Regenerate tokens từ Modal settings nếu cần

### Lỗi: "Docker Hub login failed"
- Kiểm tra Docker Hub username chính xác
- Tạo mới Docker Hub token tại https://hub.docker.com/settings/security

### Lỗi: "Build timeout"
- Tăng timeout trong `modal_build.py` (dòng `timeout=3600`)
- Kiểm tra base image có sẵn sàng không

### Lỗi: "No GPU available"
- Modal đang hết GPU T4 free tier
- Thử lại sau hoặc upgrade tài khoản Modal

---

## 📝 Customization

### Đổi GPU type

Trong `modal_build.py`, thay đổi dòng:

```python
gpu="T4",  # Các option: "T4", "A10G", "A100", "H100"
```

### Đổi timeout

```python
timeout=3600,  # seconds (1 giờ)
```

### Thêm build args

Trong `modal_build.py`, thêm vào `buildargs`:

```python
buildargs={
    "DEVICE_TYPE": "gpu",
    "BASE_IMAGE": "your-custom-base-image",
},
```

---

## ✅ Verify Build

Sau khi build xong:

```bash
# Pull image về test
docker pull YOUR_DOCKERHUB_USERNAME/paddleocr-triton:latest

# Chạy test với GPU
docker run --gpus all YOUR_DOCKERHUB_USERNAME/paddleocr-triton:latest
```

---

## 📞 Support

- Modal docs: https://modal.com/docs
- GitHub Actions docs: https://docs.github.com/actions
