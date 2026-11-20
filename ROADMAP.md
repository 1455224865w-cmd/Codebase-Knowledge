# 路线

## 远程仓库

- 仓库：https://github.com/1455224865w-cmd/Codebase-Knowledge
- `main` 已推送初始提交 `b6926dd`。
- CI 工作流是 `.github/workflows/ci.yml`，只安装项目并运行 `pytest`。
- 首次推送的运行已成功：https://github.com/1455224865w-cmd/Codebase-Knowledge/actions/runs/44689643567
- Milestone「0.2 下一步」跟踪下面三个 Issue：
  - #1 解析 Mapper XML 并关联数据表
  - #2 持久化扫描结果
  - #3 用已有关系返回结构数据
## 已完成：0.1.0

Java 文件解析、角色识别、精确继承关系、推测调用、任务上下文和有边界的问答。

## 下一步

0.1.1 已完成的部分写在变更记录里。仍未完成的是需要真实数据库或仍未替换存储的部分。

1. 解析 Mapper XML，并把 SQL 表名和 Java 方法连起来。连接不了时保持未知。
2. 持久化扫描结果，避免进程重启后丢失索引。
3. 用同一套索引画出模块和 API 关系。图形只展示已有关系。

## 暂不做

全仓库向量化、Neo4j、一次问答扫描整个磁盘。

## 0.1.2

借鉴 [JCodeIndexer](https://github.com/Lincoln-cn/JCodeIndexer) 的调用方查询，以及 [java-callgraph2](https://github.com/Adrninistrator/java-callgraph2) 的 MyBatis 操作区分：可以查调用方和已写出的实现类，并区分读表和写表。调用关系仍是推测。

## 0.1.3

接口路径和 WHERE 列只来自已经解析成功的注解或 SQL。

## 0.1.4

import 和接口路径都只来自源码里已经写出来的内容。

## 0.1.5

继承环只来自精确关系。

## 0.1.6

Spring AI 通过 MCP 读取已解析符号。推断调用不会被说成精确关系。
