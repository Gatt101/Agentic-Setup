#!/usr/bin/env python
"""Simple test to check if all imports work correctly."""
import sys
sys.path.insert(0, '.')

def test_basic_imports():
    """Test basic imports without feedback.py"""
    try:
        from fastapi import APIRouter
        print("✅ FastAPI Router imported")
        return True
    except ImportError as e:
        print(f"❌ FastAPI import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ FastAPI error: {e}")
        return False

def test_feedback_imports():
    """Test feedback.py imports step by step"""
    print("\nTesting feedback.py imports...")

    try:
        import sys
        print("✅ sys imported")
    except ImportError as e:
        print(f"❌ sys import failed: {e}")
        return False

    try:
        from datetime import datetime, timedelta
        print("✅ datetime imported")
    except ImportError as e:
        print(f"❌ datetime import failed: {e}")
        return False

    try:
        from typing import Any, Dict, List
        print("✅ typing imported")
    except ImportError as e:
        print(f"❌ typing import failed: {e}")
        return False

    try:
        from uuid import uuid4
        print("✅ uuid imported")
    except ImportError as e:
        print(f"❌ uuid import failed: {e}")
        return False

    try:
        from fastapi import APIRouter, HTTPException, Query
        print("✅ FastAPI components imported")
    except ImportError as e:
        print(f"❌ FastAPI import failed: {e}")
        return False

    try:
        from loguru import logger
        print("✅ loguru imported")
    except ImportError as e:
        print(f"❌ loguru import failed: {e}")
        return False

    try:
        from api.schemas.feedback import AgentFeedback, FeedbackResponse, FeedbackSummary
        print("✅ api.schemas.feedback imported")
    except ImportError as e:
        print(f"❌ api.schemas.feedback import failed: {e}")
        return False

    try:
        from services.mongo import mongo_service
        print("✅ services.mongo.mongo_service imported")
    except ImportError as e:
        print(f"❌ services.mongo.mongo_service import failed: {e}")
        return False

    try:
        from services.chat_store import chat_store
        print("✅ services.chat_store.chat_store imported")
    except ImportError as e:
        print(f"❌ services.chat_store.chat_store import failed: {e}")
        return False

    try:
        from services.agent_learning import adaptive_supervisor
        print("✅ services.agent_learning.adaptive_supervisor imported")
    except ImportError as e:
        print(f"❌ services.agent_learning.adaptive_supervisor import failed: {e}")
        return False

    try:
        from services.probabilistic_reasoning import confidence_estimator, probabilistic_reasoner, bayesian_updater
        print("✅ services.probabilistic_reasoning imported")
    except ImportError as e:
        print(f"❌ services.probabilistic_reasoning import failed: {e}")
        return False

    print("\n" + "="*50)
    print("✅ All basic imports successful!")
    print("="*50)

    return True

if __name__ == "__main__":
    print("Testing OrthoAssist Backend Imports")
    print("="*50)

    success = test_basic_imports()
    if success:
        success = test_feedback_imports()
        if success:
            print("\n🎉 ALL IMPORTS WORKING!")
            print("\nYour backend should be ready to start now.")
            print("Run: python main.py")
        else:
            print("\n❌ Some feedback.py imports failed")
            sys.exit(1)
    else:
        print("\n❌ Basic imports failed")
        sys.exit(1)