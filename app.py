"""LOL RAG 助手 - Web 服务"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from lol_assistant import qa, expand_query, TERM_MAP

app = FastAPI(title="LOL 助手")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/terms")
async def terms():
    """返回术语映射，供前端展示（嵌套结构按英雄分组）"""
    grouped = {}
    for (hero, slang), standard in TERM_MAP.items():
        grouped.setdefault(hero, []).append(
            {"slang": slang, "standard": standard}
        )
    return {"terms": grouped}


@app.post("/api/ask")
async def ask(request: Request):
    data = await request.json()
    query = (data.get("query") or "").strip()
    if not query:
        return JSONResponse({"error": "问题不能为空"}, status_code=400)

    expanded = expand_query(query)
    try:
        result = qa.invoke(expanded)
    except Exception as e:
        return JSONResponse(
            {"error": f"调用模型失败：{e}", "expanded": expanded},
            status_code=502,
        )

    sources = []
    for doc in result.get("source_documents", []):
        sources.append(
            {
                "content": doc.page_content,
                "source": doc.metadata.get("source", ""),
            }
        )

    return {
        "query": query,
        "expanded": expanded,
        "answer": result.get("result", ""),
        "sources": sources,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
