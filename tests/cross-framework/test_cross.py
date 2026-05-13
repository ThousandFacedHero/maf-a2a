import os
import sys
import time

import httpx

CREWAI_URL = os.environ["CREWAI_URL"]
MAF_URL = os.environ["MAF_URL"]
MAX_WAIT = 60


def wait_for_service(url: str, label: str):
    deadline = time.time() + MAX_WAIT
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{url}/healthz", timeout=5)
            if resp.status_code == 200:
                print(f"  {label} is ready")
                return
        except httpx.ConnectError:
            pass
        time.sleep(2)
    print(f"  FAIL: {label} not ready after {MAX_WAIT}s")
    sys.exit(1)


def test_agent_cards():
    print("\n=== Test: Agent Cards ===")
    for url, name in [(CREWAI_URL, "CrewAI"), (MAF_URL, "MAF")]:
        resp = httpx.get(f"{url}/.well-known/agent-card.json")
        assert resp.status_code == 200, f"{name} agent card returned {resp.status_code}"
        card = resp.json()
        assert "name" in card, f"{name} agent card missing 'name'"
        print(f"  {name}: {card['name']}")
    print("  PASS")


def test_crewai_to_maf_delegation():
    print("\n=== Test: CrewAI -> MAF delegation ===")
    resp = httpx.post(
        f"{CREWAI_URL}/",
        json={
            "jsonrpc": "2.0",
            "id": "cross-1",
            "method": "SendMessage",
            "params": {
                "message": {
                    "role": "ROLE_USER",
                    "parts": [{"text": "Analyze the impact of transformer architectures on NLP"}],
                    "messageId": "cross-msg-1",
                }
            },
        },
        headers={"A2A-Version": "1.0"},
        timeout=300,
    )
    assert resp.status_code == 200, f"CrewAI returned {resp.status_code}: {resp.text}"
    data = resp.json()
    task = data.get("result", {}).get("task", {})
    assert task["status"]["state"] == "TASK_STATE_COMPLETED", f"Task state: {task['status']['state']}"
    print(f"  Response length: {len(str(task.get('artifacts', [])))}")
    print("  PASS")


def test_maf_to_crewai_delegation():
    print("\n=== Test: MAF -> CrewAI delegation ===")
    resp = httpx.post(
        f"{MAF_URL}/",
        json={
            "jsonrpc": "2.0",
            "id": "cross-2",
            "method": "SendMessage",
            "params": {
                "message": {
                    "role": "ROLE_USER",
                    "parts": [{"text": "Research and enrich: current state of AI safety research"}],
                    "messageId": "cross-msg-2",
                }
            },
        },
        headers={"A2A-Version": "1.0"},
        timeout=300,
    )
    assert resp.status_code == 200, f"MAF returned {resp.status_code}: {resp.text}"
    data = resp.json()
    task = data.get("result", {}).get("task", {})
    assert task["status"]["state"] == "TASK_STATE_COMPLETED", f"Task state: {task['status']['state']}"
    print(f"  Response length: {len(str(task.get('artifacts', [])))}")
    print("  PASS")


if __name__ == "__main__":
    print("Cross-Framework A2A Integration Test")
    print("=" * 40)

    print("\nWaiting for services...")
    wait_for_service(CREWAI_URL, "CrewAI")
    wait_for_service(MAF_URL, "MAF")

    test_agent_cards()
    test_crewai_to_maf_delegation()
    test_maf_to_crewai_delegation()

    print("\n" + "=" * 40)
    print("ALL TESTS PASSED")
