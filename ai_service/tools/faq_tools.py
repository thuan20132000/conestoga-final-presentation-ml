"""FAQ tools for business information and services."""

import json

from agents import function_tool
from agents.run_context import RunContextWrapper

from ai_service.tools.context import CallContext
from ai_service.tools.booking_tools import look_up_appointment


@function_tool
async def get_business_information(
    ctx: RunContextWrapper[CallContext],
    info_type: str,
) -> str:
    """Get comprehensive business information including hours, contact details,
    location, and general information.

    Args:
        info_type: Type of information requested. One of: general, contact, location, all.
    """
    data = await ctx.context.booking_service.get_business_information(info_type)
    return json.dumps(data, default=str)


@function_tool
async def get_service_information(
    ctx: RunContextWrapper[CallContext],
) -> str:
    """Get detailed information about all available salon services and packages."""
    data = await ctx.context.booking_service.get_service_information()
    return json.dumps(data, default=str)


@function_tool
async def search_business_knowledge(
    ctx: RunContextWrapper[CallContext],
    query: str,
    top_k: int = 5,
) -> str:
    """Search business knowledge base for general questions and policies.

    Args:
        query: Natural language question from the caller.
        top_k: Maximum number of relevant chunks to return (1-10).
    """
    if top_k < 1:
        top_k = 1
    if top_k > 10:
        top_k = 10
        
    print(f"Searching business knowledge for query: {query}")
    data = await ctx.context.booking_service.search_knowledge(query=query, top_k=top_k)
    print(f"Business knowledge search results: {data}")
    return json.dumps(data, default=str)


FAQ_TOOLS = [
    get_business_information,
    # get_service_information,
    search_business_knowledge,
    look_up_appointment,
]
