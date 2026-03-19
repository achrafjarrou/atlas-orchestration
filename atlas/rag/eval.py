# atlas/rag/eval.py
# RAGAS evaluation — measure RAG pipeline quality
#
# RAGAS METRICS:
#
# faithfulness (0-1):
#   Are the claims in the answer supported by the retrieved context?
#   1.0 = every claim has a source in the context
#   0.0 = answer is hallucinated
#
# answer_relevancy (0-1):
#   Does the answer actually address the question?
#   1.0 = directly answers
#   0.0 = completely off-topic
#
# context_recall (0-1):
#   Did we retrieve all the relevant documents?
#   1.0 = all relevant docs were retrieved
#   0.0 = relevant docs were not retrieved
#
# context_precision (0-1):
#   Are the retrieved documents actually relevant?
#   1.0 = all retrieved docs are relevant
#   0.0 = all retrieved docs are noise

from typing import Any
import structlog

logger = structlog.get_logger(__name__)

TARGET_SCORES = {
    "faithfulness":      0.90,
    "answer_relevancy":  0.85,
    "context_recall":    0.80,
    "context_precision": 0.75,
}


async def evaluate_pipeline(
    pipeline: Any,
    test_questions: list[dict],
) -> dict[str, Any]:
    """
    Evaluate RAG pipeline with RAGAS metrics.

    Args:
        pipeline:       RAGPipeline instance
        test_questions: List of {"question": ..., "ground_truth": ...}

    Returns:
        {"faithfulness": 0.93, "answer_relevancy": 0.87, ...}
    """
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )

        rows = []
        for item in test_questions:
            docs = await pipeline.query(item["question"])
            contexts = [d["text"] for d in docs]
            rows.append({
                "question":     item["question"],
                "answer":       " ".join(contexts[:2]),
                "contexts":     contexts,
                "ground_truth": item["ground_truth"],
            })

        dataset = Dataset.from_list(rows)
        result  = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
        )

        scores = dict(result)
        passed = all(
            scores.get(m, 0) >= TARGET_SCORES.get(m, 0)
            for m in TARGET_SCORES
        )

        logger.info(
            "ragas_evaluation_complete",
            scores=scores,
            passed=passed,
        )

        return {
            "scores":  scores,
            "targets": TARGET_SCORES,
            "passed":  passed,
        }

    except ImportError as e:
        logger.warning("ragas_not_installed", error=str(e))
        return {"error": "ragas not installed", "scores": {}}