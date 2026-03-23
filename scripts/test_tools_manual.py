"""Manual integration test: verify MCP tools work end-to-end."""

import json

from errordog.server import create_server, get_error_details, list_errors


def main() -> None:
    create_server()  # initializes store with default ~/.errordog/snapshots/

    print("=== list_errors() ===")
    errors = list_errors()
    print(json.dumps(errors, indent=2))

    if errors:
        first_id = errors[0]["error_id"]
        print(f"\n=== get_error_details('{first_id}') ===")
        details = get_error_details(first_id)
        print(json.dumps(details, indent=2))

    print(f"\n=== get_error_details('nonexistent') ===")
    result = get_error_details("nonexistent")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
