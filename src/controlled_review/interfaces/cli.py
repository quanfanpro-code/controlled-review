"""命令行入口。

调用共同应用服务 AppService，与 MCP 入口同构。
所有操作通过 TOOL_HANDLERS 分发到同一个 app 实例。

用法：
    python -m controlled_review.interfaces.cli <operation> [json_args]

示例：
    python -m controlled_review.interfaces.cli project_progress '{"project_id": "p1"}'
"""

import json
import sys

from controlled_review.interfaces.app import TOOL_HANDLERS


def main() -> int:
    """命令行入口。

    从 sys.argv 读取操作名与 JSON 参数，调用对应工具并输出 JSON 结果。
    """
    if len(sys.argv) < 2:
        print("Usage: python -m controlled_review.interfaces.cli <operation> [args]")
        return 1
    operation = sys.argv[1]
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    handler = TOOL_HANDLERS.get(operation)
    if handler is None:
        print(f"Unknown operation: {operation}")
        return 1
    result = handler(**args)
    print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
