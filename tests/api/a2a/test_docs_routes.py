"""
Test documentation routes (/docs and /openapi.json)

Tests the API documentation endpoints for Swagger UI and OpenAPI schema.
"""

import pytest
from starlette.testclient import TestClient
from aipartnerupflow.api.a2a.server import create_a2a_server


@pytest.fixture(scope="function")
def docs_client(use_test_db_session):
    """Create test client with documentation enabled"""
    server_instance = create_a2a_server(
        verify_token_secret_key=None,  # No JWT for testing
        base_url="http://localhost:8000",
        enable_system_routes=True,
        enable_docs=True,  # Enable documentation
    )
    
    app = server_instance.build()
    client = TestClient(app)
    
    yield client
    
    client.close()


@pytest.fixture(scope="function")
def docs_disabled_client(use_test_db_session):
    """Create test client with documentation disabled"""
    server_instance = create_a2a_server(
        verify_token_secret_key=None,
        base_url="http://localhost:8000",
        enable_system_routes=True,
        enable_docs=False,  # Disable documentation
    )
    
    app = server_instance.build()
    client = TestClient(app)
    
    yield client
    
    client.close()


class TestDocsRoutes:
    """Test cases for documentation routes"""
    
    def test_docs_endpoint_returns_html(self, docs_client):
        """Test that /docs endpoint returns Swagger UI HTML"""
        response = docs_client.get("/docs")
        
        assert response.status_code == 200
        assert response.headers.get("content-type") == "text/html; charset=utf-8"
        
        # Verify it's HTML content
        content = response.text
        assert "<!DOCTYPE html>" in content or "<html" in content.lower()
        assert "swagger" in content.lower() or "openapi" in content.lower()
    
    def test_openapi_json_endpoint_returns_schema(self, docs_client):
        """Test that /openapi.json endpoint returns OpenAPI schema"""
        response = docs_client.get("/openapi.json")
        
        assert response.status_code == 200
        # Content-Type may or may not include charset
        content_type = response.headers.get("content-type")
        assert content_type.startswith("application/json")
        
        # Parse and verify OpenAPI schema structure
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
        
        # Verify OpenAPI version
        assert schema["openapi"].startswith("3.")
        
        # Verify info section
        assert "title" in schema["info"]
        assert "version" in schema["info"]
        
        # Verify paths exist (should have /tasks, /system, etc.)
        assert "/tasks" in schema["paths"]
        assert "/system" in schema["paths"]
    
    def test_openapi_json_schema_structure(self, docs_client):
        """Test OpenAPI schema has correct structure and required fields"""
        response = docs_client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        
        # Verify top-level structure
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
        assert "components" in schema
        
        # Verify info structure
        info = schema["info"]
        assert "title" in info
        assert "version" in info
        assert isinstance(info["title"], str)
        assert isinstance(info["version"], str)
        
        # Verify paths structure
        paths = schema["paths"]
        assert isinstance(paths, dict)
        assert len(paths) > 0
        
        # Verify /tasks endpoint exists
        assert "/tasks" in paths
        tasks_path = paths["/tasks"]
        assert "post" in tasks_path
        
        # Verify /system endpoint exists
        assert "/system" in paths
        system_path = paths["/system"]
        assert "post" in system_path
    
    def test_openapi_json_tasks_endpoint_schema(self, docs_client):
        """Test OpenAPI schema for /tasks endpoint"""
        response = docs_client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        tasks_path = schema["paths"].get("/tasks", {})
        post_method = tasks_path.get("post", {})
        
        # Verify POST method exists
        assert "summary" in post_method or "description" in post_method
        assert "requestBody" in post_method
        assert "responses" in post_method
        
        # Verify request body
        request_body = post_method["requestBody"]
        assert "content" in request_body
        assert "application/json" in request_body["content"]
        
        # Verify responses
        responses = post_method["responses"]
        assert "200" in responses
    
    def test_docs_endpoint_when_disabled(self, docs_disabled_client):
        """Test that /docs endpoint returns 404 when documentation is disabled"""
        response = docs_disabled_client.get("/docs")
        
        # When docs are disabled, the route should not exist
        assert response.status_code == 404
    
    def test_openapi_json_endpoint_when_disabled(self, docs_disabled_client):
        """Test that /openapi.json endpoint returns 404 when documentation is disabled"""
        response = docs_disabled_client.get("/openapi.json")
        
        # When docs are disabled, the route should not exist
        assert response.status_code == 404
    
    def test_docs_endpoint_content_includes_openapi_reference(self, docs_client):
        """Test that Swagger UI HTML references the OpenAPI schema"""
        response = docs_client.get("/docs")
        assert response.status_code == 200
        
        content = response.text
        
        # Swagger UI should reference /openapi.json
        assert "/openapi.json" in content or "openapi.json" in content
    
    def test_openapi_json_servers_configuration(self, docs_client):
        """Test that OpenAPI schema includes correct server configuration"""
        response = docs_client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        
        # Verify servers configuration
        if "servers" in schema:
            servers = schema["servers"]
            assert isinstance(servers, list)
            assert len(servers) > 0
            
            # Verify first server has URL
            first_server = servers[0]
            assert "url" in first_server
            assert isinstance(first_server["url"], str)
    
    def test_openapi_json_components_schemas(self, docs_client):
        """Test that OpenAPI schema includes components/schemas section"""
        response = docs_client.get("/openapi.json")
        assert response.status_code == 200
        
        schema = response.json()
        
        # Verify components section exists
        assert "components" in schema
        components = schema["components"]
        
        # Verify schemas section (may be empty but should exist)
        if "schemas" in components:
            assert isinstance(components["schemas"], dict)
    
    def test_docs_endpoint_method_not_allowed(self, docs_client):
        """Test that /docs endpoint only accepts GET requests"""
        # Try POST request
        response = docs_client.post("/docs")
        assert response.status_code == 405  # Method Not Allowed
    
    def test_openapi_json_endpoint_method_not_allowed(self, docs_client):
        """Test that /openapi.json endpoint only accepts GET requests"""
        # Try POST request
        response = docs_client.post("/openapi.json")
        assert response.status_code == 405  # Method Not Allowed
    
    def test_openapi_json_content_type(self, docs_client):
        """Test that /openapi.json returns correct Content-Type header"""
        response = docs_client.get("/openapi.json")
        
        assert response.status_code == 200
        content_type = response.headers.get("content-type")
        # Content-Type should be application/json (charset is optional)
        assert content_type.startswith("application/json")
    
    def test_docs_endpoint_accessible_without_auth(self, docs_client):
        """Test that /docs endpoint is accessible without authentication"""
        # Make request without Authorization header
        response = docs_client.get("/docs")
        
        assert response.status_code == 200
        # Should return HTML content, not authentication error
    
    def test_openapi_json_endpoint_accessible_without_auth(self, docs_client):
        """Test that /openapi.json endpoint is accessible without authentication"""
        # Make request without Authorization header
        response = docs_client.get("/openapi.json")
        
        assert response.status_code == 200
        # Should return JSON schema, not authentication error

