"""Validate exported graphs, privacy defaults and reproducible shared sources."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_three_flows_use_model_handles_and_ephemeral_messages():
    for filename, extraction in [("text-verification.json", "ClaimExtraction"), ("image-verification.json", "VisualExtraction"), ("news-summary.json", "ArticleSummary")]:
        flow = json.loads((ROOT / "langflow" / filename).read_text(encoding="utf-8"))
        nodes = {n["id"]: n for n in flow["data"]["nodes"]}
        types = {n["data"]["type"] for n in nodes.values()}
        assert {"ChatInput", "ChatOutput", "LanguageModelComponent", extraction} <= types
        assert ("EvidenceReview" in types) == (extraction != "ArticleSummary")
        for node in nodes.values():
            template = node["data"]["node"]["template"]
            compile(template["code"]["value"], node["id"], "exec")
            if node["data"]["type"] in {"ChatInput", "ChatOutput"}:
                assert template["should_store_message"]["value"] is False
            elif node["data"]["type"] == "LanguageModelComponent":
                assert template["api_key"]["value"] == ""
                assert template["stream"]["value"] is False
                assert node["data"]["selected_output"] == "model_output"
                assert any(o["name"] == "model_output" and "LanguageModel" in o["types"] for o in node["data"]["node"]["outputs"])
            else:
                assert template["backend_url"]["value"] == ""
                assert template["service_key"]["value"] == ""
        for edge in flow["data"]["edges"]:
            source = json.loads(edge["sourceHandle"].replace("\u0153", '"'))
            target = json.loads(edge["targetHandle"].replace("\u0153", '"'))
            assert source == edge["data"]["sourceHandle"]
            assert target == edge["data"]["targetHandle"]
            assert source["id"] == edge["source"] and target["id"] == edge["target"]
            outputs = nodes[edge["source"]]["data"]["node"]["outputs"]
            assert source["dataType"] == nodes[edge["source"]]["data"]["type"]
            assert any(o["name"] == source["name"] and source["output_types"][0] in o["types"] for o in outputs)
            target_field = nodes[edge["target"]]["data"]["node"]["template"][target["fieldName"]]
            assert source["output_types"][0] in target_field["input_types"]
            assert target["type"] == target_field["type"]

def test_shared_review_is_identical():
    reviews = []
    for name in ["text-verification.json", "image-verification.json"]:
        flow = json.loads((ROOT / "langflow" / name).read_text(encoding="utf-8"))
        reviews.append(next(n["data"]["node"]["template"]["code"]["value"] for n in flow["data"]["nodes"] if n["data"]["type"] == "EvidenceReview"))
    assert reviews[0] == reviews[1]

def test_custom_model_handle_does_not_trigger_secret_resolution_skip():
    for filename in ["text-verification.json", "image-verification.json", "news-summary.json"]:
        flow = json.loads((ROOT / "langflow" / filename).read_text(encoding="utf-8"))
        custom = {node["id"] for node in flow["data"]["nodes"] if node["data"]["type"] not in {"ChatInput", "ChatOutput", "LanguageModelComponent"}}
        for edge in flow["data"]["edges"]:
            if edge["target"] in custom:
                assert edge["data"]["targetHandle"]["fieldName"] != "model"
        for node in flow["data"]["nodes"]:
            if node["id"] in custom:
                assert "text_model" in node["data"]["node"]["template"]
                assert "model" not in node["data"]["node"]["template"]
