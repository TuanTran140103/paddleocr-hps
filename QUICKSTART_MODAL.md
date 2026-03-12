# 🚀 Quick Start - Modal GPU Build

## Cách setup nhanh (5 phút)

### 1. Cài đặt và authenticate Modal

```bash
pip install modal
modal setup
```

### 2. Chạy build thủ công (Test trước)

```bash
# Thay YOUR_DOCKERHUB_USERNAME và YOUR_DOCKERHUB_TOKEN bằng thông tin của bạn
# Thay GITHUB_REPO_URL bằng URL repository của bạn
modal run modal_build.py \
  --dockerhub_username YOUR_DOCKERHUB_USERNAME \
  --dockerhub_token YOUR_DOCKERHUB_TOKEN \
  --github_repo https://github.com/YOUR_USERNAME/YOUR_REPO.git \
  --image_name paddleocr-triton \
  --tag latest
```

### 3. Setup GitHub Secrets (Để tự động hóa)

Vào **Settings** → **Secrets and variables** → **Actions**, thêm:

| Secret | Giá trị |
|--------|---------|
| `MODAL_TOKEN_ID` | Từ https://modal.com/settings |
| `MODAL_TOKEN_SECRET` | Từ https://modal.com/settings |
| `DOCKERHUB_USERNAME` | Docker Hub username |
| `DOCKERHUB_TOKEN` | Docker Hub token (https://hub.docker.com/settings/security) |

### 4. Chạy workflow tự động

Workflow sẽ tự động chạy khi push code, hoặc chạy thủ công từ tab **Actions**.

---

## ⚡ Lệnh hữu ích

```bash
# Build với tag custom
modal run modal_build.py \
  --dockerhub_username YOUR_USERNAME \
  --dockerhub_token YOUR_TOKEN \
  --github_repo https://github.com/YOUR_USERNAME/YOUR_REPO.git \
  --tag v1.0.0

# Build với tag từ commit SHA
modal run modal_build.py \
  --dockerhub_username YOUR_USERNAME \
  --dockerhub_token YOUR_TOKEN \
  --github_repo https://github.com/YOUR_USERNAME/YOUR_REPO.git \
  --tag $(git rev-parse --short HEAD)

# Build từ branch khác
modal run modal_build.py \
  --dockerhub_username YOUR_USERNAME \
  --dockerhub_token YOUR_TOKEN \
  --github_repo https://github.com/YOUR_USERNAME/YOUR_REPO.git \
  --branch develop \
  --tag latest
```

---

## 🎯 Kết quả

Sau khi build xong:

```bash
# Pull image về
docker pull YOUR_USERNAME/paddleocr-triton:latest

# Chạy với GPU
docker run --gpus all YOUR_USERNAME/paddleocr-triton:latest
```

---

## 💡 Tips

- **Free tier**: Modal cho ~$30 credit/tháng
- **GPU T4**: ~$0.0003/giây (~$1/giờ)
- **Thời gian build**: 5-15 phút
- **Cost per build**: ~$0.05 - $0.15
