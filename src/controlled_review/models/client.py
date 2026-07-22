"""隔离备用模型客户端。

提供可替换模型接口、隔离会话生成与 payload 构建器：
- ModelClient 协议定义可替换模型接口，供依赖注入使用。
- new_isolated_session 生成每次 verifier 调用的独立会话 ID，
  保证第二轮独立复核无法看到第一轮上下文。
- ModelClientBuilder 构建 payload，verifier 角色不携带第一轮
  reviewer 的结论、理由、证据，避免泄露第一轮答案。
"""

import secrets
from typing import Protocol


class ModelClient(Protocol):
    def complete(self, *, system: str, task: dict, session_id: str) -> dict: ...


def new_isolated_session() -> str:
    return secrets.token_urlsafe(24)


class ModelClientBuilder:
    """模型客户端构建器，构建不泄露第一轮答案的 payload。"""

    def build_payload(self, role, target) -> dict:
        """构建 payload。

        Args:
            role: 角色（reviewer / verifier）。
            target: 复核目标。

        Returns:
            payload 字典。verifier 角色不包含 reviewer_result、reviewer_reason、
            reviewer_evidence_ids 字段，确保第二轮独立复核无法看到第一轮答案。
        """
        payload = {
            "role": role,
            "target": target,
        }
        # 仅 reviewer 携带第一轮结论；verifier 不添加这些字段，避免泄露答案
        if role == "reviewer":
            # ponytail: 占位值，实际值由调用方在运行时填入
            payload["reviewer_result"] = ""
            payload["reviewer_reason"] = ""
            payload["reviewer_evidence_ids"] = []
        return payload
