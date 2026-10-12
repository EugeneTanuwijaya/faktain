"""Shared bounded workflow; embedded in Langflow components by build_flows.py."""
import asyncio
import json
import os

from app.services.verification_prompts import SAFETY, EXTRACTION, VISION, PLAN, ADEQUACY, MATCH, COMPARISON, SUMMARY, comparison_prompt


def privacy_guard(settings):
    if (getattr(settings, "deactivate_tracing", None) is not True
        or getattr(settings, "transactions_storage_enabled", None) is not False
        or getattr(settings, "vertex_builds_storage_enabled", None) is not False
        or getattr(settings, "sync_result_storage_enabled", None) is not False
        or getattr(settings, "do_not_track", None) is not True
        or getattr(settings, "telemetry_writer_enabled", None) is not False
        or any(os.environ.get(name, "").lower() in ("true", "1", "yes", "on")
               for name in ("LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING"))):
        raise RuntimeError("Langflow privacy configuration required")


def object_result(content):
    if not isinstance(content, str):
        raise ValueError("Invalid model output")
    content = content.strip()
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("Invalid model output")
    return value


def fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError("Invalid model schema")


def strings(value, limit, max_chars):
    if not isinstance(value, list) or len(value) > limit or any(not isinstance(s, str) or not s.strip() or len(s) > max_chars for s in value):
        raise ValueError("Invalid model strings")


def claim_ids(envelope):
    return envelope["claim_ids"]


async def ask(api, model, stage, prompt, data, tokens, images=()):
    budget = await api("ai-call", {"stage": stage, "max_tokens": tokens})
    from langchain_core.messages import HumanMessage, SystemMessage
    content = json.dumps(data, ensure_ascii=False)
    if images:
        content = [{"type": "text", "text": content}] + [{"type": "image_url", "image_url": {"url": image}} for image in images]
    # bind enforces a per-call token ceiling even when the provider default is larger.
    # Disable SDK retries so one budget reservation means one provider request.
    for attribute in ("root_client", "root_async_client"):
        client = getattr(model, attribute, None)
        if client is not None:
            client.max_retries = 0
    bounded = model.bind(max_tokens=tokens, response_format={"type": "json_object"})
    try:
        reply = await asyncio.wait_for(bounded.ainvoke([SystemMessage(content=SAFETY + prompt), HumanMessage(content=content)]), timeout=budget["remaining_seconds"])
    except asyncio.TimeoutError:
        raise TimeoutError("Langflow model deadline exceeded") from None
    except Exception:
        raise RuntimeError("Langflow model service unavailable") from None
    metadata = getattr(reply, "response_metadata", {})
    if not isinstance(metadata, dict) or metadata.get("finish_reason") not in (None, "stop"):
        raise ValueError("Invalid model termination")
    return object_result(reply.content)


async def extract(analysis_id, api, model, visual):
    context = await api("context", {})
    if visual:
        if model is None or not context.get("image_data_url"):
            raise ValueError("Vision model or normalized image unavailable")
        value = await ask(api, model, "observe", VISION, {"caption": context.get("text", "")[:12000]}, 1800, [context["image_data_url"]] if context.get("image_data_url") else [])
        fields(value, ["claims", "ocr_text", "visual_description", "limitations"])
        if not isinstance(value["ocr_text"], str) or len(value["ocr_text"]) > 8000 or not isinstance(value["visual_description"], str) or len(value["visual_description"]) > 2000:
            raise ValueError("Invalid observation schema")
        if value["claims"] and not context.get("text", "").strip() and not value["ocr_text"].lower().replace("[tidak terbaca]", "").strip():
            raise ValueError("Claims require readable factual input")
        strings(value["limitations"], 10, 600)
        observation = {key: value[key] for key in ("ocr_text", "visual_description", "limitations")}
    else:
        value = await ask(api, model, "extract", EXTRACTION, {"untrusted_input": context.get("text", "")[:12000]}, 1200)
        fields(value, ["claims"])
        observation = None
    strings(value["claims"], 3, 600)
    if not visual:
        original = " ".join(context.get("text", "")[:12000].split()).casefold()
        if any(" ".join(claim.split()).casefold() not in original for claim in value["claims"]):
            raise ValueError("Extracted claim is not an input span")
    limits = value.get("limitations", [])
    if len(context.get("text", "")) > 12000:
        limits = limits + ["Input dibatasi pada 12.000 karakter untuk ekstraksi klaim."]
    return await api("register", {"claims": value["claims"], "observation": observation, "limitations": limits})


