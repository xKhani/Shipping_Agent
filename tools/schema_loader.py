# tools/schema_loader.py
import os
import sys
import psycopg2
import psycopg2.extras
from collections import defaultdict
from Levenshtein import distance

# make sure we can import config from project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import DB_CONFIG


def fetch_schema_text():
    """
    Connects to PostgreSQL, inspects tables, columns, and foreign keys,
    and returns:
      schema_text_for_llm (str),
      relationships (list of dicts),
      tables_data (list of dicts),
      column_lookup (dict)
    """
    schema_text_for_llm = ""
    relationships = []
    tables_data = []
    column_lookup = {}

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # get columns
        cur.execute("""
            SELECT
                table_name,
                column_name,
                data_type,
                is_nullable,
                column_default,
                ordinal_position
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position;
        """)
        columns_raw = cur.fetchall()

        # get comments
        cur.execute("""
            SELECT
                c.relname AS table_name,
                a.attname AS column_name,
                pg_catalog.col_description(a.attrelid, a.attnum) AS column_description
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
            WHERE c.relkind = 'r'
              AND c.relname NOT LIKE 'pg_%'
              AND c.relname NOT LIKE 'sql_%'
              AND a.attnum > 0
              AND NOT a.attisdropped;
        """)
        comments_raw = cur.fetchall()
        column_comments = {
            (row['table_name'], row['column_name']): row['column_description']
            for row in comments_raw if row['column_description']
        }

        # organize
        tables_map = defaultdict(list)
        for col in columns_raw:
            t = col['table_name']
            c = col['column_name']
            tables_map[t].append(col)
            column_lookup[(t.lower(), c.lower())] = c

        for tname, col_list in tables_map.items():
            schema_text_for_llm += f'CREATE TABLE "{tname}" (\n'
            current_cols = []
            for c in col_list:
                cname = c['column_name']
                ctype = c['data_type']
                nullable = '' if c['is_nullable'] == 'YES' else 'NOT NULL'
                default_val = c['column_default'] or ''
                comment = column_comments.get((tname, cname), '')
                line = f'  "{cname}" {ctype}'
                if nullable:
                    line += f" {nullable}"
                if default_val:
                    line += f" DEFAULT {default_val}"
                if comment:
                    line += f" -- {comment}"
                schema_text_for_llm += line + ",\n"
                current_cols.append({"name": cname, "type": ctype, "description": comment})
            schema_text_for_llm = schema_text_for_llm.rstrip(',\n') + "\n);\n\n"
            tables_data.append({"name": tname, "columns": current_cols})

        # foreign keys
        cur.execute("""
            SELECT
                kcu.table_name AS from_table,
                kcu.column_name AS from_column,
                ccu.table_name AS to_table,
                ccu.column_name AS to_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
             AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public';
        """)
        for row in cur.fetchall():
            relationships.append({
                "from_table": row['from_table'],
                "from_column": row['from_column'],
                "to_table": row['to_table'],
                "to_column": row['to_column']
            })
            schema_text_for_llm += f'-- "{row["from_table"]}"."{row["from_column"]}" -> "{row["to_table"]}"."{row["to_column"]}"\n'

        cur.close()
        conn.close()
        print("[DEBUG] ✅ Schema loaded, tables:", list(tables_map.keys()))
        return schema_text_for_llm, relationships, tables_data, column_lookup

    except Exception as e:
        return f"[ERROR] Failed to fetch schema: {e}", None, None, None


def correct_column_name(table_name_lower: str, column_name_lower: str, column_lookup: dict):
    """
    Returns corrected column name (exact or fuzzy) for the given table.
    """
    key = (table_name_lower, column_name_lower)
    if key in column_lookup:
        return column_lookup[key]

    # fuzzy match
    best_match = None
    best_distance = 3  # only consider if distance < 3
    for (t, c_lower), orig in column_lookup.items():
        if t == table_name_lower:
            d = distance(column_name_lower, c_lower)
            if d < best_distance:
                best_distance = d
                best_match = orig

    if best_match:
        print(f"[INFO] Fuzzy match for '{column_name_lower}' in '{table_name_lower}': -> '{best_match}'")
        return best_match

    return column_name_lower  # return original if nothing found


if __name__ == "__main__":
    text, rels, tables, lookup = fetch_schema_text()
    if isinstance(text, str) and text.startswith("[ERROR]"):
        print(text)
        sys.exit(1)

    print("=== SCHEMA TEXT (first 500 chars) ===")
    print(text[:500])
    print("\n=== RELATIONSHIPS ===")
    for r in rels:
        print(f"{r['from_table']}.{r['from_column']} -> {r['to_table']}.{r['to_column']}")
    print("\n=== COLUMN LOOKUP TEST ===")
    print(correct_column_name("shipment", "shiptoid", lookup))
    print(correct_column_name("shipment", "ordrid", lookup))