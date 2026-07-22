"""平台连接包契约测试。

验证 Codex / Trae / WorkBuddy / Reasonix 四个平台连接包都声明了
必需的能力（mcp 或 local_command）、必需的循环行为
（next_action_loop、resume_same_project），并明确禁止直接写数据库。

连接包位置：
- adapters/codex/AGENT.md
- adapters/trae/SKILL.md
- adapters/workbuddy/SKILL.md
- adapters/reasonix/SKILL.md

每个连接包用 YAML frontmatter 声明能力：
    ---
    platform: codex
    supports: [mcp, local_command]
    defines: [next_action_loop, resume_same_project]
    never_allows: [direct_database_write]
    ---
"""

from dataclasses import dataclass, field
from pathlib import Path

import pytest


@dataclass
class AdapterManifest:
    """平台连接包清单。

    从连接包 Markdown 文件的 YAML frontmatter 解析而来，
    用于在符合性测试中验证平台声明的能力与禁止项。

    属性：
        platform: 平台名（codex / trae / workbuddy / reasonix）。
        supports: 该平台支持的能力列表（如 mcp、local_command）。
        defined_features: 该平台定义的循环行为列表（如 next_action_loop）。
            注意：字段名故意改为 defined_features，避免与下方
            defines() 方法同名冲突（dataclass 实例属性会遮蔽同名方法）。
        disallowed_actions: 该平台明确禁止的动作列表（如 direct_database_write）。
            字段名故意改为 disallowed_actions，避免与 never_allows() 方法同名冲突。
    """

    platform: str
    supports: list = field(default_factory=list)
    defined_features: list = field(default_factory=list)
    disallowed_actions: list = field(default_factory=list)

    def supports_any(self, *capabilities) -> bool:
        """判断是否支持给定能力中的任意一个。"""
        return any(c in self.supports for c in capabilities)

    def defines(self, feature) -> bool:
        """判断是否定义了某个循环行为。"""
        return feature in self.defined_features

    def never_allows(self, action) -> bool:
        """判断是否明确禁止某个动作。"""
        return action in self.disallowed_actions


def _parse_frontmatter(content: str) -> dict:
    """手动解析 YAML frontmatter。

    不依赖 PyYAML，仅识别本测试所需的简单结构：
    key: value 或 key: [item1, item2]。

    Args:
        content: Markdown 文件的完整文本。

    Returns:
        字典，包含 frontmatter 中的键值对。
        若文件没有 frontmatter，返回空字典。
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return {}
    front: dict = {}
    for line in lines[1:end_idx]:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        # 解析 [item1, item2] 形式的列表
        if value.startswith("[") and value.endswith("]"):
            items = [item.strip() for item in value[1:-1].split(",") if item.strip()]
            front[key] = items
        else:
            front[key] = value
    return front


@pytest.fixture
def adapter_loader():
    """加载平台连接包并返回 AdapterManifest。

    根据 adapter 名读取 adapters/{adapter}/AGENT.md 或 SKILL.md，
    解析 frontmatter 后构造 AdapterManifest。
    Codex 使用 AGENT.md，其余平台使用 SKILL.md。
    """

    def _load(adapter_name: str) -> AdapterManifest:
        adapter_dir = Path(__file__).resolve().parents[2] / "adapters" / adapter_name
        md_file = adapter_dir / ("AGENT.md" if adapter_name == "codex" else "SKILL.md")
        content = md_file.read_text(encoding="utf-8")
        front = _parse_frontmatter(content)
        return AdapterManifest(
            platform=front.get("platform", adapter_name),
            supports=list(front.get("supports", [])),
            defined_features=list(front.get("defines", [])),
            disallowed_actions=list(front.get("never_allows", [])),
        )

    return _load


@pytest.mark.parametrize("adapter", ["codex", "trae", "workbuddy", "reasonix"])
def test_adapter_declares_required_capabilities(adapter_loader, adapter) -> None:
    manifest = adapter_loader(adapter)
    assert manifest.supports_any("mcp", "local_command")
    assert manifest.defines("next_action_loop")
    assert manifest.defines("resume_same_project")
    assert manifest.never_allows("direct_database_write")
