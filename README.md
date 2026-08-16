# Sonar

A bilingual (English / Hindi) voice agent that answers questions about a business
from its own website or documents.

Content is crawled, chunked, and embedded into a **pack**. At call time the
agent retrieves the matching chunks and speaks the answer.

Nothing is translated ahead of time. Chunks are indexed in whatever language
they were written in, and `multilingual-e5` puts every language in one vector
space — so a Hindi question retrieves an English passage directly, and the
answering model replies in the caller's language:

```
any source language -> chunk -> embed -> ONE index
                                            |
                                        retrieve
                                            |
                                   LLM answers in the
                                     caller's language
                                            |
                                    number expansion
                                            |
                                           TTS
```

Build cost is therefore O(pages), not O(chunks x languages), and adding a
language costs nothing at build time.

## Stack

| Piece      | Used for                                        |
| ---------- | ----------------------------------------------- |
| LiveKit    | Realtime voice session and turn detection       |
| Sarvam     | Speech-to-text (`saarika`) and TTS (`bulbul`)   |
| Groq       | LLM for answers                                 |
| fastembed  | `multilingual-e5-large` embeddings (local)      |
| FastAPI    | Dashboard, pack builds, and session tokens      |

## Layout

```
pipeline/   crawl -> chunk -> embed
worker/     the LiveKit voice agent, retrieval, number expansion, metrics
api/        FastAPI app: dashboard, packs, chats, session tokens
scripts/    setup check, retrieval probe, latency/cost report
packs/      built content, one directory per source (gitignored)
```

## Setup

```bash
uv sync
```

Create a `.env` in the repo root:

```
LIVEKIT_URL=wss://...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
SARVAM_API_KEY=...
GROQ_API_KEY=...
```

Verify keys and connectivity:

```bash
uv run python scripts/check_setup.py
```

## Running it

Two processes: the API (which serves the dashboard and builds packs) and the
voice worker.

```bash
uv run uvicorn api.main:app --reload      # http://localhost:8000/dashboard
uv run python -m worker.agent start       # in a second terminal
```

From the dashboard: add a site or a PDF in the Context panel, wait for the pack
to reach **ready**, then press the mic. Serve it over `localhost` — browsers
refuse microphone access to pages opened as `file://`.

## Packs

A pack is one source turned into retrievable, speakable content. It lives in
`packs/<pack_id>/` — `raw/` holds extracted markdown, `build/` holds chunks,
indexes, and vectors — and `meta.json` carries its build stage.

The dashboard builds packs for you. To do it from the shell:

```bash
uv run python -m pipeline.run https://example.com 25   # or a local .pdf path
```

That runs the whole chain: extract → chunk → embed. No LLM runs during a build,
so it takes seconds and costs nothing. Re-embedding an existing pack on its own:

```bash
uv run python -m pipeline.embed <pack_id>
```

To see what the agent would actually be handed for a question:

```bash
PYTHONPATH=. uv run python scripts/probe.py <pack_id> "how much is the coffee" "कीमत कितनी है"
```

Cross-lingual scores land a little below same-language ones, which is what
`RETRIEVAL_MIN_SCORE` in [worker/config.py](worker/config.py) is tuned against.

## How a call picks its pack

Each chat is attached to one pack. Starting a call posts to `/api/sessions`,
which creates a room, dispatches the agent onto it with
`{"pack_id": ...}` as job metadata, and returns a token for the browser to join
the same room. The worker reads that metadata in `pack_id_for_job()`, so
nothing about the pack is hardcoded.

To run the worker without the API — the LiveKit console, for instance — set a
fallback:

```bash
SONAR_PACK_ID=<pack_id> uv run python -m worker.agent console
```

## Speaking numbers

Sarvam reads `282006` as a quantity, which is right for a price and wrong for a
pincode. [worker/verbalize.py](worker/verbalize.py) spells identifiers out digit
by digit on the way to TTS, buffering across stream chunks so a phone number
split between two LLM tokens still expands.

It runs in `tts_node`, not `transcription_node` — the caller hears the digits
read out while the on-screen transcript keeps `282006`.

## Metrics

Every turn is appended to `logs/turns.jsonl` with latency breakdown
(end-of-utterance, LLM time-to-first-token, TTS time-to-first-byte), token
counts, and an estimated rupee cost. Summarize a session with:

```bash
uv run python scripts/report.py
```
