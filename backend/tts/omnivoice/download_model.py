"""
OmniVoice 模型下载脚本

使用 huggingface_hub 从 HuggingFace 下载 OmniVoice 模型权重到本地
"""
import os

curr_dir = os.path.dirname(os.path.abspath(__file__))
model_dir = os.path.join(curr_dir, "models")


def download_models():
    """从 HuggingFace 下载 OmniVoice 模型"""
    from huggingface_hub import snapshot_download
    
    model_id = "k2-fsa/OmniVoice"
    
    print("========== 下载 OmniVoice 模型 ==========")
    print(f"模型ID: {model_id}")
    print(f"保存路径: {model_dir}")
    
    os.makedirs(model_dir, exist_ok=True)
    
    local_dir = snapshot_download(
        repo_id=model_id,
        repo_type="model",
        local_dir=model_dir,
        local_dir_use_symlinks="auto",
        revision="main"
    )
    
    print("========== 模型下载完成 ==========")
    print(f"模型路径: {local_dir}")
    
    return local_dir


if __name__ == "__main__":
    download_models()