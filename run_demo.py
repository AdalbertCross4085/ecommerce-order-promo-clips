import os

from src.promo_service import InfraiClient, OrderClipService, PromoOrder


def main() -> None:
    client = InfraiClient.from_environment()
    bucket = os.environ["INFRAI_BUCKET"]
    recipient = os.environ["INFRAI_TEST_RECIPIENT"]
    order = PromoOrder("demo-100", "Canvas Tote", "$24", recipient)
    receipt = OrderClipService(client, bucket).create_promo_receipt(order)
    print(receipt)


if __name__ == "__main__":
    main()
