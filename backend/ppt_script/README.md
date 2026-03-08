
依赖pdf2image库（需要安装poppler系统依赖）

### 1.模型

依赖VLM模型。确保 `backend/tokens/tokens.json` 文件存在且包含有效的 API Key

### 2.运行

    import asyncio
    from backend.ppt_script import generate_presentation_scripts
    from backend.tokens import get_token
    
    async def main():
        image_dir = "../frontend/public/documents/slides"  # 图片目录路径（包含已转换的幻灯片图片）
        
        vision_config = {
            "provider": "glm",
            "api_key": get_token('glm')
        }
        
        # 3. 获取文本生成 Key
        text_key = get_token('glm')
    
        # 4. 执行生成
        print("正在生成讲稿...")
        await generate_presentation_scripts(image_dir, vision_config, text_key)
        print("生成完成！")
    
    if __name__ == "__main__":
        asyncio.run(main())

或直接使用命令行运行（推荐）：
    
    python ppt_script.py ../frontend/public/documents/slides



运行结束后生成四个文件

    1.*_data.json: 每页的PDF文字、视觉描述和讲解台词的完整数据
    2.*_scripts.txt: 每页的讲解台词（包含 [PDF_x] 标记）
    3.*_pdf_text.txt: 每页的原始文字内容
    4.*_vision.txt: 每页图片的视觉描述（此项为空，因直接生成讲稿）
    保存在图片目录下自动创建的名为 generated_scripts 的文件夹，

---

## 讲稿驱动播放（lecture_agent）

讲稿生成后，可直接用 `lecture_agent` 自动播讲并翻页：

1. 准备讲稿与图片
    - 讲稿文件：`generated_scripts/*_scripts.txt`
    - PPT 图片目录：例如 `frontend/public/documents/slides`（图片文件名按页码排序）

2. 启动后端服务器（托管 PPT 图片）
    - `uv run run_server.py --ppt-images-dir <图片目录> --ppt-mount-path /documents/slides`

3. 启动讲稿驱动 Agent
    - `uv run run_agent.py --agent-type lecture_agent --lecture-script <*_scripts.txt 或 generated_scripts 目录> --ppt-images-dir <图片目录>`

前端会收到 `ppt_assets` 事件并自动加载图片；讲稿播放会按 `[PDF_x]` 触发翻页。