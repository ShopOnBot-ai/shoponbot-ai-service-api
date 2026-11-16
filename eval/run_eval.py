"""
Eval runner: tool-selection accuracy + retrieval hit-rate (threshold sweep ke saath).

Chalane ka tareeka (project root se, ai_service container chal raha ho):

    docker cp eval/golden.jsonl ai_service:/tmp/golden.jsonl
    docker exec -i -w /app ai_service python - baseline < eval/run_eval.py
    mkdir -p eval/results
    docker cp ai_service:/tmp/eval_results_baseline.json eval/results/baseline.json

"baseline" run ka naam hai. Har naye run pe naya naam do (fix1, fix2, ...).

Kya naapta hai:
  A) Tool-selection: LLM ko production wale system prompt aur dono tools ke saath
     chalata hai (tool execute nahi hota) aur dekhta hai ki pehle jawab mein sahi
     tool(s) chune ya nahi. max_price ka argument bhi check hota hai.
  B) Retrieval: products_eval collection pe search_products chalata hai (ideal
     retrieval_query ke saath, taaki LLM ki query-writing ki galti mix na ho) aur
     hit@1/3/5, MRR, forbidden products, aur khaali-result wale cases check karta hai.
     Saath mein threshold sweep.
"""
import asyncio
import importlib
import json
import sys
import time

from langchain_core.messages import HumanMessage, SystemMessage

# ----------------------------------------------------------------------
# YAHAN APNE PROJECT KE HISAAB SE BADAL:
# jis file mein `async def search_products` hai uska module path.
# (grep -rn "async def search_products" app) se mile path ko aise likh:
#   app/services/product_search.py  ->  "app.services.product_search"
SEARCH_MODULE = "app.services.product_search"
# ----------------------------------------------------------------------

search_products = importlib.import_module(SEARCH_MODULE).search_products

# agent_brain import hote hi AsyncPostgresSaver banta hai, jise "running event loop"
# chahiye. Isliye ise top par nahi, async main ke andar (loop chalu hone ke baad)
# import karte hain.
SYSTEM_PROMPT = fetch_user_cart_data = llm_chat_engine = search_products_tool = None


def load_agent_parts() -> None:
    global SYSTEM_PROMPT, fetch_user_cart_data, llm_chat_engine, search_products_tool
    from app.services import agent_brain

    SYSTEM_PROMPT = agent_brain.SYSTEM_PROMPT
    fetch_user_cart_data = agent_brain.fetch_user_cart_data
    llm_chat_engine = agent_brain.llm_chat_engine
    search_products_tool = agent_brain.search_products_tool

GOLDEN_PATH = "/tmp/golden.jsonl"
EVAL_COLLECTION = "products_eval"
PROD_THRESHOLD = 0.35
SWEEP = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]
RUN_NAME = sys.argv[1] if len(sys.argv) > 1 else "run"
OUT_PATH = f"/tmp/eval_results_{RUN_NAME}.json"


def load_golden() -> list[dict]:
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def pct(x) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


# ----------------------------------------------------------------------
# A) Tool selection
# ----------------------------------------------------------------------
async def run_tool_selection(items: list[dict]) -> list[dict]:
    model = llm_chat_engine.bind_tools([fetch_user_cart_data, search_products_tool])
    rows = []
    for item in items:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=item["question"]),
        ]
        t0 = time.perf_counter()
        error = None
        calls = []
        try:
            resp = await asyncio.wait_for(model.ainvoke(messages), timeout=60)
            calls = resp.tool_calls or []
        except Exception as e:  # noqa: BLE001
            error = str(e)
        latency = time.perf_counter() - t0

        got = sorted({c["name"] for c in calls})
        expected = sorted(item["expected_tools"])
        tool_ok = error is None and got == expected

        search_args = next((c["args"] for c in calls if c["name"] == "search_products"), None)
        got_max_price = search_args.get("max_price") if search_args else None
        price_ok = None
        if "search_products" in expected and search_args is not None:
            price_ok = got_max_price == item.get("expected_max_price")

        rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "category": item["category"],
                "expected": expected,
                "got": got,
                "tool_ok": tool_ok,
                "expected_max_price": item.get("expected_max_price"),
                "got_max_price": got_max_price,
                "price_ok": price_ok,
                "llm_query": search_args.get("query") if search_args else None,
                "latency_s": round(latency, 2),
                "error": error,
            }
        )
        await asyncio.sleep(0.5)  # rate limit se bachne ke liye
    return rows


# ----------------------------------------------------------------------
# B) Retrieval
# ----------------------------------------------------------------------
async def run_retrieval(items: list[dict]) -> list[dict]:
    rows = []
    for item in items:
        if "search_products" not in item["expected_tools"] or not item.get("retrieval_query"):
            continue
        results = await search_products(
            query=item["retrieval_query"],
            max_price=item.get("expected_max_price"),
            limit=5,
            collection_name=EVAL_COLLECTION,
            min_score=-1.0,  # threshold nahi, sab top-5 lo; sweep neeche Python mein hota hai
            include_score=True,
        )
        rows.append(
            {
                "id": item["id"],
                "question": item["question"],
                "retrieval_query": item["retrieval_query"],
                "relevant": item["relevant_product_ids"],
                "forbidden": item["forbidden_product_ids"],
                "expect_empty": item["expect_empty"],
                "results": [
                    {"product_id": r["product_id"], "title": r["title"], "score": r["score"]}
                    for r in results
                ],
            }
        )
    return rows


