#!/usr/bin/env python3
"""
Generate a lightweight ER diagram (Mermaid) from the PostgreSQL DDL.

The script parses CREATE TABLE and ALTER TABLE statements to discover
tables, their columns, and foreign-key relationships. It emits a Mermaid
`erDiagram` file that can be rendered in Markdown preview tools.
"""

from __future__ import annotations

import argparse
import re
from collections import OrderedDict
from pathlib import Path


def strip_sql_comments(sql: str) -> str:
    """Remove single-line comments from SQL."""
    return re.sub(r"--.*", "", sql)


def iter_create_tables(sql: str):
    """Yield (table_name, body) tuples for each CREATE TABLE statement."""
    pattern = re.compile(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", re.IGNORECASE)
    for match in pattern.finditer(sql):
        table = match.group(1)
        open_idx = sql.find("(", match.end())
        if open_idx == -1:
            continue
        depth = 0
        for idx in range(open_idx, len(sql)):
            char = sql[idx]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    body = sql[open_idx + 1 : idx]
                    yield table, body
                    break


def split_columns(body: str):
    """Split a CREATE TABLE body into top-level column/constraint clauses."""
    chunks, current, depth = [], [], 0
    for char in body:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            clause = "".join(current).strip()
            if clause:
                chunks.append(clause)
            current = []
        else:
            current.append(char)
    tail = "".join(current).strip()
    if tail:
        chunks.append(tail)
    return chunks


def parse_tables(sql: str):
    """Return table metadata and inline foreign keys."""
    tables = {}
    fks = []
    for table, body in iter_create_tables(sql):
        columns = OrderedDict()
        for clause in split_columns(body):
            upper = clause.upper()
            if upper.startswith(("CONSTRAINT", "PRIMARY KEY", "UNIQUE")):
                continue
            parts = clause.split()
            if not parts:
                continue
            name = parts[0].strip('"')
            col_type = parts[1] if len(parts) > 1 else "TEXT"
            not_null = "NOT NULL" in upper
            is_pk = "PRIMARY KEY" in upper
            ref_match = re.search(r"REFERENCES\s+(\w+)", clause, re.IGNORECASE)
            if ref_match:
                ref_table = ref_match.group(1)
                fks.append((table, name, ref_table))
            columns[name] = {
                "name": name,
                "type": col_type.upper(),
                "not_null": not_null,
                "primary_key": is_pk,
            }
        tables[table] = {"name": table, "columns": columns}
    return tables, fks


def parse_alter_foreign_keys(sql: str):
    """Extract FK relationships declared via ALTER TABLE statements."""
    results = []
    statements = [stmt.strip() for stmt in sql.split(";") if stmt.strip()]
    for stmt in statements:
        alter_match = re.match(r"ALTER TABLE\s+(\w+)", stmt, re.IGNORECASE)
        if not alter_match or "FOREIGN KEY" not in stmt.upper():
            continue
        table = alter_match.group(1)
        for fk_match in re.finditer(
            r"FOREIGN KEY\s*\((.*?)\)\s*REFERENCES\s+(\w+)",
            stmt,
            re.IGNORECASE | re.DOTALL,
        ):
            columns = [col.strip().strip('"') for col in fk_match.group(1).split(",")]
            ref_table = fk_match.group(2)
            results.extend((table, column, ref_table) for column in columns)
    return results


def build_mermaid(tables, foreign_keys, output_path: Path):
    lines = ["erDiagram"]

    for table_name in sorted(tables):
        table = tables[table_name]
        lines.append(f"    {table_name} {{")
        for column in table["columns"].values():
            col_type = column["type"]
            suffix = " PK" if column["primary_key"] else ""
            lines.append(f"        {col_type} {column['name']}{suffix}")
        lines.append("    }")

    seen_edges = set()
    for table_name, column_name, ref_table in foreign_keys:
        if ref_table not in tables or table_name not in tables:
            continue
        column_info = tables[table_name]["columns"].get(column_name)
        not_null = column_info["not_null"] if column_info else False
        child_symbol = "|{" if not_null else "o{"
        edge_key = (ref_table, table_name, column_name, child_symbol)
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        lines.append(
            f'    {ref_table} ||--{child_symbol} {table_name} : "{column_name}"'
        )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sql",
        default="src/lobbyregister_ingestor/scheme.sql",
        type=Path,
        help="Path to the SQL schema file.",
    )
    parser.add_argument(
        "--output",
        default=Path("docs/ERD.mmd"),
        type=Path,
        help="Path of the generated Mermaid diagram.",
    )
    args = parser.parse_args()

    sql = strip_sql_comments(args.sql.read_text(encoding="utf-8"))
    tables, inline_fks = parse_tables(sql)
    alter_fks = parse_alter_foreign_keys(sql)
    all_fks = inline_fks + alter_fks

    args.output.parent.mkdir(parents=True, exist_ok=True)
    build_mermaid(tables, all_fks, args.output)


if __name__ == "__main__":
    main()
