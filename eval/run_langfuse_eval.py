"""
Langfuse Experiment runner (tera apna script, 4 sudhaar ke saath).

Chalane ka tareeka (project root se, ai_service container chal raha ho):

    docker exec -i -w /app ai_service python - baseline-v2 < eval/run_experiment.py

Threshold ko ALAG experiment ki tarah test karna ho (code badle bina):

    docker exec -i -e EVAL_MIN_SCORE=0.45 -w /app ai_service python - thr-045 < eval/run_experiment.py

Kya badla (tere script ke muqable):
  1. retrieval_query ab input aur expected_output, dono jagah dhundhi jaati hai (jahan bhi upload mein rakhi ho)
  2. min_score ab default mein production wala (0.35) hi use hota hai, 0.45 jaisa naya
     threshold sirf EVAL_MIN_SCORE dene par lagta hai, aur wo alag run ban jaata hai
  3. Score sirf wahan diye jaate hain jahan wo lagu hota hai (warna average jhootha ban jaata hai)
  4. Do naye scores: forbidden_ok aur empty_ok
"""
import asyncio
import importlib
import os
import sys

from langchain_core.messages import HumanMessage, SystemMessage
from langfuse import Evaluation, Langfuse

DATASET_NAME = "shoponbot-golden"  # Langfuse mein jo dataset ka naam hai wahi likhna
RUN_NAME = sys.argv[1] if len(sys.argv) > 1 else "baseline-v2"
EVAL_COLLECTION = "products_eval"

# Jab tak EVAL_MIN_SCORE na diya ho, search_products apna production default (MIN_SCORE) use karega.
_override = os.getenv("EVAL_MIN_SCORE")
MIN_SCORE_OVERRIDE = float(_override) if _override else None

langfuse = Langfuse()
search_products = importlib.import_module("app.services.product_search").search_products


# ----------------------------------------------------------------------
# 1. TASK: ek dataset item ke liye agent ko chalana
# ----------------------------------------------------------------------
async def run_agent_task(*, item, **kwargs):
    # agent_brain import ko event loop chalu hone ke baad hi karna hai (AsyncPostgresSaver ki wajah se)
    from app.services import agent_brain

    question = item.input["question"]
    expected = item.expected_output
    expected_tools = expected["expected_tools"]
    expected_max_price = expected.get("expected_max_price")
    # retrieval_query tere dataset mein item.input ke andar hai (purane upload mein expected_output
    # mein thi), isliye pehle input mein dhundhte hain, phir expected_output mein
    retrieval_query = item.input.get("retrieval_query") or expected.get("retrieval_query")

    # A) LLM ne kaun sa tool aur kaun se arguments chune
    model = agent_brain.llm_chat_engine.bind_tools(
        [agent_brain.fetch_user_cart_data, agent_brain.search_products_tool]
    )
    resp = await model.ainvoke(
        [
            SystemMessage(content=agent_brain.SYSTEM_PROMPT),
            HumanMessage(content=question),
        ]
    )
    calls = resp.tool_calls or []
    got_tools = sorted({c["name"] for c in calls})
    search_args = next((c["args"] for c in calls if c["name"] == "search_products"), None)

    # B) Search ne kya lautaya (ideal retrieval_query ke saath, taaki LLM ki query-galti mix na ho)
    retrieved = []
    if "search_products" in expected_tools and retrieval_query:
        search_kwargs = dict(
            query=retrieval_query,
            max_price=expected_max_price,
            limit=5,
            collection_name=EVAL_COLLECTION,
            include_score=True,
        )
        if MIN_SCORE_OVERRIDE is not None:
            search_kwargs["min_score"] = MIN_SCORE_OVERRIDE
        results = await search_products(**search_kwargs)
        retrieved = [{"id": r["product_id"], "score": r["score"]} for r in results]

    await asyncio.sleep(0.5)  # rate limit se bachne ke liye
    return {
        "got_tools": got_tools,
        "search_called": search_args is not None,
        "got_max_price": search_args.get("max_price") if search_args else None,
        "llm_query": search_args.get("query") if search_args else None,
        "retrieved": retrieved,
    }


# ----------------------------------------------------------------------
# 2. EVALUATOR: output ko answer key se milana
#    Score sirf tab jab wo us sawaal pe lagu ho.
# ----------------------------------------------------------------------
def grade_response(*, output, expected_output, **kwargs):
    expected_tools = sorted(expected_output["expected_tools"])
    expects_search = "search_products" in expected_tools
    retrieved_ids = [r["id"] for r in output["retrieved"]]

    # Har sawaal pe lagu: sahi tool(s) chune ya nahi
    scores = [
        Evaluation(
            name="tool_accuracy",
            value=1.0 if output["got_tools"] == expected_tools else 0.0,
        )
    ]

    # max_price sirf tab jab search expected thi aur LLM ne search bulaya
    if expects_search and output["search_called"]:
        scores.append(
            Evaluation(
                name="price_accuracy",
                value=1.0
                if output["got_max_price"] == expected_output.get("expected_max_price")
                else 0.0,
            )
        )

    # Retrieval hit@5: sirf unn sawaalon pe jinka sahi product pata hai
    relevant = expected_output.get("relevant_product_ids", [])
    if relevant:
        scores.append(
            Evaluation(
                name="retrieval_hit",
                value=1.0 if any(p in retrieved_ids for p in relevant) else 0.0,
            )
        )

    # Khaali aana chahiye wale sawaal (catalog mein hai hi nahi)
    if expected_output.get("expect_empty"):
        scores.append(
            Evaluation(name="empty_ok", value=1.0 if not retrieved_ids else 0.0)
        )

    # Jo products nahi aane chahiye (mehnge ya out-of-stock) wo to nahi aaye
    forbidden = expected_output.get("forbidden_product_ids", [])
    if forbidden:
        scores.append(
            Evaluation(
                name="forbidden_ok",
                value=0.0 if any(p in retrieved_ids for p in forbidden) else 1.0,
            )
        )

    return scores


# ----------------------------------------------------------------------
# 3. RUN
# ----------------------------------------------------------------------
async def main():
    dataset = langfuse.get_dataset(DATASET_NAME)
    note = (
        f"min_score={MIN_SCORE_OVERRIDE}"
        if MIN_SCORE_OVERRIDE is not None
        else "min_score=production default"
    )
    print(f"Experiment '{RUN_NAME}' on {len(dataset.items)} items ({note})")

    result = dataset.run_experiment(
        name=RUN_NAME,
        description=note,
        task=run_agent_task,
        evaluators=[grade_response],
        max_concurrency=3,
    )
    print(result.format())
    langfuse.flush()


if __name__ == "__main__":
    asyncio.run(main())