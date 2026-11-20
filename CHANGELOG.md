# 变更记录

## 0.1.2

- 可以查询谁调用了某个方法。没有类型绑定时仍标成推测。
- 记录 Spring 映射注解上的 HTTP 方法和路径，以及 Mapper 写入的表。
- 只返回源码里写出来的实现关系。做法参考 JCodeIndexer 的调用方查询和 java-callgraph2 的 MyBatis 操作类型。

## 0.1.1

- 解析 Mapper XML，用 SQL 解析器记录表关系；解析失败不编造表。
- 扫描结果可以重新打开，并只返回已有类型和关系。

## 0.1.0

- 建立 Codebase Knowledge 的可运行 MVP 和测试。
- 补充产品、架构、开发和决策文档。
- 加入 GitHub Actions，只运行测试，不发布、不部署。
