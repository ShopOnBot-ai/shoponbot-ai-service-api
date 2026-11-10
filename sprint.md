# 10-Day GenAI Sprint (ShopOnBot.ai)

**Goal:** 10 din baad kuch bhi build karke explain kar sakun aur numbers dikha sakun.
**Rule:** Tutorial nahi, ShopOnBot ko hi production-grade banana hai. Har din ek deliverable, ek concept, ek interview line.

---

## 1. Sprint Plan

| Din | Build (ShopOnBot me) | Concept (seekhna hai) | Interview me bolna |
|---|---|---|---|
| **1** | Streaming (FastAPI SSE + LangGraph `astream_events` + React me token-by-token), time-to-first-token measure | Tokens, context window, temperature, KV cache, quantization | "35s wait se first token ~Xs pe aaya" |
| **2** | Langfuse tracing: har step ka latency, tokens, cost. Provider swap config final | Observability, cost control | "Har request ka trace dekhta hu, bottleneck data se pakda" |
| **3** | Eval set: 30 sawal, tool-selection accuracy aur retrieval hit-rate ka script | Golden dataset, LLM-as-judge, RAG metrics | "Eval se accuracy X% se Y% gayi" |
| **4** | RAG upgrade: chunking, hybrid search (BM25 + dense), reranker, metadata filter. Eval se before/after compare | Hybrid search, reranking, query rewriting | "Dense-only me exact SKU/brand miss hota tha, hybrid se fix" |
| **5** | Agent memory (LangGraph checkpointer, Redis/Postgres), structured output, retries, order place karne se pehle human confirmation | Agent patterns, ReAct, human-in-the-loop, failure handling | "Sensitive action pe confirm, LLM akela order nahi karta" |
| **6** | Security: prompt injection ke 10 tests, user identity token se (LLM ke argument se kabhi nahi), PII filter | Prompt injection, tool authorization, guardrails | "Cart tool me `user_id` LLM nahi deta, server token se leta hai" |
| **7** | Product search aur cart tools ko MCP server bana ke agent se jodna | MCP basics | "Tools ko standard protocol se expose kiya" |
| **8** | Theory sprint: transformer/attention, tokenization, LoRA vs RAG vs prompting, vLLM. 1 page notes | Fine-tuning kab karte hain, kab nahi | "Pehle prompting, phir RAG, phir fine-tune" |
| **9** | AI system design: 5 problems bol ke practice (support chatbot, RAG 10M docs, semantic cache, multi-tenant, cost control) | Tradeoffs bolna | Whiteboard answers |
| **10** | README, architecture diagram, 2 min demo video, resume bullets (numbers ke saath), mock interview | Story banana | 90 second project pitch |

---

## 2. Daily Routine

| Slot | Time | Kaam |
|---|---|---|
| Build | 3 ghante | Us din ka deliverable |
| Concept / notes | 1 ghanta | Us din ka concept padhna, notes likhna |
| Recall | 30 min | Kal ka concept bina dekhe khud ko samjhana |
| DSA | 1 ghanta | Roz ek problem, full stack roles me abhi bhi puchta hai |
| Applications | Din 1-2 se shuru | Padhai ke saath parallel apply karna, ek ke baad ek nahi |

---

## 3. Progress Tracker

| Din | Deliverable ready | Concept samjha | Metric note kiya | Interview line yaad |
|---|---|---|---|---|
| 1 | [ ] | [ ] | [ ] | [ ] |
| 2 | [ ] | [ ] | [ ] | [ ] |
| 3 | [ ] | [ ] | [ ] | [ ] |
| 4 | [ ] | [ ] | [ ] | [ ] |
| 5 | [ ] | [ ] | [ ] | [ ] |
| 6 | [ ] | [ ] | [ ] | [ ] |
| 7 | [ ] | [ ] | [ ] | [ ] |
| 8 | [ ] | [ ] | [ ] | [ ] |
| 9 | [ ] | [ ] | [ ] | [ ] |
| 10 | [ ] | [ ] | [ ] | [ ] |

Day 1: - Metric logs -> Raw model, cold: load 3.0s; warm:~ 28 tok/s; warm TTFT estimate ~0.1sec

