"""Compatibility entry point for the maintained HOMR fine-tuning launcher.

Run `python homr_colab_train.py --help` locally or in Colab. Dataset preparation is
handled separately by `scripts/build_homr_finetune_dataset.py`.
"""

from scripts.train_homr_custom import main


if __name__ == "__main__":
    main()
