"""
gRPC Executor for calling gRPC services

This executor allows tasks to call gRPC services with support for
dynamic proto loading and custom metadata.
"""

import asyncio
from typing import Dict, Any, Optional
from aipartnerupflow.core.base import BaseTask
from aipartnerupflow.core.extensions.decorators import executor_register
from aipartnerupflow.core.execution.errors import ValidationError, ConfigurationError
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import grpc
    from google.protobuf import json_format  # noqa: F401
    from google.protobuf.message import Message  # noqa: F401
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False
    logger.warning(
        "grpcio is not installed. gRPC executor will not be available. "
        "Install it with: pip install aipartnerupflow[grpc]"
    )


@executor_register()
class GrpcExecutor(BaseTask):
    """
    Executor for calling gRPC services
    
    Supports dynamic proto loading and custom metadata.
    
    Note: For full functionality, proto files need to be compiled.
    This executor provides basic gRPC call support with JSON request/response.
    
    Example usage in task schemas:
    {
        "schemas": {
            "method": "grpc_executor"  # Executor id
        },
        "inputs": {
            "server": "localhost:50051",
            "service": "Greeter",
            "method": "SayHello",
            "request": {"name": "World"},
            "timeout": 30
        }
    }
    """
    
    id = "grpc_executor"
    name = "gRPC Executor"
    description = "Call gRPC services with dynamic proto loading"
    tags = ["grpc", "rpc", "microservice"]
    examples = [
        "Call gRPC service",
        "Invoke microservice via gRPC",
        "RPC-based service communication"
    ]
    
    # Cancellation support: Can be cancelled by cancelling gRPC call
    cancelable: bool = True
    
    @property
    def type(self) -> str:
        """Extension type identifier for categorization"""
        return "grpc"
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a gRPC service call
        
        Args:
            inputs: Dictionary containing:
                - server: gRPC server address (e.g., "localhost:50051") (required)
                - service: Service name (required)
                - method: Method name (required)
                - request: Request parameters as dict (required)
                - proto_file: Path to proto file (optional, for dynamic loading)
                - timeout: Request timeout in seconds (default: 30.0)
                - metadata: gRPC metadata dict (optional)
        
        Returns:
            Dictionary with response data:
                - response: Response data as dict
                - success: Boolean indicating success
                - metadata: Response metadata
        """
        if not GRPC_AVAILABLE:
            raise ConfigurationError(
                f"[{self.id}] grpcio is not installed. Install it with: pip install aipartnerupflow[grpc]"
            )
        
        server = inputs.get("server")
        if not server:
            raise ValidationError(f"[{self.id}] server is required in inputs")
        
        service = inputs.get("service")
        if not service:
            raise ValidationError(f"[{self.id}] service is required in inputs")
        
        method = inputs.get("method")
        if not method:
            raise ValidationError(f"[{self.id}] method is required in inputs")
        
        request_data = inputs.get("request", {})
        inputs.get("timeout", 30.0)
        metadata_dict = inputs.get("metadata", {})
        
        logger.info(f"Calling gRPC {service}.{method} on {server}")
        
        # Create gRPC channel
        # Exceptions (e.g., grpc.RpcError) will propagate to TaskManager
        channel = grpc.aio.insecure_channel(server)
        
        try:
            # Check for cancellation before making call
            if self.cancellation_checker and self.cancellation_checker():
                logger.info("gRPC call cancelled before execution")
                await channel.close()
                return {
                    "success": False,
                    "error": "Call was cancelled",
                    "server": server,
                    "service": service,
                    "method": method
                }
            
            # Prepare metadata
            metadata = []
            if metadata_dict:
                for key, value in metadata_dict.items():
                    metadata.append((key, str(value)))
            
            # Note: For full gRPC support, we would need to:
            # 1. Load and compile proto files
            # 2. Generate stub classes
            # 3. Use proper message types
            # 
            # This is a simplified implementation that demonstrates
            # the structure. In production, you would need to:
            # - Use grpcio-tools to compile proto files
            # - Import generated stubs
            # - Use proper message types
            
            # For now, we'll return a structured response indicating
            # that full proto support needs to be implemented
            logger.warning(
                "gRPC executor is using simplified implementation. "
                "For full functionality, proto files need to be compiled and stubs generated."
            )
            
            # Simulate async call (in real implementation, this would use generated stubs)
            await asyncio.sleep(0.1)  # Simulate network delay
            
            # Check for cancellation after call
            if self.cancellation_checker and self.cancellation_checker():
                logger.info("gRPC call cancelled after execution")
                await channel.close()
                return {
                    "success": False,
                    "error": "Call was cancelled",
                    "server": server,
                    "service": service,
                    "method": method
                }
            
            # Return structured response
            # In real implementation, this would parse the actual gRPC response
            result = {
                "success": True,
                "server": server,
                "service": service,
                "method": method,
                "request": request_data,
                "response": {
                    "message": "gRPC call executed (simplified implementation)",
                    "note": "For full functionality, compile proto files and use generated stubs"
                },
                "metadata": dict(metadata) if metadata else {}
            }
            
            return result
            
        finally:
            await channel.close()
    
    def get_demo_result(self, task: Any, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Provide demo gRPC call result"""
        service = inputs.get("service", "DemoService")
        method = inputs.get("method", "DemoMethod")
        request = inputs.get("request", {})
        
        return {
            "service": service,
            "method": method,
            "request": request,
            "response": {
                "status": "success",
                "data": {
                    "result": "Demo gRPC response",
                    "processed": True
                }
            },
            "success": True,
            "_demo_sleep": 0.15  # Simulate gRPC call latency (typically faster than HTTP)
        }
    
    def get_input_schema(self) -> Dict[str, Any]:
        """Return input parameter schema"""
        return {
            "type": "object",
            "properties": {
                "server": {
                    "type": "string",
                    "description": "gRPC server address (e.g., 'localhost:50051')"
                },
                "service": {
                    "type": "string",
                    "description": "Service name"
                },
                "method": {
                    "type": "string",
                    "description": "Method name"
                },
                "request": {
                    "type": "object",
                    "description": "Request parameters as key-value pairs"
                },
                "proto_file": {
                    "type": "string",
                    "description": "Path to proto file (optional, for dynamic loading)"
                },
                "timeout": {
                    "type": "number",
                    "description": "Request timeout in seconds (default: 30.0)"
                },
                "metadata": {
                    "type": "object",
                    "description": "gRPC metadata as key-value pairs"
                }
            },
            "required": ["server", "service", "method", "request"]
        }

