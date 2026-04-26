"""
Legal Adviser Orchestrator Lambda Handler
"""

import json
import asyncio
import logging

from agents import Runner, trace
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from litellm.exceptions import RateLimitError

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from agent import AdviserAgent

logger = logging.getLogger()


@retry(
    retry=retry_if_exception_type(RateLimitError),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    before_sleep=lambda retry_state: logger.info(f"Adviser: Rate limit hit, retrying in {retry_state.next_action.sleep} seconds...")
)
async def run_orchestrator(query: str) -> None:
    """Run the orchestrator agent to coordinate legal advice."""
    try:
        # Run the orchestrator
        with trace("Adviser Orchestrator"):
            adviser_agent = AdviserAgent().get_adviser_agent()

            result = await Runner.run(
                adviser_agent,
                input=query,
                max_turns=20
            )
            logger.info(f"Adviser: Result: {result}")
            return result
    except Exception as e:
        logger.error(f"Adviser: Error in orchestration: {e}", exc_info=True)
        return None

def lambda_handler(event):
    """
    Lambda handler """
    try:
        logger.info(f"Adviser Lambda invoked with event: {json.dumps(event)[:500]}")
        query = event['query']
        result = asyncio.run(run_orchestrator(query))
        return {
            'statusCode': 200,
            'body': json.dumps({'result': result})
        }
    except Exception as e:
        logger.error(f"Adviser: Error in lambda handler: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


# For local testing
if __name__ == "__main__":
    # Define a test user
    test_user_id = "test_user_adviser_local"

    event = {
        'user_id': test_user_id,
        'query': "I am facing a legal issue regarding my business. I need to know my rights and obligations as a business owner.",
    }
    
    result = lambda_handler(event)
    print(json.dumps(result, indent=2))