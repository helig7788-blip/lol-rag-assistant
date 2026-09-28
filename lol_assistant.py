from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate

# ==================== 1. 术语映射（你的差异化） ====================
# 玩家口语 -> 标准技能名/英雄名
# 术语映射：必须绑定英雄名，避免全局污染
TERM_MAP = {
    ("亚索", "Q"): "斩钢闪",
    ("亚索", "W"): "风之障壁",
    ("亚索", "E"): "踏前斩",
    ("亚索", "R"): "狂风绝息斩",
    ("锐雯", "Q"): "折翼之舞",
    ("锐雯", "W"): "震魂怒吼",
    ("锐雯", "E"): "勇往直前",
    ("锐雯", "R"): "放逐之锋",
    ("金克丝", "Q"): "枪炮交响曲",
    ("金克丝", "W"): "震荡电磁波",
    ("金克丝", "E"): "嚼火者手雷",
    ("金克丝", "R"): "超究极死神飞弹",
    ("瞎子", "Q"): "天音波",
    ("瞎子", "W"): "金钟罩",
    ("瞎子", "E"): "天雷破",
    ("瞎子", "R"): "猛龙摆尾",
    ("李青", "Q"): "天音波",
    ("李青", "W"): "金钟罩",
    ("李青", "E"): "天雷破",
    ("李青", "R"): "猛龙摆尾",
}

def expand_query(query: str) -> str:
    """只有英雄名和技能键同时出现时，才做映射"""
    for (hero, slang), standard in TERM_MAP.items():
        if hero in query and slang in query:
            query = query.replace(slang, f"{slang}（{standard}）")
    return query
# ==================== 2. 加载并切分文档 ====================
loader = DirectoryLoader("docs/", glob="**/*.md", loader_cls=TextLoader, loader_kwargs={"encoding": "utf-8"})
docs = loader.load()
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_documents(docs)
print(f"共切分出 {len(chunks)} 个文本块")

# ==================== 3. 向量化（本地中文模型） ====================
embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-zh-v1.5",
    model_kwargs={"local_files_only": True}
)
db = FAISS.from_documents(chunks, embeddings)
print("向量库构建完成")

# ==================== 4. RAG 问答 ====================
llm = Ollama(model="qwen2.5:7b")  # 本地模型

# 自定义中文 prompt：强约束模型只基于检索文档回答，避免幻觉
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

# ==================== 5. 测试 ====================
if __name__ == "__main__":
    query = "锐雯的Q是什么？"
    expanded = expand_query(query)
    print(f"原始问题：{query}")
    print(f"扩展后问题：{expanded}\n")

    result = qa.invoke(expanded)
    print("回答：")
    print(result["result"])
    print("\n依据：")
    for doc in result["source_documents"]:
        print(f"- {doc.page_content[:100]}...")