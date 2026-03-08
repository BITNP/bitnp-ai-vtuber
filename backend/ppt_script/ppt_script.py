import asyncio
import os
import sys
import base64
import json
import requests
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import functools
import glob
import re
#import logging

from PIL import Image  #  pip install Pillow

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.llm_api.glm import GlmBot  # type: ignore
    from backend.tokens import get_token  # type: ignore
except ImportError:
    from llm_api.glm import GlmBot
    from tokens import get_token

# 1.视觉识图 - using vlm_api abstraction
try:
    from vlm_api import create_vlm
except ImportError:
    # Fallback for development
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from vlm_api import create_vlm


# 2.直接从预转换图片目录加载图片
def load_preconverted_images(image_dir: str) -> List[Dict]:
    """
    从预转换的图片目录中加载图片
    图片目录默认为 ../frontend/public/documents/slides
    """
    # 查找匹配的图片文件 (幻灯片XXX.PNG 或 slide_XXX.png)
    png_pattern = os.path.join(image_dir, "幻灯片*.PNG")
    png_files = glob.glob(png_pattern)
    
    if not png_files:
        png_pattern = os.path.join(image_dir, "slide_*.png")
        png_files = glob.glob(png_pattern)
    
    # 排序图片文件以确保正确的页面顺序
    png_files.sort(key=lambda x: int(re.search(r'(\d+)', os.path.basename(x)).group(1)) if re.search(r'(\d+)', os.path.basename(x)) else 0)
    
    slides_data = []
    for i, image_path in enumerate(png_files):
        try:
            # 为图片创建基本文本描述（因为没有PDF，所以暂时使用占位符）
            slides_data.append(
                {
                    "page": i + 1,
                    "text": f"第{i+1}页内容",  # 占位文本，实际应用中可能需要OCR或其他方式获取文本
                    "image_path": image_path  # 添加图片路径用于后续处理，但不包含二进制数据
                }
            )
        except Exception as e:
            print(f"无法读取图片 {image_path}: {e}")
    
    return slides_data


# 3.核心处理

async def generate_presentation_scripts(
    image_dir: str, vision_config: Dict
):
    # 从预转换的图片目录加载图片
    slides = load_preconverted_images(image_dir)
    total_pages = len(slides)

    vision_bot = create_vlm(**vision_config)

    # 构建输入：将所有图片和文本信息按顺序组合
    inputs = []
    
    for slide in slides:
        # 添加页面文本内容
        inputs.append({
            "type": "text", 
            "content": f"第{slide['page']}页内容：{slide['text']}\n"
        })
        
        # 添加该页的图片（使用VLM的预处理功能）
        if 'image_path' in slide:
            with open(slide['image_path'], 'rb') as img_file:
                img_bytes = img_file.read()
                # 只有在图像较大时才添加到输入
                if len(img_bytes) > 3 * 1024:
                    # 使用VLM的预处理功能处理图片
                    processed_img_data = await vision_bot.preprocess_image(img_bytes)
                    inputs.append({
                        "type": "image",
                        "data": processed_img_data
                    })
    
    # 定义直接生成讲稿的提示
    presentation_script_prompt = f"""
    你现在是"树莓娘"，是网络开拓者协会（网协，北理工学生组织）的看板娘。
    你正在进行一场技术分享会的直播，主题是关于演示文稿内容的讲解。
    
    请直接为整个演示文稿生成完整的讲解台词，不要做视觉描述分析，直接开始讲稿创作。
    
    【演示文稿内容】
    以上包含了完整的演示文稿内容，包含多页幻灯片的图片和文字。
    
    【讲稿生成要求】
    1. 每一页讲稿的最开头必须严格输出 `[PDF_x]` （x是对应页码）。
       - 正确示例：`[PDF_1] 大家好！我是树莓娘...`
       - 错误示例：`好的，第1页：大家好...`
    2. 严禁 Markdown：绝对不要使用 `**加粗**`、`# 标题`、`- 列表` 等符号，直接用自然语言表达。
    3. 逻辑衔接：严禁使用"下一页是"、"接下来看下一页"、"好的"、"好呀"这种报幕词。要用内容逻辑自然过渡。
    4. 不要机械地朗读文字！要生动地讲解内容。
    5. 用口语化的表达，不要读得太书面化。
    6. 表情动作：说话时必须自然地穿插表情指令，仅限使用：[点头] [摇头] [wink]。平均每段话使用1~2个。
    7. 如果某页文字极少（如仅有标题），请结合图片内容或主题进行发挥，不要只说一句话。
    8. 讲稿需要有良好的连贯性和流畅的逻辑过渡。
    9. 结尾处要有适当的总结和告别语。
    10. 语气活泼，禁止 Markdown 符号 和 emoji 符号。
    11. 避免使用"下一页"、"接下来"等报幕词，避免在开头说当前页码。
    12. 不要说"好呀"、"好的"等口头禅。
    13. 避免在开头回顾上一页内容，要直接切入主题。
    14. 拒绝平铺直叙：不要把文字都念一遍！挑一个重点深入讲。
    """

    # 使用VLM直接生成完整讲稿
    full_script = await vision_bot.multimodal_request(inputs, presentation_script_prompt)
    #logging.getLogger(__name__).debug(f"完整讲稿生成完成：{full_script}")
    print(f"完整讲稿生成完成：{full_script}")
    # 解析整体讲稿，分离每页内容
    full_results = []
    script_parts = full_script.split('[PDF_')
    
    # 处理第一部分（如果没有以[PDF_开头的部分）
    if script_parts and not full_script.startswith('[PDF_'):
        script_parts = script_parts[1:]  # 移除第一部分
    
    for part in script_parts:
        if not part.strip():
            continue
            
        # 提取页码和内容
        parts = part.split(']', 1)
        if len(parts) >= 2:
            try:
                page_num = int(parts[0])
                content = parts[1].strip()
                
                # 找到对应的页面数据
                page_data = next((d for d in slides if d["page"] == page_num), None)
                if page_data:
                    full_results.append({
                        "page": page_num,
                        "text": page_data["text"],
                        "vision": "",  # 不再使用视觉描述
                        "script": f"[PDF_{page_num}] {content}"
                    })
            except ValueError:
                continue  # 如果无法解析页码，则跳过

    # 确保所有页面都有对应的讲稿
    for slide in slides:
        if not any(r["page"] == slide["page"] for r in full_results):
            # 如果某页没有生成讲稿，使用单独生成的方式
            # 这里为了简化，我们不会真的单独生成，而是记录缺失
            print(f"警告：第{slide['page']}页未能从整体讲稿中解析出内容")
            # 为缺失的页面创建基本结构
            full_results.append({
                "page": slide["page"],
                "text": slide["text"],
                "vision": "",
                "script": f"[PDF_{slide['page']}] 请补充讲稿内容"
            })

    # 按页面顺序排序
    full_results.sort(key=lambda x: x["page"])

    # 使用原始的PDF文件路径作为基础名，如果没有则使用目录名
    pdf_path = os.path.join(image_dir, "dummy.pdf")  # 创建一个虚拟路径用于保存函数
    save_files(pdf_path, full_results)


