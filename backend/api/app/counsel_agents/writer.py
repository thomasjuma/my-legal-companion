from __future__ import annotations

import os
import importlib
from typing import Any

from agents import Agent, Runner, function_tool
from pydantic import BaseModel, Field

from database import get_crud, session_scope
from database.models import Consultation, ConsultationType

INSTRUCTIONS = """
    You are a senior lawyer tasked with writing a cohesive report for a legal advice.
    You will be provided with the legal advice, and you must write a report for the legal advice.
    The report should be in markdown format, and it should only be one page long.
    Be concise, respectful, and plain-spoken.
    Also, you are provided with a tool to store the report in the consultations database table.
    """

_consultation_crud = get_crud(Consultation)


def _normalize_consultation_type(value: str) -> ConsultationType:
    for consultation_type in ConsultationType:
        if value == consultation_type.value:
            return consultation_type
    return ConsultationType.LEGAL


class LegalReport(BaseModel):
    summary: str = Field(description="A short 2-3 sentence summary of the legal advice.")
    report: str = Field(description="The final report")


async def store_consultation_report(
    clerk_user_id: str,
    consultation_query: str,
    consultation_report: str,
    consultation_summary: str,
    evaluation_score: float | None = None,
    evaluation_feedback: str | None = None,
    consultation_type: str = ConsultationType.LEGAL.value,
) -> dict[str, Any]:
    """Store a generated legal consultation report in the consultations table."""
    normalized_clerk_user_id = clerk_user_id.strip()
    if not normalized_clerk_user_id:
        raise ValueError("clerk_user_id is required to store consultation history.")

    normalized_type = _normalize_consultation_type(consultation_type)
    notes_parts = [f"Summary: {consultation_summary}"]
    if evaluation_score is not None:
        notes_parts.append(f"Evaluator score: {evaluation_score}")
    if evaluation_feedback:
        notes_parts.append(f"Evaluator feedback: {evaluation_feedback}")

    with session_scope() as session:
        row = _consultation_crud.create(
            session,
            data={
                "clerk_user_id": normalized_clerk_user_id,
                "consultation_type": normalized_type,
                "consultation_query": consultation_query,
                "consultation_report": consultation_report,
                "consultation_notes": "\n\n".join(notes_parts),
            },
        )
        consultation_id = int(row.id)

    return {
        "status": "stored",
        "consultation_id": consultation_id,
        "consultation_type": normalized_type.value,
    }


@function_tool
async def store_consultation_report_tool(
    clerk_user_id: str,
    consultation_query: str,
    consultation_report: str,
    consultation_summary: str,
    evaluation_score: float | None = None,
    evaluation_feedback: str | None = None,
    consultation_type: str = ConsultationType.LEGAL.value,
) -> dict[str, Any]:
    """Tool wrapper to store a report in the consultations table."""
    return await store_consultation_report(
        clerk_user_id=clerk_user_id,
        consultation_query=consultation_query,
        consultation_report=consultation_report,
        consultation_summary=consultation_summary,
        evaluation_score=evaluation_score,
        evaluation_feedback=evaluation_feedback,
        consultation_type=consultation_type,
    )


@function_tool
async def send_email(subject: str, html_body: str) -> dict[str, str]:
    """Send an email with the given subject and HTML body."""
    api_key = (os.environ.get("SENDGRID_API_KEY") or "").strip()
    if not api_key:
        return {"status": "skipped", "reason": "SENDGRID_API_KEY is not set"}
    try:
        sendgrid = importlib.import_module("sendgrid")
        mail_helpers = importlib.import_module("sendgrid.helpers.mail")
    except Exception:
        return {"status": "skipped", "reason": "sendgrid package not available"}

    sg = sendgrid.SendGridAPIClient(api_key=api_key)
    from_email = mail_helpers.Email("thomasjuma@protonmail.com")
    to_email = mail_helpers.To("thomasjuma@protonmail.com")
    content = mail_helpers.Content("text/html", html_body)
    mail = mail_helpers.Mail(from_email, to_email, subject, content).get()
    response = sg.client.mail.send.post(request_body=mail)
    return {"status": str(response.status_code)}


report_writer_agent = Agent(
    name="ReportWriterAgent",
    instructions=INSTRUCTIONS,
    model="gpt-4o-mini",
    tools=[store_consultation_report_tool],
    output_type=LegalReport,
)


async def draft_legal_report(*, legal_advice: str) -> LegalReport:
    report_input = (
        "Draft a one-page legal report from this legal advice.\n\n"
        "## Legal Advice\n"
        f"{legal_advice}"
    )
    result = await Runner.run(report_writer_agent, input=report_input)
    if result.final_output is None:
        raise ValueError("Report writer did not return an output.")
    return result.final_output


