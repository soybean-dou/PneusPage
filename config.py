#!/usr/bin/env python3
"""
Configuration management for Pneumo Page application.
Loads settings from environment variables with fallback defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
basedir = Path(__file__).resolve().parent
load_dotenv(basedir / '.env')


class Config:
    """Base configuration class."""
    
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    
    # Application paths
    BASE_DIR = Path(os.getenv('BASE_DIR', basedir))
    USER_DATA_DIR = BASE_DIR / 'user'
    LOG_DIR = BASE_DIR / 'logs'
    REFERENCE_DIR = BASE_DIR / 'reference'
    SAMPLE_DIR = BASE_DIR / 'sample'
    
    # Database settings
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'pneumo_service.db')
    DATABASE_PATH = BASE_DIR / DATABASE_NAME
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        f'sqlite:///{DATABASE_PATH}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = DEBUG
    
    # Google OAuth settings
    GOOGLE_CLIENT_SECRETS_FILE = BASE_DIR / os.getenv(
        'GOOGLE_CLIENT_SECRETS_FILE',
        'client_secret.json'
    )
    GOOGLE_SCOPES = [
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid"
    ]
    GOOGLE_REDIRECT_URI = os.getenv(
        'GOOGLE_REDIRECT_URI',
        'https://pneuspage.minholee.net/callback'
    )
    
    # File upload settings
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_UPLOAD_SIZE', 16 * 1024 * 1024 * 1024))  # 16GB default
    ALLOWED_EXTENSIONS = {'fastq', 'fq', 'gz', 'tsv'}
    
    # Pipeline tool paths
    TRIMMOMATIC_PATH = os.getenv('TRIMMOMATIC_PATH', '/home/iu98/toolkit/Trimmomatic-0.39/trimmomatic-0.39.jar')
    TRIMMOMATIC_ADAPTERS = os.getenv('TRIMMOMATIC_ADAPTERS', '/home/iu98/toolkit/Trimmomatic-0.39/adapters/TruSeq3-PE.fa')
    KRAKEN_DB_PATH = os.getenv('KRAKEN_DB_PATH', '/home/iu98/toolkit/kraken_db')
    CGMLST_DB_PATH = os.getenv('CGMLST_DB_PATH', '/home/iu98/pneumo_pipline/cgmlstfinder/cgmlstfinder_db')
    VIRULENCEFINDER_DB_PATH = os.getenv('VIRULENCEFINDER_DB_PATH', '/home/iu98/pneumo_pipline/virulencefinder/virulencefinder_db')
    POPPUNK_DB_PATH = os.getenv('POPPUNK_DB_PATH', '/home/iu98/toolkit/GPS_v6/GPS_v6')
    POPPUNK_DIST_PATH = os.getenv('POPPUNK_DIST_PATH', '/home/iu98/toolkit/GPS_v6/GPS_v6.dists')
    POPPUNK_CLUSTERS_PATH = os.getenv('POPPUNK_CLUSTERS_PATH', '/home/iu98/toolkit/GPS_v6/GPS_v6_external_clusters.csv')
    PBP_SCRIPT_DIR = os.getenv('PBP_SCRIPT_DIR', '/home/iu98/pneumo_pipline/pbp_connectagen')
    
    # Reference genome paths
    REFERENCE_GENOME = REFERENCE_DIR / 'GCF_002076835.1_ASM207683v1_genomic.fna'
    REFERENCE_GTF = REFERENCE_DIR / 's.pneumoniae.gtf'
    
    # Pipeline settings
    DEFAULT_THREADS = int(os.getenv('PIPELINE_THREADS', '8'))
    QUAST_MIN_CONTIG = int(os.getenv('QUAST_MIN_CONTIG', '100'))
    
    # SLURM settings
    SLURM_PARTITION = os.getenv('SLURM_PARTITION', 'lys')
    SLURM_CPUS = int(os.getenv('SLURM_CPUS', '4'))
    SLURM_MEMORY = os.getenv('SLURM_MEMORY', '70G')
    
    # Admin users (comma-separated user keys)
    ADMIN_USERS = set(os.getenv('ADMIN_USERS', '105794308045478426283').split(','))
    
    # Logging settings
    LOG_FILE = LOG_DIR / 'pneuspage.log'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG' if DEBUG else 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    @classmethod
    def init_app(cls, app):
        """Initialize application with this config."""
        # Create necessary directories
        cls.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
        cls.REFERENCE_DIR.mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SQLALCHEMY_ECHO = False
    
    @classmethod
    def init_app(cls, app):
        super().init_app(app)
        
        # Production-specific initialization
        import logging
        from logging.handlers import RotatingFileHandler
        
        # Ensure log directory exists
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Setup file handler with rotation
        file_handler = RotatingFileHandler(
            cls.LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(cls.LOG_FORMAT))
        app.logger.addHandler(file_handler)


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(config_name=None):
    """Get configuration object based on environment."""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    return config.get(config_name, config['default'])
