# Codebase Knowledge

这个项目把代码库变成可核对的结构：文件、类型、方法和关系。它不把整个仓库向量化后来回答问题。

## 0.1.0 能做什么

- 用 `javalang` 解析 Java 源码。解析失败会记入问题列表，不会编造符号。
- 识别类、接口、方法，以及 Spring 常见注解对应的角色。
- `extends` 和 `implements` 标为 `exact`。方法调用只拿到名字，标为 `inferred`。
- 按任务文本挑选相关类型，生成带文件和行号的上下文。
- 问答只引用索引。索引里没有的类型会明确说不知道。

## 限制

- 没有类型绑定，所以调用目标不是精确调用链。
- 只解析调用方提交的 Java 文本，不克隆远程仓库。
- 没有图形界面。关系通过 API 返回。

## 本地运行

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn codebase_knowledge.api:app --reload
```

`POST /api/scans` 接收相对路径和源码。`..` 会被拒绝。

## 许可证

Apache-2.0。
