"""Entry point of the sample shop app (demo input for the mermaid-diagram skill)."""
import api


def main() -> None:
    print(api.handle_order_request({"sku": "BOOK-1", "qty": 2, "email": "buyer@example.invalid"}))


if __name__ == "__main__":
    main()