def save_files(pdf_path, results):
    """
    保存四个文件到指定目录下的 generated_scripts 文件夹:
    1.*_data.json: 每页的PDF文字、视觉描述和讲解台词的完整数据
    2.*_scripts.txt: 每页的讲解台词（包含 [PDF_x] 标记）
    3.*_pdf_text.txt: 每页的原始文字内容
    4.*_vision.txt: 每页图片的视觉描述（当前为空，因为我们直接生成讲稿）
    
    保存路径: 
    - 如果输入是真实PDF路径: 在PDF同级目录下创建 generated_scripts 文件夹
    - 如果输入是虚拟路径（如dummy.pdf）: 在图片目录下创建 generated_scripts 文件夹
    """
    # 清理结果数据，移除任何不能序列化的字段（如图片字节数据）
    cleaned_results = []
    for item in results:
        cleaned_item = {
            "page": item.get("page"),
            "text": item.get("text"),
            "vision": item.get("vision", ""),
            "script": item.get("script")
        }
        cleaned_results.append(cleaned_item)
    
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(pdf_path)), "generated_scripts"
    )
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    base = os.path.splitext(os.path.basename(pdf_path))[0]

    json_path = os.path.join(out_dir, f"{base}_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_results, f, ensure_ascii=False, indent=4)

    script_txt_path = os.path.join(out_dir, f"{base}_scripts.txt")
    with open(script_txt_path, "w", encoding="utf-8") as f:
        for item in cleaned_results:
            f.write(f"{item['script']}\n\n")

    vision_txt_path = os.path.join(out_dir, f"{base}_vision.txt")
    with open(vision_txt_path, "w", encoding="utf-8") as f:
        for item in cleaned_results:
            f.write(f" 第 {item['page']} 页 \n")
            f.write(f"{item['vision'] if item['vision'] else '(无视觉描述，直接生成讲稿)'}\n")
            f.write("\n")

    pdf_text_path = os.path.join(out_dir, f"{base}_pdf_text.txt")
    with open(pdf_text_path, "w", encoding="utf-8") as f:
        for item in cleaned_results:
            f.write(f" 第 {item['page']} 页 \n")
            f.write(f"{item['text']}\n")
            f.write("\n")


from argparse import ArgumentParser


def args_parse():
    parser = ArgumentParser(
        description="""演示文稿讲稿生成器
        - 直接从预转换的图片目录生成讲解稿
        - 无需事先生成视觉描述，直接使用VLM模型生成完整讲稿
        - 输出4个文件到generated_scripts子目录: JSON数据、讲稿、原文、视觉描述（空）""",
        epilog="""示例: python ppt_script.py ../frontend/public/documents/slides
        
        输出文件说明:
        - [basename]_data.json: 每页的完整数据（文字、视觉、讲稿）
        - [basename]_scripts.txt: 讲解台词（含[PDF_x]标记）
        - [basename]_pdf_text.txt: 原始文字内容
        - [basename]_vision.txt: 视觉描述（此项为空，因直接生成讲稿）
        
        生成的文件保存在图片目录下的 generated_scripts 子目录中."""
    )
    parser.add_argument("image_dir", type=str, help="图片目录路径（包含已转换的幻灯片图片，支持幻灯片*.PNG或slide_*.png格式）")
    return parser.parse_args()


if __name__ == "__main__":
    from tokens import get_token
    #logging.basicConfig(level=logging.DEBUG)

    VISION_CFG = {"provider": "openai", "api_key": get_token("openai"), "model_name": "Qwen3.5-4B", "timeout": 1200}
    args = args_parse()
    IMAGE_DIR = args.image_dir
    if os.path.exists(IMAGE_DIR):
        asyncio.run(generate_presentation_scripts(IMAGE_DIR, VISION_CFG))
    else:
        print("目录不存在")