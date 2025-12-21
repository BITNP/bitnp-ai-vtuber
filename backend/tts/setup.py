"""
Setup for tts (text to speech) module
"""
import os
import subprocess
curr_dir = os.path.dirname(os.path.abspath(__file__))

# 1. 克隆 Genie-TTS 仓库 (包含混合语言支持)
print("========== Step 1/2: Cloning Genie-TTS repository... ==========")
# # original github repo
# genie_with_hybrid_language_support_repo_id = "https://githubfast.com/SiliconSiliconGrass/Genie-TTS.git"
# using "githubfast" mirror
genie_with_hybrid_language_support_repo_id = "https://githubfast.com/SiliconSiliconGrass/Genie-TTS.git"
subprocess.run(["git", "clone", genie_with_hybrid_language_support_repo_id], cwd=curr_dir)

# 2. 下载预训练模型
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ["GENIE_DATA_DIR"] = os.path.join(curr_dir, "GenieData")

from huggingface_hub import snapshot_download
from modelscope import snapshot_download as snapshot_download_modelscope

model_dir = os.path.join(curr_dir, 'pretrained')

def download_models_hf(repo_id: str, files_to_download: list[str], local_dir: str):
    snapshot_download(
        repo_id=repo_id,
        repo_type="model",
        local_dir=local_dir,
        local_dir_use_symlinks="auto",
        revision="main",
        allow_patterns=files_to_download
    )


genie_repo_id = "High-Logic/Genie"
genie_models = [
    "GenieData/*", # base models
    # "CharacterModels/v2ProPlus/mika/*", # pre-defined character "mika"
    # "CharacterModels/v2ProPlus/feibi/*", # pre-defined character "feibi"
]

pretrained_repo_id = "IndexError/gptsovits-v2proplus-genie-onnx-export"

# 下载 genie 提供的 mika 预设模型 (暂时使用该模型)
# TODO: 使用自己的预训练模型
print("========== Step 2/2: Downloading pretrained models... ==========")
download_models_hf(genie_repo_id, genie_models, model_dir)
snapshot_download_modelscope(pretrained_repo_id, cache_dir=model_dir)
