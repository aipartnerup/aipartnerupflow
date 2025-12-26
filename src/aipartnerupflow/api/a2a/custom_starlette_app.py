"""
Custom Starlette Application that supports system-level methods and optional JWT authentication
"""
import os
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from a2a.server.apps.jsonrpc.starlette_app import A2AStarletteApplication
from typing import Optional, Callable, Type, List
from a2a.utils.constants import (
    AGENT_CARD_WELL_KNOWN_PATH,
    EXTENDED_AGENT_CARD_PATH,
    PREV_AGENT_CARD_WELL_KNOWN_PATH,
)

from aipartnerupflow.core.storage.sqlalchemy.models import TaskModel
from aipartnerupflow.core.utils.logger import get_logger
from aipartnerupflow.api.routes import TaskRoutes, SystemRoutes, DocsRoutes

logger = get_logger(__name__)


class LLMAPIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware to extract LLM API key from request headers"""
    
    async def dispatch(self, request: Request, call_next):
        """
        Extract LLM API key from X-LLM-API-KEY header and set it in context.
        
        Clears context at the start of each request to prevent using stale keys
        from previous requests (security measure).
        """
        from aipartnerupflow.core.utils.llm_key_context import (
            clear_llm_key_context,
            set_llm_key_from_header
        )
        
        # Clear context at start of each request to prevent using stale keys
        clear_llm_key_context()
        
        # Extract and set LLM key from header if present
        # Format: provider:key (e.g., "openai:sk-xxx...") or just key (backward compatible)
        llm_key_header = request.headers.get("X-LLM-API-KEY") or request.headers.get("x-llm-api-key")
        if llm_key_header:
            # Parse format: provider:key or just key
            provider = None
            api_key = llm_key_header
            
            if ':' in llm_key_header:
                # Format: provider:key
                parts = llm_key_header.split(':', 1)  # Split only on first colon
                if len(parts) == 2:
                    provider = parts[0].strip()
                    api_key = parts[1].strip()
                    if not provider or not api_key:
                        # Invalid format, treat as plain key
                        provider = None
                        api_key = llm_key_header
            
            set_llm_key_from_header(api_key, provider=provider)
            logger.debug(f"Received LLM key from request header (provider: {provider or 'auto'})")
        
        return await call_next(request)


class JWTAuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware to verify JWT tokens for authenticated requests (optional)"""
    
    # Public endpoints that don't require authentication
    PUBLIC_ENDPOINTS = [
        AGENT_CARD_WELL_KNOWN_PATH,
        EXTENDED_AGENT_CARD_PATH,
        PREV_AGENT_CARD_WELL_KNOWN_PATH,
    ]
    
    def __init__(self, app, verify_token_func=None):
        """
        Initialize JWT authentication middleware
        
        Args:
            app: Starlette application
            verify_token_func: Optional function to verify JWT tokens. 
                             If None, JWT verification is disabled.
        """
        super().__init__(app)
        self.verify_token_func = verify_token_func
    
    async def dispatch(self, request: Request, call_next):
        """Verify JWT token from Authorization header or cookie"""

        # Skip authentication for OPTIONS requests (CORS preflight)
        # OPTIONS requests are sent by browsers automatically for CORS preflight
        # They don't include credentials and should always be allowed
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Skip authentication for public endpoints
        if request.url.path in self.PUBLIC_ENDPOINTS:
            return await call_next(request)
        
        # If no verify function provided, skip JWT authentication
        if not self.verify_token_func:
            return await call_next(request)
        
        # Try to get token from Authorization header first (priority)
        authorization = request.headers.get("Authorization")
        token = None
        
        if authorization:
            # Extract token from Bearer <token>
            if authorization.startswith("Bearer "):
                token = authorization[7:]  # Remove "Bearer " prefix
            else:
                token = authorization
        else:
            # Fallback: try to get token from cookie (for cookie-based auth)
            # Support multiple cookie names for flexibility
            token = (
                request.cookies.get("authorization")
                or request.cookies.get("auth_token")
            )
        
        if not token:
            logger.warning(f"Missing Authorization header or cookie for {request.url.path}")
            return JSONResponse(
                status_code=401,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32001,
                        "message": "Unauthorized",
                        "data": "Missing Authorization header or cookie"
                    }
                }
            )
        
        # Verify token
        try:
            payload = self.verify_token_func(token)
            logger.debug(f"JWT payload: {payload}")
            if not payload:
                logger.warning(f"Invalid JWT token for {request.url.path}")
                return JSONResponse(
                    status_code=401,
                    content={
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32001,
                            "message": "Unauthorized",
                            "data": "Invalid or expired JWT token"
                        }
                    }
                )
            
            # Add user info to request state for use in handlers
            request.state.user_id = payload.get("sub")
            request.state.token_payload = payload
            
            logger.debug(f"Authenticated request from user {request.state.user_id} for {request.url.path}")
            
            return await call_next(request)
        except Exception as e:
            logger.error(f"Error verifying JWT token: {e}")
            return JSONResponse(
                status_code=401,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32001,
                        "message": "Unauthorized",
                        "data": "Invalid or expired JWT token"
                    }
                }
            )


