"""Contratos versionados de manifesto e estado operacional."""
from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class InputRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class Failure(BaseModel):
    type: str
    message: str


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["0.1.0"]
    stage: Literal["02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"] = "02"
    run_id: str = Field(pattern=r"^\d{8}T\d{6}Z_[a-f0-9]{10}$")
    command: str
    status: Literal["running", "completed", "failed", "interrupted"]
    started_at: AwareDatetime
    finished_at: AwareDatetime | None
    config: dict
    inputs: list[InputRecord]
    environment: dict
    code_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    outputs: list[str]
    cache_hit: bool
    scientific_pilot_executed: Literal[False]
    source_run_id: str | None = None
    error: Failure | None = None

    @model_validator(mode="after")
    def consistent_status(self):
        if self.status == "running" and self.finished_at is not None:
            raise ValueError("Execução em andamento não pode ter término")
        if self.status != "running" and self.finished_at is None:
            raise ValueError("Status final exige término")
        if self.status == "completed" and (not self.outputs or self.error):
            raise ValueError("Conclusão exige produtos e ausência de erro")
        if self.status in {"failed", "interrupted"} and self.error is None:
            raise ValueError("Falha/interrupção exige contexto do erro")
        if self.finished_at and self.finished_at < self.started_at:
            raise ValueError("Término anterior ao início")
        return self


class StageRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    nome: str
    status: Literal["nao_iniciada", "em_execucao", "concluida", "incompleta_por_dependencia"]
    artefatos: list[str]


class ProjectState(BaseModel):
    # Preserva decisões e campos científicos adicionados em outras etapas.
    model_config = ConfigDict(extra="allow")
    schema_version: str
    etapa_atual: str = Field(pattern=r"^\d{2}$")
    status: str
    etapas: dict[str, StageRecord]
    piloto_executado: bool
    pipeline_cientifico_implementado: bool
