"""MCP tool: vtf_delete_link — delete a Link by id."""
from mcp_server.decorators import handle_errors, serialize_response
from mcp_server.server import mcp


@mcp.tool()
@handle_errors
@serialize_response
def vtf_delete_link(link_id: str) -> dict:
    """Delete a link by id.

    Use this to remove task dependencies (depends_on Links) or any other
    link previously created via vtf_create_link.

    Args:
        link_id: Link id (nanoid) to delete.
    """
    from core.authorization import check_project_membership
    from links.models import Link
    from mcp_server.user_context import get_current_user

    if not link_id:
        return {"error": True, "message": "link_id is required."}

    try:
        link = Link.objects.get(pk=link_id)
    except Link.DoesNotExist:
        return {"error": True, "message": f"Link '{link_id}' not found."}

    user = get_current_user()
    if user is None:
        return {"error": True, "message": "Authentication required."}
    if not user.is_staff and link.project_id and not check_project_membership(user, link.project_id):
        return {
            "error": True,
            "message": f"You are not a member of project '{link.project_id}'.",
        }

    summary = f"{link.source_type}:{link.source_id} --[{link.link_type}]--> {link.target_type}:{link.target_id}"
    link.delete()

    return {
        "data": {"link_id": link_id},
        "message": f"Deleted link {link_id} ({summary}).",
        "available_actions": ["vtf_task_detail"],
    }
