"""
基于分层总结策略的课件讲稿生成器
输入：文本文档（纯文本或者Markdown）
输出：Markdown文档
通过分层处理解决上下文长度限制
"""

import os
import re
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from backend.llm_api import create_bot

logger = logging.getLogger(__name__)

@dataclass
class DocumentSegment:
    """文档段落"""
    segment_id: str
    chapter_id: str
    chapter_title: str
    content: str
    summary: Optional[str] = None
    script: Optional[str] = None

@dataclass
class Chapter:
    """章节"""
    chapter_id: str
    title: str
    segments: List[DocumentSegment]
    segments_summary: Optional[str] = None
    chapter_summary: Optional[str] = None

class HierarchicalScriptGenerator:
    """分层讲稿生成器"""
    
    def __init__(
        self, 
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-3.5-turbo",
        api_name: str = "openai"
    ):
        """
        初始化生成器
        
        Args:
            api_key: API密钥
            base_url: API基础URL（兼容OpenAI格式）
            model: 模型名称
            api_name: API名称（openai或glm）
        """
        # 使用llm_api创建bot实例
        self.bot = create_bot(
            api_name=api_name,
            token=api_key,
            model_name=model,
            base_url=base_url
        )
        self.model = model
        self.api_name = api_name
        
        # 缓存存储中间结果
        self.document_summary = None
        self.chapters = {}
            
    def split_document(self, document_path: str, custom_pattern: str = None) -> Dict[str, Chapter]:
        """
        将文档分割为章节和段落
        
        Args:
            document_path: 文档路径
            custom_pattern: 自定义章节分割正则表达式
            
        Returns:
            章节字典
        """
        with open(document_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 预处理：标准化换行符
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        # 定义章节分割模式 - 改进版
        if custom_pattern:
            chapter_pattern = custom_pattern
        else:
            # 综合模式：匹配Markdown标题、中文章节、数字编号等
            chapter_pattern = r'^(#{1,6}\s+.+)|(第[一二三四五六七八九十零百千\d]+[章节条].+)|((?:\d+\.)+\d*\s*.+)|([IVXLCDM]+\.\s*.+)|([A-Z]\.\s*.+)|(\(\d+\)\s*.+)$'
        
        # 按行读取并处理
        lines = content.split('\n')
        chapters_dict = {}
        current_chapter = None
        current_content = []
        chapter_count = 0
        
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            
            # 检查是否是章节标题
            if re.match(chapter_pattern, line, re.MULTILINE):
                # 保存前一个章节（如果有）
                if current_chapter is not None:
                    chapter_content = '\n'.join(current_content).strip()
                    if chapter_content:  # 只添加有内容的章节
                        chapter_count += 1
                        chapter_id = f"chapter_{chapter_count:03d}"
                        
                        # 分割段落
                        paragraphs = self._split_paragraphs(chapter_content)
                        segments = []
                        
                        for j, para in enumerate(paragraphs, 1):
                            if para.strip():
                                segment_id = f"{chapter_id}_seg{j:03d}"
                                segments.append(DocumentSegment(
                                    segment_id=segment_id,
                                    chapter_id=chapter_id,
                                    chapter_title=current_chapter,
                                    content=para.strip()
                                ))
                        
                        # 如果没有分割出段落，使用整个内容作为一个段落
                        if not segments and chapter_content:
                            segment_id = f"{chapter_id}_seg001"
                            segments.append(DocumentSegment(
                                segment_id=segment_id,
                                chapter_id=chapter_id,
                                chapter_title=current_chapter,
                                content=chapter_content
                            ))
                        
                        chapters_dict[chapter_id] = Chapter(
                            chapter_id=chapter_id,
                            title=current_chapter,
                            segments=segments
                        )
                
                # 开始新章节
                current_chapter = line.strip()
                current_content = []
            else:
                # 添加到当前章节内容
                current_content.append(line)
            
            i += 1
        
        # 处理最后一个章节
        if current_chapter is not None:
            chapter_content = '\n'.join(current_content).strip()
            if chapter_content:  # 只添加有内容的章节
                chapter_count += 1
                chapter_id = f"chapter_{chapter_count:03d}"
                
                # 分割段落
                paragraphs = self._split_paragraphs(chapter_content)
                segments = []
                
                for j, para in enumerate(paragraphs, 1):
                    if para.strip():
                        segment_id = f"{chapter_id}_seg{j:03d}"
                        segments.append(DocumentSegment(
                            segment_id=segment_id,
                            chapter_id=chapter_id,
                            chapter_title=current_chapter,
                            content=para.strip()
                        ))
                
                # 如果没有分割出段落，使用整个内容作为一个段落
                if not segments and chapter_content:
                    segment_id = f"{chapter_id}_seg001"
                    segments.append(DocumentSegment(
                        segment_id=segment_id,
                        chapter_id=chapter_id,
                        chapter_title=current_chapter,
                        content=chapter_content
                    ))
                
                chapters_dict[chapter_id] = Chapter(
                    chapter_id=chapter_id,
                    title=current_chapter,
                    segments=segments
                )
        
        # 如果没有检测到章节标题，将整个文档作为一个章节
        if not chapters_dict:
            chapter_count = 1
            chapter_id = "chapter_001"
            chapter_title = "文档内容"
            
            paragraphs = self._split_paragraphs(content)
            segments = []
            
            for j, para in enumerate(paragraphs, 1):
                if para.strip():
                    segment_id = f"{chapter_id}_seg{j:03d}"
                    segments.append(DocumentSegment(
                        segment_id=segment_id,
                        chapter_id=chapter_id,
                        chapter_title=chapter_title,
                        content=para.strip()
                    ))
            
            # 如果没有分割出段落，使用整个内容作为一个段落
            if not segments and content.strip():
                segment_id = f"{chapter_id}_seg001"
                segments.append(DocumentSegment(
                    segment_id=segment_id,
                    chapter_id=chapter_id,
                    chapter_title=chapter_title,
                    content=content.strip()
                ))
            
            chapters_dict[chapter_id] = Chapter(
                chapter_id=chapter_id,
                title=chapter_title,
                segments=segments
            )
        
        return chapters_dict

    def _split_paragraphs(self, content: str) -> List[str]:
        """
        智能分割段落
        
        Args:
            content: 文本内容
            
        Returns:
            段落列表
        """
        if not content or not content.strip():
            return []
        
        # 方法1: 按空行分割
        paragraphs = re.split(r'\n\s*\n', content.strip())
        
        # 清理空段落
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        # 如果段落太少，尝试其他分割方法
        if len(paragraphs) <= 1 and len(content) > 500:
            # 方法2: 按句子分割后重新组合
            paragraphs = self._split_by_sentences(content)
        
        return paragraphs

    def _split_by_sentences(self, content: str, max_length: int = 500) -> List[str]:
        """
        按句子分割内容
        
        Args:
            content: 文本内容
            max_length: 最大段落长度
            
        Returns:
            段落列表
        """
        # 分割句子（支持中英文标点）
        sentence_pattern = r'(?<=[。！？.!?])\s+'
        sentences = re.split(sentence_pattern, content)
        
        paragraphs = []
        current_paragraph = []
        current_length = 0
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # 检查句子是否特别长（可能需要进一步分割）
            if len(sentence) > 300:
                # 尝试按逗号、分号分割长句
                sub_sentences = re.split(r'[，；,;]\s*', sentence)
                for sub_sentence in sub_sentences:
                    sub_sentence = sub_sentence.strip()
                    if sub_sentence:
                        if current_length + len(sub_sentence) <= max_length and current_paragraph:
                            current_paragraph.append(sub_sentence)
                            current_length += len(sub_sentence)
                        else:
                            if current_paragraph:
                                paragraphs.append(' '.join(current_paragraph))
                            current_paragraph = [sub_sentence]
                            current_length = len(sub_sentence)
            else:
                if current_length + len(sentence) <= max_length and current_paragraph:
                    current_paragraph.append(sentence)
                    current_length += len(sentence)
                else:
                    if current_paragraph:
                        paragraphs.append(' '.join(current_paragraph))
                    current_paragraph = [sentence]
                    current_length = len(sentence)
        
        # 添加最后一个段落
        if current_paragraph:
            paragraphs.append(' '.join(current_paragraph))
        
        return paragraphs

    async def call_llm(self, prompt: str, system_prompt: str = None) -> str:
        """
        调用LLM API
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            
        Returns:
            LLM响应
        """
        logger.debug('LLM调用：%s' % prompt[:20])
        try:
            # 清空之前的上下文
            self.bot.messages = []
            
            # 设置系统提示
            if system_prompt:
                self.bot.append_context(system_prompt, role='system')
            
            # 添加用户提示
            self.bot.append_context(prompt, role='user')
            
            # 调用LLM API
            response = await self.bot.respond_to_context()
            
            return response
        except Exception as e:
            print(f"API调用错误: {e}")
            return ""
    
    async def generate_segment_summary(self, segment: DocumentSegment) -> str:
        """
        生成段落总结
        
        Args:
            segment: 文档段落
            
        Returns:
            段落总结
        """
        prompt = f"""请概括以下段落的主要内容，保持简洁明了，直接输出结果：
{segment.content}"""
        
        summary = await self.call_llm(
            prompt=prompt,
            system_prompt="你是一个理想坚定、循循善诱、学识渊博、温柔美丽的青年女教师。",
            #max_tokens=200
        )
        logger.debug('段落总结：%s...' % summary[:20])
        return summary
    
    def generate_chapter_segments_summary(self, chapter: Chapter) -> str:
        """
        生成章节所有段落的合并总结
        
        Args:
            chapter: 章节对象
            
        Returns:
            合并后的段落总结
        """
        # 收集所有段落总结
        segments_summaries = []
        for segment in chapter.segments:
            if segment.summary:
                segments_summaries.append(f"段落{segment.segment_id}的总结: {segment.summary}")
        
        if not segments_summaries:
            return ""
        
        return "\n".join(segments_summaries)
    
    async def generate_chapter_summary(self, chapter: Chapter) -> str:
        """
        基于合并的段落总结生成章节总结
        
        Args:
            chapter: 章节对象
            
        Returns:
            章节总结
        """
        if not chapter.segments_summary:
            return ""
        
        prompt = f"""以下是章节"{chapter.title}"中各个段落的总结，请在此基础上总结本章的主要内容，保留其中的要点，简洁明了，直接输出结果：

{chapter.segments_summary}"""
        
        summary = await self.call_llm(
            prompt=prompt,
            system_prompt="你是一个理想坚定、循循善诱、学识渊博、温柔美丽的青年女教师。",
            #max_tokens=250
        )
        logger.debug('章节总结：%s...' % summary[:20])
        return summary
    
    async def generate_document_summary(self, chapters_dict: Dict[str, Chapter]) -> str:
        """
        生成整个文档的总结
        
        Args:
            chapters_dict: 章节字典
            
        Returns:
            文档总结
        """
        # 收集所有章节总结
        chapter_summaries = []
        for chapter_id, chapter in chapters_dict.items():
            if chapter.chapter_summary:
                chapter_summaries.append(f"章节 {chapter.title}: {chapter.chapter_summary}")
        
        if not chapter_summaries:
            return ""
        
        combined_chapter_summaries = "\n".join(chapter_summaries)
        
        prompt = f"""以下是文档中各个章节的总结，请基于这些章节总结，保留其中的要点，生成整个文档的总体总结，简洁明了，直接输出结果：

{combined_chapter_summaries}"""
        
        summary = await self.call_llm(
            prompt=prompt,
            system_prompt="你是一个理想坚定、循循善诱、学识渊博、温柔美丽的青年女教师。",
            #max_tokens=400
        )
        
        return summary
    
    async def generate_segment_script(
        self, 
        segment: DocumentSegment, 
        chapter_summary: str, 
        document_summary: str
    ) -> str:
        """
        生成段落的讲稿
        
        Args:
            segment: 文档段落
            chapter_summary: 章节总结
            document_summary: 文档总结
            
        Returns:
            讲稿内容
        """
        prompt = f"""
【整体文档总结】
{document_summary}

【所在章节总结】
{chapter_summary}

【当前段落总结】
{segment.summary}

【当前段落内容】
{segment.content}

基于以上上下文，为当前段落生成教学讲稿，注意，生成的不是完整的讲稿，只是这一段落的讲稿，作为整个讲稿的一部分，因此，严禁出现引入和结束语，只输出正文；本段落、本段落所在的章节、整篇文档的总结都已作为上下文给出，要求：
1. 语言生动、易于理解
2. 你可以使用以下表情：[点头]、[摇头]、[wink]，除此之外不应输出其他提示性内容"""
        
        script = await self.call_llm(
            prompt=prompt,
            system_prompt="你是一个理想坚定、循循善诱、学识渊博、温柔美丽的青年女教师。",
            #max_tokens=800
        )
        
        return script
    
    async def process_document(self, document_path: str, output_dir: str = "output") -> Dict[str, Any]:
        """
        处理整个文档生成讲稿
        
        Args:
            document_path: 文档路径
            output_dir: 输出目录
            
        Returns:
            处理结果
        """
        # 创建输出目录
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        print("步骤1: 分割文档...")
        self.chapters = self.split_document(document_path)
        
        print(f"找到 {len(self.chapters)} 个章节")
        
        # 第一层：生成段落总结
        print("步骤2: 生成段落总结...")
        for chapter_id, chapter in self.chapters.items():
            print(f"  处理章节: {chapter.title}")
            for segment in chapter.segments:
                print(f"    处理段落: {segment.segment_id}")
                segment.summary = await self.generate_segment_summary(segment)
        
        # 第二层：生成章节段落合并总结
        print("步骤3: 生成章节段落合并总结...")
        for chapter_id, chapter in self.chapters.items():
            chapter.segments_summary = self.generate_chapter_segments_summary(chapter)
        
        # 第三层：生成章节总结
        print("步骤4: 生成章节总结...")
        for chapter_id, chapter in self.chapters.items():
            chapter.chapter_summary = await self.generate_chapter_summary(chapter)
        
        # 第四层：生成文档总结
        print("步骤5: 生成文档整体总结...")
        self.document_summary = await self.generate_document_summary(self.chapters)
        
        # 第五层：生成每个段落的讲稿
        print("步骤6: 生成段落讲稿...")
        all_scripts = []
        
        for chapter_id, chapter in self.chapters.items():
            print(f"  为章节生成讲稿: {chapter.title}")
            for segment in chapter.segments:
                script = await self.generate_segment_script(
                    segment, 
                    chapter.chapter_summary, 
                    self.document_summary
                )
                segment.script = script
                all_scripts.append({
                    "chapter": chapter.title,
                    "segment_id": segment.segment_id,
                    "script": script
                })
        
        # 保存结果
        print("步骤7: 保存结果...")
        self.save_results(output_dir, all_scripts)
        
        return {
            "document_summary": self.document_summary,
            "chapters": self.chapters,
            "scripts": all_scripts
        }
    
    def save_results(self, output_dir: str, all_scripts: List[Dict]):
        """保存处理结果"""
        
        # 保存文档总结
        with open(f"{output_dir}/document_summary.txt", "w", encoding="utf-8") as f:
            f.write("=== 文档总体总结 ===\n\n")
            f.write(self.document_summary)
            f.write("\n\n")
        
        # 保存章节总结
        with open(f"{output_dir}/chapter_summaries.txt", "w", encoding="utf-8") as f:
            f.write("=== 各章节总结 ===\n\n")
            for chapter_id, chapter in self.chapters.items():
                f.write(f"## {chapter.title}\n")
                f.write(chapter.chapter_summary or "")
                f.write("\n\n")
        
        # 保存所有讲稿
        with open(f"{output_dir}/all_scripts.md", "w", encoding="utf-8") as f:
            f.write("# 完整讲稿\n\n")
            for script_data in all_scripts:
                f.write(f"## {script_data['chapter']} - {script_data['segment_id']}\n\n")
                f.write(script_data["script"])
                f.write("\n\n---\n\n")
        
        # 保存结构化数据
        structured_data = {
            "document_summary": self.document_summary,
            "chapters": {}
        }
        
        for chapter_id, chapter in self.chapters.items():
            structured_data["chapters"][chapter_id] = {
                "title": chapter.title,
                "chapter_summary": chapter.chapter_summary,
                "segments": [
                    {
                        "segment_id": seg.segment_id,
                        "content_preview": seg.content[:100] + "..." if len(seg.content) > 100 else seg.content,
                        "summary": seg.summary,
                        "script_preview": seg.script[:200] + "..." if seg.script and len(seg.script) > 200 else seg.script
                    }
                    for seg in chapter.segments
                ]
            }
        
        with open(f"{output_dir}/structured_data.json", "w", encoding="utf-8") as f:
            json.dump(structured_data, f, ensure_ascii=False, indent=2)
        
        print(f"结果已保存到 {output_dir}/ 目录")

async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="分层讲稿生成器")
    parser.add_argument("--document", type=str, required=True, help="文本文档路径")
    parser.add_argument("--api-key", type=str, default=os.getenv("OPENAI_API_KEY"), help="API密钥")
    parser.add_argument("--base-url", type=str, default="https://api.openai.com/v1", 
                       help="API基础URL（默认为OpenAI官方API）")
    parser.add_argument("--model", type=str, default="gpt-3.5-turbo", 
                       help="模型名称")
    parser.add_argument("--api-name", type=str, default="openai", 
                       help="API名称（openai或glm）")
    parser.add_argument("--output_dir", type=str, default="output", 
                       help="输出目录")
    
    args = parser.parse_args()
    
    # 初始化生成器
    generator = HierarchicalScriptGenerator(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        api_name=args.api_name
    )
    
    # 处理文档
    results = await generator.process_document(
        document_path=args.document,
        output_dir=args.output_dir
    )
    
    print("处理完成！")
    
    # 打印统计信息
    total_segments = sum(len(chapter.segments) for chapter in generator.chapters.values())
    print(f"\n统计信息:")
    print(f"- 文档总结长度: {len(generator.document_summary)} 字符")
    print(f"- 章节数量: {len(generator.chapters)}")
    print(f"- 段落总数: {total_segments}")
    print(f"- 输出文件保存在: {args.output_dir}/")

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())