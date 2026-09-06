"""
homr Colab fine-tune 脚本
用法：在 Google Colab 单元格粘贴运行

准备数据格式：
  data/
    train/
      images/   <- 谱图 PNG/JPG
      scores/   <- 对应 MusicXML (文件名匹配)
    val/
      images/
      scores/

文件命名规则：images/foo.png 对应 scores/foo.musicxml
"""

# ========== Cell 1: 装环境 ==========
# !git clone https://github.com/liebharc/homr.git
# %cd homr
# !pip install poetry
# !poetry install --extras gpu
# !poetry run homr --init  # 下载预训练模型
# !python -c "import onnxruntime; print(onnxruntime.get_device())"  # 应该显示 GPU


# ========== Cell 2: 上传数据 ==========
# 方式 A: 直接上传 zip
# from google.colab import files
# uploaded = files.upload()  # 上传 data.zip
# !unzip -q data.zip -d /content/data

# 方式 B: 从 Google Drive
# from google.colab import drive
# drive.mount('/content/drive')
# !ls /content/drive/MyDrive/sposobin_data


# ========== Cell 3: 数据格式转换（MusicXML -> homr 训练格式） ==========
"""
homr 训练数据要求 (来自 homr/training/data_preparation.py)：
- 谱图 + MusicXML 对
- 谱图按 staff 切分（每个 staff 一张图）
- MusicXML 按 staff 解析为 token 序列

如已有现成数据，按下面规则组织：
  data/train/images/staff_001.png  (单行谱)
  data/train/scores/staff_001.musicxml
"""
import os
from pathlib import Path
import music21

def prepare_sposobin_dataset(data_dir: str, output_dir: str):
    """
    将用户数据转为 homr 训练格式。
    输入: data_dir/{images,scores}/ 谱图 + MusicXML 对
    输出: output_dir/staffs/ 单行谱图 + token json
    """
    images_dir = Path(data_dir) / "images"
    scores_dir = Path(data_dir) / "scores"
    out_dir = Path(output_dir) / "staffs"
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for img_path in sorted(images_dir.glob("*.png")):
        score_path = scores_dir / (img_path.stem + ".musicxml")
        if not score_path.exists():
            score_path = scores_dir / (img_path.stem + ".xml")
        if not score_path.exists():
            print(f"skip {img_path.name} - no matching score")
            continue

        # 解析 MusicXML
        score = music21.converter.parse(str(score_path))
        # 简单验证
        manifest.append({
            "image": str(img_path),
            "score": str(score_path),
            "measures": len(score.parts[0].getElementsByClass("Measure")),
        })
        print(f"OK {img_path.name}: {manifest[-1]['measures']} measures")

    print(f"\nTotal: {len(manifest)} samples")
    return manifest


# ========== Cell 4: 配置 + 启动训练 ==========
"""
homr 训练入口: training/transformer/train.py
配置在 homr/transformer/configs.py

关键参数:
  - learning_rate: 1e-4 (从 TrOMR paper)
  - batch_size: 16 train / 8 eval
  - epochs: 30
  - optimizer: AdamW
  - 数据集混合权重: (1.0, 1.0, 1.0)

启动命令（需要在 homr 目录内）:
  !poetry run python training/transformer/train.py \\
      --training.max_epochs=10 \\
      --training.batch_size=8 \\
      --data.train_dirs=/content/data/train \\
      --data.val_dirs=/content/data/val
"""


# ========== Cell 5: 导出 ONNX (回 Windows 推理) ==========
"""
训练完导出 .pth → .onnx
然后把 .onnx 拷回 Windows，替换 homr 包里的默认模型。

导出命令:
  !poetry run python training/transformer/export_onnx.py \\
      --checkpoint /content/homr/training/architecture/transformer/run_XXX.pth \\
      --output /content/homr_finetuned.onnx
"""
