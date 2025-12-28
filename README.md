# 树莓娘 AI 虚拟主播

---

## 1. 项目介绍
「树莓娘」是网络开拓者协会的看板娘。本项目是网协技术部的一个旗舰项目，目标是实现一个树莓娘 AI 虚拟主播。

---

## 2. 仓库结构

| 目录 | 说明 |
|------|------|
| frontend | 前端代码 (`Vue`) |
| backend | 后端代码 (`Python`) |
| **backend/tts** | 后端代码 - 语音合成模块（基于 `GPT-SoVITS`，对 API 脚本进行了一定修改，且去除了部分不必要的文件） |
| **backend/llm_api** | 后端代码 - 大语言模型 API 调用实现 |
| **backend/agent** | 后端代码 - 虚拟主播代理模块 |
| backend/stream_node | 后端代码 - 流式处理工具类 |
| backend/config_types | 后端代码 - 配置类型定义 |
| backend/_examples | 后端部分代码的使用示例 （为开发者准备的） |

---

## 3. 安装项目
### 3.1 克隆仓库
``` shell
git clone https://github.com/SiliconSiliconGrass/bitnp-ai-vtuber.git
```

### 3.2 安装依赖
#### 3.2.1 安装前端依赖
> ⚠️ 请先确保已全局安装 `pnpm`。  
> 如未安装，请运行：  `npm install -g pnpm`

运行以下命令

``` shell
cd frontend
pnpm install
cd public/Resources
git clone git@git.bitnp.net:project-shumeiniang/daver3.0.git
mv daver3.0 DAver3.0
```
解释：先安装node_modules, 再从daver3.0仓库中克隆Live2D文件

#### 3.2.2 安装后端依赖
> ⚠️ 请先确保已安装`uv`。  
> 如未安装，请运行：  `pip install uv`



``` shell
cd backend
uv sync
```

⚠️ 若使用本地 Genie 语音合成引擎，需要先运行 `uv run tts/genie/setup.py` 来下载相应模型。
运行以下命令

---

## 4. 启动项目
### 4.1 启动前端
``` shell
cd frontend
pnpm dev
```

### 4.2 启动后端
#### 4.2.1 启动后端服务器
``` shell
cd backend
uv run run_server.py
```

#### 4.2.2 启动 agent 并连接到后端
``` shell
cd backend
uv run run_agent.py
```
