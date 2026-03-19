# atlas/rag/dspy_optimizer.py
# DSPy automated prompt optimization
#
# WHY DSPy?
#   Instead of manually crafting prompts like:
#     "You are an expert. Analyze the following..."
#   DSPy tests hundreds of prompt variations on your training data
#   and finds the one that maximizes your metric (e.g. RAGAS faithfulness).
#   Result: +15% accuracy vs manually written prompts, zero guesswork.
#
# HOW IT WORKS:
#   1. Define a Signature (input fields → output fields)
#   2. Define a Program (chain of modules)
#   3. Provide training examples (question, expected_answer pairs)
#   4. DSPy's optimizer (MIPROv2) searches the prompt space
#   5. Save the best prompt for production use
#
# TRAINING DATA FORMAT:
#   [{"question": "What is A2A?", "answer": "Agent-to-Agent protocol..."}]

from typing import Any
import structlog

logger = structlog.get_logger(__name__)


def build_rag_program():
    """
    Build a DSPy RAG program with Chain-of-Thought reasoning.

    The program:
    1. Takes a question + context (retrieved docs)
    2. Reasons step by step (ChainOfThought)
    3. Produces a grounded answer

    Returns the program (unoptimized — call optimize() to optimize it).
    """
    try:
        import dspy

        class RAGSignature(dspy.Signature):
            """Answer questions using only the provided context."""
            question = dspy.InputField(desc="The user's question")
            context  = dspy.InputField(desc="Retrieved document chunks")
            answer   = dspy.OutputField(desc="Factual answer grounded in context")

        class RAGProgram(dspy.Module):
            def __init__(self):
                super().__init__()
                # ChainOfThought: generates reasoning steps before the final answer
                # More accurate than direct prediction for complex questions
                self.generate = dspy.ChainOfThought(RAGSignature)

            def forward(self, question: str, context: str) -> dspy.Prediction:
                return self.generate(question=question, context=context)

        return RAGProgram()
    except ImportError:
        logger.warning("dspy_not_installed")
        return None


async def optimize_rag_program(
    program: Any,
    training_data: list[dict],
    llm_model: str = "llama-3.1-8b-instant",
    groq_api_key: str = "",
    num_trials: int = 10,
) -> Any:
    """
    Run DSPy MIPROv2 optimizer on the RAG program.

    Args:
        program:       The DSPy RAGProgram to optimize
        training_data: List of {"question": ..., "answer": ...} dicts
        llm_model:     LLM to use (Groq is free)
        num_trials:    Number of prompt variations to test (more = better but slower)

    Returns:
        Optimized program with the best prompts found

    Example training_data:
        [
            {"question": "What is A2A Protocol?",
             "answer": "Agent-to-Agent Protocol is a Linux Foundation standard..."},
            {"question": "What does SHA-256 do?",
             "answer": "SHA-256 is a cryptographic hash function that..."},
        ]
    """
    if program is None:
        logger.warning("dspy_program_is_none_skipping_optimization")
        return None

    try:
        import dspy
        from dspy.evaluate import Evaluate
        from dspy.teleprompt import MIPROv2

        # Configure DSPy to use Groq (free)
        lm = dspy.LM(
            model=f"groq/{llm_model}",
            api_key=groq_api_key,
        )
        dspy.configure(lm=lm)

        # Convert training data to DSPy examples
        examples = [
            dspy.Example(
                question=d["question"],
                context="",    # context will be filled by the pipeline
                answer=d["answer"],
            ).with_inputs("question", "context")
            for d in training_data
        ]

        # Define evaluation metric
        # We use simple substring matching for demo
        # In production: use RAGAS faithfulness score
        def metric(example, prediction, trace=None):
            pred_answer = prediction.answer.lower()
            gold_answer = example.answer.lower()
            # Check if key words from the expected answer appear
            key_words = gold_answer.split()[:5]   # first 5 words
            matches = sum(1 for w in key_words if w in pred_answer)
            return matches / max(len(key_words), 1)

        # Run MIPROv2 optimizer
        optimizer = MIPROv2(
            metric=metric,
            num_candidates=num_trials,
            init_temperature=1.0,
        )

        logger.info("dspy_optimization_starting", trials=num_trials)

        optimized = optimizer.compile(
            program,
            trainset=examples,
            num_trials=num_trials,
            minibatch_size=min(5, len(examples)),
        )

        logger.info("dspy_optimization_complete")
        return optimized

    except Exception as e:
        logger.error("dspy_optimization_failed", error=str(e))
        return program   # return unoptimized as fallback