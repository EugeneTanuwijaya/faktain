from langflow.custom import Component
from langflow.io import HandleInput, StrInput, SecretStrInput, Output
from langflow.schema import Message
import httpx
import time
import uuid

class FaktainComponent(Component):
    display_name = "Faktain Stage"
    description = "Bounded service-authenticated workflow; no model tools or persistent payloads."
    icon = "ShieldCheck"
    inputs = [
        HandleInput(name="input_value", display_name="Session", input_types=["Message"], required=True),
        # Langflow 1.12.1 skips secret-variable resolution when a wired field is named model.
        HandleInput(name="text_model", display_name="9Router Model", input_types=["LanguageModel"], required=True),
        HandleInput(name="vision_model", display_name="9Router Vision Model", input_types=["LanguageModel"], required=False),
        StrInput(name="backend_url", display_name="Backend URL", value="", required=True),
        SecretStrInput(name="service_key", display_name="Service Key", value="", required=True),
    ]
    outputs = [Output(display_name="Result", name="message", method="run_stage")]

    async def run_stage(self) -> Message:
        try:
            return await self.execute_stage()
        except TimeoutError:
            kind = "timeout"
        except ValueError:
            kind = "invalid_output"
        except RuntimeError:
            kind = "service_unavailable"
        return Message(text=json.dumps({"error": {"kind": kind, "stage": STAGE}}))

    async def execute_stage(self) -> Message:
        payload = object_result(self.input_value.text)
        if STAGE == "review" and set(payload) == {"error"}:
            return Message(text=json.dumps(payload))
        from langflow.services.deps import get_settings_service
        privacy_guard(get_settings_service().settings)
        analysis_id = payload.get("analysis_id")
        try:
            uuid.UUID(analysis_id)
        except (ValueError, TypeError, AttributeError):
            raise ValueError("Invalid analysis session") from None
        key = self.service_key
        if hasattr(key, "get_secret_value"):
            key = key.get_secret_value()
        deadline = None
        async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as client:
            async def api(action, body):
                nonlocal deadline
                remaining = deadline - time.monotonic() if deadline is not None else 10
                if remaining <= 0:
                    raise TimeoutError("Analysis deadline exceeded")
                try:
                    response = await client.post(self.backend_url.rstrip("/") + "/internal/analyses/" + analysis_id + "/" + action,
                        headers={"X-Faktain-Service-Key": key}, json=body, timeout=min(remaining, 90))
                    if response.status_code == 410:
                        raise TimeoutError("Analysis expired")
                    if response.status_code in (409, 422):
                        raise ValueError("Workflow callback rejected")
                    response.raise_for_status()
                    result = response.json()
                except (TimeoutError, ValueError):
                    raise
                except httpx.TimeoutException:
                    raise TimeoutError("Faktain callback timeout") from None
                except Exception:
                    raise RuntimeError("Faktain callback unavailable or rejected") from None
                if "remaining_seconds" in result:
                    bound = time.monotonic() + result["remaining_seconds"]
                    deadline = min(deadline, bound) if deadline is not None else bound
                return result
            if STAGE == "text":
                await extract(analysis_id, api, self.text_model, False)
                result = {"analysis_id": analysis_id}
            elif STAGE == "image":
                await extract(analysis_id, api, self.vision_model, True)
                result = {"analysis_id": analysis_id}
            elif STAGE == "review":
                context = await api("context", {})
                allowed = ("claims", "claim_ids", "sources", "image_observation", "original_input", "matched_source_ids", "limitations", "reference_date", "reference_timezone", "remaining_seconds")
                envelope = {key: context[key] for key in allowed if key in context}
                result = await review(analysis_id, envelope, api, self.text_model, self.vision_model)
            else:
                result = await summarize(api, self.text_model)
        return Message(text=json.dumps(result, ensure_ascii=False))
