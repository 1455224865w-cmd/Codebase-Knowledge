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

1. 解析 Mapper XML，并把 SQL 表名和 Java 方法连起来。连接不了时保持未知。
2. 持久化扫描结果，避免进程重启后丢失索引。
3. 用同一套索引画出模块和 API 关系。图形只展示已有关系。

## 暂不做

全仓库向量化、Neo4j、一次问答扫描整个磁盘。
