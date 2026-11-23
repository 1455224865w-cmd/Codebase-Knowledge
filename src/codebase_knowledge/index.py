"""Java 源码索引。解析成功的符号是事实，方法调用在没有类型绑定前标成推测。"""

from __future__ import annotations

import json
import re
import sqlite3
import xml.etree.ElementTree as ET

import javalang
import sqlglot
from javalang.parser import JavaSyntaxError
from sqlglot import exp
from sqlglot.errors import ParseError

ROLE_ANNOTATIONS = {
    "RestController": "controller",
    "Controller": "controller",
    "Service": "service",
    "Repository": "repository",
    "Mapper": "mapper",
    "Configuration": "configuration",
    "Component": "component",
}


class ParseIssue:
    def __init__(self, path: str, message: str):
        self.path = path
        self.message = message

    def to_dict(self) -> dict:
        return {"path": self.path, "message": self.message, "status": "error"}


def _annotation_name(annotation) -> str:
    name = getattr(annotation, "name", "")
    return name if isinstance(name, str) else str(name)


def _line(node) -> int | None:
    position = getattr(node, "position", None)
    return position.line if position else None


def parse_java(path: str, source: str) -> tuple[dict, list[dict]]:
    """返回一个文件的符号和关系。解析失败时不编造符号。"""
    try:
        tree = javalang.parse.parse(source)
    except (JavaSyntaxError, javalang.tokenizer.LexerError, TypeError, ValueError) as exc:
        return {"path": path, "parsed": False, "types": []}, [ParseIssue(path, (str(exc).splitlines() or [exc.__class__.__name__])[0]).to_dict()]

    types = []
    relations = []
    classes = [node for _, node in tree.filter(javalang.tree.ClassDeclaration)]
    interfaces = [node for _, node in tree.filter(javalang.tree.InterfaceDeclaration)]
    for node in classes + interfaces:
        kind = "interface" if isinstance(node, javalang.tree.InterfaceDeclaration) else "class"
        annotations = [_annotation_name(item) for item in (node.annotations or [])]
        roles = sorted({ROLE_ANNOTATIONS[name] for name in annotations if name in ROLE_ANNOTATIONS})
        methods = []
        for method in node.body or []:
            if not isinstance(method, javalang.tree.MethodDeclaration):
                continue
            http, route = _mapping(method)
            methods.append({
                "name": method.name,
                "line": _line(method),
                "status": "exact",
                "http": http,
                "route": route,
            })
        entry = {
            "kind": kind,
            "name": node.name,
            "line": _line(node),
            "annotations": annotations,
            "roles": roles,
            "extends": getattr(getattr(node, "extends", None), "name", None),
            "implements": [item.name for item in (getattr(node, "implements", None) or [])],
            "methods": methods,
            "status": "exact",
        }
        types.append(entry)
        if entry["extends"]:
            relations.append(_rel(path, node.name, "extends", entry["extends"], _line(node), "exact"))
        for name in entry["implements"]:
            relations.append(_rel(path, node.name, "implements", name, _line(node), "exact"))
        for method in node.body or []:
            if not isinstance(method, javalang.tree.MethodDeclaration):
                continue
            for _, call in method.filter(javalang.tree.MethodInvocation):
                target = f"{call.qualifier}.{call.member}" if call.qualifier else call.member
                relations.append(
                    _rel(path, f"{node.name}.{method.name}", "calls", target, _line(call), "inferred")
                )
    for imp in tree.imports or []:
        target = getattr(imp, "path", None)
        if isinstance(target, str) and target:
            relations.append(_rel(path, path, "imports", target, _line(imp), "exact"))
    return {"path": path, "parsed": True, "types": types, "relations": relations}, []


def _rel(path: str, source: str, kind: str, target: str, line: int | None, status: str) -> dict:
    return {
        "path": path,
        "line": line,
        "source": source,
        "kind": kind,
        "target": target,
        "status": status,
    }


