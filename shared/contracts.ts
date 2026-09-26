/* Safe Harbor wire contract v1. Integrator-owned. */
export const SCHEMA_VERSION = 1 as const;
export type Mode = 'mock' | 'deterministic' | 'real_model';
export type ScreenStatus = 'pass' | 'fail' | 'incomplete';
export type EvidenceStatus = 'supported_for_endpoint' | 'conflicting' | 'unknown';
export type Freshness = 'current' | 'stale';
export type TaskStatus = 'queued' | 'running' | 'complete' | 'blocked' | 'reopened' | 'superseded' | 'failed';
export type TaskKind = 'screen_regions' | 'inspect_evidence' | 'compute_features' | 'assess_candidate' | 'review_candidate' | 'publish_shortlist';
export interface Interval { assembly:'GRCh38'; chromosome:string; start:number; end:number; coordinate_system:'zero_based_half_open' }
export interface Candidate extends Interval { candidate_id:string; name:string; cell_context:string; source_coordinates:Record<string,unknown>; evidence_ids:string[]; group_id:string; data_version:string; [key:string]:unknown }
export interface ReadSet { key:string; version:number | string; kind:'artifact' | 'query_scope' | 'criteria' }
export interface Budget { token_limit:number; tool_limit:number; cost_limit_usd:number; tokens_used:number; tool_calls:number; model_calls:number; cost_usd:number|null; reserved_tokens:number; uncertain_tokens:number; [key:string]:unknown }
export interface Run { run_id:string; schema_version:1; objective:string; mode:Mode; status:string; candidate_ids:string[]; assembly:'GRCh38'; cell_context:string; data_version:string; harness_hash:string; run_revision:number; through_sequence:number; coordinator_epoch:number; budget:Budget; created_at:string; [key:string]:unknown }
export interface Task { task_id:string; run_id:string; candidate_id?:string|null; kind:TaskKind; question:string; canonical_question_key:string; decision_target:string; depends_on:string[]; input_read_set:ReadSet[]; role_id:string; harness_hash:string; allowed_tools:string[]; completion_condition:string; budget:Record<string,unknown>; status:TaskStatus; attempt:number; result_artifact_ids?:string[]; reopen_reason?:string; [key:string]:unknown }
export interface Artifact { artifact_id:string; run_id:string; kind:string; revision:number; content_hash:string; data:Record<string,unknown>; evidence_ids:string[]; input_read_set:ReadSet[]; provenance:Record<string,unknown>; created_at:string; [key:string]:unknown }
export interface CriterionResult { criterion_id:string; status:ScreenStatus; reason:string; evidence_ids:string[]; [key:string]:unknown }
export interface EndpointResult { endpoint:string; assay:string; cell_context:string; evidence_status:EvidenceStatus; reason:string; evidence_ids:string[]; [key:string]:unknown }
export interface Assessment { assessment_id:string; run_id:string; candidate_id:string; assembly:'GRCh38'; cell_context:string; screen_status:ScreenStatus; evidence_status:EvidenceStatus; criterion_results:CriterionResult[]; experimental_endpoint_results:EndpointResult[]; evidence_ids:string[]; unresolved_questions:string[]; limitations:string[]; assessment_revision:number; freshness:Freshness; conclusion:string; input_read_set:ReadSet[]; [key:string]:unknown }
export interface Role { role_id:string; kind:TaskKind; question:string; depends_on:string[]; allowed_tools:string[]; context_policy:string; instructions:string; [key:string]:unknown }
export interface HarnessVersion { harness_hash:string; name:string; parent_hash:string|null; roles:Role[]; patch:Record<string,unknown>|null; proposal_mode:string; immutable_constraints:Record<string,unknown>; [key:string]:unknown }
export interface Evaluation { evaluation_id:string; [key:string]:unknown }
export interface Upserts { runs?:Run[]; candidates?:Candidate[]; tasks?:Task[]; artifacts?:Artifact[]; assessments?:Assessment[]; harness_versions?:HarnessVersion[]; evaluations?:Evaluation[] }
export interface CommitEvent { schema_version:1; run_id:string; sequence:number; event_id:string; operation_id:string; occurred_at:string; type:'state.committed'; cause:string; run_revision:number; upserts:Upserts; camera_cue?:Record<string,unknown> }
export interface Snapshot { schema_version:1; run_id:string; through_sequence:number; run:Run; candidates:Candidate[]; tasks:Task[]; artifacts:Artifact[]; assessments:Assessment[]; harness_versions:HarnessVersion[]; evaluations:Evaluation[] }
export interface Catalog { schema_version:1; assembly:'GRCh38'; cell_context:string; data_version:string; candidates:Candidate[]; chromosomes:{chromosome:string; length:number}[]; modes:Mode[]; model_available:boolean; revision_fixtures:{fixture_id:string; label:string; description:string}[]; [key:string]:unknown }
export interface CreateRun { candidate_ids:string[]; mode:Mode; harness_hash?:string; budget?:{token_limit:number; tool_limit:number; cost_limit_usd:number} }
export interface EventPage { events:CommitEvent[]; through_sequence:number; has_more:boolean }