def retrieval_metrics(rows: list[dict], t: float) -> dict:
    n_rel = hit1 = hit3 = hit5 = 0
    mrr = 0.0
    n_empty = empty_ok = 0
    forbidden_bad = 0
    irrelevant = 0

    for r in rows:
        kept = [x for x in r["results"] if x["score"] >= t]
        ids = [x["product_id"] for x in kept]

        if any(i in r["forbidden"] for i in ids):
            forbidden_bad += 1

        if r["expect_empty"]:
            n_empty += 1
            empty_ok += int(not kept)

        if r["relevant"]:
            n_rel += 1
            ranks = [ids.index(p) + 1 for p in r["relevant"] if p in ids]
            first = min(ranks) if ranks else None
            if first is not None:
                mrr += 1 / first
                hit1 += int(first <= 1)
                hit3 += int(first <= 3)
                hit5 += int(first <= 5)
            irrelevant += sum(1 for i in ids if i not in r["relevant"])

    return {
        "threshold": t,
        "n_relevant_queries": n_rel,
        "hit@1": hit1 / n_rel if n_rel else None,
        "hit@3": hit3 / n_rel if n_rel else None,
        "hit@5": hit5 / n_rel if n_rel else None,
        "mrr": mrr / n_rel if n_rel else None,
        "n_empty_queries": n_empty,
        "empty_ok": empty_ok / n_empty if n_empty else None,
        "forbidden_violations": forbidden_bad,
        "avg_irrelevant_returned": irrelevant / n_rel if n_rel else None,
    }


# ----------------------------------------------------------------------
async def main() -> None:
    load_agent_parts()
    items = load_golden()
    model_name = getattr(llm_chat_engine, "model_name", None) or getattr(
        llm_chat_engine, "model", None
    )
    print(f"RUN: {RUN_NAME} | model: {model_name} | questions: {len(items)}")

    ts_rows = await run_tool_selection(items)
    rt_rows = await run_retrieval(items)

    # ---------- A) tool selection summary ----------
    total = len(ts_rows)
    ok = sum(r["tool_ok"] for r in ts_rows)
    print("\n=== A) TOOL SELECTION ===")
    print(f"overall: {ok}/{total} = {pct(ok / total)}")

    by_cat: dict[str, list[bool]] = {}
    for r in ts_rows:
        by_cat.setdefault(r["category"], []).append(r["tool_ok"])
    for cat, vals in by_cat.items():
        print(f"  {cat:8s}: {sum(vals)}/{len(vals)} = {pct(sum(vals) / len(vals))}")

    price_rows = [r for r in ts_rows if r["price_ok"] is not None]
    if price_rows:
        p_ok = sum(r["price_ok"] for r in price_rows)
        print(f"max_price argument correct: {p_ok}/{len(price_rows)} = {pct(p_ok / len(price_rows))}")

    avg_lat = sum(r["latency_s"] for r in ts_rows) / total
    print(f"avg LLM latency (decide step): {avg_lat:.2f}s")

    failures = [r for r in ts_rows if not r["tool_ok"]]
    if failures:
        print("\nTool-selection failures:")
        for r in failures:
            extra = f" ERROR: {r['error']}" if r["error"] else ""
            print(f"  #{r['id']} {r['question']!r}: expected {r['expected']} got {r['got']}{extra}")
    bad_price = [r for r in price_rows if not r["price_ok"]]
    if bad_price:
        print("\nmax_price failures:")
        for r in bad_price:
            print(
                f"  #{r['id']} {r['question']!r}: expected {r['expected_max_price']} "
                f"got {r['got_max_price']} (llm query: {r['llm_query']!r})"
            )

    # ---------- B) retrieval summary ----------
    main_m = retrieval_metrics(rt_rows, PROD_THRESHOLD)
    print(f"\n=== B) RETRIEVAL (collection {EVAL_COLLECTION}, threshold {PROD_THRESHOLD}) ===")
    print(
        f"hit@1 {pct(main_m['hit@1'])} | hit@3 {pct(main_m['hit@3'])} | "
        f"hit@5 {pct(main_m['hit@5'])} | MRR {main_m['mrr']:.2f} "
        f"(on {main_m['n_relevant_queries']} queries)"
    )
    print(
        f"empty-result cases correct: {pct(main_m['empty_ok'])} "
        f"(on {main_m['n_empty_queries']} queries) | forbidden-product violations: "
        f"{main_m['forbidden_violations']}"
    )

    print("\nRetrieval problems at this threshold:")
    any_problem = False
    for r in rt_rows:
        kept = [x for x in r["results"] if x["score"] >= PROD_THRESHOLD]
        ids = [x["product_id"] for x in kept]
        problems = []
        if r["relevant"] and not any(p in ids for p in r["relevant"]):
            problems.append("MISS (no relevant product returned)")
        if any(i in r["forbidden"] for i in ids):
            problems.append("FORBIDDEN product returned")
        if r["expect_empty"] and kept:
            problems.append("expected empty but got results")
        if problems:
            any_problem = True
            top = ", ".join(f"{x['product_id']}:{x['score']}" for x in r["results"][:3])
            print(f"  #{r['id']} {r['retrieval_query']!r}: {'; '.join(problems)} | top scores {top}")
    if not any_problem:
        print("  none")

    print("\nThreshold sweep:")
    print("  thr   hit@5  empty_ok  forbidden  avg_irrelevant")
    sweep_rows = []
    for t in SWEEP:
        m = retrieval_metrics(rt_rows, t)
        sweep_rows.append(m)
        print(
            f"  {t:.2f}  {pct(m['hit@5']):>5}  {pct(m['empty_ok']):>8}  "
            f"{m['forbidden_violations']:>9}  {m['avg_irrelevant_returned']:.2f}"
        )

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "run": RUN_NAME,
                "model": str(model_name),
                "tool_selection": ts_rows,
                "retrieval": rt_rows,
                "retrieval_main": main_m,
                "retrieval_sweep": sweep_rows,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\nsaved: {OUT_PATH}")


asyncio.run(main())