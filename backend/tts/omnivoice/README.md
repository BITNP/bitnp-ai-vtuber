# OmniVoice TTS 部署指南

## 概述

OmniVoice 是小米 k2-fsa 团队开源的大规模多语言零样本 TTS 模型，支持 600+ 语言、语音克隆等功能。

官方 GitHub: https://github.com/k2-fsa/OmniVoice

## 环境要求

- Python 3.10+
- CUDA 12.8+ (可选,用于 GPU 加速)
- 至少 8GB 显存 (GPU 推理)

## 安装步骤

### 1. 安装 PyTorch 和 OmniVoice

```bash
# 安装 PyTorch 2.8.0 with CUDA 12.8
uv add torch==2.8.0+cu128 torchaudio==2.8.0+cu128 --extra-index-url https://download.pytorch.org/whl/cu128

# 安装 omnivoice 包
uv add omnivoice
```

注意: 如果使用 Apple Silicon (M1/M2/M3),使用 `device_map="mps"` 代替 CUDA。

### 2. 下载模型

```bash
cd backend/tts/omnivoice
python download_model.py
```

模型将下载到 `backend/tts/omnivoice/models/k2-fsa/OmniVoice` 目录。

或者手动下载:

```bash
# 使用 huggingface-cli 下载
huggingface-cli download k2-fsa/OmniVoice --local-dir ./models/k2-fsa/OmniVoice
```

### 3. 配置国内镜像 (可选)

如果网络访问困难,可以设置 HuggingFace 镜像:

```bash
# Linux/Mac
export HF_ENDPOINT=https://hf-mirror.com

# Windows (PowerShell)
$env:HF_ENDPOINT="https://hf-mirror.com"

# 或在 Python 中
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
```

## 使用方法

### 基本用法

```python
import asyncio
from backend.tts import create_tts

async def main():
    tts = create_tts("omnivoice", language="zh")
    
    audio = await tts.synthesize("你好，世界")
    with open("output.wav", "wb") as f:
        f.write(audio)

asyncio.run(main())
```

### 语音克隆

使用参考音频进行语音克隆:

```python
tts = create_tts(
    "omnivoice",
    ref_audio="path/to/reference.wav",
    ref_text="参考音频的文本内容"
)
```

模型会自动使用 Whisper ASR 转录参考音频,也可以手动提供 `ref_text`。

### GPU 加速

```python
tts = create_tts(
    "omnivoice",
    device="cuda:0",
    dtype="float16"
)
```

### Apple Silicon

```python
tts = create_tts(
    "omnivoice",
    device="mps",
    dtype="float16"
)
```

### CPU 推理

```python
tts = create_tts(
    "omnivoice",
    device="cpu",
    dtype="float32"
)
```

## API 参考

### create_tts 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model_path` | Optional[str] | "./models/k2-fsa/OmniVoice" | 本地模型路径 |
| `device` | str | "auto" | 设备 ("cuda:0", "cpu", "mps", "auto") |
| `dtype` | str | "float16" | 模型精度 ("float16", "float32", "bfloat16") |
| `ref_audio` | Optional[str] | None | 参考音频路径 |
| `ref_text` | Optional[str] | None | 参考音频文本 |
| `language` | str | "zh" | 语言代码 (暂未使用,官方 API 未集成) |

## 官方推理示例

```python
from omnivoice import OmniVoice
import soundfile as sf
import torch

model = OmniVoice.from_pretrained(
    "./model/k2-fsa/OmniVoice",
    device_map="cuda:0",
    dtype=torch.float16
)

audio = model.generate(
    text="Hello, this is a test.",
    ref_audio="ref.wav",
    ref_text="Transcription of the reference audio."
)

sf.write("out.wav", audio[0], 24000)
```

## 故障排除

### 安装 PyTorch 失败

检查 CUDA 版本:

```bash
nvidia-smi
```

确保 CUDA 版本 >= 12.8,或使用对应版本的 PyTorch。

### 模型下载失败

使用镜像:

```bash
export HF_ENDPOINT=https://hf-mirror.com
python download_model.py
```

### 显存不足

使用 float32 或 CPU:

```python
tts = create_tts("omnivoice", device="cpu", dtype="float32")
```