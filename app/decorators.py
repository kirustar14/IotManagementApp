from functools import wraps
from typing import Callable, Optional, Dict, Any, List, Tuple
from fastapi import Request, Response, HTTPException, Depends
from fastapi.responses import RedirectResponse
import inspect
import mysql.connector
from mysql.connector import pooling
import secrets
import hashlib
import uuid
import time
import json
from datetime import datetime, timedelta
from pydantic import BaseModel
from database import get_session


def auth_required(func: Callable) -> Callable:
    """
    Universal authentication decorator for FastAPI route handlers.
    Works with both sync and async functions.
    
    Usage:
    ```
    @app.get("/protected")
    @auth_required
    def protected_route(request: Request):
        return {"message": "This is a protected route"}
    
    @app.get("/protected-async")
    @auth_required
    async def protected_async_route(request: Request):
        return {"message": "This is a protected async route"}
    ```
    """
    is_async = inspect.iscoroutinefunction(func)
    
    if is_async:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract request from args or kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request and 'request' in kwargs:
                request = kwargs['request']
            
            if not request:
                raise HTTPException(status_code=500, detail="Request object not found in function arguments")
            
            # Get response from kwargs or create new one
            response = kwargs.get('response', None)
            
            # Check if user is authenticated
                
            session_id = request.cookies.get("sessionId")
            if not session_id:
                return RedirectResponse(url="/login")
            
            
            session = await get_session(session_id)
            if not session:
                return RedirectResponse(url="/login")
            
            
            # Set user in request state for later access
            #request.state.user = 

            request.state.user = session["username"]

            # Extend session

            session["expires"] = datetime.utcnow() + timedelta(hours=1)

            # Continue with the original function
            return await func(*args, **kwargs)
        
        return async_wrapper
    else:
        @wraps(func)
        async def sync_wrapper(*args, **kwargs):
            # Extract request from args or kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request and 'request' in kwargs:
                request = kwargs['request']
            
            if not request:
                raise HTTPException(status_code=500, detail="Request object not found in function arguments")
            
            # Get response from kwargs or create new one
            response = kwargs.get('response', None)
            
            # Check if user is authenticated
            
            session_id = request.cookies.get("sessionId")
            if not session_id:
                return RedirectResponse(url="/login")
            
            # Check if session is valid
            session = get_session(session_id)
            if not session:
                return RedirectResponse(url="/login")
            
            # Set user in request state for later access
            #request.state.user = 

            request.state.user = session["username"]

            # Extend session
            
            session["expires"] = datetime.utcnow() + timedelta(hours=1)

            # Continue with the original function
            return func(*args, **kwargs)
        
        return sync_wrapper


