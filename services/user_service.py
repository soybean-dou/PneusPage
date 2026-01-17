#!/usr/bin/env python3
"""
User Service Layer
Handles user-related business logic.
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path

from config import Config
import db as db_operations
from models import User

logger = logging.getLogger(__name__)


class UserService:
    """Service class for user-related operations."""
    
    @staticmethod
    def create_user(user_info: Dict[str, str]) -> Optional[User]:
        """
        Create a new user and their directory.
        
        Args:
            user_info: Dictionary with user_key, email, name
        
        Returns:
            User object if successful, None otherwise
        """
        try:
            user = db_operations.insert_user(user_info)
            if user:
                logger.info(f"User created: {user_info['email']}")
            return user
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            return None
    
    @staticmethod
    def get_user(user_key: str) -> Optional[User]:
        """
        Get user by user_key.
        
        Args:
            user_key: User's unique identifier
        
        Returns:
            User object if found, None otherwise
        """
        return db_operations.get_user(user_key)
    
    @staticmethod
    def is_user_registered(user_key: str) -> bool:
        """
        Check if user exists.
        
        Args:
            user_key: User's unique identifier
        
        Returns:
            True if user exists, False otherwise
        """
        return db_operations.is_joined(user_key)
    
    @staticmethod
    def get_user_info(user_key: str) -> Optional[Dict[str, Any]]:
        """
        Get user information.
        
        Args:
            user_key: User's unique identifier
        
        Returns:
            Dictionary with user info or None
        """
        return db_operations.read_user_db(user_key)
    
    @staticmethod
    def is_admin(user_key: str) -> bool:
        """
        Check if user is admin.
        
        Args:
            user_key: User's unique identifier
        
        Returns:
            True if user is admin, False otherwise
        """
        return user_key in Config.ADMIN_USERS
    
    @staticmethod
    def can_access_user_data(requesting_user_key: str, target_user_key: str) -> bool:
        """
        Check if requesting user can access target user's data.
        
        Args:
            requesting_user_key: User making the request
            target_user_key: User whose data is being accessed
        
        Returns:
            True if access is allowed, False otherwise
        """
        # User can access their own data
        if requesting_user_key == target_user_key:
            return True
        
        # Admin can access all data
        if UserService.is_admin(requesting_user_key):
            return True
        
        return False
