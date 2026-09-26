"""Safe Harbor wire contract v1. Integrator owns changes."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
SCHEMA_VERSION = 1
Mode = Literal['mock','deterministic','real_model']
TaskKind = Literal['screen_regions','inspect_evidence','compute_features','assess_candidate','review_candidate','publish_shortlist']
TaskStatus = Literal['queued','running','complete','blocked','reopened','superseded','failed']
class Record(BaseModel):
    model_config = ConfigDict(extra='allow')
class Interval(Record):
    assembly: Literal['GRCh38']='GRCh38'
    chromosome: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    coordinate_system: Literal['zero_based_half_open']='zero_based_half_open'
    @model_validator(mode='after')
    def ordered(self):
        if self.end <= self.start: raise ValueError('end must exceed start')
        if self.chromosome not in [f'chr{i}' for i in range(1,23)]+['chrX','chrY','chrM']: raise ValueError('canonical chromosome required')
        return self
class Candidate(Interval):
    candidate_id: str
    name: str
    cell_context: str='H1 human embryonic stem cells'
    source_coordinates: dict[str,Any]
    evidence_ids: list[str]
    group_id: str
    data_version: str
class ReadSet(Record):
    key: str
    version: int|str
    kind: Literal['artifact','query_scope','criteria']
class Budget(Record):
    token_limit: int=200000
    tool_limit: int=40
    cost_limit_usd: float=5.0
    tokens_used: int=0
    tool_calls: int=0
    model_calls: int=0
    cost_usd: float|None=None
    reserved_tokens: int=0
    uncertain_tokens: int=0
class Run(Record):
    run_id: str
    schema_version: Literal[1]=1
    objective: str
    mode: Mode
    status: str
    candidate_ids: list[str]
    assembly: Literal['GRCh38']='GRCh38'
    cell_context: str='H1 human embryonic stem cells'
    data_version: str
    harness_hash: str
    run_revision: int=0
    through_sequence: int=0
    coordinator_epoch: int=0
    budget: Budget=Field(default_factory=Budget)
    created_at: str
class Task(Record):
    task_id: str
    run_id: str
    candidate_id: str|None=None
    kind: TaskKind
    question: str
    canonical_question_key: str
    decision_target: str
    depends_on: list[str]
    input_read_set: list[ReadSet]
    role_id: str
    harness_hash: str
    allowed_tools: list[str]
    completion_condition: str
    budget: dict[str,Any]
    status: TaskStatus='queued'
    attempt: int=0
class Artifact(Record):
    artifact_id: str
    run_id: str
    kind: str
    revision: int
    content_hash: str
    data: dict[str,Any]
    evidence_ids: list[str]
    input_read_set: list[ReadSet]
    provenance: dict[str,Any]
    created_at: str
class Assessment(Record):
    assessment_id: str
    run_id: str
    candidate_id: str
    assembly: Literal['GRCh38']='GRCh38'
    cell_context: str='H1 human embryonic stem cells'
    screen_status: Literal['pass','fail','incomplete']
    evidence_status: Literal['supported_for_endpoint','conflicting','unknown']
    criterion_results: list[dict[str,Any]]
    experimental_endpoint_results: list[dict[str,Any]]
    evidence_ids: list[str]
    unresolved_questions: list[str]
    limitations: list[str]
    assessment_revision: int
    freshness: Literal['current','stale']
    conclusion: str
    input_read_set: list[ReadSet]
class CreateRun(BaseModel):
    model_config=ConfigDict(extra='forbid')
    candidate_ids: list[str]=Field(min_length=1,max_length=3)
    mode: Mode='deterministic'
    harness_hash: str|None=None
    budget: dict[str,Any]|None=None
class EvidenceRevision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    fixture_id: str
class CreateExperiment(BaseModel):
    model_config=ConfigDict(extra='forbid')
    mode: Mode='real_model'
    candidate_ids: list[str]|None=None
