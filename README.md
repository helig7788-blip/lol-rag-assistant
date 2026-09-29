[README.md](https://github.com/user-attachments/files/32781206/README.md)
# LOL RAG 问答助手

基于 RAG（检索增强生成）的英雄联盟智能问答系统。用户用自然语言提问（如"锐雯的 Q 是什么？"、"瞎子的 W 技能"），系统基于官方英雄数据检索相关文档，再由本地大模型生成答案，并附上回答依据。

支持命令行问答和 Web 界面两种使用方式，Web 界面可通过局域网在手机上访问。

---

## 功能特性

- 基于 Riot Data Dragon 官方数据构建英雄知识库（167+ 英雄）
- 术语映射：玩家口语（如"瞎子"、"德玛"）自动扩展为标准英雄名
- 中文向量化模型 `BAAI/bge-small-zh-v1.5` 做语义检索
- 本地 Ollama 运行 `qwen2.5:7b`，数据不出本机，无 API 费用
- 自定义中文强约束 Prompt，降低幻觉
- 返回答案 + 参考文档片段，可追溯依据
- Web 界面：快捷问题、术语对照表、错误友好提示

---

## 技术栈

| 层 | 技术 |
|---|------|
| 数据采集 | Python + Riot Data Dragon（公开接口，无需 API Key） |
| 知识库构建 | Python + Markdown 文档 |
| 向量化 | LangChain + HuggingFace Embeddings (`bge-small-zh-v1.5`) |
| 向量检索 | FAISS |
| 大模型 | Ollama + `qwen2.5:7b`（本地推理） |
| RAG 编排 | LangChain `RetrievalQA` |
| Web 服务 | FastAPI + Uvicorn |
| 前端 | 原生 HTML/CSS/JS（无构建步骤） |

---

## 目录结构

```
RGGLOL/
├── lol_assistant.py          # RAG 问答核心（术语映射 + 检索 + LLM）
├── app.py                    # FastAPI Web 服务
├── build_knowledge.py        # champions/*.json → docs/*.md 知识库构建
├── download_champions.py    # 从 Data Dragon 下载英雄 JSON
├── static/
│   └── index.html            # Web 前端单页
├── docs/                     # 知识库 Markdown（167+ 英雄）
├── champion.json             # 英雄总表（被 .gitignore 排除）
├── champions/                # 原始英雄 JSON（被 .gitignore 排除）
├── 问答错误分析.csv          # 历史错误案例与诊断
├── .gitignore
└── README.md
```

---

## 快速开始

### 环境要求

- Python 3.10+
- [Ollama](https://ollama.com/) 已安装并运行
- 网络可访问 HuggingFace（首次下载 embedding 模型）

### 1. 克隆仓库

```bash
git clone https://github.com/helig7788-blip/lol-rag-assistant.git
cd lol-rag-assistant
```

### 2. 创建虚拟环境并安装依赖

```bash
python -m venv venv
venv\Scripts\activate                 # Windows
# source venv/bin/activate            # macOS/Linux
pip install -r requirements.txt       # 若无此文件，见下方"依赖清单"
```

**依赖清单**（若无 requirements.txt，手动安装）：

```bash
pip install langchain langchain-community langchain-huggingface faiss-cpu sentence-transformers ollama fastapi uvicorn
```

### 3. 启动 Ollama 拉取模型

```bash
ollama pull qwen2.5:7b
ollama serve                          # 保持后台运行
```

### 4. 准备知识库（可选）

仓库已带 `docs/`，可直接使用。若要重新生成：

```bash
# 1. 下载英雄原始 JSON（生成 champions/ 和 champion.json）
python download_champions.py
# 2. 转换为 Markdown 知识库
python build_knowledge.py
```

### 5. 运行

**命令行问答**：

```bash
python lol_assistant.py
```

**Web 服务**：

```bash
python app.py
```

打开浏览器访问 http://127.0.0.1:8000

---

## 使用示例

### 命令行

```
原始问题：锐雯的Q是什么？
扩展后问题：锐雯的Q（折翼之舞）是什么？

回答：
锐雯的 Q 技能是"折翼之舞"...

依据：
- # 锐雯（放逐之刃）...
- ## 折翼之舞 ...
```

### Web 界面

- 顶部输入框提问，或点击预设快捷问题按钮
- 底部展示术语映射表（按英雄分组）
- 模型未启动时返回 502 + 错误提示

### 手机访问

将 [app.py](app.py) 中 `uvicorn.run` 的 `host` 改为 `0.0.0.0`，同局域网设备访问 `http://你的电脑IP:8000` 即可。Windows 防火墙首次会弹窗，允许即可。

---

## 核心配置说明

| 配置项 | 位置 | 说明 |
|--------|------|------|
| 术语映射表 | `lol_assistant.py` `TERM_MAP` | (英雄, 按键) → 标准技能名 |
| 切分参数 | `lol_assistant.py` `chunk_size=500, chunk_overlap=50` | 文本块大小与重叠 |
| 检索 Top-K | `lol_assistant.py` `search_kwargs={"k": 4}` | 每次返回最相似的 4 个块 |
| Embedding 模型 | `lol_assistant.py` `BAAI/bge-small-zh-v1.5` | 中文向量化模型 |
| LLM 模型 | `lol_assistant.py` `qwen2.5:7b` | 本地大模型 |
| Prompt 模板 | `lol_assistant.py` `PROMPT` | 中文强约束，要求只基于资料回答 |

---

## 常见问题

### 启动报 `ConnectionRefusedError: [WinError 10061]`

Ollama 服务未启动。运行 `ollama serve` 后重试。

### 启动报 `ModuleNotFoundError: No module named 'fastapi'`

依赖装到了错误的 venv。用 `python -m pip install ...` 强制装到当前解释器，而非 `pip install`。

### 首次启动很慢

`lol_assistant.py` 在 import 时会加载 295 个文本块 + 构建 FAISS 索引。可通过 `db.save_local("faiss_index")` 持久化避免每次重建。

### 回答不准确

常见原因：默认 Prompt 是英文、检索未按英雄过滤、`chunk_size` 过大。详见 [LOL助手知识手册.md](LOL助手知识手册.md) 第 7-8 章。

---

## 项目文档

- [LOL助手知识手册.md](LOL助手知识手册.md) —— 完整架构原理、代码逐模块讲解、问题诊断与优化方案
- [问答错误分析.csv](问答错误分析.csv) —— 历史错误案例记录

---

## 扩展方向

- 向量库持久化（`db.save_local`）
- 多轮对话（`ConversationBufferMemory`）
- 流式输出（前端 SSE）
- 检索时按英雄 metadata 过滤，提升准确率
- 接入更多数据源（装备、符文、对线技巧）

---

## License

MIT
