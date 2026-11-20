"""Java 源码索引。解析成功的符号是事实，方法调用在没有类型绑定前标成推测。"""

from __future__ import annotations

import javalang
from javalang.parser import JavaSyntaxError

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
            methods.append({"name": method.name, "line": _line(method), "status": "exact"})
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
        if not path.endswith(".java"):
            self.files.append({"path": path, "parsed": False, "types": [], "relations": [], "skipped": "不是 Java 文件"})
            return
        parsed, issues = parse_java(path, source)
        parsed.setdefault("relations", [])
        self.files.append(parsed)
        self.issues.extend(issues)

    def types(self) -> list[dict]:
        rows = []
        for file in self.files:
            for item in file.get("types") or []:
                rows.append({**item, "path": file["path"]})
        return rows

    def relations(self, status: str | None = None) -> list[dict]:
        rows = [rel for file in self.files for rel in file.get("relations") or []]
        if status:
            return [row for row in rows if row["status"] == status]
        return rows

    def find_type(self, name: str) -> list[dict]:
        return [item for item in self.types() if item["name"] == name]

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
    if not evidence:
        return {
            "answer": "索引里没有这个问题点名的类型，不能把推测写成事实。",
            "evidence": [],
            "certainty": "unknown",
        }
    return {
        "answer": "下面是解析到的定义和关系。带 inferred 的调用只说明源码里出现了这个调用表达式。",
        "evidence": evidence[:30],
        "certainty": "parsed",
    }
