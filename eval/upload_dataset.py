import json
from langfuse import Langfuse

langfuse = Langfuse()

DATASET_NAME = "shoponbot-golden"
GOLDEN_PATH = "/tmp/golden.jsonl"

def upload_to_langfuse():
    langfuse.create_dataset(
        name=DATASET_NAME,
        description="ShopOnBot Golden Evaluation Dataset (Tool Selection + Retrieval)"
    )
    print(f"Dataset '{DATASET_NAME}' ready on Langfuse!")

    with open(GOLDEN_PATH, encoding="utf-8") as f:
        items = [json.loads(line) for line in f if line.strip()]

    for item in items:
        langfuse.create_dataset_item(
            dataset_name=DATASET_NAME,
            input={
                "question": item["question"],
                "retrieval_query": item.get("retrieval_query"),
            },
            expected_output={
                "expected_tools": item["expected_tools"],
                "expected_max_price": item.get("expected_max_price"),
                "relevant_product_ids": item.get("relevant_product_ids", []),
                "forbidden_product_ids": item.get("forbidden_product_ids", []),
                "expect_empty": item.get("expect_empty", False),
            },
            metadata={
                "id": item["id"],
                "category": item["category"]
            }
        )
        print(f"Uploaded Q#{item['id']}: {item['question']}")

    langfuse.flush()
    print(f"\nSuccess! Total {len(items)} items uploaded to Langfuse.")

if __name__ == "__main__":
    upload_to_langfuse()
