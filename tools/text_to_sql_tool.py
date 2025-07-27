import requests, json, re, os
from datetime import datetime
from tools.schema_loader import fetch_schema_text, correct_column_name
from config import OLLAMA_API_BASE_URL, OLLAMA_MODEL

HISTORY_FILE = os.path.join("tools", "sql_history.json")
NEGATIVE_FILE = os.path.join("tools", "sql_negative_history.json")

RESERVED_TABLES = {
    "order", "user", "group", "select", "where", "limit", "offset",
    "index", "column", "table", "from", "join", "by", "for"
}

def quote_reserved_tables(sql: str) -> str:
    def replacer(match):
        kw, _, tname, alias = match.groups()
        if tname.lower() in RESERVED_TABLES:
            return f'{kw} "{tname}"{(" "+alias) if alias else ""}'
        return match.group(0)
    return re.sub(
        r'(\bFROM\b|\bJOIN\b)\s+("?)([A-Za-z_][A-Za-z0-9_]*)\2\s*(\w*)?',
        replacer, sql, flags=re.IGNORECASE
    )

def sanitize_columns(sql: str, schema_raw, column_lookup):
    valid_cols = {c["name"].lower() for t in schema_raw for c in t["columns"]}
    allowed_aliases = {"s", "cs", "c", "p"}  # known table aliases
    tokens = re.split(r'(\s|,|\(|\))', sql)
    result = []
    in_select = False
    last_token_was_as = False
    # ✅ added avg, sum, as
    allowed_keywords = {
        "select","from","where","and","or","true","false","count","on",
        "join","group","by","desc","asc","order","limit","avg","sum","as"
    }
    for t in tokens:
        if not t or t.isspace() or t in (',','(',')'):
            result.append(t)
            continue
        low = t.lower()
        if low == "select":
            in_select = True; result.append(t); continue
        if low == "from":
            in_select = False; result.append(t); continue
        if last_token_was_as:
            result.append(t); last_token_was_as = False; continue
        if low == "as":
            result.append(t); last_token_was_as = True; continue
        if '(' in t or ')' in t or t == '*':
            result.append(t); continue
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', t):
            # Allow known aliases to pass through
            if low in allowed_aliases:
                result.append(t)
                continue
            if low not in valid_cols and low not in allowed_keywords:
                print(f"[WARN] Removing hallucinated column: {t}")
                result.append("NULL" if in_select else "")
                continue
            # try correcting case using column lookup
            corrected = t
            for tab in {tdata["name"].lower() for tdata in schema_raw}:
                c_corr = correct_column_name(tab, low, column_lookup)
                if c_corr.lower() == low:
                    corrected = c_corr
                    break
            result.append(corrected)
        else:
            result.append(t)
    return "".join(result)

def save_sql_history(prompt, sql, extra_info=None):
    try:
        hist = json.load(open(HISTORY_FILE)) if os.path.exists(HISTORY_FILE) else []
    except: hist = []
    entry = {"prompt": prompt, "sql": sql, "timestamp": datetime.now().isoformat()}
    if extra_info: entry["extra"] = extra_info
    hist.append(entry)
    json.dump(hist[-50:], open(HISTORY_FILE, "w", encoding="utf-8"), indent=2)

def save_sql_negative(prompt, bad, reason):
    try:
        hist = json.load(open(NEGATIVE_FILE)) if os.path.exists(NEGATIVE_FILE) else []
    except: hist = []
    hist.append({
        "prompt": prompt, "bad_sql": bad, "reason": reason,
        "timestamp": datetime.now().isoformat()
    })
    json.dump(hist[-50:], open(NEGATIVE_FILE, "w", encoding="utf-8"), indent=2)

def load_few():
    if not os.path.exists(HISTORY_FILE): return ""
    try:
        data = json.load(open(HISTORY_FILE))
        return "\n\n".join([f"User's request: {h['prompt']}\nSQL: {h['sql']}" for h in data[-10:]])
    except: return ""

def load_neg():
    if not os.path.exists(NEGATIVE_FILE): return ""
    try:
        data = json.load(open(NEGATIVE_FILE))
        lines = [f"❌ Bad example: {h['bad_sql']}" for h in data[-5:]]
        return "\n\nAvoid mistakes:\n" + "\n".join(lines) if lines else ""
    except: return ""

def extract_sql_block(raw: str) -> str:
    raw = raw.replace("“", '"').replace("”", '"').replace("`", '"').rstrip('}" ').strip()
    lines = raw.splitlines()
    sql_block, capture = [], False
    for line in lines:
        s = line.strip()
        if s.upper().startswith("SQL:"):
            s = s[len("SQL:"):].strip()
            if s.lower().startswith(("select","with")):
                if s.endswith(";"): sql_block.append(s); break
                else: capture = True
        if not capture and s.lower().startswith(("select","with")):
            capture = True
        if capture:
            if s.startswith("```") or s.lower().startswith("user's request") or s.lower().startswith("note that") or "<jupyter" in s.lower():
                break
            if s and not s.startswith("--"):
                sql_block.append(s)
            if s.endswith(";"):
                break
    cleaned = " ".join(sql_block).strip()
    return cleaned[:-1].strip() if cleaned.endswith(";") else cleaned