class CodeIndex:
    def __init__(self):
        self.files: list[dict] = []
        self.issues: list[dict] = []

    def add_file(self, path: str, source: str) -> None:
        if path.endswith(".java"):
            parsed, issues = parse_java(path, source)
            parsed.setdefault("relations", [])
            self.files.append(parsed)
            self.issues.extend(issues)
            return
        if path.endswith(".xml"):
            parsed, issues = parse_mapper_xml(path, source)
            self.files.append(parsed)
            self.issues.extend(issues)
            return
        self.files.append({"path": path, "parsed": False, "types": [], "relations": [], "skipped": "不是 Java 或 Mapper XML"})

    def types(self) -> list[dict]:
        rows = []
        for file in self.files:
            for item in file.get("types") or []:
                rows.append({**item, "path": file["path"]})
        return rows

    def relations(self, status: str | None = None) -> list[dict]:
        rows = [rel for file in self.files for rel in file.get("relations") or []]
        rows.extend(self._statement_links())
        if status:
            return [row for row in rows if row["status"] == status]
        return rows

    def _statement_links(self) -> list[dict]:
        types = {item["name"]: item for item in self.types()}
        links = []
        for file in self.files:
            for stmt in file.get("statements") or []:
                simple = stmt["namespace"].split(".")[-1] if stmt.get("namespace") else ""
                java = types.get(simple)
                if not java:
                    continue
                if any(method["name"] == stmt["id"] for method in java["methods"]):
                    links.append(_rel(file["path"], f"{simple}.{stmt['id']}", "maps", stmt["id"], stmt["line"], "exact"))
        return links

    def find_type(self, name: str) -> list[dict]:
        return [item for item in self.types() if item["name"] == name]

    def callers(self, name: str) -> list[dict]:
        """谁调用了这个名字。没有类型绑定时仍是推测。"""
        suffix = "." + name
        return [
            rel
            for rel in self.relations()
            if rel["kind"] == "calls" and (rel["target"] == name or rel["target"].endswith(suffix))
        ]

    def routes(self) -> list[dict]:
        """只返回注解里写明的路径，不猜测未标注的接口。"""
        rows = []
        for item in self.types():
            for method in item["methods"]:
                if not method.get("route"):
                    continue
                rows.append(
                    {
                        "http": method.get("http"),
                        "path": method["route"],
                        "type": item["name"],
                        "method": method["name"],
                        "file": item["path"],
                        "line": method["line"],
                        "status": "exact",
                    }
                )
        return rows

    def implementations(self, name: str) -> list[dict]:
        """只返回解析到的 extends 或 implements，不补没有写出来的实现类。"""
        return [
            rel
            for rel in self.relations("exact")
            if rel["kind"] in {"extends", "implements"} and rel["target"] == name
        ]

    def cycles(self) -> list[dict]:
        """只在精确的继承和实现关系里找环，不把推测调用算进去。"""
        graph: dict[str, list[str]] = {}
        for rel in self.relations("exact"):
            if rel["kind"] in {"extends", "implements"}:
                graph.setdefault(rel["source"], []).append(rel["target"])
        found = []
        seen = set()

        def walk(node: str, stack: list[str]) -> None:
            if node in stack:
                cycle = stack[stack.index(node) :] + [node]
                key = tuple(sorted(set(cycle)))
                if key not in seen:
                    seen.add(key)
                    found.append({"nodes": cycle, "status": "exact"})
                return
            for nxt in graph.get(node, []):
                walk(nxt, stack + [node])

        for node in graph:
            walk(node, [])
        return found

    def summary(self) -> dict:
        roles: dict[str, int] = {}
        for item in self.types():
            for role in item["roles"]:
                roles[role] = roles.get(role, 0) + 1
        return {
            "files": len(self.files),
            "parsed_files": sum(1 for file in self.files if file.get("parsed")),
            "parse_errors": len(self.issues),
            "types": len(self.types()),
            "exact_relations": len(self.relations("exact")),
            "inferred_relations": len(self.relations("inferred")),
            "roles": roles,
        }


