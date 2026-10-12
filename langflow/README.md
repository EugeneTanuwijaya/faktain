# Faktain flows (Langflow 1.12.1)

Import `text-verification.json`, `image-verification.json` and `news-summary.json`.
The generator also writes a local `flow.json` alias, which is excluded from Git.

Configure every custom component's Backend URL and Service Key using the same
private callback configuration as FastAPI. Configure the built-in Language Model
handle with an OpenAI Compatible 9Router provider; configure a vision-capable
handle separately in the image flow. Exported credentials and provider selection
are intentionally blank. Do not enter secrets into prompts or Chat Input.
The current local text/image verification handles use `gh/gpt-4.1` through
9Router, after `gh/gpt-4o-mini` repeatedly mistook a completed event for a future
prediction in the regression sample. Summary retains its previous model. These
are local router IDs, not universal defaults; importing an export requires model
configuration and a live evidence test. Token/call/deadline limits are unchanged.

Chat Input accepts only `{"analysis_id":"<backend-issued ID>"}`. The backend
creates and cleans an ephemeral session. Raw input, normalized images and source
articles are obtained through authenticated callbacks. Intermediate graph
messages contain only the session ID, and Store Messages is disabled on input
and output. Components refuse sensitive callbacks unless runtime tracing and
transaction/vertex/synchronous-result storage are disabled, `do_not_track` is
true, the disk telemetry writer is disabled, and global LangChain/LangSmith
tracing flags are disabled. Logging must also avoid payloads and credentials;
export settings alone do not prove runtime privacy.

`workflow.py` is the single source for stage logic; prompts are maintained in
`backend/app/services/verification_prompts.py`. `component.py` provides the
Langflow adapter. Generate all exports after source edits:

```powershell
.venv/Scripts/python.exe langflow/build_flows.py --url http://127.0.0.1:7860
```

The generator reads native component templates and validates custom components
using the target instance; it does not import flows or change provider settings.
It uses local auto-login and is intended for the local development instance.
All model calls reserve the backend budget first, use the shared remaining
deadline and bind a stage-specific output token limit. SDK retries are disabled
on the injected OpenAI synchronous/asynchronous clients before invocation.

Expected failures return only a sanitized typed error and stage. Neither image
payloads nor provider/HTTP exception details are returned. A failed extraction
is propagated to output without restarting extraction. FastAPI remains
responsible for strict final verdict/evidence validation and eligible fallback.

See `docs/LANGFLOW.md` for deployment configuration, privacy checks, demos and
verification status.
