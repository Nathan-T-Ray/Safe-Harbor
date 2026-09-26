"""Validated, scoped worker tools. No arbitrary files, URLs, uploads or writes.

The runtime supplies evidence availability from its ledger and owns every write.
These tools operate only on the immutable, allowlisted scientific source pack.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from .catalog import DATA, _load
from .calculations import candidate_record, differential_gene_proximity, screen_candidate
from .expression_tools import control_overlap, expression_comparison, expression_rows, numeric_row, qpcr_summary

APPROVED_TOOL_NAMES = ("inspect_candidate", "list_evidence", "table_slice", "expression_comparison", "control_overlap",
                       "gene_proximity", "screen_candidate", "reference_sequence")
MAX_RESULT_BYTES = 30000


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cell_context: Literal["H1", "H9"] = "H1"


class EvidenceArguments(Arguments):
    controls_available: StrictBool = True


class TableArguments(EvidenceArguments):
    contrast: Literal["candidate", "untargeted"] = "candidate"
    offset: StrictInt = Field(default=0, ge=0, le=1000)
    limit: StrictInt = Field(default=8, ge=1, le=20)


class SequenceArguments(Arguments):
    offset: StrictInt = Field(default=0, ge=-100, le=2000)
    length: StrictInt = Field(default=120, ge=1, le=240)


class ScientificResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool_name: str
    candidate_id: str
    assembly: Literal["GRCh38"] = "GRCh38"
    cell_context: str
    data_version: str
    evidence_ids: list[str]
    source_hashes: dict[str, str]
    calculation: dict[str, Any]
    limitations: list[str]
    input_read_set: list[dict[str, Any]]
    provenance: dict[str, Any]


ARGUMENT_MODELS = {
    "inspect_candidate": Arguments, "list_evidence": EvidenceArguments, "table_slice": TableArguments,
    "expression_comparison": EvidenceArguments, "control_overlap": EvidenceArguments,
    "gene_proximity": Arguments, "screen_candidate": Arguments, "reference_sequence": SequenceArguments,
}
SCOPES = {
    "inspect_candidate": ("catalog",),
    "list_evidence": ("catalog", "expression", "annotation", "sequence"),
    "table_slice": ("expression",), "expression_comparison": ("expression",), "control_overlap": ("expression",),
    "gene_proximity": ("expression", "annotation"), "screen_candidate": ("annotation",),
    "reference_sequence": ("sequence",),
}
DESCRIPTIONS = {
    "inspect_candidate": "Inspect the selected publication-derived region, verified GRCh38 coordinates, methods, criteria and evidence availability.",
    "list_evidence": "List bounded source evidence metadata and query coverage for the selected region; explicitly report unavailable required evidence.",
    "table_slice": "Read up to 20 original significant-only expression table rows by offset, candidate/untargeted contrast and H1 or separately labeled H9 context.",
    "expression_comparison": "Recompute unique DE gene counts at absolute log2 fold change >=1 and FDR<=0.01, comparing the selected clone with independent untargeted controls when available.",
    "control_overlap": "Recompute overlap of targeted and independent untargeted DE gene sets with explicit denominators and expression-direction concordance.",
    "gene_proximity": "Use Bioframe to locate nearest same-chromosome DE gene bodies in frozen GENCODE v36, report unmapped IDs and distinct source-table mapping.",
    "screen_candidate": "Compute frozen named genomic criteria with Bioframe; distinguish gene-body overlap, strand-aware TSS and missing cancer/regulatory evidence.",
    "reference_sequence": "Retrieve at most 240 actual GRCh38 reference bases within the frozen selected-candidate window; offset is relative to candidate start, orientation is plus.",
}


def tool_definitions(names: list[str] | tuple[str, ...] = APPROVED_TOOL_NAMES) -> list[dict]:
    result = []
    for name in names:
        if name not in ARGUMENT_MODELS:
            raise ValueError("Unknown scientific tool")
        schema = ARGUMENT_MODELS[name].model_json_schema()
        # The availability bit is reserved for trusted runtime injection. Models
        # cannot request that a withdrawn source become available again.
        schema["properties"].pop("controls_available", None)
        result.append({"type": "function", "function": {"name": name, "description": DESCRIPTIONS[name], "parameters": schema}})
    return result


def _evidence(name: str, candidate_id: str, context: str, controls_available: bool) -> tuple[list[str], list[str]]:
    supplement = "supp5" if context == "H1" else "supp6"
    files, ids = [], []
    if name in ("inspect_candidate", "list_evidence"):
        files.append("elife-79592-supp1.xlsx")
        ids.append("source:supp1")
    if name in ("list_evidence", "table_slice", "expression_comparison", "control_overlap", "gene_proximity"):
        if name != "control_overlap" or controls_available:
            files.append(f"elife-79592-{supplement}.xlsx")
            ids.append(f"source:{supplement}:{candidate_id}")
            if controls_available and name in ("list_evidence", "expression_comparison", "control_overlap"):
                ids.append(f"source:{supplement}:untargeted")
    if name in ("list_evidence", "gene_proximity", "screen_candidate"):
        files += ["wgEncodeGencodeCompV36.txt.gz", "wgEncodeGencodeAttrsV36.txt.gz", "wgEncodeGencodePseudoGeneV36.txt.gz",
                  "wgEncodeGencodeCompV36.sql", "wgEncodeGencodeAttrsV36.sql", "wgEncodeGencodePseudoGeneV36.sql"]
        ids.append(f"source:gencode-v36:{candidate_id}")
    if name in ("list_evidence", "reference_sequence"):
        files.append(f"{candidate_id}-hg38-sequence.json")
        ids.append(f"source:reference:{candidate_id}")
    return ids, files


def _list_evidence(candidate_id: str, context: str, controls_available: bool) -> dict:
    c = candidate_record(candidate_id)
    supplement = "supp5" if context == "H1" else "supp6"
    return {"status": "complete_catalog_query", "query_scope": {"candidate_id": candidate_id, "cell_context": context},
            "evidence": [
                {"evidence_id": "source:supp1", "kind": "published_candidate_interval", "availability": "available", "source": c["source_coordinates"]},
                {"evidence_id": f"source:{supplement}:{candidate_id}", "kind": "expression_table", "availability": "available", "cell_context": context,
                 "row_count": len(expression_rows(candidate_id, context)), "coverage": "significant-only"},
                {"evidence_id": f"source:{supplement}:untargeted", "kind": "independent_untargeted_expression_table", "cell_context": context,
                 "availability": "available" if controls_available else "unavailable", "row_count": len(expression_rows(candidate_id, context, "untargeted")) if controls_available else None},
                {"evidence_id": "source:supp4", "kind": "qPCR_replicate_table", "cell_context": context, "availability": "available"},
                {"evidence_id": f"source:gencode-v36:{candidate_id}", "kind": "reference_annotation", "availability": "available",
                 "coverage": _load("reference_assets")[candidate_id]["annotation"]["coverage"], "release": "GENCODE v36"},
                {"evidence_id": f"source:reference:{candidate_id}", "kind": "reference_sequence", "availability": "available",
                 "start": _load("reference_assets")[candidate_id]["sequence"]["start"], "end": _load("reference_assets")[candidate_id]["sequence"]["end"]}],
            "unavailable_required": _load("manifest")["unavailable"],
            "methods": _load("manifest")["input_contract"],
            "limitations": ["A complete evidence-catalog query can return unavailable requirements; unavailable is not a negative result."]}


def _table(candidate_id: str, args: TableArguments) -> dict:
    if args.contrast == "untargeted" and not args.controls_available:
        raise PermissionError("Untargeted control table is unavailable under the current evidence revision")
    rows = expression_rows(candidate_id, args.cell_context, args.contrast)
    selected = rows[args.offset:args.offset+args.limit]
    return {"status": "computed", "cell_context": args.cell_context, "contrast": args.contrast,
            "table_coverage": "significant-only", "offset": args.offset, "limit": args.limit,
            "total_rows": len(rows), "returned_rows": len(selected),
            "next_offset": args.offset+len(selected) if args.offset+len(selected) < len(rows) else None,
            "rows": [numeric_row(row) for row in selected],
            "omitted_source_columns": "Precomputed overlap flags are excluded; use control_overlap to compute them from original gene sets.",
            "limitations": ["No raw counts or nonsignificant rows are supplied in this source table."]}


def _sequence(candidate_id: str, args: SequenceArguments) -> dict:
    c = candidate_record(candidate_id)
    frozen = _load("reference_assets")[candidate_id]["sequence"]
    start = c["start"]+args.offset
    end = start+args.length
    if start < frozen["start"] or end > frozen["end"]:
        raise ValueError("Requested sequence lies outside the frozen reference window")
    seq = frozen["sequence"][start-frozen["start"]:end-frozen["start"]]
    return {"status": "computed", "assembly": "GRCh38", "chromosome": c["chromosome"], "start": start, "end": end,
            "sequence": seq, "coordinate_system": "zero_based_half_open", "orientation": "reference_plus",
            "display_coordinate_note": "One-based display base labels are internal position + 1.", "length": len(seq),
            "sequence_sha256": hashlib.sha256(seq.encode()).hexdigest(), "frozen_window_sha256": frozen["sha256"],
            "limitations": ["GRCh38 reference sequence, not a personalized H1 genome; no insertion or variant is inferred."]}


def run_tool(tool_name: str, candidate_id: str, arguments: dict | None = None) -> dict:
    if tool_name not in APPROVED_TOOL_NAMES:
        raise PermissionError("Tool is not approved")
    c = candidate_record(candidate_id)
    if arguments is not None and not isinstance(arguments, dict):
        raise TypeError("Tool arguments must be a JSON object")
    args = ARGUMENT_MODELS[tool_name].model_validate(arguments or {})
    context = args.cell_context
    available = getattr(args, "controls_available", True)
    if tool_name == "inspect_candidate":
        calculation = {"status": "computed", "candidate": c, "methods": _load("manifest")["input_contract"],
                       "criteria": _load("criteria"),
                       "limitations": ["Publication-derived shortlist; not a newly discovered locus."]}
    elif tool_name == "list_evidence":
        calculation = _list_evidence(candidate_id, context, available)
    elif tool_name == "table_slice":
        calculation = _table(candidate_id, args)
    elif tool_name == "expression_comparison":
        calculation = expression_comparison(candidate_id, context, available)
        calculation["qpcr"] = qpcr_summary(candidate_id, context)
    elif tool_name == "control_overlap":
        calculation = control_overlap(candidate_id, context, available)
    elif tool_name == "gene_proximity":
        calculation = differential_gene_proximity(candidate_id, context)
    elif tool_name == "screen_candidate":
        calculation = screen_candidate(candidate_id)
    else:
        calculation = _sequence(candidate_id, args)
    evidence_ids, source_names = _evidence(tool_name, candidate_id, context, available)
    if tool_name in ("expression_comparison", "list_evidence"):
        evidence_ids.append("source:supp4")
        source_names.append("elife-79592-supp4.xlsx")
    if tool_name == "table_slice" and args.contrast == "untargeted":
        supplement = "supp5" if context == "H1" else "supp6"
        evidence_ids = [f"source:{supplement}:untargeted"]
    manifest = _load("manifest")
    hashes = {s["source_id"]: s["sha256"] for s in manifest["sources"] if s["source_id"] in source_names}
    reads = [{"key": "source:data_version", "version": manifest["data_version"], "kind": "artifact"},
             {"key": "criteria:v1", "version": 1, "kind": "criteria"}]
    reads += [{"key": f"scope:{candidate_id}:{scope}", "version": 1, "kind": "query_scope"} for scope in SCOPES[tool_name]]
    limitations = list(calculation.get("limitations", []))
    if context == "H9":
        limitations.append("H9 is a separate biological context; this result does not establish an H1 endpoint.")
    result = ScientificResult(tool_name=tool_name, candidate_id=candidate_id, cell_context=f"{context} human embryonic stem cells",
                              data_version=manifest["data_version"], evidence_ids=evidence_ids, source_hashes=hashes,
                              calculation=calculation, limitations=limitations, input_read_set=reads,
                              provenance={"mode": "real_data", "calculation_type": "deterministic_scientific",
                                          "criteria_sha256": hashlib.sha256((DATA / "criteria.json").read_bytes()).hexdigest(),
                                          "runtime_requirement": "Replace query-scope version 1 with the current ledger version before dispatch/acceptance; ledger state governs availability.",
                                          "parameters": args.model_dump(), "tool_implementation": f"safe_harbor.science.{tool_name}"}).model_dump()
    if len(json.dumps(result, ensure_ascii=False).encode()) > MAX_RESULT_BYTES:
        raise ValueError("Scientific result exceeded bounded output limit; retrieve narrower table slices")
    return result


def assessment_facts(candidate_id: str) -> dict:
    """Named deterministic criteria only. No model interpretation is fabricated."""
    result = run_tool("screen_candidate", candidate_id)
    return {"screen_status": result["calculation"]["screen_status"],
            "criterion_results": result["calculation"]["criterion_results"],
            "evidence_ids": result["evidence_ids"], "source_hashes": result["source_hashes"],
            "input_read_set": result["input_read_set"], "evidence_status": "unknown",
            "limitations": result["limitations"]}
