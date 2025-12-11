"""
System operations route handlers - protocol-agnostic

This module provides system operation handlers that can be used by any protocol
(A2A, REST, GraphQL, etc.) to handle system-level operations like health checks,
LLM key configuration, and examples management.
"""

import time
import uuid
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.responses import JSONResponse

from aipartnerupflow.api.routes.base import BaseRouteHandler
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class SystemRoutes(BaseRouteHandler):
    """
    System operations route handlers

    Provides protocol-agnostic handlers for system operations like health checks,
    LLM key configuration, and examples management that can be used by any
    protocol implementation.
    """

    async def handle_system_requests(self, request: Request) -> JSONResponse:
        """Handle system operations through /system endpoint"""
        start_time = time.time()
        request_id = str(uuid.uuid4())

        try:
            # Parse JSON request
            body = await request.json()
            method = body.get("method")
            params = body.get("params", {})

            logger.info(
                f"🔍 [handle_system_requests] [{request_id}] Method: {method}, Params: {params}"
            )

            # Route to specific handler based on method
            if method == "system.health":
                result = await self.handle_health(params, request_id)
            elif method == "config.llm_key.set":
                result = await self.handle_llm_key_set(params, request, request_id)
            elif method == "config.llm_key.get":
                result = await self.handle_llm_key_get(params, request, request_id)
            elif method == "config.llm_key.delete":
                result = await self.handle_llm_key_delete(params, request, request_id)
            elif method == "examples.init":
                result = await self.handle_examples_init(params, request, request_id)
            elif method == "examples.status":
                result = await self.handle_examples_status(params, request, request_id)
            else:
                return JSONResponse(
                    status_code=400,
                    content={
                        "jsonrpc": "2.0",
                        "id": body.get("id"),
                        "error": {
                            "code": -32601,
                            "message": "Method not found",
                            "data": f"Unknown system method: {method}",
                        },
                    },
                )

            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"🔍 [handle_system_requests] [{request_id}] Completed in {duration:.3f}s")

            return JSONResponse(content={"jsonrpc": "2.0", "id": body.get("id"), "result": result})

        except Exception as e:
            logger.error(f"Error handling system request: {str(e)}", exc_info=True)
            # Get request ID safely (body might not be defined if JSON parsing failed)
            request_id_from_body = None
            try:
                if "body" in locals() and body is not None:
                    request_id_from_body = body.get("id")
            except Exception as inner_e:
                logger.debug(f"Failed to extract request ID from body: {str(inner_e)}")
                pass

            return JSONResponse(
                status_code=500,
                content={
                    "jsonrpc": "2.0",
                    "id": request_id_from_body,
                    "error": {"code": -32603, "message": "Internal error", "data": str(e)},
                },
            )

    async def handle_health(self, params: dict, request_id: str) -> dict:
        """Handle health check"""
        return {
            "status": "healthy",
            "message": "aipartnerupflow is healthy",
            "version": "0.2.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "running_tasks_count": 0,  # TODO: Implement actual task count
        }

    async def handle_llm_key_set(self, params: dict, request: Request, request_id: str) -> dict:
        """
        Handle LLM key configuration - set LLM API key for user

        Params:
            api_key: LLM API key to store
            user_id: Optional user ID (defaults to authenticated user)
            provider: Optional provider name (e.g., "openai", "anthropic", "google")

        Returns:
            {"success": True, "user_id": str, "provider": str}
        """
        try:
            # Check if llm-key-config extension is available
            try:
                from aipartnerupflow.extensions.llm_key_config import LLMKeyConfigManager
            except ImportError:
                raise ValueError(
                    "LLM key configuration extension not available. "
                    "Install with: pip install aipartnerupflow[llm-key-config]"
                )

            api_key = params.get("api_key")
            if not api_key:
                raise ValueError("api_key is required")

            provider = params.get("provider")  # Optional provider name

            # Get user_id from params or authenticated user
            user_id = params.get("user_id")
            if not user_id:
                authenticated_user_id, _ = self._get_user_info(request)
                if not authenticated_user_id:
                    raise ValueError("user_id is required (not authenticated)")
                user_id = authenticated_user_id

            # Check permission
            self._check_permission(request, user_id, "set LLM key for")

            # Set key
            config_manager = LLMKeyConfigManager()
            config_manager.set_key(user_id, api_key, provider=provider)

            provider_str = provider or "default"
            logger.info(f"Set LLM key for user {user_id}, provider {provider_str}")
            return {"success": True, "user_id": user_id, "provider": provider_str}

        except Exception as e:
            logger.error(f"Error setting LLM key: {str(e)}", exc_info=True)
            raise

    async def handle_llm_key_get(self, params: dict, request: Request, request_id: str) -> dict:
        """
        Handle LLM key configuration - get LLM API key status for user

        Params:
            user_id: Optional user ID (defaults to authenticated user or "default")
            provider: Optional provider name to check

        Returns:
            {"has_key": bool, "user_id": str, "providers": dict}
        """
        # Default response for graceful degradation
        default_user_id = params.get("user_id") or "default"
        default_response = {
            "has_key": False,
            "user_id": default_user_id,
            "provider": params.get("provider"),
            "providers": {},
        }

        try:
            # Check if llm-key-config extension is available
            try:
                from aipartnerupflow.extensions.llm_key_config import LLMKeyConfigManager
            except ImportError:
                # Extension not available, return empty status (graceful degradation)
                logger.debug(
                    "LLM key configuration extension not available, returning empty status"
                )
                return default_response

            provider = params.get("provider")

            # Get user_id from params, authenticated user, or default to "default"
            user_id = params.get("user_id")
            if not user_id:
                try:
                    authenticated_user_id, _ = self._get_user_info(request)
                    user_id = (
                        authenticated_user_id or "default"
                    )  # Default user for single-user scenarios
                except Exception as e:
                    logger.debug(f"Error getting user info: {e}, using default user_id")
                    user_id = "default"

            # Check permission (only if JWT is enabled) - catch all exceptions
            try:
                self._check_permission(request, user_id, "get LLM key for")
            except Exception as e:
                # Permission check failed, but in non-JWT mode we allow it
                # Just log and continue
                logger.debug(f"Permission check skipped for user {user_id}: {e}")

            # Check if key exists (don't return the actual key for security)
            try:
                config_manager = LLMKeyConfigManager()
                has_key = config_manager.has_key(user_id, provider=provider)
                all_providers = config_manager.get_all_providers(user_id)

                return {
                    "has_key": has_key,
                    "user_id": user_id,
                    "provider": provider,
                    "providers": all_providers,
                }
            except Exception as e:
                logger.warning(
                    f"Error accessing LLM key config manager: {e}, returning empty status"
                )
                return default_response

        except Exception as e:
            # Catch all exceptions and return graceful response
            logger.error(f"Error getting LLM key status: {str(e)}", exc_info=True)
            # Return empty status instead of raising exception
            return default_response

    async def handle_llm_key_delete(self, params: dict, request: Request, request_id: str) -> dict:
        """
        Handle LLM key configuration - delete LLM API key for user

        Params:
            user_id: Optional user ID (defaults to authenticated user)
            provider: Optional provider name (if None, deletes all keys for user)

        Returns:
            {"success": True, "user_id": str, "deleted": bool, "provider": str}
        """
        try:
            # Check if llm-key-config extension is available
            try:
                from aipartnerupflow.extensions.llm_key_config import LLMKeyConfigManager
            except ImportError:
                raise ValueError(
                    "LLM key configuration extension not available. "
                    "Install with: pip install aipartnerupflow[llm-key-config]"
                )

            provider = params.get("provider")

            # Get user_id from params or authenticated user
            user_id = params.get("user_id")
            if not user_id:
                authenticated_user_id, _ = self._get_user_info(request)
                if not authenticated_user_id:
                    raise ValueError("user_id is required (not authenticated)")
                user_id = authenticated_user_id

            # Check permission
            self._check_permission(request, user_id, "delete LLM key for")

            # Delete key
            config_manager = LLMKeyConfigManager()
            deleted = config_manager.delete_key(user_id, provider=provider)

            provider_str = provider or "all"
            if not deleted:
                logger.warning(f"LLM key not found for user {user_id}, provider {provider_str}")

            logger.info(f"Deleted LLM key for user {user_id}, provider {provider_str}")
            return {
                "success": True,
                "user_id": user_id,
                "deleted": deleted,
                "provider": provider_str,
            }

        except Exception as e:
            logger.error(f"Error deleting LLM key: {str(e)}", exc_info=True)
            raise

    async def handle_examples_init(self, params: dict, request: Request, request_id: str) -> dict:
        """
        Handle examples initialization - initialize example data

        Params:
            force: Optional, if True, re-initialize even if examples already exist

        Returns:
            {"success": True, "created_count": int, "message": str}
        """
        try:
            # Check if examples module is available
            try:
                from aipartnerupflow.examples.init import init_examples_data
            except ImportError:
                raise ValueError(
                    "Examples module not available. "
                    "Install with: pip install aipartnerupflow[examples] or pip install aipartnerupflow[all]"
                )

            force = params.get("force", False)

            # Initialize examples data
            created_count = await init_examples_data(force=force)

            if created_count > 0:
                message = f"Successfully initialized {created_count} example tasks"
            else:
                message = "Examples data already exists or initialization skipped"

            logger.info(f"Examples initialization requested: {message}")
            return {"success": True, "created_count": created_count, "message": message}

        except Exception as e:
            logger.error(f"Error initializing examples: {str(e)}", exc_info=True)
            raise

    async def handle_examples_status(self, params: dict, request: Request, request_id: str) -> dict:
        """
        Handle examples status check - check if examples are initialized

        Returns:
            {"initialized": bool, "available": bool, "message": str}
        """
        try:
            # Check if examples module is available
            try:
                from aipartnerupflow.examples.init import check_if_examples_initialized

                examples_available = True
            except ImportError:
                examples_available = False

            if not examples_available:
                return {
                    "initialized": False,
                    "available": False,
                    "message": "Examples module not available. Install with: pip install aipartnerupflow[examples]",
                }

            # Check if examples are initialized
            initialized = await check_if_examples_initialized()

            if initialized:
                message = "Examples data is initialized"
            else:
                message = "Examples data is not initialized. Call examples.init to initialize."

            return {"initialized": initialized, "available": True, "message": message}

        except Exception as e:
            logger.error(f"Error checking examples status: {str(e)}", exc_info=True)
            return {
                "initialized": False,
                "available": False,
                "message": f"Error checking status: {str(e)}",
            }
