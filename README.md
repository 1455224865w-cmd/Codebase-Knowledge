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

## 语言和 Spring AI

默认语言是中文。请求带 `Accept-Language: en` 或 `?lang=en` 时，错误信息和工具说明返回英文。源码、SQL、日志原文不翻译。

Spring AI 不内嵌在本服务里。把 `spring-ai/pom-snippet.xml` 的 `spring-ai-starter-mcp-client` 加到 Spring AI 应用，连接配置由 `spring-ai/application-mcp.yml` 指向 Nacos，地址写在 `nacos/spring-mcp.yaml`。端点默认是 `/mcp`。本仓库的测试覆盖 MCP 的 initialize、tools/list 和 tools/call，不编译 Java。

## 配置

服务地址不写进镜像。设置 `NACOS_SERVER` 后，进程启动时读取 Nacos 中的服务配置，默认 dataId 见 `nacos/service.properties`。没有 Nacos 时使用 `APP_HOST`、`APP_PORT`、`APP_DATABASE` 和 `APP_LOCALE`。

Spring AI 的 MCP 地址放在 Nacos 的 `nacos/spring-mcp.yaml`。`spring-ai/application-mcp.yml` 只指向 Nacos，不写服务地址。

## 镜像

```bash
docker build -t codebase-knowledge:local .
```

`main` 分支的 `.github/workflows/image.yml` 会把镜像推到 `ghcr.io/1455224865w-cmd/codebase-knowledge`。
