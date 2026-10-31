"""
Nyaya.ai Backend — Indian Legal Research Platform
FastAPI server with semantic search using Qdrant vector database
"""

import os
import json
import anthropic
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

QDRANT_URL    = os.getenv("QDRANT_URL", "http://localhost:6333")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
COLLECTION    = "indian_cases"
EMBED_MODEL   = "all-MiniLM-L6-v2"

app = FastAPI(title="Nyaya.ai API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

print("Loading embedding model...")
embedder = SentenceTransformer(EMBED_MODEL)
print("Ready.")

qdrant    = QdrantClient(url=QDRANT_URL)
ai_client = anthropic.Anthropic(api_key=ANTHROPIC_KEY) if ANTHROPIC_KEY else None

class SearchRequest(BaseModel):
    query: str
    court_filter: Optional[str] = "all"
    year_filter:  Optional[str] = "all"
    top_k:        Optional[int] = 5

class CaseResult(BaseModel):
    id: str; title: str; citation: str; court: str; year: int
    bench: Optional[str]; holding: str; summary: str; tags: list[str]; score: float

class SearchResponse(BaseModel):
    cases: list[CaseResult]; legal_areas: list[str]; ai_analysis: str; query_used: str

def build_filter(court_filter, year_filter):
    conditions = []
    court_map = {"supreme": "Supreme Court of India", "highcourt": "High Court", "tribunal": "Tribunal"}
    if court_filter in court_map:
        conditions.append(FieldCondition(key="court_type", match=MatchValue(value=court_map[court_filter])))
    year_ranges = {"recent": (2020,2026), "decade": (2015,2026), "landmark": (1947,2010)}
    if year_filter in year_ranges:
        from qdrant_client.models import Range
        lo, hi = year_ranges[year_filter]
        conditions.append(FieldCondition(key="year", range=Range(gte=lo, lte=hi)))
    return Filter(must=conditions) if conditions else None

def get_ai_analysis(query, cases):
    if not ai_client:
        return "", []
    titles = "\n".join([f"- {c['title']} ({c['year']})" for c in cases[:3]])
    prompt = f"""Indian legal research assistant. Case: "{query}"\nTop cases:\n{titles}\nAnalyse in 2-3 sentences. JSON only:\n{{"analysis":"...","areas":["area1","area2"]}}"""
    try:
        msg = ai_client.messages.create(model="claude-sonnet-4-20250514", max_tokens=400,
                                         messages=[{"role":"user","content":prompt}])
        text = msg.content[0].text.strip().replace("```json","").replace("```","").strip()
        data = json.loads(text)
        return data.get("analysis",""), data.get("areas",[])
    except Exception as e:
        print(f"AI error: {e}"); return "", []

@app.get("/")
def root(): return {"name":"Nyaya.ai API","status":"running"}

@app.get("/health")
def health():
    try:
        qdrant.get_collections()
        return {"status":"ok","qdrant":"connected","ai":bool(ANTHROPIC_KEY)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@app.get("/stats")
def stats():
    try:
        info = qdrant.get_collection(COLLECTION)
        return {"total_cases":info.points_count,"status":"ready"}
    except:
        return {"total_cases":0,"status":"empty — run ingest.py"}

@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    if len(req.query.strip()) < 10:
        raise HTTPException(status_code=400, detail="Please describe your case in more detail.")
    vec = embedder.encode(req.query).tolist()
    try:
        results = qdrant.search(collection_name=COLLECTION, query_vector=vec,
                                query_filter=build_filter(req.court_filter, req.year_filter),
                                limit=req.top_k, with_payload=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not results:
        return SearchResponse(cases=[], legal_areas=[], ai_analysis="No matching cases found.", query_used=req.query)
    raw, out = [], []
    for r in results:
        p = r.payload; raw.append(p)
        out.append(CaseResult(id=str(r.id), title=p.get("title",""), citation=p.get("citation",""),
            court=p.get("court",""), year=p.get("year",0), bench=p.get("bench"),
            holding=p.get("holding",""), summary=p.get("summary",""),
            tags=p.get("tags",[]), score=round(r.score*100,1)))
    analysis, areas = get_ai_analysis(req.query, raw)
    return SearchResponse(cases=out, legal_areas=areas, ai_analysis=analysis, query_used=req.query)
