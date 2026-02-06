
依赖python-pptx库

### 1.模型

依赖智谱 AI 的 **glm-4-flash**和**glm-4v-flash** 模型。确保 `backend/tokens/tokens.json` 文件存在且包含有效的 API Key

### 2.运行

    import asyncio
    from backend.ppt_generator import generate_ppt_scripts
    from backend.tokens import get_token
    
    async def main():
        ppt_path = "C:/Docs/demo.pptx"  # ppt路径
        
        vision_config = {
            "provider": "glm",
            "api_key": get_token('glm')
        }
        
        # 3. 获取文本生成 Key
        text_key = get_token('glm')
    
        # 4. 执行生成
        print("正在生成讲稿...")
        await generate_ppt_scripts(ppt_path, vision_config, text_key)
        print("生成完成！")
    
    if __name__ == "__main__":
        asyncio.run(main())

或直接修改`ppt_script.py`底部的`PPT_FILE`为你的目标文件夹运行



运行结束后生成四个文件

    1.*_json: 每页的PPT文字、视觉描述和讲解台词
    2.*_ppt_text: 每页的文字内容
    3.*_scripts: 每页的讲解
    4.*_vision: 每页图片的视觉描述
    保存在PPT文件所在目录下自动创建的名为 generated_scripts 的文件夹，
