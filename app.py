from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import os
from name_matcher import NameMatcherWrapper
from compound_matcher import CompoundNameMatcher

app = FastAPI(title="Deep Name Matcher")
base_matcher = NameMatcherWrapper()
matcher = CompoundNameMatcher(base_matcher)

class MatchRequest(BaseModel):
    name1: str
    name2: str
    compound_strategy: str = "symmetrical"
    use_carlton: bool = True
    use_wikidata: bool = True
    use_jrc: bool = True
    use_l2_model: bool = True
    strict_order: bool = False
    allow_initials: bool = True
    strict_unknowns: bool = False
    allow_stepwise: bool = False

@app.post("/api/match")
async def match_names(req: MatchRequest):
    result = matcher.evaluate(
        req.name1, req.name2, 
        compound_strategy=req.compound_strategy,
        use_carlton=req.use_carlton, 
        use_wikidata=req.use_wikidata, 
        use_jrc=req.use_jrc, 
        use_l2=req.use_l2_model,
        strict_order=req.strict_order,
        allow_initials=req.allow_initials,
        strict_unknowns=req.strict_unknowns,
        allow_stepwise=req.allow_stepwise
    )
    return result

# Serve the static UI files seamlessly
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_ui(request: Request):
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

import sqlite3

def get_db_connection():
    conn = sqlite3.connect("names_kb.db")
    conn.row_factory = sqlite3.Row
    return conn

class DBAddRequest(BaseModel):
    name1: str
    name2: str
    relationship_type: str

class DBRemoveRequest(BaseModel):
    name1: str
    name2: str

@app.post("/api/kb/add")
async def add_kb_entry(req: DBAddRequest):
    # Enforce strict single-token rules
    tokens1 = matcher.tokenize(req.name1)
    tokens2 = matcher.tokenize(req.name2)
    if len(tokens1) > 1 or len(tokens2) > 1:
        return {"success": False, "error": "Cannot map compound strings. Please enter single names."}
    if not tokens1 or not tokens2:
        return {"success": False, "error": "Names cannot be empty."}
        
    n1 = req.name1.strip().lower()
    n2 = req.name2.strip().lower()
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Add names if missing into CanonicalNames
    c.execute("SELECT id FROM CanonicalNames WHERE name_string = ?", (n1,))
    r1 = c.fetchone()
    id1 = r1['id'] if r1 else c.execute("INSERT INTO CanonicalNames (name_string) VALUES (?)", (n1,)).lastrowid
    
    c.execute("SELECT id FROM CanonicalNames WHERE name_string = ?", (n2,))
    r2 = c.fetchone()
    id2 = r2['id'] if r2 else c.execute("INSERT INTO CanonicalNames (name_string) VALUES (?)", (n2,)).lastrowid
    
    # 2. Inject relationship mapping bidirectionally into NameRelations
    c.execute("""
        INSERT OR REPLACE INTO NameRelations (source_id, target_id, relation_type, confidence, context)
        VALUES (?, ?, ?, ?, ?)
    """, (id1, id2, req.relationship_type, 1.0, "custom_override"))
    c.execute("""
        INSERT OR REPLACE INTO NameRelations (source_id, target_id, relation_type, confidence, context)
        VALUES (?, ?, ?, ?, ?)
    """, (id2, id1, req.relationship_type, 1.0, "custom_override"))
    
    conn.commit()
    conn.close()
    return {"success": True, "message": f"Successfully mapped '{n1}' <-> '{n2}' as {req.relationship_type}."}

@app.post("/api/kb/remove")
async def remove_kb_entry(req: DBRemoveRequest):
    n1 = req.name1.strip().lower()
    n2 = req.name2.strip().lower()
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM CanonicalNames WHERE name_string = ?", (n1,))
    r1 = c.fetchone()
    c.execute("SELECT id FROM CanonicalNames WHERE name_string = ?", (n2,))
    r2 = c.fetchone()
    
    if r1 and r2:
        c.execute("""
            DELETE FROM NameRelations 
            WHERE (source_id = ? AND target_id = ?) OR (source_id = ? AND target_id = ?)
        """, (r1['id'], r2['id'], r2['id'], r1['id']))
        deleted = c.rowcount
    else:
        deleted = 0
        
    conn.commit()
    conn.close()
    
    if deleted > 0:
        return {"success": True, "message": f"Wiped {deleted} dictionary links between '{n1}' and '{n2}'."}
    return {"success": False, "error": "No dictionary links exist between these names."}

if __name__ == "__main__":
    print("Launching Engine...")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
