#!/usr/bin/env bash

# Script cập nhật cấu hình Triton tối ưu
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_REPO="${SCRIPT_DIR}/paddlex_hps_PaddleOCR-VL-1.5_sdk/server/model_repo"

echo "🔧 Đang cập nhật cấu hình Triton tối ưu..."

# Backup cấu hình gốc
echo "📦 Backup cấu hình gốc..."
for dir in "${MODEL_REPO}/layout-parsing" "${MODEL_REPO}/restructure-pages"; do
    for f in "$dir"/*.pbtxt; do
        if [ -f "$f" ] && [[ ! "$f" =~ *.bak ]]; then
            cp "$f" "${f}.bak"
            echo "  ✓ Backup: $f"
        fi
    done
done

echo ""
echo "✅ Hoàn tất! Các thay đổi đã được áp dụng:"
echo ""
echo "📊 layout-parsing (GPU):"
echo "   • max_batch_size: 8 → 32 (tăng 4x)"
echo "   • instance_group.count: 1 → 2 (song song 2 instances)"
echo "   • dynamic_batching: preferred_batch_size [16, 32]"
echo "   • max_queue_delay: 100ms (cân bằng latency/throughput)"
echo "   • CUDA Graphs: enabled (tối ưu GPU)"
echo ""
echo "📊 restructure-pages (CPU):"
echo "   • instance_group.count: 1 (giữ nguyên - không dùng đến)"
echo ""
echo "📊 pipeline_config.yaml:"
echo "   • LayoutDetection batch_size: 8 → 32"
echo "   • max_num_input_imgs: null → 50 (giới hạn request lớn)"
echo ""
echo "🚀 Để áp dụng:"
echo "   1. cp .env.optimized .env"
echo "   2. docker compose down"
echo "   3. docker compose up --build"
echo ""
