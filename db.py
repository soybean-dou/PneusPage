#!/usr/bin/env python3
"""
Database operations for Pneumo Page application.
Refactored to use SQLAlchemy ORM for security and better maintainability.
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import create_engine, event
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from models import db, User, Job
from config import Config

logger = logging.getLogger(__name__)


# Database session management
# This will be initialized by init_db()
Session = None


def init_db(app=None, config: Config = None):
    """
    Initialize database connection and session factory.
    
    Args:
        app: Flask application instance (optional)
        config: Configuration object (optional)
    
    Returns:
        Database session factory
    """
    global Session
    
    if app is not None:
        # Flask-SQLAlchemy initialization
        db.init_app(app)
        with app.app_context():
            db.create_all()
        return db
    
    # Standalone SQLAlchemy initialization (for scripts)
    if config is None:
        config = Config
    
    engine = create_engine(
        config.SQLALCHEMY_DATABASE_URI,
        echo=config.SQLALCHEMY_ECHO,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=3600    # Recycle connections after 1 hour
    )
    
    # Enable foreign key constraints for SQLite
    if 'sqlite' in config.SQLALCHEMY_DATABASE_URI:
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    
    Session = scoped_session(sessionmaker(bind=engine))
    
    # Create tables if they don't exist
    from models import User, Job
    User.metadata.create_all(engine)
    Job.metadata.create_all(engine)
    
    logger.info("Database initialized successfully")
    return Session


def get_session():
    """Get database session."""
    if Session is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return Session()


# User operations

def insert_user(user_info: Dict[str, str]) -> Optional[User]:
    """
    Insert a new user into the database.
    
    Args:
        user_info: Dictionary containing user_key, email, and name
    
    Returns:
        User object if successful, None otherwise
    """
    try:
        # Check if user already exists
        existing_user = get_user(user_info['user_key'])
        if existing_user:
            logger.info(f"User {user_info['email']} already exists")
            return existing_user
        
        # Create new user
        user = User(
            user_key=user_info['user_key'],
            email=user_info['email'],
            name=user_info['name']
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Create user directory
        user_dir = Config.USER_DATA_DIR / user_info['user_key']
        user_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Created new user: {user_info['email']}")
        return user
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error inserting user: {e}")
        return None


def get_user(user_key: str) -> Optional[User]:
    """
    Get user by user_key.
    
    Args:
        user_key: User's unique identifier
    
    Returns:
        User object if found, None otherwise
    """
    try:
        return db.session.query(User).filter_by(user_key=user_key).first()
    except SQLAlchemyError as e:
        logger.error(f"Error getting user: {e}")
        return None


def is_joined(user_key: str) -> bool:
    """
    Check if user exists in database.
    
    Args:
        user_key: User's unique identifier
    
    Returns:
        True if user exists, False otherwise
    """
    try:
        user = db.session.query(User).filter_by(user_key=user_key).first()
        return user is not None
    except SQLAlchemyError as e:
        logger.error(f"Error checking user existence: {e}")
        return False


def read_user_db(user_key: str) -> Optional[Dict[str, Any]]:
    """
    Read user information from database.
    
    Args:
        user_key: User's unique identifier
    
    Returns:
        Dictionary with user information or None
    """
    try:
        user = db.session.query(User).filter_by(user_key=user_key).first()
        if user:
            return {'date': user.date}
        return None
    except SQLAlchemyError as e:
        logger.error(f"Error reading user data: {e}")
        return None


# Job operations

def insert_job(user_info: Dict[str, str], job_info: Dict[str, Any]) -> Optional[Job]:
    """
    Insert a new job into the database.
    
    Args:
        user_info: Dictionary containing user_key and username
        job_info: Dictionary containing jobname, file1, and file2
    
    Returns:
        Job object if successful, None otherwise
    """
    try:
        # Get next job number for this user
        job_num = read_job_num(user_info['user_key'])
        
        # Create input file string
        input_files = f"{job_info['file1']}|{job_info['file2']}"
        
        # Create new job
        job = Job(
            user_key=user_info['user_key'],
            username=user_info['username'],
            job_num=job_num,
            jobname=job_info['jobname'],
            input_files=input_files,
            state='queue'
        )
        
        db.session.add(job)
        db.session.commit()
        
        logger.info(f"Created job {job_num} for user {user_info['user_key']}")
        return job
        
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error inserting job: {e}")
        return None


def read_user_job(user_key: str) -> List[Dict[str, Any]]:
    """
    Read all jobs for a specific user.
    
    Args:
        user_key: User's unique identifier
    
    Returns:
        List of job dictionaries
    """
    try:
        jobs = db.session.query(Job).filter_by(user_key=user_key).order_by(Job.job_num).all()
        
        # Convert to list of dictionaries for backward compatibility
        result = []
        for job in jobs:
            result.append({
                'user_key': job.user_key,
                'username': job.username,
                'job_num': job.job_num,
                'jobname': job.jobname,
                'input': job.input,
                'state': job.state,
                'date': job.date
            })
        
        return result
        
    except SQLAlchemyError as e:
        logger.error(f"Error reading user jobs: {e}")
        return []


def read_job_num(user_key: str) -> int:
    """
    Get the next available job number for a user.
    
    Args:
        user_key: User's unique identifier
    
    Returns:
        Next job number (1-indexed)
    """
    try:
        last_job = (db.session.query(Job)
                   .filter_by(user_key=user_key)
                   .order_by(Job.job_num.desc())
                   .first())
        
        if last_job:
            return last_job.job_num + 1
        return 1
        
    except SQLAlchemyError as e:
        logger.error(f"Error reading job number: {e}")
        return 1


def update_db(user_key: str, job_key: int, state: str) -> bool:
    """
    Update job state in database.
    
    Args:
        user_key: User's unique identifier
        job_key: Job number
        state: New state ('queue', 'running', 'complete', 'fail')
    
    Returns:
        True if successful, False otherwise
    """
    try:
        job = db.session.query(Job).filter_by(
            user_key=user_key,
            job_num=job_key
        ).first()
        
        if job:
            job.state = state
            db.session.commit()
            logger.info(f"Updated job {user_key}:{job_key} state to {state}")
            return True
        else:
            logger.warning(f"Job not found: {user_key}:{job_key}")
            return False
            
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error updating job state: {e}")
        return False


def read_db_row(user_key: str, job_key: int) -> tuple:
    """
    Read a specific job from database.
    
    Args:
        user_key: User's unique identifier
        job_key: Job number
    
    Returns:
        Tuple of (job_list, column_names) for backward compatibility
    """
    try:
        job = db.session.query(Job).filter_by(
            user_key=user_key,
            job_num=job_key
        ).first()
        
        if job:
            # Create SQLite Row-like object for backward compatibility
            job_dict = {
                'user_key': job.user_key,
                'username': job.username,
                'job_num': job.job_num,
                'jobname': job.jobname,
                'input': job.input,
                'state': job.state,
                'date': job.date
            }
            
            cols = ['user_key', 'username', 'job_num', 'jobname', 'input', 'state', 'date']
            return [job_dict], cols
        else:
            return [], []
            
    except SQLAlchemyError as e:
        logger.error(f"Error reading job: {e}")
        return [], []


def delete_user_job(user_key: str, job_key: int) -> bool:
    """
    Delete a specific job from database.
    
    Args:
        user_key: User's unique identifier
        job_key: Job number
    
    Returns:
        True if successful, False otherwise
    """
    try:
        job = db.session.query(Job).filter_by(
            user_key=user_key,
            job_num=job_key
        ).first()
        
        if job:
            db.session.delete(job)
            db.session.commit()
            logger.info(f"Deleted job {user_key}:{job_key}")
            return True
        else:
            logger.warning(f"Job not found for deletion: {user_key}:{job_key}")
            return False
            
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error deleting job: {e}")
        return False


# Utility functions

def get_job(user_key: str, job_num: int) -> Optional[Job]:
    """
    Get a specific job object.
    
    Args:
        user_key: User's unique identifier
        job_num: Job number
    
    Returns:
        Job object if found, None otherwise
    """
    try:
        return db.session.query(Job).filter_by(
            user_key=user_key,
            job_num=job_num
        ).first()
    except SQLAlchemyError as e:
        logger.error(f"Error getting job: {e}")
        return None


def get_jobs_by_state(state: str) -> List[Job]:
    """
    Get all jobs with a specific state.
    
    Args:
        state: Job state to filter by
    
    Returns:
        List of Job objects
    """
    try:
        return db.session.query(Job).filter_by(state=state).all()
    except SQLAlchemyError as e:
        logger.error(f"Error getting jobs by state: {e}")
        return []


def cleanup_old_jobs(days: int = 30) -> int:
    """
    Delete jobs older than specified days (for future use).
    
    Args:
        days: Number of days to keep jobs
    
    Returns:
        Number of deleted jobs
    """
    # This is a placeholder for future implementation
    # Would need to parse the date string and compare
    logger.info(f"Cleanup function called (not implemented yet)")
    return 0
