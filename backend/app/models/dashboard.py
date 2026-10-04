"""Import every dashboard-owned model here so migration metadata is complete."""

from app.models.ai_tag import JudgeProblemAiTag
from app.models.class_preferences import ClassStar
from app.models.virtual_class import VirtualClassSession
from app.models.skill_config import SkillConfiguration, SkillConfigurationVersion
