from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator


class SkillNodeDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)
    parent_id: Optional[str] = None
    target: Optional[int] = Field(default=None, exclude=True)


class SkillDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodes: List[SkillNodeDefinition] = Field(min_length=1, max_length=200)
    assignments: Dict[int, str] = Field(default_factory=dict, max_length=1000)

    @model_validator(mode="after")
    def validate_tree(self):
        nodes = {node.id: node for node in self.nodes}
        if len(nodes) != len(self.nodes):
            raise ValueError("ID kỹ năng bị trùng.")
        other = nodes.get("other")
        if not other or other.parent_id is not None or other.title != "Khác":
            raise ValueError("Phải giữ nút gốc hệ thống Khác.")
        for node in self.nodes:
            seen = {node.id}
            parent = node.parent_id
            while parent is not None:
                if parent not in nodes or parent in seen:
                    raise ValueError("Cha không tồn tại hoặc cây có vòng lặp.")
                if parent == "other":
                    raise ValueError("Khác không chứa nhóm con.")
                seen.add(parent)
                if len(seen) > 8:
                    raise ValueError("Cây hỗ trợ tối đa 8 cấp.")
                parent = nodes[parent].parent_id
        if any(tag <= 0 or node not in nodes for tag, node in self.assignments.items()):
            raise ValueError("Ánh xạ tag không hợp lệ.")
        return self

    def require_roots(self):
        if not any(n.parent_id is None and n.id != "other" for n in self.nodes):
            raise ValueError("Hãy tạo ít nhất một nút gốc trước khi phân loại hoặc áp dụng.")


class SkillConfigWrite(BaseModel):
    revision: int = Field(ge=0)
    document: SkillDocument


class SkillConfigAction(BaseModel):
    revision: int = Field(ge=0)


class SkillPreviewRequest(BaseModel):
    document: SkillDocument
    user_id: Optional[int] = Field(default=None, gt=0)


class SkillAISuggestion(BaseModel):
    tag_id: int
    node_id: str
    reason: str = Field(min_length=1, max_length=300)


class SkillAISuggestions(BaseModel):
    suggestions: List[SkillAISuggestion] = Field(max_length=20)

    @model_validator(mode="before")
    @classmethod
    def accept_array_response(cls, value):
        if isinstance(value, list):
            return {"suggestions": value}
        return value


class SkillProposalReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document: SkillDocument
    action: Literal["reject", "approve"]
    tag_ids: List[int] = Field(min_length=1, max_length=1000)
    revision: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_revision_for_approval(self):
        if self.action == "approve" and self.revision is None:
            raise ValueError("Cần revision hiện tại để duyệt đề xuất.")
        return self
