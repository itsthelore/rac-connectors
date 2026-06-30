---
schema_version: 1
id: LCON-KWC2WD0WAYRA
type: decision
---
# ADR-009: Vector-Store Connectors Embed via an External Service

## Context

Every documents backend so far embeds **server-side** — Supermemory, Mem0, and
Zep each take text and produce the vectors themselves. That is what let the
connectors stay model-free: the seam (ADR-002) ships text and metadata, and
"no embeddings, vectors, or model calls happen here — those live in the backend"
holds, consistent with the engine's AI-optional stance (rac-core ADR-002) and its
no-embeddings rule (rac-core ADR-066).

A **bare vector store breaks that assumption.** Qdrant — the first, and the
open-source target — stores vectors but does not produce them. Self-hosted
open-source Qdrant has no server-side embedding (Qdrant Cloud Inference is a
cloud-only feature), so the vectors must be supplied. A vector-store connector
therefore has to obtain an embedding somewhere before it can upsert. This decision
records how, generically, so Qdrant and any future vector store follow one rule
rather than each re-litigating it.

## Decision

Vector-store connectors embed each record's text by calling a **configured
external embedding service**, and that is an explicit, scoped exception to the
model-free connector invariant.

1. **External, OpenAI-compatible endpoint.** The connector POSTs text to a
   configured `/embeddings` endpoint and upserts the returned vectors. A
   [LiteLLM](https://litellm.ai) gateway is the reference deployment, mirroring
   the grounding benchmark's `*_BASE_URL` proxy pattern; any OpenAI-compatible
   endpoint works. The endpoint, model, and credentials are environment config
   (`RAC_EMBED_BASE_URL`, `RAC_EMBED_MODEL`, `RAC_EMBED_API_KEY`) — they live in
   the deployment, never in RAC.
2. **No bundled model, no provider SDK.** The embedding seam
   (`rac_connectors.embedding.Embedder`) is a small Protocol with a stdlib-HTTP
   adapter, so RAC gains no model and no dependency; the connector depends only on
   the Protocol and the test-suite drives a fake.
3. **Scoped exception only.** This applies solely to vector-store connectors that
   need vectors. Server-side-embedding backends stay model-free, and the engine
   (rac-core ADR-002/ADR-066) is unchanged — RAC still ships no model and makes no
   model call of its own.
4. **Pin the model.** Vectors, and the vector store's collection dimension, are
   tied to the embedding model; it must be pinned, and changing it means
   re-embedding the corpus.

## Consequences

### Positive

- Qdrant — and any future vector store — becomes integrable on the existing
  `Connector.push` seam.
- Provider-neutral: the gateway (LiteLLM, OpenAI, Ollama, …) is chosen and
  swapped in the deployment with no connector change; keys and model stay
  external to RAC.
- No dependency weight: only the vector store's own client is an extra; the
  embedding call is stdlib HTTP.

### Negative

- A live push to a vector store now requires a reachable external embedding
  endpoint — these connectors are no longer model-free.
- Reproducibility depends on the pinned model (and the gateway's routing), not on
  RAC alone.

### Risks

- An embedding model is changed silently and the collection's vectors become
  inconsistent. Mitigation: pin the model, document that a change requires a
  re-embed, and keep the collection dimension derived from the live vector size.

## Status

Accepted

## Category

Architecture

## Alternatives Considered

### Bundle a local embedding model (e.g. fastembed) as the default

Rejected as the default: it pulls a model and its runtime into RAC, is heavier and
less neutral, and bakes a model choice into the connector. An external endpoint
keeps RAC model-free and lets the deployment own the model; a bundled local option
can still be added later behind the same `Embedder` seam.

### Require server-side embedding (Qdrant Cloud Inference only)

Rejected: it would exclude self-hosted open-source Qdrant — the open-source target
— so it does not actually solve the integration.

## Related Decisions

- adr-001
- adr-002

## Review Date

Revisit if a vector store gains a server-side embedding path worth adopting, or if
a bundled local-embedding option is wanted as an alternative behind the `Embedder`
seam.