def context_for_task(index: CodeIndex, task: str, limit: int = 8) -> dict:
    """只挑选任务文本里点名的类型，不把整个项目塞进上下文。"""
    picked = [item for item in index.types() if item["name"] in task]
    if not picked:
        tokens = [part for part in task.replace("，", " ").replace(",", " ").split() if len(part) > 2]
        picked = [item for item in index.types() if any(token in item["name"] for token in tokens)]
    picked = picked[:limit]
    names = {item["name"] for item in picked}
    relations = [
        rel
        for rel in index.relations()
        if any(rel["source"].startswith(name) or rel["target"].startswith(name) for name in names)
    ]
    lines = ["以下内容来自解析结果。status=inferred 的调用没有做类型绑定，不能当成精确调用链。"]
    for item in picked:
        methods = ", ".join(method["name"] for method in item["methods"]) or "无"
        lines.append(
            f"- {item['path']}:{item['line']} {item['kind']} {item['name']} 角色 {item['roles'] or ['未标注']} 方法 {methods}"
        )
    for rel in relations[:20]:
        lines.append(
            f"- {rel['path']}:{rel['line']} {rel['source']} {rel['kind']} {rel['target']} [{rel['status']}]"
        )
    if not picked:
        lines.append("任务文本没有命中已解析的类型。不要凭空补文件。")
    return {"files": [item["path"] for item in picked], "prompt": "\n".join(lines)}


def answer(index: CodeIndex, question: str) -> dict:
    """只根据索引回答。找不到就说明没有证据。"""
    evidence = []
    for item in index.types():
        if item["name"] in question:
            evidence.append(f"{item['path']}:{item['line']} 定义了 {item['kind']} {item['name']}")
            for rel in index.relations():
                if rel["source"].startswith(item["name"] + ".") or rel["source"] == item["name"]:
                    evidence.append(
                        f"{rel['path']}:{rel['line']} {rel['source']} {rel['kind']} {rel['target']} [{rel['status']}]"
                    )
    for route in index.routes():
        if route["path"] and route["path"] in question:
            evidence.append(
                f"{route['file']}:{route['line']} {route['http']} {route['path']} -> {route['type']}.{route['method']} [exact]"
            )
    if not evidence:
        return {
            "answer": "索引里没有这个问题点名的类型或路径，不能把推测写成事实。",
            "evidence": [],
            "certainty": "unknown",
        }
    return {
        "answer": "下面是解析到的定义和关系。带 inferred 的调用只说明源码里出现了这个调用表达式。",
        "evidence": evidence[:30],
        "certainty": "parsed",
    }


def parse_mapper_xml(path: str, source: str) -> tuple[dict, list[dict]]:
    """解析 MyBatis Mapper XML。SQL 解析失败时不编造表关系。"""
    cleaned = re.sub(r"<!DOCTYPE[^>]*>", "", source, count=1)
    try:
        root = ET.fromstring(cleaned)
    except ET.ParseError as exc:
        return {"path": path, "parsed": False, "types": [], "relations": [], "statements": []}, [
            ParseIssue(path, str(exc).splitlines()[0]).to_dict()
        ]
    if not root.tag.endswith("mapper"):
        return {"path": path, "parsed": False, "types": [], "relations": [], "statements": []}, [
            ParseIssue(path, "根节点不是 mapper").to_dict()
        ]
    namespace = root.get("namespace") or ""
    relations = []
    statements = []
    issues = []
    lines = source.splitlines()
    for child in list(root):
        tag = child.tag.split("}")[-1]
        if tag not in {"select", "insert", "update", "delete"}:
            continue
        stmt_id = child.get("id") or ""
        sql = "".join(child.itertext())
        line = _xml_line(lines, tag, stmt_id)
        tables, columns, where_columns, parsed = _sql_facts(sql)
        statements.append({
            "id": stmt_id,
            "namespace": namespace,
            "operation": tag,
            "sql": sql.strip(),
            "line": line,
            "tables": tables,
            "columns": columns,
            "where_columns": where_columns,
        })
        if not parsed:
            issues.append(ParseIssue(path, f"{stmt_id or tag} 的 SQL 未能解析，没有记录表关系").to_dict())
            continue
        kind = "reads_table" if tag == "select" else "writes_table"
        for table in tables:
            relations.append(_rel(path, f"{namespace}#{stmt_id}", kind, table, line, "exact"))
        for column in where_columns:
            relations.append(_rel(path, f"{namespace}#{stmt_id}", "filters_column", column, line, "exact"))
    return {
        "path": path,
        "parsed": True,
        "types": [],
        "relations": relations,
        "statements": statements,
    }, issues


