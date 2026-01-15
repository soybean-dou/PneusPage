#!/usr/bin/env python3
"""
Database models for Pneumo Page application.
Defines SQLAlchemy ORM models for User and Job tables.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

db = SQLAlchemy()


class User(db.Model):
    """User model for storing user information from Google OAuth."""
    
    __tablename__ = 'user'
    
    user_key = Column(String(100), primary_key=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    date = Column(String(100), nullable=False)  # Keep as string to match existing DB format
    
    # Relationship to jobs
    jobs = relationship('Job', back_populates='user', cascade='all, delete-orphan', lazy='dynamic')
    
    def __init__(self, user_key, email, name, date=None):
        self.user_key = user_key
        self.email = email
        self.name = name
        if date is None:
            # Format: "Monday 16. January 2026 14:30:45"
            date = datetime.now().strftime("%A %d. %B %Y %H:%M:%S")
        self.date = date
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def to_dict(self):
        """Convert user object to dictionary."""
        return {
            'user_key': self.user_key,
            'email': self.email,
            'name': self.name,
            'date': self.date
        }


class Job(db.Model):
    """Job model for storing analysis job information."""
    
    __tablename__ = 'job'
    
    # Composite primary key
    user_key = Column(String(100), ForeignKey('user.user_key', ondelete='CASCADE'), 
                      primary_key=True, nullable=False)
    job_num = Column(Integer, primary_key=True, nullable=False)
    
    # Job details
    username = Column(String(255), nullable=False)
    jobname = Column(String(255), nullable=False)
    input = Column(Text, nullable=False)  # Pipe-separated file names: "file1.fastq.gz|file2.fastq.gz"
    state = Column(String(50), nullable=False, default='queue', index=True)
    date = Column(String(100), nullable=False)  # Keep as string to match existing DB format
    
    # Relationship to user
    user = relationship('User', back_populates='jobs')
    
    def __init__(self, user_key, username, job_num, jobname, input_files, state='queue', date=None):
        self.user_key = user_key
        self.username = username
        self.job_num = job_num
        self.jobname = jobname
        self.input = input_files
        self.state = state
        if date is None:
            # Format: "Monday 16. January 2026 14:30:45"
            date = datetime.now().strftime("%A %d. %B %Y %H:%M:%S")
        self.date = date
    
    def __repr__(self):
        return f'<Job {self.user_key}:{self.job_num} - {self.jobname}>'
    
    def to_dict(self):
        """Convert job object to dictionary."""
        return {
            'user_key': self.user_key,
            'user_name': self.username,
            'job_num': self.job_num,
            'jobname': self.jobname,
            'input': self.input,
            'state': self.state,
            'date': self.date
        }
    
    @property
    def input_files(self):
        """Get input files as a list."""
        return self.input.split('|') if self.input else []
    
    @property
    def is_complete(self):
        """Check if job is complete."""
        return self.state == 'complete'
    
    @property
    def is_running(self):
        """Check if job is running."""
        return self.state == 'running'
    
    @property
    def is_failed(self):
        """Check if job has failed."""
        return self.state == 'fail'
    
    @property
    def is_queued(self):
        """Check if job is queued."""
        return self.state == 'queue'


def init_db(app):
    """Initialize database with application context."""
    db.init_app(app)
    
    with app.app_context():
        # Import existing data if needed
        db.create_all()
        
        # You can add migration logic here if needed
        # to migrate from old database schema to new ORM schema
        
    return db