def fix_schema_specifics(sql: str) -> str:
    # ✅ Fix city join
    if re.search(r'\bcity\b', sql, flags=re.IGNORECASE) and 'pii' not in sql:
        sql = re.sub(
            r'FROM\s+"shipment"\s*(WHERE|GROUP|ORDER|$)',
            'FROM "shipment" s JOIN "pii" p ON s."shipToId" = p."id" \\1',
            sql,
            flags=re.IGNORECASE
        )
        sql = re.sub(r'(\s|,)city(\s|,)', r'\1p."city"\2', sql)
        sql = re.sub(r'GROUP BY\s+city', 'GROUP BY p."city"', sql, flags=re.IGNORECASE)
        sql = re.sub(r'ORDER BY\s+city', 'ORDER BY p."city"', sql, flags=re.IGNORECASE)

    # ✅ Fix courier join and references
    if re.search(r'courierid', sql, flags=re.IGNORECASE):
        # remove any duplicated joins
        sql = re.sub(
            r'JOIN\s+"courierService".*?JOIN\s+"courier".*?(JOIN\s+"courierService".*?JOIN\s+"courier".*?)',
            '',
            sql,
            flags=re.IGNORECASE | re.DOTALL
        )
        sql = re.sub(
            r'FROM\s+"shipment"',
            'FROM "shipment" s JOIN "courierService" cs ON s."courierServiceTypeId" = cs."id" '
            'JOIN "courier" c ON cs."courierId" = c."id"',
            sql,
            flags=re.IGNORECASE
        )
        sql = re.sub(r'SELECT\s+courierid\s*,\s*COUNT\(\*\)\s+AS\s+total_shipments',
                     'SELECT c."name", COUNT(*) AS total_shipments', sql, flags=re.IGNORECASE)
        sql = re.sub(r'SELECT\s+COUNT\(\*\)\s+AS\s+total_by_courier\s*,?\s*courierid?',
                     'SELECT c."name", COUNT(*) AS total_by_courier', sql, flags=re.IGNORECASE)
        sql = re.sub(r'GROUP BY\s+courierid', 'GROUP BY c."name"', sql, flags=re.IGNORECASE)
        sql = re.sub(r'ORDER BY\s+courierid', 'ORDER BY total_by_courier', sql, flags=re.IGNORECASE)

    # ✅ Fix ORDER BY desc/asc with no column
    sql = re.sub(r'ORDER BY\s+desc', 'ORDER BY total_by_courier DESC', sql, flags=re.IGNORECASE)
    sql = re.sub(r'ORDER BY\s+asc', 'ORDER BY total_by_courier ASC', sql, flags=re.IGNORECASE)

    # ✅ Booleans
    sql = re.sub(r'\bshipped\s*=\s*1\b', 'shipped = TRUE', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bshipped\s*=\s*0\b', 'shipped = FALSE', sql, flags=re.IGNORECASE)

    # ✅ Fix date fields
    sql = re.sub(r'created_at', 'createdAt', sql, flags=re.IGNORECASE)
    sql = re.sub(r'delivery_date', 'deliveryDate', sql, flags=re.IGNORECASE)

    return sql

def generate_sql_with_sqlcoder(user_prompt: str) -> str:
    try:
        schema_text, rels, schema_raw, column_lookup = fetch_schema_text()
        if isinstance(schema_text, str) and schema_text.startswith("[ERROR]"):
            return f"-- SQLCoder error: {schema_text}"
        print(f"[DEBUG] ✅ Schema loaded, tables: {[t['name'] for t in schema_raw]}")
        examples = f"{load_few()}\n\n{load_neg()}"

        prompt = f"""
You are an expert PostgreSQL SQL generator.

STRICT RULES:
- Output ONE valid SQL starting with SELECT or WITH.
- No markdown or explanation.
- Use p."city" with JOIN pii for city filters.
- Use c."name" with proper JOIN for courier grouping.
- Use TRUE/FALSE for booleans.
- Use createdAt for creation dates (not created_at).
- Use deliveryDate for delivery dates (not delivery_date).
- Avoid non-existent columns like status.

Schema:
{schema_text}

{examples}

User's request: {user_prompt}

SQL:
"""
        resp = requests.post(
            f"{OLLAMA_API_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 1024, "temperature": 0.0}
            },
            timeout=60
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "")
        if not isinstance(raw, str):
            raw = str(raw)
        print(f"[DEBUG] 📩 Raw response:\n{raw}")

        candidate = extract_sql_block(raw)
        if not candidate:
            save_sql_negative(user_prompt, raw, "No SQL found")
            return "-- SQLCoder error: No valid SQL extracted"

        if not re.match(r'(?is)^SELECT\s+.+\s+FROM\s+.+', candidate.strip()):
            print("[WARN] Candidate SQL does not match expected patterns")
            save_sql_negative(user_prompt, candidate, "Invalid SQL pattern")
            candidate = 'SELECT COUNT(*) AS total_shipments FROM "shipment"'

        candidate = quote_reserved_tables(candidate)
        candidate = sanitize_columns(candidate, schema_raw, column_lookup)
        candidate = fix_schema_specifics(candidate)

        print(f"[DEBUG] ✅ Final SQL ready:\n{candidate}")
        save_sql_history(user_prompt, candidate)
        return candidate
    except Exception as e:
        print(f"[ERROR] {e}")
        save_sql_negative(user_prompt, "", str(e))
        return f"-- SQLCoder error: {e}"
