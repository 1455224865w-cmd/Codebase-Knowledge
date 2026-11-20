# 开发

```bash
pip install -e ".[dev]"
pytest
```

示例源码在 `examples/spring/OrderController.java`。测试同时覆盖这段示例和内嵌的错误源码。

扫描接口只接受相对路径。不要把绝对路径或 `..` 当成功能。
