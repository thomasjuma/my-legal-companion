from __future__ import annotations

from agents import Agent, Runner
from pydantic import BaseModel, Field

from core.schemas import ChatMessage

INSTRUCTIONS = """
You are an Evaluation Agent that evaluates the quality of a legal advice from a legal adviser agent.
You will be provided with the instructions that were sent to the legal adviser, the full chat history with the user, and the legal advice.
Evaluate how well the legal advice addresses the user's needs and follows the assistant's instructions.
"""


class Evaluation(BaseModel):    
    feedback: str = Field(description="Your feedback on the legal advice and rationale for your score")
    score: float = Field(description="Your score for the legal advice, on a scale of 0 to 100")


evaluator_agent = Agent(
    name="EvaluatorAgent",
    instructions=INSTRUCTIONS,
    model="gpt-4o-mini",
    output_type=Evaluation,
)


def _history_for_evaluator(messages: list[ChatMessage]) -> str:
    parts: list[str] = []
    for message in messages:
        role = message.role.capitalize()
        parts.append(f"{role}:\n{message.content}")
    return "\n\n".join(parts)


async def evaluate_legal_advice(
    *,
    adviser_instructions: str,
    messages: list[ChatMessage],
    legal_advice: str,
) -> Evaluation:
    eval_input = (
        "Evaluate the legal advice and return feedback with a 0-100 score.\n\n"
        "## Legal Adviser Instructions\n"
        f"{adviser_instructions}\n\n"
        "## Full Chat History\n"
        f"{_history_for_evaluator(messages)}\n\n"
        "## Legal Advice To Evaluate\n"
        f"{legal_advice}"
    )
    result = await Runner.run(evaluator_agent, input=eval_input)
    if result.final_output is None:
        raise ValueError("Evaluator did not return an output.")
    return result.final_output