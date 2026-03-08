#!/usr/bin/env python3
"""
PDF转图片工具
使用pdf2image库将PDF转换为高质量图片
需要系统安装poppler依赖
支持跨平台使用，具有良好的可移植性。

注意：需要先安装poppler系统依赖
Ubuntu/Debian: sudo apt-get install poppler-utils
macOS: brew install poppler
Windows: 从 https://github.com/oschwartz10612/poppler-windows/releases/ 下载并添加到PATH

运行以下命令进行转换：
``` shell
cd backend
uv run ppt_to_images.py <PDF文件路径> -o ../frontend/public/documents/slides
```
支持批量转换目录中的PDF文件：
``` shell
cd backend
uv run ppt_to_images.py <目录路径> -o ../frontend/public/documents/slides
```

转换完成后的pdf文件会在../frontend/public/documents/slides生成对应的图片文件。
"""
import os
import sys
import argparse
import glob
from pdf2image import convert_from_path
from PIL import Image


def convert_pdf_to_images_pdf2image(pdf_path, output_folder="../frontend/public/documents/slides"):
    """
    使用pdf2image将PDF转换为高质量图片
    
    Args:
        pdf_path (str): PDF文件路径
        output_folder (str): 输出图片目录
    """
    # 创建输出文件夹
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    print(f"正在使用pdf2image转换PDF: {pdf_path}")
    
    try:
        # 使用pdf2image将PDF转换为图片列表
        # 设置高DPI以获得高质量图像
        pages = convert_from_path(
            pdf_path, 
            dpi=96,  # 设置DPI以获得高质量图像
            fmt='png',  # 输出格式为PNG
            thread_count=4  # 使用多线程提高性能
        )
        
        total_pages = len(pages)
        print(f"共 {total_pages} 页")
        
        for i, page in enumerate(pages):
            # 保存为PNG文件
            output_path = os.path.join(output_folder, f"幻灯片{i+1:03d}.PNG")
            page.save(output_path, "PNG")
            
            print(f"已保存第 {i+1} 页: {output_path}")
        
        print("转换完成！")
        print(f"输出目录: {output_folder}")
        return True
        
    except Exception as e:
        print(f"pdf2image转换失败: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF转图片工具")
    parser.add_argument("path", help="PDF文件路径或包含PDF文件的目录路径")
    parser.add_argument("-o", "--output", default="../frontend/public/documents/slides", help="输出图片目录")
    parser.add_argument("-r", "--recursive", action="store_true", help="递归查找子目录中的PDF文件")
    
    args = parser.parse_args()
    
    # 确定要转换的文件列表
    pdf_files = []
    
    if os.path.isdir(args.path):
        # 如果是目录，查找所有PDF文件
        pattern = "**/*.pdf" if args.recursive else "*.pdf"
        pdf_files = glob.glob(os.path.join(args.path, pattern), recursive=args.recursive)
        
        print(f"在目录 {args.path} 中找到 {len(pdf_files)} 个PDF文件")
    else:
        # 如果是文件，直接添加到列表
        if args.path.lower().endswith('.pdf'):
            pdf_files = [args.path]
        else:
            print(f"错误：{args.path} 不是PDF文件")
            sys.exit(1)
    
    # 转换所有找到的PDF文件
    for pdf_file in pdf_files:
        print(f"\n=== 正在处理: {pdf_file} ===")
        
        # 创建输出目录
        output_dir = args.output
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # 使用pdf2image进行转换
        result = convert_pdf_to_images_pdf2image(pdf_file, output_dir)
        
        if not result:
            # pdf2image转换失败，尝试使用pdf2image+PIL
            print("\npdf2image转换失败，尝试使用pdf2image+PIL...")
            result = convert_pdf_to_images_pil(pdf_file, output_dir)
        
        if not result:
            print(f"\n转换失败: {pdf_file}")
        else:
            print(f"\n转换成功: {pdf_file}")
    
    print(f"\n=== 处理完成，共处理 {len(pdf_files)} 个PDF文件 ===")