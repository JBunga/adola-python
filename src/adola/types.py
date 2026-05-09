from __future__ import annotations

from typing import Literal, TypedDict


class CompressionOptions(TypedDict, total=False):
    target_ratio: float
    max_output_tokens: int | None
    keep: int | None
    preserve_order: bool


class ProtectedOptions(TypedDict, total=False):
    xml_tags: list[str]
    patterns: list[str]


class Span(TypedDict, total=False):
    id: str
    text: str
    protected: bool
    metadata: dict[str, str]


class CompressRequest(TypedDict, total=False):
    model: Literal["rose-1"]
    query: str | None
    input: str | None
    spans: list[Span] | None
    compression: CompressionOptions
    protected: ProtectedOptions
    include_spans: bool


class Risk(TypedDict):
    level: str
    flags: list[str]


class Receipt(TypedDict):
    original_tokens: int
    output_tokens: int
    tokens_saved: int
    compression_ratio: float
    selected_count: int
    total_spans: int
    protected_tokens: int
    latency_ms: float
    risk: Risk


class SelectedSpan(TypedDict):
    id: str
    index: int
    text: str
    tokens: int
    protected: bool


class CompressResponse(TypedDict):
    model: Literal["rose-1"]
    output: str
    receipt: Receipt
    selected_spans: list[SelectedSpan]


class Model(TypedDict):
    id: Literal["rose-1"]
    name: str
    mode: Literal["context-compression"]
    target: Literal["production-llm-systems"]


class BatchCompressRequest(TypedDict):
    requests: list[CompressRequest]
