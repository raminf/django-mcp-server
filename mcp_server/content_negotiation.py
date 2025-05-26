import logging
from rest_framework.content_negotiation import DefaultContentNegotiation
from rest_framework.renderers import JSONRenderer

logger = logging.getLogger(__name__)


class MCPContentNegotiation(DefaultContentNegotiation):
    """
    Custom content negotiation for MCP endpoints that handles mixed Accept headers
    and always falls back to JSON rendering.
    """
    
    def select_renderer(self, request, renderers, format_suffix=None):
        """
        Override to handle MCP-specific Accept headers and always return JSON renderer.
        """
        # Log the Accept header for debugging
        accept_header = request.headers.get('Accept', 'Not provided')
        logger.debug(f"MCP Content Negotiation - Accept header: {accept_header}")
        
        # Always use JSON renderer for MCP endpoints
        json_renderer = None
        for renderer in renderers:
            if isinstance(renderer, JSONRenderer):
                json_renderer = renderer
                break
        
        if json_renderer is None:
            # Fallback to first available renderer
            json_renderer = renderers[0] if renderers else JSONRenderer()
            logger.debug(f"MCP Content Negotiation - Using fallback renderer: {type(json_renderer).__name__}")
        else:
            logger.debug(f"MCP Content Negotiation - Using JSON renderer")
        
        # Return the JSON renderer with application/json media type
        return json_renderer, 'application/json' 