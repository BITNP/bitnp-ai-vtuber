"""
To download pretrained GPT-SoVITS models
"""
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com' # use hf-mirror (for users in China)

from huggingface_hub import snapshot_download

curr_dir = os.path.dirname(os.path.abspath(__file__))
local_dir = os.path.join(curr_dir, "GPT_SoVITS", "pretrained_models")

repo_id = "lj1995/GPT-SoVITS"
files_to_download = [
    "s2G488k.pth", # SoVITS model (v1)
    "s1bert25hz-2kh-longer-epoch=68e-step=50232.ckpt", # GPT model (v1)
    "chinese-roberta-wwm-ext-large/*", # Bert model
    "chinese-hubert-base/*" # Hubert model
]

# # if you want to download all files, uncomment the following line
# files_to_download = ["*"]

print("Downloading GPT-SoVITS pretrained models...")

try:
    snapshot_download(
        repo_id=repo_id,
        repo_type="model",
        local_dir=local_dir,
        local_dir_use_symlinks="auto",
        revision="main",
        allow_patterns=files_to_download
    )
except Exception as e:
    print(f"Failed: {e}")
else:
    print("Download completed successfully!")