def _xml_line(lines: list[str], tag: str, stmt_id: str) -> int | None:
    needle = f'id="{stmt_id}"'
    for index, line in enumerate(lines, start=1):
        if f"<{tag}" in line and needle in line:
            return index
    return None


def _sql_facts(sql: str) -> tuple[list[str], list[str], list[str], bool]:
    normalized = re.sub(r"#\{[^}]+\}|\$\{[^}]+\}", "?", sql)
    try:
        parsed = sqlglot.parse_one(normalized, read="postgres")
    except ParseError:
        return [], [], [], False
    if not isinstance(parsed, (exp.Select, exp.Insert, exp.Update, exp.Delete)):
        return [], [], [], False
    tables = sorted({table.name for table in parsed.find_all(exp.Table)})
    columns = sorted({column.name for column in parsed.find_all(exp.Column)})
    where = parsed.args.get("where")
    where_columns = sorted({column.name for column in where.find_all(exp.Column)}) if where else []
    return tables, columns, where_columns, True


def _mapping(method) -> tuple[str | None, str | None]:
    http_methods = {
        "GetMapping": "GET",
        "PostMapping": "POST",
        "PutMapping": "PUT",
        "DeleteMapping": "DELETE",
        "PatchMapping": "PATCH",
        "RequestMapping": "REQUEST",
    }
    for annotation in method.annotations or []:
        name = _annotation_name(annotation)
        if name in http_methods:
            return http_methods[name], _annotation_text(annotation.element)
    return None, None


def _annotation_text(element) -> str | None:
    if isinstance(element, javalang.tree.Literal) and isinstance(element.value, str):
        return element.value.strip('"').strip("'")
    if isinstance(element, list):
        for pair in element:
            if getattr(pair, "name", None) in {"value", "path"}:
                return _annotation_text(getattr(pair, "value", None))
    return None


def structure(index: CodeIndex) -> dict:
    """只返回已经解析到的类型和关系，不补不存在的节点。"""
    nodes = [
        {"id": f"{item['path']}::{item['name']}", "name": item["name"], "status": "exact", "path": item["path"]}
        for item in index.types()
    ]
    edges = [
        {"source": rel["source"], "target": rel["target"], "kind": rel["kind"], "status": rel["status"], "path": rel["path"], "line": rel["line"]}
        for rel in index.relations()
    ]
    return {"nodes": nodes, "edges": edges}


class ScanStore:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("CREATE TABLE IF NOT EXISTS scans (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")

    def ids(self) -> list[str]:
        return [row[0] for row in self.conn.execute("SELECT id FROM scans")]

    def save(self, scan_id: str, index: CodeIndex) -> None:
        payload = json.dumps({"files": index.files, "issues": index.issues}, ensure_ascii=False)
        self.conn.execute("INSERT OR REPLACE INTO scans VALUES (?, ?)", (scan_id, payload))
        self.conn.commit()

    def load(self, scan_id: str) -> CodeIndex | None:
        row = self.conn.execute("SELECT payload FROM scans WHERE id=?", (scan_id,)).fetchone()
        if row is None:
            return None
        data = json.loads(row[0])
        index = CodeIndex()
        index.files = data["files"]
        index.issues = data["issues"]
        return index
