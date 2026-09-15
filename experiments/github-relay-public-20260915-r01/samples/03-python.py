from __future__ import annotations

import json


def build_result() -> dict[str, object]:
    return {
        "sample": 3,
        "kind": "python",
        "safe": True,
        "checks": ["syntax", "utf-8", "round-trip"],
    }


if __name__ == "__main__":
    print(json.dumps(build_result(), ensure_ascii=False, indent=2))
