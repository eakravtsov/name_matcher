import sqlite3
from unidecode import unidecode
import os

DB_PATH = "names_kb.db"

def levenshtein_distance(s1, s2):
    if len(s1) > len(s2):
        s1, s2 = s2, s1
    distances = range(len(s1) + 1)
    for index2, char2 in enumerate(s2):
        new_distances = [index2 + 1]
        for index1, char1 in enumerate(s1):
            if char1 == char2:
                new_distances.append(distances[index1])
            else:
                new_distances.append(1 + min((distances[index1], distances[index1+1], new_distances[-1])))
        distances = new_distances
    return distances[-1]


def normalize(name):
    if not name:
        return ""
    return unidecode(name).lower().strip()

def check_level_1(name1, name2, use_carlton=True, use_wikidata=True, use_jrc=True, **kwargs):
    """
    Level 1 Router: Queries the SQLite DB for strictly known relations.
    Filters by the chosen dataset contexts.
    Returns a dictionary: {"match": bool, "confidence": float, "explanation": str}
    """
    n1 = normalize(name1)
    n2 = normalize(name2)
    
    if n1 == n2:
        return {"match": True, "confidence": 1.0, "explanation": "Exact string match"}
        
    dist = levenshtein_distance(n1, n2)
    
    if not os.path.exists(DB_PATH):
        return {"match": False, "confidence": 0.0, "explanation": "Database not found"}

    try:
        # Use URI for read-only access to avoid locking or permission issues in Docker
        db_uri = f"file:{DB_PATH}?mode=ro"
        conn = sqlite3.connect(db_uri, uri=True)
        cursor = conn.cursor()
    except sqlite3.OperationalError as e:
        print(f"ERROR connecting to DB (L1): {e}")
        return {"match": False, "confidence": 0.0, "explanation": f"Database access error: {e}"}
    
    cursor.execute("SELECT id, gender FROM CanonicalNames WHERE name_string = ?", (n1,))
    res1 = cursor.fetchone()
    cursor.execute("SELECT id, gender FROM CanonicalNames WHERE name_string = ?", (n2,))
    res2 = cursor.fetchone()
    
    
    if not res1 or not res2:
        conn.close()
        return {
            "match": False, 
            "confidence": 0.0, 
            "explanation": "One or both names not in dictionary",
            "gender1": "Unknown",
            "gender2": "Unknown"
        }
    
    id1, gender1 = res1[0], res1[1]
    id2, gender2 = res2[0], res2[1]
    
    # 1. Direct relationships (no intermediate hop)
    cursor.execute("""
        SELECT relation_type, confidence, context, NULL as hop_name
        FROM NameRelations 
        WHERE source_id = ? AND target_id = ?
    """, (id1, id2))
    
    relations = cursor.fetchall()
    
    # 2. 1-hop (transitive) relationships
    # We JOIN CanonicalNames to extract the intermediate node's actual name for diagnostics.
    cursor.execute("""
        SELECT r1.relation_type, (r1.confidence * r2.confidence), r1.context, cn.name_string as hop_name
        FROM NameRelations r1
        JOIN NameRelations r2 ON r1.target_id = r2.source_id
        JOIN CanonicalNames cn ON r1.target_id = cn.id
        WHERE r1.source_id = ? AND r2.target_id = ?
    """, (id1, id2))
    
    relations.extend(cursor.fetchall())
    conn.close()
    
    # Evaluate found relations against user filters
    best_conf = -1.0
    best_rel = None
    
    for rel_type, conf, context, hop_name in relations:
        ctx_lower = context.lower()
        is_valid = False
        
        if use_carlton and 'carlton' in ctx_lower:
            is_valid = True
        elif use_wikidata and 'wikidata' in ctx_lower:
            is_valid = True
        elif use_jrc and 'jrc' in ctx_lower:
            is_valid = True
        if 'custom_override' in ctx_lower:
            # User defined explicit overrides ALWAYS bypass dataset toggles
            is_valid = True
            
            # Anti-Match Veto Protocol:
            if rel_type.lower() == "mismatch":
                return {
                    "match": False,
                    "confidence": 0.0,
                    "explanation": "Level 1 applied a hard mismatch based on an explicit user-defined override.",
                    "gender1": gender1,
                    "gender2": gender2
                }
            
        if is_valid and conf > best_conf:
            best_conf = conf
            best_rel = (rel_type, conf, context, hop_name)
            
    if best_rel:
        rel_type, conf, context, hop_name = best_rel
        
        # JRC Noisy Data Heuristic for Short Names
        if 'jrc' in context.lower():
            if max(len(n1), len(n2)) <= 5 and dist >= 2:
                return {
                    "match": False,
                    "confidence": 0.0,
                    "explanation": f"Level 1 found a potential {rel_type} link via the JRC dataset, but deferred to Level 2 due to the high variance of short strings.",
                    "gender1": gender1,
                    "gender2": gender2
                }
        
        hop_detail = f" [via '{hop_name}']" if hop_name else ""
        return {
            "match": True, 
            "confidence": round(conf, 3), 
            "explanation": f"Level 1 approved the match based on a known {rel_type} relationship in the {context} Knowledge Base{hop_detail}.",
            "gender1": gender1,
            "gender2": gender2
        }
        
    return {
        "match": False,
        "confidence": 0.0,
        "explanation": f"Level 1 did not find any active links linking these entities. Decision deferred to Level 2 Neural Model.",
        "gender1": gender1,
        "gender2": gender2
    }