class CustomA2AStarletteApplication(A2AStarletteApplication):
    """Custom A2A Starlette Application that supports system-level methods and optional JWT authentication"""
    
    def __init__(
        self, 
        *args, 
        verify_token_func: Optional[Callable[[str], Optional[dict]]] = None,
        verify_permission_func: Optional[Callable[[str, Optional[str], Optional[list]], bool]] = None,
        enable_system_routes: bool = True,
        enable_docs: bool = True,
        task_model_class: Optional[Type[TaskModel]] = None,
        task_routes_class: Optional[Type[TaskRoutes]] = None,
        custom_routes: Optional[List[Route]] = None,
        custom_middleware: Optional[List[Type[BaseHTTPMiddleware]]] = None,
        **kwargs
    ):
        """
        Initialize Custom A2A Starlette Application
        
        As a library: All configuration via function parameters (recommended)
        No automatic environment variable reading to avoid conflicts.
        
        For service deployment: Read environment variables in application layer (main.py)
        and pass them as explicit parameters.
        
        Args:
            *args: Positional arguments for A2AStarletteApplication
            verify_token_func: Function to verify JWT tokens.
                             If None, JWT auth will be disabled.
                             Signature: verify_token_func(token: str) -> Optional[dict]
            verify_permission_func: Function to verify user permissions.
                                  If None, permission checking is disabled.
                                  Signature: verify_permission_func(user_id: str, target_user_id: Optional[str], roles: Optional[list]) -> bool
                                  Returns True if user has permission to access target_user_id's resources.
                                  - If user is admin (roles contains "admin"), can access any user_id
                                  - If user is not admin, can only access their own user_id
                                  - If target_user_id is None, permission is granted (no specific user restriction)
            enable_system_routes: Whether to enable system routes like /system (default: True)
            enable_docs: Whether to enable interactive API documentation at /docs (default: True).
                        Only available when API server is running, not when used as a library.
            task_model_class: Optional custom TaskModel class.
                             Users can pass their custom TaskModel subclass that inherits TaskModel
                             to add custom fields (e.g., project_id, department, etc.).
                             If None, default TaskModel will be used.
            task_routes_class: Optional custom TaskRoutes class to use instead of default TaskRoutes.
                             Allows extending TaskRoutes functionality without monkey patching.
                             If None, default TaskRoutes will be used.
            custom_routes: Optional list of custom Starlette Route objects to add to the application.
                          Routes are merged after default routes (custom routes can override defaults if needed).
                          If None, no custom routes are added.
            custom_middleware: Optional list of custom Starlette BaseHTTPMiddleware classes to add to the application.
                              Middleware will be added in the order provided, after default middleware (CORS, LLM API key, JWT).
                              Each middleware class should be a subclass of BaseHTTPMiddleware.
                              Example: [MyCustomMiddleware, AnotherMiddleware]
            **kwargs: Keyword arguments for A2AStarletteApplication
        """
        super().__init__(*args, **kwargs)
        
        # Use parameter values directly (no environment variable reading)
        self.enable_system_routes = enable_system_routes
        self.enable_docs = enable_docs
        
        # Handle verify_token_func
        self.verify_token_func = verify_token_func
        
        # Handle verify_permission_func
        self.verify_permission_func = verify_permission_func
        
        # Store task_model_class for task management APIs
        self.task_model_class = task_model_class or TaskModel
        
        # Store custom routes
        self.custom_routes = custom_routes or []
        
        # Store custom middleware
        self.custom_middleware = custom_middleware or []
        
        # Use provided task_routes_class or default TaskRoutes
        task_routes_cls = task_routes_class or TaskRoutes
        
        # Initialize protocol-agnostic route handlers
        self.task_routes = task_routes_cls(
            task_model_class=self.task_model_class,
            verify_token_func=self.verify_token_func,
            verify_permission_func=self.verify_permission_func
        )
        self.system_routes = SystemRoutes(
            task_model_class=self.task_model_class,
            verify_token_func=self.verify_token_func,
            verify_permission_func=self.verify_permission_func
        )
        
        # Initialize documentation routes handler
        # Note: We need to do this after super().__init__() so we can access self.agent_card
        # DocsRoutes will handle OpenAPI schema generation internally
        def get_base_url():
            """Get base URL from agent_card or fallback"""
            if hasattr(self, "agent_card") and hasattr(self.agent_card, "url"):
                return self.agent_card.url
            # Fallback: check args/kwargs if agent_card not yet set
            if args and len(args) > 0 and hasattr(args[0], "url"):
                return args[0].url
            elif "agent_card" in kwargs and hasattr(kwargs["agent_card"], "url"):
                return kwargs["agent_card"].url
            return f"http://localhost:{os.getenv('AIPARTNERUPFLOW_PORT', '8000')}"
        
        self.docs_routes = DocsRoutes(
            enable_docs=self.enable_docs,
            agent_card=getattr(self, "agent_card", None),
            get_base_url_func=get_base_url
        )
        
        # Store openapi_schema for backward compatibility and logging
        self.openapi_schema = self.docs_routes.openapi_schema
        
        # Update enable_docs if schema generation failed
        if self.enable_docs and self.openapi_schema is None:
            logger.warning("Documentation was enabled but schema generation failed. Disabling docs.")
            self.enable_docs = False
        
        logger.info(
            f"Initialized CustomA2AStarletteApplication "
            f"(System routes: {self.enable_system_routes}, "
            f"Docs: {self.enable_docs}, "
            f"JWT auth: {self.verify_token_func is not None}, "
            f"Permission check: {self.verify_permission_func is not None}, "
            f"TaskModel: {self.task_model_class.__name__})"
        )
    
        # Initialize _built_app to None (will be set when build() is called)
        self._built_app = None
    
    def __call__(self, scope, receive, send):
        """
        ASGI callable - automatically calls build() if needed
        
        This allows CustomA2AStarletteApplication to be used directly as an ASGI app
        without requiring an explicit build() call.
        
        Args:
            scope: ASGI scope
            receive: ASGI receive callable
            send: ASGI send callable
        """
        if self._built_app is None:
            self._built_app = self.build()
        return self._built_app(scope, receive, send)
    
    def build(self):
        """
        Build the Starlette app with optional JWT authentication middleware and system routes
        
        This method caches the built app, so subsequent calls return the same instance.
        Can be called explicitly, or will be called automatically when used as ASGI app.
        
        Returns:
            Built Starlette application instance
        """
        # Return cached app if already built
        if self._built_app is not None:
            return self._built_app
        
        app = super().build()
        
        # Add CORS middleware (should be added before other middleware)
        # Get allowed origins from environment variable or use defaults
        allowed_origins_str = os.getenv(
            "AIPARTNERUPFLOW_CORS_ORIGINS",
            "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001"
        )
        allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]
        
        # Allow all origins in development if explicitly set
        allow_all_origins = os.getenv("AIPARTNERUPFLOW_CORS_ALLOW_ALL", "false").lower() in ("true", "1", "yes")
        
        if allow_all_origins:
            allowed_origins = ["*"]
            logger.info("CORS: Allowing all origins (development mode)")
        else:
            logger.info(f"CORS: Allowing origins: {allowed_origins}")
        
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Add LLM API key middleware (extracts X-LLM-API-KEY header for all routes including /)
        # This should be added before JWT middleware so it works for all requests
        app.add_middleware(LLMAPIKeyMiddleware)
        logger.info("LLM API key middleware enabled (X-LLM-API-KEY header support)")
        
        if self.verify_token_func:
            # Add JWT authentication middleware
            logger.info("JWT authentication is enabled")
            app.add_middleware(JWTAuthenticationMiddleware, verify_token_func=self.verify_token_func)
        else:
            logger.info("JWT authentication is disabled")
        
        # Add user-provided custom middleware
        if self.custom_middleware:
            for middleware_class in self.custom_middleware:
                app.add_middleware(middleware_class)
                logger.info(f"Added custom middleware: {middleware_class.__name__}")
        
        # Cache the built app
        self._built_app = app
        return self._built_app
    
    def routes(
        self,
        agent_card_url: str = "/.well-known/agent-card",
        rpc_url: str = "/",
        extended_agent_card_url: str = EXTENDED_AGENT_CARD_PATH,
    ) -> list[Route]:
        """Returns the Starlette Routes for handling A2A requests plus optional system methods"""
        # Get the standard A2A routes
        app_routes = super().routes(agent_card_url, rpc_url, extended_agent_card_url)
        
        if not self.enable_system_routes:
            return app_routes
        
        # Build all custom routes in one place
        # All custom routes: task management, system operations, and docs
        # Note: SSE streaming is handled directly by handle_task_execute (use_streaming=True)
        custom_routes = [
            # Task management routes
            Route(
                "/tasks",
                self._handle_task_requests,
                methods=['POST'],
                name='task_handler',
            ),
            # System operations routes
            Route(
                "/system",
                self._handle_system_requests,
                methods=['POST'],
                name='system_handler',
            ),
        ]
        
        # Add documentation routes if enabled
        if self.enable_docs and self.docs_routes.openapi_schema:
            custom_routes.extend([
                Route(
                    "/docs",
                    self.docs_routes.handle_swagger_ui,
                    methods=['GET'],
                    name='swagger_ui',
                ),
                Route(
                    "/openapi.json",
                    self.docs_routes.handle_openapi_json,
                    methods=['GET'],
                    name='openapi_json',
                ),
            ])
        
        # Add user-provided custom routes
        if self.custom_routes:
            custom_routes.extend(self.custom_routes)
        
        # Combine standard routes with custom routes
        return app_routes + custom_routes

    async def _handle_task_requests(self, request: Request) -> JSONResponse:
        """Handle all task management requests through /tasks endpoint"""
        return await self.task_routes.handle_task_requests(request)

    async def _handle_system_requests(self, request: Request) -> JSONResponse:
        """Handle system operations through /system endpoint"""
        return await self.system_routes.handle_system_requests(request)

