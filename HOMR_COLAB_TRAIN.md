# homr Colab Fine-tune 教程

## 概览
- **目标**：用 PRIMUS + GrandStaff + Lieder 公开数据集 fine-tune homr TrOMR 模型
- **硬件**：Google Colab 免费 T4 16GB
- **时间**：~5-6 小时（10k subset + 5 epoch）
- **输出**：fine-tune 后的 ONNX 模型，回 Windows 替换

## 步骤

### Cell 1: 开 GPU
```
菜单 → 运行时 → 更改运行时类型 → 硬件加速器 → T4 GPU
```

### Cell 2: 检查环境
```python
!nvidia-smi
!python --version
!df -h /content  # 看可用空间
```

### Cell 3: 装系统依赖
```bash
!apt-get update -qq
!apt-get install -y -qq librsvg2-bin libfuse2 libjack-jackd2-0 fuse
```

### Cell 4: Clone homr + 装 poetry
```bash
!git clone https://github.com/liebharc/homr.git
%cd homr
!pip install -q poetry
!poetry config virtualenvs.create false
!poetry install --extras gpu
```

### Cell 5: 下预训练模型
```bash
!poetry run homr --init
```

### Cell 6: 下 + 转换 PRIMUS (~30 分钟)
```bash
!mkdir -p datasets
# PRIMUS 自动下
!poetry run python training/omr_datasets/convert_primus.py
```

### Cell 7: 下 + 转换 GrandStaff + Lieder (~1 小时)
```bash
!poetry run python training/omr_datasets/convert_grandstaff.py
!poetry run python training/omr_datasets/convert_lieder.py
```

### Cell 8: 截取 10k subset
```python
import random
random.seed(42)

for split in ['train', 'val']:
    idx_path = f'datasets/primus_{split}_index.txt'
    with open(idx_path) as f:
        lines = f.readlines()
    n = 10000 if split == 'train' else 500
    sampled = random.sample(lines, min(n, len(lines)))
    with open(idx_path, 'w') as f:
        f.writelines(sampled)
    print(f"{split}: {len(sampled)}/{len(lines)}")
```

### Cell 9: 启动训练 (后台)
```bash
!poetry run python training/train.py transformer \
    --training.max_epochs=5 \
    --training.batch_size=18 \
    --training.learning_rate=5e-5 \
    > training_run.log 2>&1 &
!echo $! > train.pid
```

### Cell 10: 监控进度
```python
!tail -50 training_run.log
!nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv
```

### Cell 11: 训练完后导出 ONNX
```bash
# 找到最新 checkpoint
!ls training/architecture/transformer/
!poetry run python training/onnx/convert.py \
    --checkpoint training/architecture/transformer/pytorch_model_XXX.pth \
    --output homr_finetuned.onnx
```

### Cell 12: 打包下载
```python
import shutil
# 替换 3 个 fine-tuned 模型
for f in ['encoder', 'decoder']:
    src = f"training/architecture/transformer/{f}_pytorch_model_*.onnx"
    dst = f"homr_{f}_finetuned.onnx"
    !cp $src $dst

# 打包
shutil.make_archive('homr_finetuned_models', 'zip', '.', '.')
from google.colab import files
files.download('homr_finetuned_models.zip')
```

## Windows 端回装
1. 解压 zip
2. 复制到 `C:\Users\Administrator\AppData\Roaming\uv\tools\homr\Lib\site-packages\homr\transformer\`
3. 改 homr/transformer/configs.py 里的 `model_name` 指向新 checkpoint hash
4. 跑你的 Sposobin 题测准确率

## 注意事项
- Colab 12 小时限制；用 `nohup`/`&` 后台跑 + 监控
- 如果中途 GPU 断了，checkpoint 在 `training/architecture/transformer/pytorch_model_XXX.pth`，下次 resume
- 5 epoch 可能不够，建议至少 10 epoch（按 epoch 数据 ~30 分钟/epoch 算）

## 故障
- **MuseScore 下载失败**：训练只能用 homr 训练集自带的 converted 数据
- **CUDA OOM**：batch_size 减到 8
- **Poetry 装包慢**：用清华源 `poetry config repositories.pypi https://pypi.tuna.tsinghua.edu.cn/simple`
