#!/usr/bin/env python3
"""
Job Service Layer
Handles job-related business logic.
"""

import logging
import os
import shutil
from typing import Optional, Dict, Any, List
from pathlib import Path
import pandas as pd

from config import Config
import db as db_operations
import run_pipeline as rp
from models import Job

logger = logging.getLogger(__name__)


class JobService:
    """Service class for job-related operations."""
    
    @staticmethod
    def create_job(user_info: Dict[str, str], job_info: Dict[str, Any]) -> Optional[Job]:
        """
        Create a new job.
        
        Args:
            user_info: Dictionary with user_key, username
            job_info: Dictionary with jobname, file1, file2
        
        Returns:
            Job object if successful, None otherwise
        """
        try:
            job = db_operations.insert_job(user_info, job_info)
            if job:
                logger.info(f"Job created: {user_info['user_key']}:{job_info.get('job_key')}")
            return job
        except Exception as e:
            logger.error(f"Failed to create job: {e}")
            return None
    
    @staticmethod
    def get_next_job_number(user_key: str) -> int:
        """
        Get next available job number for user.
        
        Args:
            user_key: User's unique identifier
        
        Returns:
            Next job number
        """
        return db_operations.read_job_num(user_key)
    
    @staticmethod
    def get_user_jobs(user_key: str) -> pd.DataFrame:
        """
        Get all jobs for a user with species information.
        
        Args:
            user_key: User's unique identifier
        
        Returns:
            DataFrame with job information formatted for display
        """
        try:
            # Get jobs from database
            db_info = db_operations.read_user_job(user_key)
            
            # Convert to DataFrame
            df = pd.DataFrame.from_records(
                data=db_info,
                columns=["user_key", "username", "job_num", "jobname", "input", "state", "date"]
            )
            
            # Rename columns to match template expectations
            df = df.rename(columns={
                'job_num': 'job_id',
                'jobname': 'job_name',
                'input': 'input_file',
                'state': 'states'
            })
            
            # Add species column
            df["species"] = ""
            
            # Get species for each job
            for job_id in df["job_id"]:
                species = rp.get_species(user_key, str(job_id))
                df.loc[df["job_id"] == job_id, "species"] = species if species else ""
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to get user jobs: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def get_job(user_key: str, job_key: int) -> Optional[Dict[str, Any]]:
        """
        Get specific job information.
        
        Args:
            user_key: User's unique identifier
            job_key: Job number
        
        Returns:
            Dictionary with job info or None
        """
        try:
            db_info, cols = db_operations.read_db_row(user_key, job_key)
            if db_info:
                return db_info[0]
            return None
        except Exception as e:
            logger.error(f"Failed to get job: {e}")
            return None
    
    @staticmethod
    def get_job_details(user_key: str, job_key: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed job results including analysis outputs.
        
        Args:
            user_key: User's unique identifier
            job_key: Job number (as string)
        
        Returns:
            Dictionary with job details and analysis results
        """
        try:
            # Get basic job info
            db_info, cols = db_operations.read_db_row(user_key, int(job_key))
            
            if not db_info:
                logger.warning(f"Job not found: {user_key}:{job_key}")
                return None
            
            data_df = pd.DataFrame.from_records(data=db_info, columns=cols)
            files = data_df["input"][0].split("|")
            species = rp.get_species(user_key, job_key)
            
            result = {
                'job_info': db_info,
                'files': files,
                'species': species,
                'job_key': job_key,
                'user_key': user_key
            }
            
            # Get analysis results
            if species == "Streptococcus pneumoniae":
                analysis_data = rp.get_info(user_key, job_key)
                result['full_analysis'] = analysis_data
            else:
                # Basic results only
                basic_data = rp.get_info(user_key, job_key)
                result['basic_analysis'] = basic_data
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get job details: {e}")
            return None
    
    @staticmethod
    def create_job_directory(user_key: str, job_key: int) -> Path:
        """
        Create directory for job.
        
        Args:
            user_key: User's unique identifier
            job_key: Job number
        
        Returns:
            Path to created directory
        
        Raises:
            FileExistsError: If directory already exists
        """
        job_dir = Config.USER_DATA_DIR / str(user_key) / str(job_key)
        
        if job_dir.exists():
            raise FileExistsError(f"Job directory already exists: {job_dir}")
        
        job_dir.mkdir(parents=True, exist_ok=False)
        logger.info(f"Created job directory: {job_dir}")
        
        return job_dir
    
    @staticmethod
    def save_uploaded_files(job_dir: Path, files: list) -> Dict[str, str]:
        """
        Save uploaded files to job directory.
        
        Args:
            job_dir: Path to job directory
            files: List of uploaded file objects
        
        Returns:
            Dictionary with file1 and file2 names
        
        Raises:
            ValueError: If files are invalid
        """
        from werkzeug.utils import secure_filename
        
        if not files or len(files) < 2:
            raise ValueError("Both forward and reverse read files are required")
        
        saved_files = {}
        
        for i, f in enumerate(files[:2]):  # Only take first 2 files
            if f and f.filename:
                filename = secure_filename(f.filename)
                filepath = job_dir / filename
                f.save(str(filepath))
                saved_files[f'file{i+1}'] = filename
                logger.debug(f"Saved file: {filename}")
        
        if len(saved_files) < 2:
            raise ValueError("Failed to save both files")
        
        return saved_files
    
    @staticmethod
    def submit_to_slurm(user_key: str, job_info: Dict[str, Any]) -> bool:
        """
        Submit job to SLURM scheduler.
        
        Args:
            user_key: User's unique identifier
            job_info: Dictionary with job details
        
        Returns:
            True if submitted successfully, False otherwise
        """
        try:
            job_dir = Config.USER_DATA_DIR / str(user_key) / str(job_info["job_key"])
            sbatch_file = job_dir / "sbatch.sh"
            
            # Create SLURM batch script
            with open(sbatch_file, "w") as f:
                f.write("#!/bin/sh\n\n")
                f.write(f"#SBATCH -J pne_{job_info['job_key']}\n")
                f.write(f"#SBATCH --cpus-per-task={Config.SLURM_CPUS}\n")
                f.write(f"#SBATCH --mem {Config.SLURM_MEMORY}\n")
                f.write(f"#SBATCH -p {Config.SLURM_PARTITION}\n")
                f.write(f"#SBATCH -o {job_info['job_key']}.out\n")
                f.write(f"#SBATCH -e {job_info['job_key']}.err\n\n")
                f.write(f"python {Config.BASE_DIR}/run_pipeline.py ")
                f.write(f"{user_key} {job_info['job_key']} {job_info['file1']} {job_info['file2']}\n")
            
            # Submit to SLURM
            current_dir = os.getcwd()
            os.chdir(job_dir)
            result = os.system("sbatch sbatch.sh")
            os.chdir(current_dir)
            
            if result == 0:
                logger.info(f"Submitted job {job_info['job_key']} to SLURM")
                return True
            else:
                logger.error(f"Failed to submit job {job_info['job_key']} to SLURM")
                return False
                
        except Exception as e:
            logger.error(f"Error submitting to SLURM: {e}")
            return False
    
    @staticmethod
    def delete_job(user_key: str, job_key: int) -> bool:
        """
        Delete job and its data.
        
        Args:
            user_key: User's unique identifier
            job_key: Job number
        
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Delete job directory
            job_dir = Config.USER_DATA_DIR / str(user_key) / str(job_key)
            if job_dir.exists():
                shutil.rmtree(job_dir)
                logger.info(f"Deleted job directory: {job_dir}")
            
            # Delete from database
            result = db_operations.delete_user_job(user_key, job_key)
            
            if result:
                logger.info(f"Deleted job from database: {user_key}:{job_key}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to delete job: {e}")
            return False
    
    @staticmethod
    def update_job_status(user_key: str, job_key: int, status: str) -> bool:
        """
        Update job status.
        
        Args:
            user_key: User's unique identifier
            job_key: Job number
            status: New status ('queue', 'running', 'complete', 'fail')
        
        Returns:
            True if updated successfully, False otherwise
        """
        return db_operations.update_db(user_key, job_key, status)
    
    @staticmethod
    def create_multi_directory(user_key: str) -> Path:
        """
        Create 'multi' directory for batch uploads.
        
        Args:
            user_key: User's unique identifier
        
        Returns:
            Path to multi directory
        """
        multi_dir = Config.USER_DATA_DIR / str(user_key) / "multi"
        multi_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created multi directory: {multi_dir}")
        return multi_dir
    
    @staticmethod
    def process_batch_upload(user_key: str, username: str, file_list_df: pd.DataFrame, 
                           uploaded_files: list) -> tuple[int, List[str]]:
        """
        Process batch job upload from TSV file.
        
        Args:
            user_key: User's unique identifier
            username: User's name
            file_list_df: DataFrame with columns ['jobs', 'read1', 'read2']
            uploaded_files: List of uploaded file objects
        
        Returns:
            Tuple of (number of jobs created, list of error messages)
        
        Raises:
            ValueError: If file validation fails
        """
        from werkzeug.utils import secure_filename
        
        errors = []
        
        # Validate uploaded files match TSV
        raw_list = []
        for f in uploaded_files:
            if f.filename in list(file_list_df["read1"]):
                raw_list.append(f.filename)
            elif f.filename in list(file_list_df["read2"]):
                raw_list.append(f.filename)
            else:
                raise ValueError(f"File '{f.filename}' not found in file list TSV")
        
        # Check all required files are present
        required_files = set(file_list_df["read1"]) | set(file_list_df["read2"])
        uploaded_names = set(f.filename for f in uploaded_files)
        missing_files = required_files - uploaded_names
        
        if missing_files:
            raise ValueError(f"Missing required files: {', '.join(missing_files)}")
        
        # Get starting job number
        job_key = db_operations.read_job_num(user_key)
        jobs_created = 0
        
        user_info = {
            "user_key": user_key,
            "username": username
        }
        
        # Process each job in file list
        for idx, row in file_list_df.iterrows():
            try:
                job_info = {
                    'user_key': user_key,
                    "jobname": row["jobs"],
                    "job_key": job_key,
                    "file1": row["read1"],
                    "file2": row["read2"]
                }
                
                # Create job directory
                job_dir = JobService.create_job_directory(user_key, job_key)
                
                # Save files for this job
                for file_num, file_col in enumerate(['read1', 'read2'], 1):
                    filename = row[file_col]
                    # Find the file in uploaded list
                    file_idx = raw_list.index(filename)
                    f = uploaded_files[file_idx]
                    
                    save_path = job_dir / secure_filename(f.filename)
                    f.save(str(save_path))
                    logger.debug(f"Saved {filename} to {save_path}")
                
                # Insert job into database
                JobService.create_job(user_info, job_info)
                
                # Submit to SLURM
                JobService.submit_to_slurm(user_key, job_info)
                
                jobs_created += 1
                job_key += 1
                
            except Exception as e:
                error_msg = f"Failed to create job '{row['jobs']}': {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        return jobs_created, errors
