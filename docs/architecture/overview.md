# 架构

`javalang` 提供 Java 语法树。索引把类型、注解和继承存为 `exact`，把方法调用存为 `inferred`。问答只遍历这份索引，不在提问时重新扫描全部文件。

不使用图数据库。关系就是带状态的记录，PostgreSQL 以后也放得下。不使用向量检索作为答案来源，避免无法指出行号。

Tree-sitter 是后续选项。MVP 选择纯 Python 的 `javalang`，因为 CI 不需要编译原生解析器。
