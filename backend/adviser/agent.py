import os
from agents import Agent
from agents.extensions.models.litellm_model import LitellmModel
from instructions import INSTRUCTIONS
from tools import get_legal_references


ANTHROPIC_MODEL_ID = os.getenv("ANTHROPIC_MODEL_ID", "claude-sonnet-4-20250514")
ANTHROPIC_MODEL = f"anthropic/{ANTHROPIC_MODEL_ID}"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")

OPENAI_MODEL = f"openai/{OPENAI_MODEL}"

class AdviserAgent:
    def __init__(self):
        self.adviser_model = LitellmModel(model=OPENAI_MODEL)
        

    def get_adviser_agent(self):
        return Agent(
            name="Adviser",
            instructions=INSTRUCTIONS,
            tools=self.get_adviser_tools(),
            model=self.adviser_model,
        )

    def get_adviser_tools(self):
        return [get_legal_references]   