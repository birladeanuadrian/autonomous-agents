from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

Status = Literal["todo", "in_progress", "done"]
ProjectName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
IssueTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ProjectDescription = Annotated[str, StringConstraints(max_length=5000)]
IssueDescription = Annotated[str, StringConstraints(max_length=10000)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectCreate(Input):
    key: Annotated[str, StringConstraints(min_length=2, max_length=10, pattern=r"^[A-Z]{2,10}$")]
    name: ProjectName
    description: ProjectDescription = ""


class IssueCreate(Input):
    title: IssueTitle
    description: IssueDescription = ""
    status: Status = "todo"


class IssueUpdate(Input):
    title: IssueTitle | None = None
    description: IssueDescription | None = None
    status: Status | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Fields cannot be null")
        return self


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    key: str
    name: str
    description: str
    created_at: datetime


class IssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    title: str
    description: str
    status: Status
    created_at: datetime
    updated_at: datetime
