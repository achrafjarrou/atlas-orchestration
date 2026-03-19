# atlas/a2a/agent_card.py
# Serves the ATLAS Agent Card at GET /.well-known/agent.json
# This is the discovery endpoint — first thing other A2A agents fetch.

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from atlas.a2a.protocol import A2AAgentCard, A2ASkill, AgentCapabilitySpec, AgentProvider
from atlas.core.config import settings

agent_card_router = APIRouter(tags=["A2A Discovery"])


def build_atlas_agent_card() -> A2AAgentCard:
    """Build the ATLAS Agent Card with all skills and capabilities."""
    return A2AAgentCard(
        name=settings.atlas_agent_name,
        description=(
            "ATLAS is a universal multi-agent orchestration platform. "
            "Discovers, routes, and coordinates tasks across heterogeneous AI agents "
            "using A2A Protocol v0.3. Provides cryptographic audit trails compliant "
            "with EU AI Act Article 9. Supports LangGraph, CrewAI, and any A2A agent."
        ),
        url=settings.atlas_base_url,
        version="0.1.0",
        provider=AgentProvider(
            organization="Achraf Jarrou",
            url="https://github.com/achrafjarrou/atlas-orchestration"
        ),
        capabilities=AgentCapabilitySpec(streaming=True, push_notifications=False),
        authentication={
            "schemes": [
                {"scheme": "none"} if not settings.a2a_auth_enabled
                else {"scheme": "bearer", "description": "JWT Bearer token"}
            ]
        },
        default_input_modes=["text", "data"],
        default_output_modes=["text", "data"],
        skills=[
            A2ASkill(
                id="route_task",
                name="Route Task to Best Agent",
                description=(
                    "Analyze a task description and route it to the most capable "
                    "available agent using semantic similarity matching. "
                    "Returns the selected agent response."
                ),
                tags=["orchestration", "routing", "coordination"],
                examples=[
                    "Analyze this legal document for GDPR compliance",
                    "Generate Python code to process this CSV file",
                    "Summarize this research paper",
                ],
            ),
            A2ASkill(
                id="audit_report",
                name="Generate EU AI Act Article 9 Compliance Report",
                description=(
                    "Generate a cryptographically verified EU AI Act Article 9 "
                    "compliance report. Verifies SHA-256 audit chain integrity "
                    "and produces a detailed compliance document for regulators."
                ),
                tags=["compliance", "audit", "eu-ai-act", "reporting"],
                examples=[
                    "Generate EU AI Act Article 9 compliance report",
                    "Verify audit trail integrity for the last 1000 records",
                ],
            ),
            A2ASkill(
                id="register_agent",
                name="Register A2A Agent",
                description=(
                    "Register a new A2A-compliant agent with the ATLAS registry. "
                    "Fetches the agent card, embeds capabilities for semantic routing. "
                    "Agent becomes immediately available for task delegation."
                ),
                tags=["registry", "discovery", "administration"],
                examples=[
                    "Register agent at http://my-agent:8001",
                    "Add THEMIS compliance agent to the ATLAS registry",
                ],
            ),
            A2ASkill(
                id="list_agents",
                name="List Available Agents",
                description=(
                    "List all registered agents with capabilities, health scores, "
                    "and current status. Filter by capability domain or tag."
                ),
                tags=["registry", "discovery"],
                examples=["What agents are available?", "List agents for legal analysis"],
            ),
        ],
    )


@agent_card_router.get(
    "/.well-known/agent.json",
    summary="A2A Agent Card",
    description="ATLAS Agent Card (A2A Protocol v0.3). Auto-discovered by A2A clients.",
    response_class=JSONResponse,
)
async def get_agent_card():
    """Return ATLAS Agent Card. Public endpoint — no auth required."""
    card = build_atlas_agent_card()
    return JSONResponse(
        content=card.model_dump(exclude_none=True),
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=300",
        }
    )