def queries(value, ids):
    fields(value, ["queries"])
    items = value["queries"]
    if not isinstance(items, list) or len(items) != len(ids):
        raise ValueError("Invalid search plan")
    seen = []
    for item in items:
        fields(item, ["claim_id", "query"])
        if not isinstance(item["query"], str) or not item["query"].strip() or len(item["query"]) > 600:
            raise ValueError("Invalid query")
        if not isinstance(item["claim_id"], str):
            raise ValueError("Invalid claim ID type")
        seen.append(item["claim_id"])
    if len(set(seen)) != len(seen) or set(seen) != set(ids):
        raise ValueError("Invalid plan claim IDs")
    return items


def supplemental(value, ids):
    fields(value, ["claims"])
    items = value["claims"]
    if not isinstance(items, list) or len(items) != len(ids):
        raise ValueError("Invalid adequacy schema")
    seen, result = [], []
    for item in items:
        fields(item, ["claim_id", "sufficient", "gaps", "query"])
        if not isinstance(item["claim_id"], str):
            raise ValueError("Invalid claim ID type")
        seen.append(item["claim_id"])
        if type(item["sufficient"]) is not bool:
            raise ValueError("Invalid sufficiency")
        strings(item["gaps"], 8, 600)
        query = item["query"]
        if query is not None and (not isinstance(query, str) or not query.strip() or len(query) > 600):
            raise ValueError("Invalid supplemental query")
        if item["sufficient"] and (item["gaps"] or query is not None):
            raise ValueError("Inconsistent adequacy")
        if not item["sufficient"] and item["gaps"] and query:
            result.append({"claim_id": item["claim_id"], "query": query})
    if len(set(seen)) != len(seen) or set(seen) != set(ids):
        raise ValueError("Invalid adequacy claim IDs")
    return result


async def review(analysis_id, envelope, api, model, vision_model):
    ids = claim_ids(envelope)
    if not ids:
        image = {"verdict": "INSUFFICIENT_EVIDENCE", "reasoning": "Tidak ada klaim faktual terbaca untuk memeriksa konteks gambar.", "evidence": []} if envelope.get("image_observation") is not None else None
        return {"claims": [], "image_context": image, "indicators": []}
    plan = await ask(api, model, "plan", PLAN, envelope, 900)
    envelope = await api("search", {"round": 0, "queries": queries(plan, ids)})
    assessment = await ask(api, model, "adequacy", ADEQUACY, envelope, 1600)
    extra = supplemental(assessment, ids)
    if extra:
        envelope = await api("search", {"round": 1, "queries": extra})
    if envelope.get("image_observation") is not None:
        if vision_model is None:
            raise ValueError("Vision model unavailable")
        context = await api("context", {})
        candidates = (await api("candidates", {}))["candidates"]
        if len(candidates) > 2:
            raise ValueError("Candidate limit exceeded")
        matches = []
        for candidate in candidates:
            value = await ask(api, vision_model, "match", MATCH, {"description": "First uploaded photograph; second approved publisher photograph"}, 500, [context["image_data_url"], candidate["image_data_url"]])
            fields(value, ["match", "features"])
            if value["match"] not in ("SAME_IMAGE", "DIFFERENT", "UNCERTAIN") or not isinstance(value["features"], str) or not 1 <= len(value["features"].strip()) <= 2000 or (value["match"] == "SAME_IMAGE" and len(value["features"].strip()) < 20):
                raise ValueError("Invalid image match schema")
            matches.append({"source_id": candidate["source_id"], **value})
        envelope = await api("matches", {"matches": matches})
    prompt = comparison_prompt(envelope.get("image_observation") is not None)
    try:
        raw = await ask(api, model, "compare", prompt, envelope, 2500)
    except ValueError:
        raw = None
    checked = await api("validate", {"result": raw})
    if not checked["valid"]:
        raw = await ask(api, model, "compare_repair", prompt + "\nThe previous comparison failed schema/evidence validation. Return a complete corrected result for the SAME claim IDs. Select only source_id and passage_id pairs present in source content. Never write an excerpt or invent IDs. Omit a reference you cannot identify; do not force a verdict.", envelope, 1700)
        checked = await api("validate", {"result": raw})
        if not checked["valid"]:
            raise ValueError("Corrected comparison is still invalid")
    return checked["result"]


async def summarize(api, model):
    context = await api("context", {})
    value = await ask(api, model, "summarize", SUMMARY, {"title": context.get("title", ""), "article_content": context["article_content"]}, 500)
    fields(value, ["summary"])
    if not isinstance(value["summary"], str) or not value["summary"].strip() or len(value["summary"]) > 6000:
        raise ValueError("Invalid summary schema")
    return value
