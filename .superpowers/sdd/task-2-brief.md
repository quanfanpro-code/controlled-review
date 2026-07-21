## Task 2: 定义领域状态和结构化结论

**Requirements:** R-FN-001、R-FN-009、R-FN-010，AC-007  
**Files:**
- Create: `controlled-review/src/controlled_review/domain/models.py`
- Create: `controlled-review/tests/unit/test_domain_models.py`

- [ ] **Step 1: 写状态与结论验证的失败测试**

```python
from decimal import Decimal
import pytest
from controlled_review.domain.models import ReviewConclusion, ReviewResult


def test_clear_issue_requires_fact_and_evidence() -> None:
    with pytest.raises(ValueError):
        ReviewConclusion(result=ReviewResult.CLEAR_ISSUE, fact="", evidence_ids=())


def test_rounding_difference_preserves_amount() -> None:
    item = ReviewConclusion(
        result=ReviewResult.ROUNDING,
        fact="附注明细合计与报表相差1千元",
        evidence_ids=("ev-1",),
        difference=Decimal("1"),
    )
    assert item.difference == Decimal("1")
```

- [ ] **Step 2: 运行并确认模型尚不存在**

Run: `python -m pytest tests/unit/test_domain_models.py -v`  
Expected: FAIL，提示 `controlled_review.domain.models` 不存在。

- [ ] **Step 3: 实现有限状态和不可缺省字段**

```python
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class ReviewResult(StrEnum):
    NO_EXCEPTION = "no_exception"
    CLEAR_ISSUE = "clear_issue"
    HIGH_RISK = "high_risk"
    ATTENTION = "attention"
    ROUNDING = "rounding"
    OFFICIAL_UNCONFIRMED = "official_unconfirmed"
    PROFESSIONAL_DISAGREEMENT = "professional_disagreement"
    UNRELIABLE = "unreliable"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class ReviewConclusion:
    result: ReviewResult
    fact: str
    evidence_ids: tuple[str, ...]
    difference: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.fact.strip() or not self.evidence_ids:
            raise ValueError("fact and evidence are required")
```

同时补齐设计定义的项目状态、目标状态、角色、质量模式和把握程度枚举；所有外部字符串必须先转换为枚举才能入库。

- [ ] **Step 4: 运行模型测试**

Run: `python -m pytest tests/unit/test_domain_models.py -v`  
Expected: PASS。

- [ ] **Step 5: 提交领域模型**

```bash
git add src/controlled_review/domain/models.py tests/unit/test_domain_models.py
git commit -m "feat: define review domain states"
```
