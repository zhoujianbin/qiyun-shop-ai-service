"""结构化规则：YAML 映射、六键校验、冲突检测与解决、过期不参与。"""
import pathlib
import uuid

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.generated import Rule
from tests.conftest import auth, new_key, staff_token

RULES_DIR = pathlib.Path(__file__).resolve().parents[1] / "knowledge_raw" / "13_结构化规则"


def _upload(client, token, names):
    files = [("files", (name, (RULES_DIR / name).read_bytes(), "application/yaml")) for name in names]
    return client.post("/api/v1/knowledge/rules/import", headers=auth(token, new_key()), files=files)


def _rule_payload(rule_id: str, group: str, decision: str) -> dict:
    return {
        "rule_id": rule_id,
        "condition": {"issue_type": "conflict_probe", "identity_level": "public"},
        "action": {"decision": decision},
        "status": "ACTIVE",
        "conflict_group": group,
        "priority": 100,
    }


def test_import_three_yaml_families(client):
    token = staff_token(client)
    response = _upload(client, token, ["policy_rules.yaml", "product_warranty.yaml", "escalation_matrix.yaml"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["by_source_kind"] == {"policy": 9, "warranty": 7, "escalation": 8}
    assert body["total"] == 24

    with SessionLocal() as db:
        rows = db.execute(select(Rule).where(Rule.rule_id == "RETURN-NO-REASON-7D")).scalar_one()
        warranty = db.execute(
            select(Rule).where(Rule.rule_id == "WARRANTY-QR-R5M-BATTERY-12M")
        ).scalar_one()
    assert rows.condition["issue_type"] == "return_no_reason"
    assert rows.condition["time_window"]["max_days"] == 7
    assert rows.action["decision"] == "ALLOW_RETURN"
    assert warranty.condition["product_line"] == "QR-R5M"
    assert warranty.condition["component"] == "battery"
    assert warranty.action["months"] == 12


def test_unmanaged_yaml_form_is_rejected(client):
    token = staff_token(client)
    response = _upload(client, token, ["intent_taxonomy.yaml"])
    assert response.status_code == 400, response.text
    assert response.json()["code"] == "RULE_FORM_NOT_MANAGED"
    assert "不纳管" in response.json()["message"]


def test_condition_accepts_only_six_keys(client):
    token = staff_token(client)
    payload = {
        "rule_id": f"KB-RULE-BAD-{uuid.uuid4().hex[:6]}",
        "condition": {"issue_type": "x", "refund_state": "ACCEPTED"},
        "action": {"decision": "ALLOW_RETURN"},
    }
    response = client.post("/api/v1/knowledge/rules", headers=auth(token, new_key()), json=payload)
    assert response.status_code == 422, response.text
    assert "refund_state" in response.json()["message"]


def test_conflict_detection_and_resolution(client):
    token = staff_token(client)
    group = f"probe_{uuid.uuid4().hex[:8]}"
    first = client.post("/api/v1/knowledge/rules", headers=auth(token, new_key()),
                        json=_rule_payload(f"PROBE-A-{group}", group, "ALLOW_RETURN"))
    second = client.post("/api/v1/knowledge/rules", headers=auth(token, new_key()),
                         json=_rule_payload(f"PROBE-B-{group}", group, "DENY_RETURN"))
    assert first.status_code == 200 and second.status_code == 200, first.text + second.text

    checked = client.post("/api/v1/knowledge/rules/check-conflicts", headers=auth(token, new_key()))
    assert checked.status_code == 200, checked.text
    blocking = [
        row for row in checked.json()
        if row["detail"].get("group") == group and row["severity"] == "BLOCK"
    ]
    assert blocking, checked.json()

    resolved = client.patch(
        f"/api/v1/knowledge/rule-conflicts/{blocking[0]['id']}", headers=auth(token, new_key())
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "RESOLVED"
    assert resolved.json()["resolved_at"] is not None


def test_same_decision_with_different_params_is_warn(client):
    token = staff_token(client)
    group = f"probe_warn_{uuid.uuid4().hex[:8]}"
    client.post("/api/v1/knowledge/rules", headers=auth(token, new_key()),
                json={**_rule_payload(f"PROBE-C-{group}", group, "ALLOW_RETURN"),
                      "action": {"decision": "ALLOW_RETURN", "months": 24}})
    client.post("/api/v1/knowledge/rules", headers=auth(token, new_key()),
                json={**_rule_payload(f"PROBE-D-{group}", group, "ALLOW_RETURN"),
                      "action": {"decision": "ALLOW_RETURN", "months": 12}})
    checked = client.post("/api/v1/knowledge/rules/check-conflicts", headers=auth(token, new_key()))
    warn = [row for row in checked.json()
            if row["detail"].get("group") == group and row["severity"] == "WARN"]
    assert warn
    # 清理：避免提醒级冲突泄漏到后续用例
    for row in warn:
        client.patch(f"/api/v1/knowledge/rule-conflicts/{row['id']}", headers=auth(token, new_key()))


def test_expired_rules_do_not_participate(client):
    token = staff_token(client)
    group = f"probe_expired_{uuid.uuid4().hex[:8]}"
    created = client.post("/api/v1/knowledge/rules", headers=auth(token, new_key()),
                          json=_rule_payload(f"PROBE-E-{group}", group, "ALLOW_RETURN")).json()
    client.post("/api/v1/knowledge/rules", headers=auth(token, new_key()),
                json=_rule_payload(f"PROBE-F-{group}", group, "DENY_RETURN"))
    checked = client.post("/api/v1/knowledge/rules/check-conflicts", headers=auth(token, new_key()))
    assert [row for row in checked.json() if row["detail"].get("group") == group]

    # 把两条都置为过期后，冲突应消失
    with SessionLocal() as db:
        rows = db.execute(select(Rule).where(Rule.conflict_group == group)).scalars().all()
        from datetime import datetime, timedelta, timezone
        for row in rows:
            row.effective_until = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()
    after = client.post("/api/v1/knowledge/rules/check-conflicts", headers=auth(token, new_key()))
    assert not [row for row in after.json() if row["detail"].get("group") == group]
    assert created["rule_id"].startswith("PROBE-E-")
