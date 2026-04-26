"""Run against a live backend to inject a demo cascade.

Usage:
    python scripts/demo_seed.py [--host http://localhost:8000]
"""
import argparse
import httpx


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="http://localhost:8000")
    args = p.parse_args()

    g = httpx.get(f"{args.host}/graph").json()
    ports = [n for n in g["nodes"] if n["type"] == "port"]

    target = next((n for n in ports if n["id"] == "port-rotterdam"), ports[0])
    body = {
        "target_type": "node",
        "target_id": target["id"],
        "severity": 0.85,
        "expected_duration_mean_hours": 36,
        "expected_duration_sigma_hours": 8,
        "source": "manual",
    }
    r = httpx.post(f"{args.host}/disruptions", json=body)
    r.raise_for_status()
    print(f"Injected demo disruption at {target['name']}: {r.json()['id']}")


if __name__ == "__main__":
    main()