Metric	Value
Decode speed (agent ke andar)	27-29 tok/s, stable
Decide call output	31 tokens (tool-call JSON), ~1.2s
Agent prompt size	~380 tokens (system + 2 tool schemas)
Cold-tool (LLM + embedding cold)	8.50s = decide 5.61 + tool ~1.04 + answer 1.60 + ~0.25
Prefill speed	258 tok/s (cold), baaki test pending
---

## 4. Metrics Log (resume bullets yahin se banenge)

| Metric | Pehle (baseline) | Baad me | Kaise measure kiya |
|---|---|---|---|
| Time to first token | | | Din 1, streaming |
| Total response latency | | | Din 1-2, Langfuse trace |
| Tokens / cost per request | | | Din 2, Langfuse |
| Tool-selection accuracy | | | Din 3, eval script |
| Retrieval hit-rate (top-k) | | | Din 3-4, eval script |
| Prompt injection tests passed | | | Din 6, 10 test cases |

---

## 5. Is Sprint Me Nahi Karna

| Skip karo | Kyu |
|---|---|
| Fine-tuning implement karna | Interview me concept kaafi hai (LoRA, kab use karna) |
| Multimodal | Is target role ke liye secondary |
| Cloud certifications | Portfolio aur shipped project zyada kaam aata hai |
| Naye frameworks ki tutorial series | Seekhne jaisa lagta hai, interview me kaam nahi aata |
| Har naya Twitter/LinkedIn tool | Focus tootta hai |

---

## 6. Yaad Rakhne Wali Baatein

| Point | Matlab |
|---|---|
| Depth vs speed | 10 din me tools aur workflow aa sakte hain, depth nahi. Isliye har step me tradeoff aur numbers yaad rakho |
| "Use kiya" vs "measure kiya" | "Maine ye use kiya" se "maine ye measure kiya" wala answer hamesha upar jata hai |
| Har feature ke liye 3 sawal | Kyu kiya? Alternative kya tha? Data ne kya bataya? |
| Production mindset | AI ko ek production system ka component maano, notebook ki tarah nahi |

---

## 7. Final Deliverables (Din 10 tak)

| Item | Status |
|---|---|
| ShopOnBot GitHub repo with clean README | [ ] |
| Architecture diagram | [ ] |
| 2 min demo video | [ ] |
| Resume bullets with numbers | [ ] |
| 90 second project pitch | [ ] |
| 5 AI system design answers | [ ] |
| 1 mock interview complete | [ ] |



<!-- SOME USEFULL COMMANDS TO FAST MODEL prefill time -->

<!-- check system usage -->
sysctl vm.swapusage






------------ # EXPERIMENTS -----------:

# DAY 2:

## Performance Metrics
* **Input Tokens Used:** 1,169 tokens
* **Output Tokens Generated:** 104 tokens  
  * *Response Output:* 93 tokens
  * *Reasoning Process:* 11 tokens
* **Total Tokens Consumed:** 1,273 tokens

---

## Core Problem: Heavy State Traversal
When utilizing `AsyncPostgresSaver` for persistence, the checkpoint manager automatically loads the **entire conversation history** mapped to the specific `user_id`. 
* This complete log is appended directly to the active state framework.
* During the execution flow, the entire history payload is dispatched to the LLM endpoint during every single generation cycle.
* **Impact:** This structural behavior directly spikes API pricing overheads and creates an unwanted footprint bottleneck.

---

## The Solution: Predictive Trim Architecture
To mitigate token bleed, minimize upstream latency, and enforce strict **cost control logic**, we decouple the raw persistent state from the final payload compilation:

1. **Import Utility:** We leverage `trim_messages` directly from the core orchestration module:
   ```python
   from langchain_core.messages import trim_messages
   ```
2. **Context Window Restriction:** Instead of forwarding the complete chat graph, the optimization layer dynamically slices the buffer array.
3. **Execution Bound:** The pipeline is strictly configured to intercept and pass **only the past 12 conversational interactions** to the target LLM node.

---

## 📈 Projected Architectural Gains
* **Latency Reduction:** Slimmer network payload means drastically lower Time-To-First-Token (TTFT) and processing overhead.
* **Cost Optimization:** By hard-bounding input window arrays to a static max history threshold, recurring token expenses remain predictable and flatlined.
