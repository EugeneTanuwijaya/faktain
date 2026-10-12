"""Generate importable 1.12.1 flows from live native component templates.
Run: python langflow/build_flows.py --url http://127.0.0.1:7860
Only reads component templates/validates custom code; does not import/configure flows.
"""
import argparse
import copy
import json
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]

def build(url):
    client = httpx.Client(base_url=url, timeout=90)
    client.get("/api/v1/auto_login").raise_for_status()
    templates_response = client.get("/api/v1/all")
    templates_response.raise_for_status()
    templates = templates_response.json()
    prompts = (ROOT / "backend/app/services/verification_prompts.py").read_text(encoding="utf-8")
    engine = (ROOT / "langflow/workflow.py").read_text(encoding="utf-8")
    engine = "\n".join(line for line in engine.splitlines() if not line.startswith("from app.services.verification_prompts"))
    component = (ROOT / "langflow/component.py").read_text(encoding="utf-8")
    stages = {}
    names = {"text": "ClaimExtraction", "image": "VisualExtraction", "review": "EvidenceReview", "summary": "ArticleSummary"}
    for stage, name in names.items():
        code = prompts + "\n" + engine + "\nSTAGE = " + repr(stage) + "\n" + component.replace("FaktainComponent", name).replace('display_name = "Faktain Stage"', 'display_name = "' + name + '"')
        response = client.post("/api/v1/custom_component", json={"code": code})
        response.raise_for_status()
        value = response.json()
        if "data" not in value:
            raise RuntimeError("Langflow rejected custom component")
        stages[stage] = value["data"]
    def node(kind, template, index):
        identifier = kind + "-faktain"
        return {"id": identifier, "type": "genericNode", "position": {"x": index * 340, "y": 120}, "data": {"id": identifier, "type": kind, "node": copy.deepcopy(template), "display_name": template.get("display_name", kind), "description": template.get("description", "")}}
    def edge(source, target, name="message", field="input_value", dtype="Message"):
        sh = {"id": source["id"], "name": name, "output_types": [dtype], "dataType": source["data"]["type"]}
        th = {"id": target["id"], "fieldName": field, "inputTypes": [dtype], "type": target["data"]["node"]["template"][field]["type"]}
        # The installed 1.12.1 editor decodes U+0153 as quotes, not question marks.
        source_handle = json.dumps(sh, separators=(",", ":")).replace('"', "\u0153")
        target_handle = json.dumps(th, separators=(",", ":")).replace('"', "\u0153")
        return {"id": f"reactflow__edge-{source['id']}{source_handle}-{target['id']}{target_handle}", "source": source["id"], "target": target["id"], "sourceHandle": source_handle, "targetHandle": target_handle, "data": {"sourceHandle": sh, "targetHandle": th}}
    for mode, filename in [("text", "text-verification.json"), ("image", "image-verification.json"), ("summary", "news-summary.json")]:
        inp = node("ChatInput", templates["input_output"]["ChatInput"], 0)
        first = node(names[mode], stages[mode], 1)
        out = node("ChatOutput", templates["input_output"]["ChatOutput"], 3)
        model = node("LanguageModelComponent", templates["models_and_agents"]["LanguageModelComponent"], 0)
        model["id"] = "LanguageModelComponent-text"; model["data"]["id"] = model["id"]
        model["position"]["y"] = -220
        for native in [inp, out]:
            native["data"]["node"]["template"]["should_store_message"]["value"] = False
        mt = model["data"]["node"]["template"]
        mt["api_key"]["value"] = ""; mt["stream"]["value"] = False
        mt["temperature"]["value"] = 0; mt["max_tokens"]["value"] = 2500
        mt["model"]["value"] = []
        model["data"]["selected_output"] = "model_output"
        nodes = [inp, first, out, model]
        edges = [edge(inp, first), edge(model, first, "model_output", "text_model", "LanguageModel")]
        if mode != "summary":
            rev = node(names["review"], stages["review"], 2)
            nodes.append(rev); edges += [edge(first, rev), edge(rev, out), edge(model, rev, "model_output", "text_model", "LanguageModel")]
            if mode == "image":
                vision = copy.deepcopy(model); vision["id"] = "LanguageModelComponent-vision"; vision["data"]["id"] = vision["id"]; vision["position"]["y"] = 460
                first["data"]["node"]["template"]["vision_model"]["required"] = True
                rev["data"]["node"]["template"]["vision_model"]["required"] = True
                nodes.append(vision)
                edges += [edge(vision, first, "model_output", "vision_model", "LanguageModel"), edge(vision, rev, "model_output", "vision_model", "LanguageModel")]
        else:
            edges.append(edge(first, out))
        flow = {"name": "Faktain " + mode, "description": "Ephemeral bounded Langflow orchestration via authenticated FastAPI evidence callbacks", "is_component": False, "data": {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 0.7}}, "tags": ["Faktain", "1.12.1"]}
        content = json.dumps(flow, ensure_ascii=False, indent=2) + "\n"
        (ROOT / "langflow" / filename).write_text(content, encoding="utf-8")
        if mode == "text": (ROOT / "flow.json").write_text(content, encoding="utf-8")
    client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--url", default="http://127.0.0.1:7860"); args = parser.parse_args(); build(args.url)
