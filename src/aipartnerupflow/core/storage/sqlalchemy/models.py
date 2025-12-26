"""
SQLAlchemy models for task storage
"""

from sqlalchemy import Column, String, Integer, DateTime, JSON, Text, Boolean, Numeric
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base
from typing import Dict, Any
import uuid
import os

Base = declarative_base()

# Table name configuration - supports environment variable override
# Default: "apflow_tasks" (aipartnerupflow tasks)
# Can be overridden via AIPARTNERUPFLOW_TASK_TABLE_NAME environment variable
TASK_TABLE_NAME = os.getenv("AIPARTNERUPFLOW_TASK_TABLE_NAME", "apflow_tasks")


class TaskModel(Base):
    """
    Task Definition Model - Handles task orchestration and definition
    
    This model represents task definitions for orchestration. A2A Protocol Task represents
    execution instances with LLM message context.
    
    Key design:
    - TaskModel: Task definition (static, orchestration)
    - A2A Protocol Task: Task execution instance (dynamic, LLM context)
    
    Mapping relationship:
    - TaskModel.id -> A2A Task.context_id (task definition ID = context ID)
    - A2A Task.id -> Execution instance ID (A2A Protocol internal, auto-generated)
    - One TaskModel can have multiple Task execution instances
    
    Note: A2A Protocol Task fields (artifacts, history, kind, metadata) are execution-level
    and should NOT be stored in TaskModel. They are managed by A2A Protocol TaskStore.
    
    Table name: Configurable via AIPARTNERUPFLOW_TASK_TABLE_NAME environment variable.
    Default: "apflow_tasks" - prefixed to distinguish from A2A Protocol's "tasks" table.
    This table stores both task definitions (orchestration) and execution results.
    """
    __tablename__ = TASK_TABLE_NAME  # Configurable table name (default: "apflow_tasks")
    
    # === Task Definition Identity ===
    id = Column(String(255), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))  # Task definition ID (maps to A2A Task.context_id)
    
    # === Task Tree Structure (TaskManager) ===
    parent_id = Column(String(255), nullable=True, index=True)  # Parent task ID (for task tree hierarchy)
    
    # === User Identification (Optional, Multi-user Support) ===
    user_id = Column(String(255), nullable=True, index=True)  # User ID (optional, for multi-user scenarios)
    
    # === Task Basic Information ===
    name = Column(String(100), nullable=False, index=True)  # Task name/method identifier
    status = Column(String(50), default="pending")  # Task status: pending, in_progress, completed, failed, cancelled
    
    # === Task Orchestration (TaskManager) ===
    priority = Column(Integer, default=2)  # Priority level: 0=urgent (highest), 1=high, 2=normal (default), 3=low (lowest). ASC order: smaller numbers execute first.
    dependencies = Column(JSON, nullable=True)  # Task dependencies: [{"id": "uuid", "required": true}]
    
    # === Task Data ===
    inputs = Column(JSON, nullable=True)  # Execution-time input parameters for executor.execute(inputs)
    params = Column(JSON, nullable=True)  # Executor initialization parameters for executor.__init__(**params)
    result = Column(JSON, nullable=True)  # Latest execution result (extracted from A2A Task.artifacts)
    error = Column(Text, nullable=True)  # Error message (extracted from A2A TaskStatus.message)
    schemas = Column(JSON, nullable=True)  # Validation schemas (input_schema, output_schema)
    
    # Note: A2A Protocol execution fields (artifacts, history, kind, metadata) are NOT stored here.
    # They are managed by A2A Protocol TaskStore as execution instances.
    
    # === Task Progress ===
    progress = Column(Numeric(3, 2), default=0.0)  # Progress as decimal (0.00 to 1.00)
    
    # === Timestamps ===
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # === Auxiliary Fields ===
    has_children = Column(Boolean, default=False)  # UI/performance optimization flag
    
    # === Task Copy Fields ===
    original_task_id = Column(String(255), nullable=True, index=True)  # Original task ID (if this is a copy for re-execution)
    has_copy = Column(Boolean, default=False, index=True)  # Whether this task has copies (for efficient querying)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            # Task definition identity
            "id": self.id,
            # Task tree structure
            "parent_id": self.parent_id,
            # User identification
            "user_id": self.user_id,
            # Task basic information
            "name": self.name,
            "status": self.status,
            # Task orchestration
            "priority": self.priority,
            "dependencies": self.dependencies,
            # Task data
            "inputs": self.inputs,
            "params": self.params,
            "result": self.result,  # Latest execution result
            "error": self.error,
            "schemas": self.schemas,
            # Task progress
            "progress": float(self.progress) if self.progress is not None else 0.0,
            # Timestamps
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            # Auxiliary fields
            "has_children": self.has_children,
            # Task copy fields
            "original_task_id": self.original_task_id,
            "has_copy": self.has_copy,
        }
    
    def __repr__(self):
        return f"<TaskModel(id='{self.id}', name='{self.name}', status='{self.status}')>"

