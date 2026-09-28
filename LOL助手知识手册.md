# 英雄联盟 RAG 问答助手 · 知识手册

> 本手册面向学习目的，系统讲解本项目从数据采集到智能问答、再到 Web 可视化的完整流水线，涵盖架构原理、核心代码、技术栈说明以及常见问题的诊断与优化方案。

---

## 目录

1. [项目概述与最终效果](#1-项目概述与最终效果)
2. [整体架构与数据流](#2-整体架构与数据流)
3. [阶段一：数据采集（download_champions.py）](#3-阶段一数据采集download_championspy)
4. [阶段二：知识库构建（build_knowledge.py）](#4-阶段二知识库构建build_knowledgepy)
5. [阶段三：RAG 问答核心（lol_assistant.py）](#5-阶段三rag-问答核心lol_assistantpy)
6. [阶段四：Web 服务（app.py + static/）](#6-阶段四web-服务apppy--static)
7. [技术栈原理详解](#7-技术栈原理详解)
8. [问题诊断与优化方案](#8-问题诊断与优化方案)
9. [扩展方向与学习建议](#9-扩展方向与学习建议)

---

## 1. 项目概述与最终效果

### 1.1 项目目标

做一个**英雄联盟智能问答助手**：用户用自然语言提问（如"锐雯的Q是什么？"、"瞎子的W技能是什么"），系统能基于官方英雄数据，用中文给出准确回答，并附上回答的依据来源。最终通过浏览器页面使用，支持手机等局域网设备访问。

### 1.2 最终形态

项目现在有两种使用方式：

**命令行方式**：运行 `lol_assistant.py`，程序会：

1. 加载 `docs/` 下所有英雄的 Markdown 文档
2. 切分成文本块并构建 FAISS 向量索引
3. 接受用户问题 → 术语映射 → 向量检索 → 本地大模型生成答案
4. 输出形如：

```
原始问题：锐雯的Q是什么？
扩展后问题：锐雯的Q（折翼之舞）是什么？

回答：
锐雯的Q技能是"折翼之舞"...

依据：
- # 放逐之刃（锐雯）...
- ## 折翼之舞 ...
```

**Web 方式**：运行 `app.py` 启动 FastAPI 服务，浏览器访问 `http://127.0.0.1:8000`：

- 页面输入问题，实时显示答案与参考依据
- 显示术语扩展后的问题（便于观察口语 → 标准名的转换）
- 按英雄分组展示术语映射表
- 提供快捷问题按钮
- 绑定 `0.0.0.0`，同一 WiFi 下的手机也可访问

### 1.3 技术关键词

- **RAG (Retrieval-Augmented Generation)**：检索增强生成
- **LangChain**：LLM 应用编排框架
- **FAISS**：Facebook 开源的向量相似度检索库
- **HuggingFace Embeddings (bge-small-zh-v1.5)**：中文文本向量化模型
- **Ollama + qwen2.5:7b**：本地部署的大语言模型
- **FastAPI + Uvicorn**：Python 异步 Web 框架与 ASGI 服务器
- **Riot Data Dragon**：英雄联盟官方公开数据接口

---

## 2. 整体架构与数据流

```
┌─────────────────────────────────────────────────────────────┐
│                      数据源层                                │
│  Riot Data Dragon (ddragon.leagueoflegends.com)             │
│         │                                                   │
│         ▼                                                   │
│  champion.json (英雄总表 + 版本号)                           │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段一：数据采集  download_champions.py                     │
│  遍历 champion.json，下载每个英雄的详细 JSON → champions/    │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段二：知识库构建  build_knowledge.py                      │
│  champions/*.json → 提取技能/属性/背景 → docs/*.md           │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段三：RAG 问答  lol_assistant.py                          │
│                                                             │
│  用户问题 ──► expand_query() 术语映射（英雄+按键绑定）        │
│                │                                            │
│                ▼                                            │
│         docs/*.md 加载                                       │
│                │                                            │
│                ▼                                            │
│     RecursiveCharacterTextSplitter 切分 (500字符/块)         │
│                │                                            │
│                ▼                                            │
│     HuggingFaceEmbeddings 向量化 → FAISS 向量库              │
│                │                                            │
│                ▼                                            │
│       检索 Top-K=4 相似文本块                                │
│                │                                            │
│                ▼                                            │
│     自定义中文 Prompt + Ollama(qwen2.5:7b) 生成答案          │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  阶段四：Web 服务  app.py + static/index.html                │
│                                                             │
│  浏览器/手机 ──HTTP──► FastAPI                               │
│    POST /api/ask   → 复用 lol_assistant 的 qa 链             │
│    GET  /api/terms → 术语映射（按英雄分组）                  │
│    GET  /          → 前端问答页面                            │
└─────────────────────────────────────────────────────────────┘
```

**核心思想**：让大模型"先查资料再回答"，而不是凭记忆瞎编。向量检索负责从知识库中捞出相关片段，LLM 负责把片段组织成通顺的中文回答；Web 层只负责把这套能力通过 HTTP 暴露给浏览器。

---

## 3. 阶段一：数据采集（download_champions.py）

### 3.1 代码逻辑

```python
with open("champion.json", encoding="utf-8") as f:
    data = json.load(f)["data"]

version = data["Aatrox"]["version"]  # 自动获取版本号
```

- `champion.json` 是英雄联盟的**英雄总表**，包含所有英雄的 ID、名称、版本号等。
- 从中取出 `version`（如 `16.1.1`），用于拼接下载 URL。

```python
url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/zh_CN/champion/{champ_id}.json"
urllib.request.urlretrieve(url, save_path)
```

- 对每个英雄 ID，向 Riot Data Dragon 发起请求，下载该英雄的完整 JSON（含技能、皮肤、属性、背景故事等）。
- `time.sleep(0.2)` 是礼貌性限流，避免请求过快被服务器拒绝。

### 3.2 数据结构（以 LeeSin.json 为例）

每个英雄 JSON 的关键字段：

| 字段 | 含义 | 示例 |
|------|------|------|
| `name` | 英雄称号 | "盲僧" |
| `title` | 英雄名 | "李青" |
| `lore` | 背景故事 | 长文本 |
| `stats` | 基础属性 | hp, attackdamage, armor... |
| `passive` | 被动技能 | {name, description} |
| `spells` | Q/W/E/R 技能数组 | 每个含 name, description, cooldown... |

> 注意：Data Dragon 中文数据中 `name` 是称号、`title` 是英雄名，与直觉相反，所以生成的文档标题形如"# 放逐之刃（锐雯）"。

### 3.3 学习要点

- **Data Dragon 是 Riot 官方免费开放的数据接口**，无需 API Key，适合做数据分析和学习项目。
- 版本号很重要：不同版本的技能数据可能不同，用总表里的版本号能保证一致性。
- `champion.json` 本身也是从 Data Dragon 下载的（`https://ddragon.leagueoflegends.com/cdn/{version}/data/zh_CN/champion.json`）。

---

## 4. 阶段二：知识库构建（build_knowledge.py）

### 4.1 代码逻辑

```python
champ_data = json.load(f)["data"]
champ_id = list(champ_data.keys())[0]  # 每个文件只有一个英雄
champ = champ_data[champ_id]
```

- 每个 `champions/{id}.json` 的 `data` 下只有一个键，就是该英雄 ID。

```python
md = f"# {champ['name']}（{champ['title']}）\n\n"
md += f"## 背景故事\n{champ.get('lore', '暂无')}\n\n"
md += f"## 基础属性\n生命值: {champ['stats']['hp']}\n..."
md += f"## 被动技能：{champ['passive']['name']}\n{champ['passive']['description']}\n\n"
for spell in champ["spells"]:
    md += f"## {spell['name']}\n{spell['description']}\n\n"
```

- 把 JSON 中的关键字段拼成 Markdown 文档，一个英雄对应一个 `.md` 文件。

### 4.2 生成效果（Riven.md）

```markdown
# 放逐之刃（锐雯）

## 背景故事
曾担任诺克萨斯军队剑士长的锐雯……

## 基础属性
生命值: 630
攻击力: 64
护甲: 33

## 被动技能：符文之刃
锐雯的技能会为她的剑刃充能……

## 折翼之舞
锐雯斩出一套猛烈的剑式。在短时间内，这个技能最多可以重新激活3次……
```

### 4.3 为什么要转成 Markdown？

1. **LangChain 的 `DirectoryLoader` 原生支持加载文本文件**，Markdown 是纯文本，加载方便。
2. Markdown 的标题层级（`#`、`##`）天然适合作为文本切分的边界参考。
3. 人类可读性好，方便调试和检查知识库内容。

### 4.4 ⚠️ 潜在隐患（后续优化重点）

当前每个技能段落只有技能名，**没有重复英雄名**。例如：

```markdown
## 折翼之舞
锐雯斩出一套猛烈的剑式……
```

如果文本切分把这个段落和"# 放逐之刃（锐雯）"标题切开，单独的 chunk 里英雄归属信息就会变弱，检索其他英雄同类问题时可能互相干扰。**这是后续需要优化的关键点**，详见第 8 章。

---

## 5. 阶段三：RAG 问答核心（lol_assistant.py）

这是项目最核心的文件，下面逐模块讲解。

### 5.1 模块一：术语映射（英雄 + 按键 绑定）

```python
TERM_MAP = {
    ("亚索", "Q"): "斩钢闪",
    ("亚索", "W"): "风之障壁",
    ("亚索", "E"): "踏前斩",
    ("亚索", "R"): "狂风绝息斩",
    ("锐雯", "Q"): "折翼之舞",
    ("金克丝", "R"): "超究极死神飞弹",
    ("瞎子", "W"): "金钟罩",
    ("李青", "W"): "金钟罩",
}

def expand_query(query: str) -> str:
    for (hero, slang), standard in TERM_MAP.items():
        if hero in query and slang in query:
            query = query.replace(slang, f"{slang}（{standard}）")
    return query
```

**作用**：玩家常说口语/简称，把它们扩展成标准术语，提高检索命中率。例如：

- `"锐雯的Q是什么？"` → `"锐雯的Q（折翼之舞）是什么？"`
- `"瞎子的W是什么？"` → `"瞎子的W（金钟罩）是什么？"`（同时匹配"瞎子"和"W"）

**关键设计：二元组 key `(英雄, 口语)`**。`Q/W/E/R` 是所有英雄共通的按键，早期版本把它们全局映射成亚索的技能名，会导致问任何英雄的 R 都被注入"狂风绝息斩"。现在必须**英雄名和按键同时出现**才替换，消除了全局误伤。别名（瞎子/李青）可以指向同一标准技能，两条映射并存即可。

### 5.2 模块二：文档加载与切分

```python
loader = DirectoryLoader("docs/", glob="**/*.md", loader_cls=TextLoader, loader_kwargs={"encoding": "utf-8"})
docs = loader.load()
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_documents(docs)
```

- `DirectoryLoader`：递归加载 `docs/` 下所有 `.md` 文件。
- `RecursiveCharacterTextSplitter`：按字符数切分，每块最多 500 字符，相邻块重叠 50 字符（防止句子被截断丢失上下文）。
- 切分优先级：`"\n\n"` → `"\n"` → `" "` → `""`，尽量在段落/句子边界切开。

**为什么要切分？**
- Embedding 模型有最大输入长度限制，太长的文本无法一次性向量化。
- 检索时返回的是"块"，块太大包含太多无关信息，太小又丢失上下文。500 字符是经验值。

### 5.3 模块三：向量化与向量库

```python
embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-zh-v1.5",
    model_kwargs={"local_files_only": True}
)
db = FAISS.from_documents(chunks, embeddings)
```

- `bge-small-zh-v1.5`：BAAI 出品的**中文**轻量级 embedding 模型，把文本转成 512 维向量。
- `local_files_only=True`：强制从本地加载，不联网下载（模型需提前放到 HuggingFace 缓存目录）。
- `FAISS.from_documents`：把所有 chunk 向量化后存入 FAISS 索引，用于后续相似度检索。

### 5.4 模块四：RAG 问答链（含自定义中文 Prompt）

```python
llm = Ollama(model="qwen2.5:7b")  # 本地模型

PROMPT_TEMPLATE = """你是英雄联盟知识助手。请严格根据下方【参考文档】回答问题。

规则：
1. 只能使用【参考文档】中的信息作答，禁止使用你自己的先验知识。
2. 如果【参考文档】中没有相关信息，必须回答"根据现有资料无法回答"。
3. 不要编造技能名或英雄信息。
4. 回答要简洁、直接，使用中文。

【参考文档】
{context}

问题：{question}

回答："""

PROMPT = PromptTemplate(template=PROMPT_TEMPLATE, input_variables=["context", "question"])

qa = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=db.as_retriever(search_kwargs={"k": 4}),
    return_source_documents=True,
    chain_type_kwargs={"prompt": PROMPT}
)
```

- `Ollama(model="qwen2.5:7b")`：通过 Ollama 调用本地运行的通义千问 2.5 7B 模型。
- `db.as_retriever(search_kwargs={"k": 4})`：把 FAISS 包装成检索器，每次返回最相似的 4 个文本块。
- `return_source_documents=True`：返回结果中包含被检索到的原文，方便查看"依据"。
- **自定义 Prompt**：LangChain 默认模板是英文且约束较弱，qwen2.5:7b 这类小模型容易用先验知识覆盖检索事实（例如检索到的明明是锐雯资料，却回答"斩钢闪"——那是亚索的技能）。自定义中文模板强约束模型"只准用参考文档、不准编造、没信息就明说"，显著降低幻觉。
- `RetrievalQA` 内部流程：
  1. 把用户问题向量化
  2. 在 FAISS 中检索 Top-K 相似 chunk
  3. 把 chunk 拼进 prompt 的 `{context}`
  4. 调用 LLM 生成回答

### 5.5 模块五：测试入口

```python
if __name__ == "__main__":
    query = "锐雯的Q是什么？"
    expanded = expand_query(query)
    result = qa.invoke(expanded)
    print(result["result"])           # 回答
    print(result["source_documents"])  # 依据
```

---

## 6. 阶段四：Web 服务（app.py + static/）

### 6.1 设计思路

`lol_assistant.py` 在模块顶层完成了文档加载、向量库构建和 `qa` 链初始化，**import 即初始化**。因此 `app.py` 直接 `from lol_assistant import qa, expand_query, TERM_MAP` 复用整套 RAG 能力，不重复构建索引。

### 6.2 后端接口（app.py）

```python
app = FastAPI(title="LOL 助手")

@app.get("/")                    # 首页：返回 static/index.html
@app.get("/api/terms")           # 术语映射（按英雄分组）
@app.post("/api/ask")            # 问答接口
```

**`POST /api/ask`** 请求体：`{"query": "锐雯的Q是什么？"}`

处理流程：
1. 取问题并做空值校验
2. `expand_query()` 做术语扩展
3. `qa.invoke(expanded)` 走完整 RAG 链
4. 提取答案与 `source_documents`（内容 + 来源文件路径）返回
5. Ollama 未启动等异常被捕获，返回 502 + 中文错误信息，前端友好展示

返回示例：

```json
{
  "query": "锐雯的Q是什么？",
  "expanded": "锐雯的Q（折翼之舞）是什么？",
  "answer": "锐雯的Q技能是折翼之舞……",
  "sources": [
    {"content": "## 折翼之舞\n锐雯斩出一套猛烈的剑式……", "source": "docs/Riven.md"}
  ]
}
```

**`GET /api/terms`**：Python 的 tuple key 不能直接 JSON 序列化，后端在接口内把 `TERM_MAP` 重新按英雄分组：

```python
grouped = {}
for (hero, slang), standard in TERM_MAP.items():
    grouped.setdefault(hero, []).append({"slang": slang, "standard": standard})
```

### 6.3 前端页面（static/index.html）

纯原生 HTML/CSS/JS 单文件，无需构建工具：

- **问答区**：输入框 + 提问按钮（支持回车），加载中转圈动画
- **快捷问题**：锐雯Q / 亚索R / 李青W / 盖伦被动，一键提问
- **扩展问题回显**：直观展示术语映射效果
- **答案区 + 参考依据**：答案左侧金边高亮，依据逐条列出并标注来源文件
- **术语映射表**：按英雄分组卡片，每行显示 `口语 → 标准名`
- **错误态**：模型连不上时红字提示（如"调用模型失败：[WinError 10061]…"）

样式为英雄联盟风格：深蓝黑底 + 暗金色描边。

### 6.4 启动方式

```bash
# 1. 启动本地模型服务（必须先启动，否则问答报连接拒绝）
ollama serve

# 2. 激活虚拟环境并安装依赖
python -m pip install fastapi uvicorn

# 3. 启动 Web 服务
python app.py
```

浏览器访问 `http://127.0.0.1:8000`。

> 注意：`app.py` 启动时 import `lol_assistant`，会先加载全部 docs 并构建 FAISS 索引（控制台打印"共切分出 N 个文本块""向量库构建完成"），首次启动较慢属正常现象。

### 6.5 局域网（手机）访问

`uvicorn.run(app, host="0.0.0.0", port=8000)` 中 `0.0.0.0` 表示监听所有网卡：

1. 电脑执行 `ipconfig`，查 IPv4 地址（通常为 `192.168.x.x`）
2. 手机连同一个 WiFi，浏览器访问 `http://192.168.x.x:8000`
3. Windows 防火墙首次弹窗时点"允许"

前提：手机与电脑必须在同一局域网；不同 WiFi/路由器之间无法访问。

---

## 7. 技术栈原理详解

### 7.1 RAG（检索增强生成）

**为什么需要 RAG？**
- 大模型有知识截止日期，且可能幻觉（编造信息）。
- 英雄联盟数据频繁更新，不可能每次更新都重新训练模型。
- RAG 的思路：**把外挂知识库检索到的相关片段塞进 prompt，让模型基于事实回答**。

**RAG vs 微调 (Fine-tuning)**：

| 维度 | RAG | 微调 |
|------|-----|------|
| 知识更新 | 替换文档即可，快 | 需重新训练，慢 |
| 成本 | 低（只需 embedding + 检索） | 高（需 GPU 训练） |
| 可解释性 | 高（可返回依据来源） | 低 |
| 适合场景 | 知识密集型问答 | 风格/格式学习 |

### 7.2 Embedding（文本向量化）

把一段文本转换成一个**高维浮点数向量**（如 512 维），语义相近的文本在向量空间中距离也近。

- `bge-small-zh-v1.5` 专门针对中文优化，比通用模型效果好。
- 向量维度越高，表达能力越强，但检索速度越慢。small 版本是速度和效果的折中。

### 7.3 FAISS（向量检索库）

Facebook AI 开源的**相似度搜索库**，核心解决的问题：

> 给定一个查询向量，如何从百万级向量中快速找出最相似的 K 个？

- 本项目数据量小（~160+ 个英雄 × 几块），用的是暴力检索（Flat Index），速度已经足够。
- 大规模场景下 FAISS 支持 IVF、HNSW 等近似最近邻算法，牺牲少量精度换取百倍速度。

### 7.4 Ollama（本地大模型运行工具）

- Ollama 让本地运行大模型变得像 `docker run` 一样简单。
- `ollama pull qwen2.5:7b` 下载模型，`ollama run qwen2.5:7b` 启动。
- LangChain 通过 `Ollama()` 类以 HTTP 方式调用本地 Ollama 服务（默认 `http://localhost:11434`）。
- 服务未启动时会报 `[WinError 10061] 由于目标计算机积极拒绝`，运行 `ollama serve` 即可。
- **本地部署的好处**：数据不出本机，无 API 费用，适合学习和隐私场景。

### 7.5 LangChain（LLM 应用框架）

本项目用到的 LangChain 组件：

| 组件 | 作用 |
|------|------|
| `DirectoryLoader` | 批量加载目录下的文档 |
| `RecursiveCharacterTextSplitter` | 递归字符文本切分器 |
| `HuggingFaceEmbeddings` | 调用 HF 模型做向量化 |
| `FAISS` | 向量数据库封装 |
| `RetrievalQA` | 检索 + 生成的端到端链 |
| `PromptTemplate` | 自定义提示词模板 |
| `Ollama` | Ollama 模型封装 |

### 7.6 FastAPI（Web 框架）

- 基于 Starlette + Pydantic 的异步 Web 框架，自动生成 `/docs` 接口文档。
- `@app.post("/api/ask")` 用协程处理请求；通过 `Request.json()` 取请求体。
- Uvicorn 是其 ASGI 服务器，负责监听端口、把 HTTP 请求转给 FastAPI。
- 复用 Python 对象（`qa` 链）非常直接：模块级 import 后在接口函数里调用即可。

---

## 8. 问题诊断与优化方案

### 8.1 历史问题与修复状态

| # | 问题 | 错误回答 | 正确答案 | 根因 | 状态 |
|---|------|---------|---------|------|------|
| 1 | 瞎子的W技能是什么 | 风之障壁 | 金钟罩/铁布衫 | 全局按键映射 + chunk 召回不准 | 映射已修复（见 8.2），召回仍可优化 |
| 2 | 金克斯的R技能是什么 | 终极闪光 | 超究极死神飞弹 | R 被全局替换成亚索大招 | ✅ 已修复（tuple 绑定） |
| 3 | 亚索的W是什么 | （空答） | 风之障壁 | chunk 未召回 + 默认 prompt 无兜底约束 | prompt 已修复（见 8.4） |
| 4 | 锐雯的Q是什么 | 答成"斩钢闪"并否认折翼之舞 | 折翼之舞 | 模型先验知识覆盖检索事实 | ✅ 已修复（中文强约束 prompt） |

### 8.2 已修复：术语映射全局误伤

**旧根因代码**：

```python
"Q": "斩钢闪", "W": "风之障壁",
"E": "踏前斩", "R": "狂风绝息斩",
```

`Q/W/E/R` 是所有英雄共通的技能按键，旧版做全局字符串替换，问任何英雄的 R 都会被注入"狂风绝息斩"。

**修复方案（当前代码）**：key 改为 `(英雄, 按键)` 二元组，两个条件同时命中才替换：

```python
TERM_MAP = {
    ("亚索", "R"): "狂风绝息斩",
    ("锐雯", "Q"): "折翼之舞",
    ("瞎子", "W"): "金钟罩",
    ("李青", "W"): "金钟罩",
}
```

### 8.3 待优化：文本切分丢失英雄归属

**根因**：`build_knowledge.py` 生成的技能段落不含英雄名，切分后 chunk 可能丢失"这是哪个英雄"的信息。

**优化方案**（修改 build_knowledge.py 后重新生成 docs）：

```python
# 在每个技能标题前加上英雄名，保证每个 chunk 都携带英雄归属
for spell in champ["spells"]:
    md += f"## {champ['title']} - {spell['name']}\n{spell['description']}\n\n"
md += f"## {champ['title']} - 被动技能：{champ['passive']['name']}\n..."
```

这样切分后，即使 chunk 只包含一个技能段落，也带有英雄名，检索"李青 W"时能精准命中。

### 8.4 已修复：LLM 空答/幻觉

**根因**：默认英文 prompt 约束弱，召回内容与问题看似相关时（如同时召回锐雯、卡蜜尔文档），小模型会用自己的先验知识回答，甚至否认参考文档中的事实。

**修复方案（当前代码）**：自定义中文 prompt（见 5.4 节），四条硬规则：只用参考文档、禁止先验知识、无信息明说、中文简洁回答。

### 8.5 待优化：检索未按英雄过滤

**根因**：FAISS 检索只看语义相似度，不知道"瞎子的W"应该限定在李青的文档范围内，Top-K 中可能混入其他英雄的 chunk（页面上曾出现问锐雯却召回卡蜜尔文档的情况）。

**优化方案**：利用 metadata 过滤。

```python
# 切分后给每个 chunk 注入英雄名 metadata
for chunk in chunks:
    champ_id = os.path.basename(chunk.metadata["source"]).replace(".md", "")
    chunk.metadata["champion"] = champ_id

# 检索时先解析问题中的英雄，再用 filter 限定（需自定义检索逻辑）
```

更简单的做法：调小 `k`（如 4 → 2）减少无关 chunk，或在 query 中明确加入英雄名（术语扩展已部分实现）。

### 8.6 待清理：TERM_MAP 重复定义

当前 `lol_assistant.py` 中 `TERM_MAP` 被定义了两次（内容相同，后者覆盖前者），功能无害但属于冗余，应删除其中一份。

### 8.7 工程化优化建议

1. **向量库持久化**：`db.save_local("faiss_index")` + `FAISS.load_local(...)`，避免每次启动 Web 服务都重新构建索引（目前每次 import 都要重建，启动慢）。
2. **依赖环境一致性**：注意 `python -m pip` 与当前解释器绑定，避免包装到别的虚拟环境（本机曾出现 fastapi 装在 `D:\LOLrag\venv` 而项目用 `E:\RGGLOL\venv` 的问题）。
3. **服务异常预检**：启动时可先探测 `http://localhost:11434`，Ollama 不在线时在页面给出明确提示。

---

## 9. 扩展方向与学习建议

### 9.1 功能扩展

1. ~~**Web 界面**：用 Gradio / Streamlit 做可视化问答页面。~~ ✅ 已用 FastAPI + 原生前端实现
2. **交互式问答**：命令行用 `while True` 循环接收输入，做成聊天式助手。
3. **多轮对话**：引入 `ConversationBufferMemory`，支持上下文追问（如"那她的R呢？"）。
4. **技能连招查询**：不仅回答单个技能，还能根据英雄给出连招建议。
5. **向量库持久化**：`db.save_local("faiss_index")`，避免每次运行都重建索引。
6. **流式输出**：Ollama 支持流式响应，可改成 SSE/WebSocket 让答案逐字显示。

### 9.2 学习路径建议

| 阶段 | 目标 | 建议 |
|------|------|------|
| 入门 | 跑通项目 | 先确保 Ollama + qwen2.5:7b 能跑，再运行 lol_assistant.py |
| 理解 | 读懂代码 | 对照本手册逐行理解，打印中间变量观察 |
| 优化 | 修复问题 | 按第 8 章方案修改代码，对比优化前后的回答质量 |
| 进阶 | 功能扩展 | 尝试多轮对话、向量库持久化、流式输出 |
| 深入 | 原理探究 | 学习 FAISS 索引算法、embedding 模型评测、prompt 工程 |

### 9.3 关键学习资源

- **LangChain 官方文档**：https://python.langchain.com/
- **FastAPI 官方文档**：https://fastapi.tiangolo.com/
- **Ollama 模型库**：https://ollama.com/library
- **Riot Data Dragon**：https://developer.riotgames.com/docs/lol#data-dragon
- **bge 模型介绍**：https://huggingface.co/BAAI/bge-small-zh-v1.5

---

## 附录：文件速查表

| 文件 | 作用 | 运行时机 |
|------|------|---------|
| `champion.json` | 英雄总表（含版本号） | 手动下载一次 |
| `download_champions.py` | 下载所有英雄 JSON 到 champions/ | 数据更新时运行 |
| `champions/*.json` | 每个英雄的原始详细数据 | 由上一步生成 |
| `build_knowledge.py` | JSON → Markdown 知识库 | champions/ 更新后运行 |
| `docs/*.md` | RAG 知识库 | 由上一步生成 |
| `lol_assistant.py` | RAG 问答核心（术语映射 + 检索 + LLM 链） | 被问答/Web 复用 |
| `app.py` | FastAPI Web 服务，复用 lol_assistant 的 qa 链 | `python app.py` 启动 |
| `static/index.html` | 问答前端页面（单文件，无构建依赖） | 由 Web 服务托管 |
| `问答错误分析.csv` | 错误案例记录 | 调试参考 |
