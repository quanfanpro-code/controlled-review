-- 通用受控财务报表复核系统 - 状态库建表脚本
-- 本脚本一次性创建 16 个表，使用 IF NOT EXISTS 保证幂等。
-- 外键约束在应用层通过 PRAGMA foreign_keys=ON 启用。

-- 1. 项目表
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    path TEXT,
    report_type TEXT,
    fiscal_year TEXT,
    quality_mode TEXT,
    materiality_level TEXT,
    status TEXT,
    created_at TEXT
);

-- 2. 输入文件表
CREATE TABLE IF NOT EXISTS source_files (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    path TEXT,
    file_type TEXT,
    size_bytes INTEGER,
    modified_at TEXT,
    sha256 TEXT,
    read_only INTEGER,
    created_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- 3. 文档节点表
CREATE TABLE IF NOT EXISTS document_nodes (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_file_id TEXT NOT NULL,
    node_type TEXT,
    title_path TEXT,
    row_index INTEGER,
    col_index TEXT,
    formula TEXT,
    text TEXT,
    original_location TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (source_file_id) REFERENCES source_files(id)
);

-- 4. 对应关系表
CREATE TABLE IF NOT EXISTS mappings (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    statement_item TEXT,
    note_node_id TEXT,
    relation_type TEXT,
    confidence TEXT,
    source TEXT,
    confirmation_method TEXT,
    version INTEGER,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (note_node_id) REFERENCES document_nodes(id)
);

-- 5. 核对目标表（项目内唯一）
CREATE TABLE IF NOT EXISTS targets (
    project_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    template_version TEXT,
    target_scope TEXT,
    related_node_ids TEXT,
    machine_findings TEXT,
    current_status TEXT,
    PRIMARY KEY (project_id, target_id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- 6. 任务分配表
CREATE TABLE IF NOT EXISTS assignments (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    worker_id TEXT,
    role TEXT,
    claim_token TEXT,
    target_ids TEXT,
    started_at TEXT,
    expires_at TEXT,
    status TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- 7. 任务项目表（任务与目标多对多）
CREATE TABLE IF NOT EXISTS assignment_items (
    id TEXT PRIMARY KEY,
    assignment_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    target_id TEXT,
    FOREIGN KEY (assignment_id) REFERENCES assignments(id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- 8. 证据表
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_file_id TEXT,
    original_location TEXT,
    context TEXT,
    file_sha256 TEXT,
    target_id TEXT,
    role TEXT,
    signature TEXT,
    obtained_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (source_file_id) REFERENCES source_files(id)
);

-- 9. 字段核对表
CREATE TABLE IF NOT EXISTS field_checks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    target_id TEXT,
    scope TEXT,
    period TEXT,
    unit TEXT,
    currency TEXT,
    mapping_id TEXT,
    related_accounts TEXT,
    context TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (mapping_id) REFERENCES mappings(id)
);

-- 10. 复核结论表
CREATE TABLE IF NOT EXISTS review_conclusions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    target_id TEXT,
    result TEXT,
    fact TEXT,
    difference TEXT,
    reason TEXT,
    confidence TEXT,
    suggested_value TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- 11. 隐藏测试表
CREATE TABLE IF NOT EXISTS canaries (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    original_target_id TEXT,
    changed_field TEXT,
    expected_judgment TEXT,
    worker_observation TEXT,
    gate_status TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- 12. 门禁回执表
CREATE TABLE IF NOT EXISTS gate_receipts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    assignment_id TEXT,
    check_item TEXT,
    result TEXT,
    checked_at TEXT,
    receipt_sha256 TEXT,
    failure_reason TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (assignment_id) REFERENCES assignments(id)
);

-- 13. 官方依据表
CREATE TABLE IF NOT EXISTS official_sources (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    institution TEXT,
    name TEXT,
    document_number TEXT,
    publish_date TEXT,
    effective_date TEXT,
    source_url TEXT,
    body_summary TEXT,
    local_copy_path TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- 14. 问题表
CREATE TABLE IF NOT EXISTS issues (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    category TEXT,
    risk_level TEXT,
    confidence TEXT,
    fact TEXT,
    difference TEXT,
    evidence_id TEXT,
    official_source_id TEXT,
    unconfirmed TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (evidence_id) REFERENCES evidence(id),
    FOREIGN KEY (official_source_id) REFERENCES official_sources(id)
);

-- 15. 事件表
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    event_type TEXT,
    event_data TEXT,
    occurred_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- 16. 输出回执表
CREATE TABLE IF NOT EXISTS output_receipts (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    input_summary TEXT,
    template_version TEXT,
    task_count INTEGER,
    completion_status TEXT,
    output_files TEXT,
    receipt_sha256 TEXT,
    generated_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
