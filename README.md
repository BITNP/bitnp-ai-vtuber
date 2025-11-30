# 树莓娘 AI 虚拟主播

## 1. 项目介绍
「树莓娘」是网络开拓者协会的看板娘。本项目是网协技术部的一个旗舰项目，目标是实现一个树莓娘 AI 虚拟主播。

## 2. 仓库结构
```
frontend 前端代码
backend  后端代码

backend/tts 后端代码 - 语音合成模块 (基于 GPT-SoVITS, 对api脚本进行了一定修改, 且去除了部分不必要的文件)
```

## 3. 安装步骤
### 3.1 克隆仓库
``` shell
git clone git@git.bitnp.net:project-shumeiniang/bitnp-ai-vtuber.git
```

### 3.2 安装依赖
**前端**
``` shell
cd frontend
pnpm install
cd frontend/public/Resources
git clone git@git.bitnp.net:project-shumeiniang/daver3.0.git
mv daver3.0 DAver3.0
```

**后端**
``` shell
cd backend/tts
conda create -n gptsovits python=3.10
conda activate gptsovits
pip install -r requirements.txt
python get_pretrained.py
```

## 4. 启动项目
**前端**
``` shell
cd frontend
pnpm dev
```

**后端**
启动后端服务器
``` shell
cd backend
python run_server.py
```

启动 agent 并连接到后端
``` shell
cd backend
python run_agent.py
```
