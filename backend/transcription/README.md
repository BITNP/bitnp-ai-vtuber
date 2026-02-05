# 文本文档->讲稿 生成器

输入：文本文档（纯文本或者Markdown）

输出：Markdown文档

使用兼容OpenAI API的大语言模型，通过分层处理解决上下文长度限制

## 运行

可以利用[ollama](https://ollama.com/)或者[llama.cpp](https://github.com/ggml-org/llama.cpp)本地部署一个小模型（推荐[Nanbeige4-3B-Thinking-2511](https://modelscope.cn/models/nanbeige/Nanbeige4-3B-Thinking-2511)），可以在成本、效率和质量之间达到较好的平衡。

`uv run main.py --base-url http://localhost:8080/v1 --api-key xxxx --model xxxx --document xxxx.txt/md`

输出默认存储于output文件夹，可用`--output`参数进行修改。

当前实现了树莓娘的动作控制。
