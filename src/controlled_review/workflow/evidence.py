"""签名证据服务。

为复核节点生成本机 HMAC 签名证据，将证据绑定到具体 assignment（角色）和目标，
防止证据跨目标、跨角色复用。密钥保存在系统状态目录，不写入项目输出、日志和任务负载。
"""

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class EvidenceRejected(Exception):
    """证据验证被拒绝（目标、角色或签名不匹配）。"""
    pass


@dataclass(frozen=True)
class Evidence:
    """签名证据，绑定 assignment、角色、目标、节点与上下文。

    signature 覆盖所有关键字段，任何篡改都会导致验签失败。
    """

    id: str
    assignment_id: str
    role: str
    target_id: str
    node_id: str
    file_sha256: str
    context_sha256: str
    signature: str
    nonce: str
    obtained_at: str


class EvidenceService:
    """签名证据服务。

    使用 HMAC-SHA256 对 (assignment_id, role, target_id, file_sha256, node_id,
    context_sha256, nonce) 七元组签名，确保证据不可伪造、不可复用。
    """

    def __init__(self, secret: bytes = None):
        """初始化服务。

        Args:
            secret: HMAC 密钥。为 None 时从系统状态目录加载或生成新密钥，
                    保证进程间一致。
        """
        self.secret = secret or self._load_or_generate_secret()
        # 进程内证据存储：id -> Evidence
        # ponytail: 简化实现，不引入持久化；validate 需根据 id 查找证据
        self._store: dict[str, Evidence] = {}

    def record(
        self,
        assignment,
        target_id,
        node_id,
        context: str = "",
        file_sha256: str = "",
    ) -> Evidence:
        """记录证据，返回包含 HMAC 签名的 Evidence 对象。

        Args:
            assignment: Assignment 对象，提供 assignment_id 与 role
            target_id: 目标 ID（证据绑定到此目标）
            node_id: 节点 ID（如工作表与单元格地址）
            context: 上下文文本，参与签名（可选）
            file_sha256: 文件摘要，参与签名（可选）

        Returns:
            Evidence 对象，已存入内部存储，可通过 id 查找
        """
        nonce = secrets.token_hex(16)
        context_sha256 = hashlib.sha256(context.encode("utf-8")).hexdigest()
        # 签名 payload：七元组拼接，原样使用简报代码（字段名适配 Assignment）
        payload = "|".join(
            (
                assignment.assignment_id,
                assignment.role,
                target_id,
                file_sha256,
                node_id,
                context_sha256,
                nonce,
            )
        )
        signature = hmac.new(
            self.secret, payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        evidence_id = f"ev-{nonce[:8]}"
        evidence = Evidence(
            id=evidence_id,
            assignment_id=assignment.assignment_id,
            role=assignment.role,
            target_id=target_id,
            node_id=node_id,
            file_sha256=file_sha256,
            context_sha256=context_sha256,
            signature=signature,
            nonce=nonce,
            obtained_at=datetime.now(timezone.utc).isoformat(),
        )
        self._store[evidence_id] = evidence
        return evidence

    def validate(self, evidence_id, assignment, target_id) -> bool:
        """验证证据是否属于当前 assignment 和 target。

        校验顺序：
        1. 证据存在性
        2. target_id 匹配
        3. assignment_id 与 role 匹配
        4. 签名匹配（防篡改）

        任何一步失败均抛出 EvidenceRejected。

        Args:
            evidence_id: 证据 ID
            assignment: 当前调用方的 Assignment
            target_id: 当前请求的目标 ID

        Returns:
            True（校验通过）

        Raises:
            EvidenceRejected: 任一校验失败
        """
        evidence = self._store.get(evidence_id)
        if evidence is None:
            raise EvidenceRejected(f"证据不存在: {evidence_id}")
        # 检查 target_id
        if evidence.target_id != target_id:
            raise EvidenceRejected(
                f"证据目标 {evidence.target_id} 与请求目标 {target_id} 不匹配"
            )
        # 检查 assignment_id 与 role
        if (
            evidence.assignment_id != assignment.assignment_id
            or evidence.role != assignment.role
        ):
            raise EvidenceRejected("证据不属于当前工作者")
        # 重新构建 payload 并验证签名
        payload = "|".join(
            (
                evidence.assignment_id,
                evidence.role,
                evidence.target_id,
                evidence.file_sha256,
                evidence.node_id,
                evidence.context_sha256,
                evidence.nonce,
            )
        )
        expected_signature = hmac.new(
            self.secret, payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        # 常量时间比较，防止时序攻击
        if not hmac.compare_digest(evidence.signature, expected_signature):
            raise EvidenceRejected("签名验证失败")
        return True

    @staticmethod
    def _load_or_generate_secret() -> bytes:
        """从系统状态目录加载或生成 HMAC 密钥。

        Windows 下使用 %APPDATA%\\controlled-review\\evidence.key，
        首次调用生成 32 字节随机密钥并保存。
        """
        appdata = os.environ.get("APPDATA")
        if appdata:
            state_dir = Path(appdata) / "controlled-review"
        else:
            # 回退：用户主目录
            state_dir = Path.home() / ".controlled-review"
        state_dir.mkdir(parents=True, exist_ok=True)
        key_path = state_dir / "evidence.key"
        if key_path.exists():
            return key_path.read_bytes()
        secret = secrets.token_bytes(32)
        # 仅所有者可读写（Windows 下 chmod 限制有限，但仍设置）
        key_path.write_bytes(secret)
        try:
            key_path.chmod(0o600)
        except OSError:
            # Windows 上 chmod 可能不完全生效，忽略
            pass
        return secret
