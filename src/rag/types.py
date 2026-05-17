from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class QueryPlan:
    question: str
    search_query: str
    format_instruction: str
    complexity: str
    use_paid: bool
    model_name: str
    top_k: int
    merged_filters: Dict[str, Any]
    queries: List[str]
    free_model: Optional[str]
    paid_model: Optional[str]

