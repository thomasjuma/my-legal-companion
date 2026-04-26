import os
import logging

from agents import Agent, Runner
from pydantic import BaseModel, Field
from agents.extensions.models.litellm_model import LitellmModel

from instructions import INSTRUCTIONS, TASK

logger = logging.getLogger()


class Evaluation(BaseModel):
    feedback: str = Field(
        description="Your feedback on the legal advice and rationale for your score"
    )
    score: float = Field(
        description="Score from 0 to 100 where 0 represents a terrible quality legal advice and 100 represents an outstanding legal advice"
    )


async def evaluate(original_instructions, original_query, original_advice) -> Evaluation:
    # Get model configuration
    model_id = os.getenv("OPENAI_MODEL", "gpt-4.1")
    model = LitellmModel(model=f"openai/{model_id}")

    task = f"""
    The legal adviser agent was given the following instructions:

    {original_instructions}

    And it was given this query:

    {original_query}

    The legal adviser agent's legal advice was:

    {original_advice}

    Evaluate this output and respond with your comments and score.
    """

    try:
        logger.info("Evaluating legal advice")
        agent = Agent(
            name="Evaluator Agent", instructions=INSTRUCTIONS, model=model, output_type=Evaluation
        )
        result = await Runner.run(agent, input=task, max_turns=5)
        return result.final_output_as(Evaluation)
    except Exception as e:
        logger.error(f"Error evaluating legal advice: {e}")
        return Evaluation(feedback=f"Error evaluating legal advice: {e}", score=80)
