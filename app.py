import os
import sys
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler

import requests
import pandas as pd
import numpy as np
import jsonpickle
from flask import Flask, redirect, request, url_for, jsonify, render_template, abort, session, send_file, flash
from flask_bootstrap import Bootstrap
from werkzeug.utils import secure_filename
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests

# Import application modules
from config import Config, get_config
from models import db, User, Job
import db as db_operations
import run_pipeline as rp
from services import UserService, JobService

# Initialize Flask app
app = Flask(__name__)

# Load configuration
config_name = os.getenv('FLASK_ENV', 'development')
app_config = get_config(config_name)
app.config.from_object(app_config)

# Initialize configuration
app_config.init_app(app)

# Initialize database
db.init_app(app)

# Setup logging
if not app.debug:
    app_config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        app_config.LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(app_config.LOG_FORMAT))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Pneumo Page startup')
else:
    logging.basicConfig(
        filename=str(app_config.LOG_FILE),
        level=logging.DEBUG,
        format=app_config.LOG_FORMAT
    )

# Allow HTTP for OAuth in development only
if app.debug:
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# Initialize Google OAuth Flow
try:
    flow = Flow.from_client_secrets_file(
        client_secrets_file=str(app_config.GOOGLE_CLIENT_SECRETS_FILE),
        scopes=app_config.GOOGLE_SCOPES,
        redirect_uri=app_config.GOOGLE_REDIRECT_URI
    )
except Exception as e:
    app.logger.error(f"Failed to initialize OAuth flow: {e}")
    flow = None

@app.route("/login")  #the page where the user can login
def login():
    if protected():
        is_logined=True
    else:
        is_logined=False 
    return render_template('login.html',login=is_logined)

@app.route("/login/google")  #the page where the user can login
def login_with_google():
    authorization_url, state = flow.authorization_url()  #asking the flow class for the authorization (login) url
    session["state"] = state
    return redirect(authorization_url)


@app.route("/callback")  # OAuth callback handler
def callback():
    try:
        if flow is None:
            app.logger.error("OAuth flow not initialized")
            flash("Authentication system error. Please contact administrator.")
            return redirect("/")
        
        flow.fetch_token(authorization_response=request.url)

        if not session.get("state") == request.args.get("state"):
            app.logger.warning("OAuth state mismatch")
            abort(500)  # State does not match!

        credentials = flow.credentials
        CLIENT_ID = flow.client_config["client_id"]
        request_session = requests.session()
        cached_session = cachecontrol.CacheControl(request_session)
        token_request = google.auth.transport.requests.Request(session=cached_session)

        id_info = id_token.verify_oauth2_token(
            id_token=credentials._id_token,
            request=token_request,
            audience=CLIENT_ID
        )

        # Store user info in session
        id_info["user_key"] = id_info["sub"]
        session["user_info"] = id_info
        session["user_key"] = id_info["sub"]
        session["email"] = id_info.get("email")
        session["name"] = id_info.get("name")
        
        app.logger.info(f"User logged in: {id_info.get('email')}")
        
        # Create user if not exists
        if not UserService.is_user_registered(id_info["user_key"]):
            UserService.create_user(id_info)
        
        return redirect("/")
        
    except Exception as e:
        app.logger.error(f"OAuth callback error: {e}")
        flash("Login failed. Please try again.")
        return redirect("/")


@app.route("/logout")  #the logout page and function
def logout():
    print("logout")
    session.clear()
    return redirect("/")

def protected():
    user_info = session.get('user_info')
    if user_info:
        return user_info["user_key"]
    return False

@app.route('/')
def index():
    if protected()!=False:
        print("login")
        return render_template('index.html',login=True,user_key=session["user_key"])
    else:
        print("logout")
        return render_template('index.html',login=False)

@app.route('/doc')
def about():
    if protected()!=False:
        print("login")
        return render_template('doc.html',login=True,user_key=session["user_key"])
    else:
        print("logout")
        return render_template('doc.html',login=False)

@app.route('/submit')
def submit():
    if protected()!=False:
        print("login")
        return render_template('submit.html',login=True,user_key=session["user_key"])
    else:
        print("logout")
        return render_template('submit.html',login=False)

@app.route('/upload', methods=['POST'])
def upload():
    if request.method == 'POST':
        try:
            user_info = {
                "user_key": session["user_key"],
                "username": session["name"]
            }
            
            jobname = request.form.get('jobname')
            if not jobname:
                flash("Job name is required!")
                return redirect("/submit")
            
            # Get next job number
            job_key = JobService.get_next_job_number(user_info['user_key'])
            app.logger.info(f"Creating job {job_key} for user {user_info['user_key']}")

            # Create job directory
            try:
                job_dir = JobService.create_job_directory(user_info['user_key'], job_key)
            except FileExistsError:
                flash("Job directory already exists. Please try again.")
                return redirect("/submit")
            
            # Process uploaded files
            files = request.files.getlist("file[]")
            try:
                saved_files = JobService.save_uploaded_files(job_dir, files)
            except ValueError as e:
                flash(str(e))
                return redirect("/submit")
            
            # Create job info
            job_info = {
                'user_key': user_info['user_key'],
                "jobname": jobname,
                "job_key": job_key,
                "file1": saved_files['file1'],
                "file2": saved_files['file2']
            }
            
            # Insert job into database
            JobService.create_job(user_info, job_info)
            
            # Submit to SLURM
            JobService.submit_to_slurm(user_info["user_key"], job_info)
            
            flash(f"Job '{jobname}' submitted successfully!")
            return redirect(f"/result/{str(user_info['user_key'])}")
            
        except KeyError as e:
            app.logger.error(f"Missing session key: {e}")
            flash("Please log in to submit jobs.")
            return redirect("/login")
        except Exception as e:
            app.logger.error(f"Upload error: {e}")
            flash("An error occurred while uploading your files. Please try again.")
            return redirect("/submit")
    
    return redirect("/submit")

@app.route('/uploadMulti', methods=['POST'])
def upload_multi():
    if request.method == 'POST':
        try:
            user_info = {
                "user_key": session["user_key"],
                "username": session["name"]
            }
            
            # Create multi directory for TSV file
            multi_dir = JobService.create_multi_directory(user_info['user_key'])
            
            # Save TSV file
            tsv = request.files["file"]
            if not tsv or not tsv.filename:
                flash("File list TSV is required!")
                return redirect("/submit")
            
            from werkzeug.utils import secure_filename
            tsv_path = multi_dir / secure_filename(tsv.filename)
            tsv.save(str(tsv_path))
            
            # Read file list from TSV
            file_list = pd.read_table(
                tsv_path,
                sep="\t",
                names=["jobs", "read1", "read2"]
            )
            app.logger.info(f"Processing batch upload with {len(file_list)} jobs")
            
            # Get uploaded raw files
            raws = request.files.getlist("file[]")
            if not raws:
                flash("No read files uploaded!")
                return redirect("/submit")
            
            # Process batch upload
            try:
                jobs_created, errors = JobService.process_batch_upload(
                    user_info['user_key'],
                    user_info['username'],
                    file_list,
                    raws
                )
                
                if errors:
                    for error in errors:
                        flash(error)
                
                if jobs_created > 0:
                    flash(f"Successfully created {jobs_created} jobs!")
                else:
                    flash("No jobs were created. Check errors above.")
                
            except ValueError as e:
                flash(str(e))
                return redirect("/submit")
            
            return redirect(f"/result/{str(user_info['user_key'])}")
            
        except KeyError as e:
            app.logger.error(f"Missing session key: {e}")
            flash("Please log in to submit jobs.")
            return redirect("/login")
        except Exception as e:
            app.logger.error(f"Batch upload error: {e}")
            flash("An error occurred during batch upload. Please try again.")
            return redirect("/submit")
    else:
        flash("Invalid request!")
        return redirect("/submit")



@app.route('/result/')
def result_first():
    if protected()!=False:
        return redirect(f"/result/{session['user_key']}")
    else:
        return redirect("/") 

@app.route('/result/<user_key>')
def result(user_key):
    try:
        if protected() == False:
            return redirect("/")
        
        # Check permission
        if not UserService.can_access_user_data(session['user_key'], user_key):
            flash("You do not have permission!")
            return redirect(f"/result/{session['user_key']}")
        
        # Get user's jobs
        db_df = JobService.get_user_jobs(user_key)
        
        return render_template('result.html', rows=db_df, login=True, user_id=user_key)
        
    except Exception as e:
        app.logger.error(f"Error displaying results: {e}")
        flash("Error loading results.")
        return redirect("/") 
    

@app.route('/result/<user_key>/<job_key>')
def detail(user_key, job_key):
    try:
        is_logined = protected() != False
        
        if not is_logined:
            return redirect("/")
        
        # Check permission
        if not UserService.can_access_user_data(session.get('user_key', ''), user_key):
            flash("You do not have permission!")
            return redirect("/")
        
        # Get job information
        db_info, cols = db_operations.read_db_row(user_key, int(job_key))
        
        if not db_info:
            flash("Job not found.")
            return redirect(f"/result/{user_key}")
        
        data_df = pd.DataFrame.from_records(data=db_info, columns=cols)
        files = data_df["input"][0].split("|")
        species = rp.get_species(user_key, job_key)
        
        # If not S. pneumoniae, show basic results only
        if species != "Streptococcus pneumoniae":
            kraken, quast = rp.get_info(user_key, job_key)
            return render_template(
                'detail.html',
                login=is_logined,
                kraken=kraken,
                species=species,
                key=job_key,
                user_id=user_key,
                files=files,
                rows=db_info,
                quast=quast
            )
        
        # Get full analysis results for S. pneumoniae
        (species, quast, sero_bool, sero_txt, seroba, vir, mlst_info, mlst_val,
         mge, cgmlst, kraken, plasmid, amr, prokka, poppunk,
         pbp_category, pbp_agent) = rp.get_info(user_key, job_key)
        
        # Fix column name if needed
        if "stop" in mge.columns:
            mge.rename(columns={"stop": "end"}, inplace=True)
        
        mge = mge.drop(columns=["contig", "start", "end"], axis=1, errors='ignore')
        
        return render_template(
            'detail.html',
            login=is_logined,
            species=species,
            key=job_key,
            user_id=user_key,
            files=files,
            rows=db_info,
            sero_txt=sero_txt,
            seroba=seroba,
            vir=vir,
            mlst_info=mlst_info,
            mlst_val=mlst_val,
            mge=mge,
            cgmlst=cgmlst,
            kraken=kraken,
            plasmid=plasmid,
            amr=amr,
            quast=quast,
            prokka=prokka,
            poppunk=poppunk,
            sero_bool=sero_bool,
            pbp_category=pbp_category,
            pbp_agent=pbp_agent
        )
        
    except Exception as e:
        app.logger.error(f"Error displaying job details: {e}")
        flash("Error loading job details.")
        return redirect(f"/result/{user_key}")

@app.route('/result/<user_key>/<job_key>/fastqc/<file_name>/download')
def fastqc_download(user_key, job_key, file_name):
    try:
        # Check permission
        if not UserService.can_access_user_data(session.get('user_key', ''), user_key):
            flash("You do not have permission!")
            return redirect("/")
        
        file_name = file_name.split(".")[0] + "_fastqc.html"
        path = app_config.USER_DATA_DIR / user_key / str(job_key) / "fastqc" / file_name
        
        if not path.exists():
            flash("File not found.")
            return redirect(f"/result/{user_key}/{job_key}")
        
        return send_file(str(path), as_attachment=True)
    except Exception as e:
        app.logger.error(f"Download error: {e}")
        flash("Error downloading file.")
        return redirect(f"/result/{user_key}/{job_key}")

@app.route('/result/<user_key>/<job_key>/assembled_fasta/download')
def assembled_fasta_download(user_key, job_key):
    try:
        # Check permission
        if not UserService.can_access_user_data(session.get('user_key', ''), user_key):
            flash("You do not have permission!")
            return redirect("/")
        
        path = app_config.USER_DATA_DIR / user_key / str(job_key) / "spades" / "scaffolds.fasta"
        
        if not path.exists():
            flash("File not found.")
            return redirect(f"/result/{user_key}/{job_key}")
        
        return send_file(str(path), as_attachment=True)
    except Exception as e:
        app.logger.error(f"Download error: {e}")
        flash("Error downloading file.")
        return redirect(f"/result/{user_key}/{job_key}")

@app.route('/result/<user_key>/<job_key>/gene_anot/download')
def gene_annot_download(user_key, job_key):
    try:
        # Check permission
        if not UserService.can_access_user_data(session.get('user_key', ''), user_key):
            flash("You do not have permission!")
            return redirect("/")
        
        path = app_config.USER_DATA_DIR / user_key / str(job_key) / "prokka" / "prokka.tsv"
        
        if not path.exists():
            flash("File not found.")
            return redirect(f"/result/{user_key}/{job_key}")
        
        return send_file(str(path), as_attachment=True)
    except Exception as e:
        app.logger.error(f"Download error: {e}")
        flash("Error downloading file.")
        return redirect(f"/result/{user_key}/{job_key}")

@app.route('/submit/tsv/download')
def ex_tsv_download():
    path = app_config.BASE_DIR / "sample" / "file_list.tsv"
    return send_file(str(path), as_attachment=True)

@app.route('/submit/forward/download')
def ex_forward_download():
    path = app_config.BASE_DIR / "sample" / "ERR11640752_1.fastq.gz"
    return send_file(str(path), as_attachment=True)

@app.route('/submit/reverse/download')
def ex_reverse_download():
    path = app_config.BASE_DIR / "sample" / "ERR11640752_2.fastq.gz"
    return send_file(str(path), as_attachment=True)
    

@app.route('/mypage')
def mypage():
    try:
        if protected() == False:
            return redirect("/login")
        
        date_info = UserService.get_user_info(session['user_key'])
        join_date = date_info['date'] if date_info else 'Unknown'
        
        return render_template(
            'mypage.html',
            username=session["name"],
            email=session["email"],
            join_date=join_date
        )
    except Exception as e:
        app.logger.error(f"Error loading mypage: {e}")
        flash("Error loading your profile.")
        return redirect("/")


@app.route('/result/<user_key>/<job_key>/delete')
def delete_job(user_key, job_key):
    try:
        if protected() == False:
            return redirect("/login")
        
        # Check permission
        if str(user_key) != session['user_key']:
            flash("You do not have permission to delete this job!")
            return redirect(f"/result/{session['user_key']}")
        
        # Delete job
        if JobService.delete_job(user_key, int(job_key)):
            flash(f"Job {job_key} deleted successfully.")
        else:
            flash(f"Failed to delete job {job_key}.")
        
        return redirect(f"/result/{session['user_key']}")
        
    except Exception as e:
        app.logger.error(f"Error deleting job: {e}")
        flash("Error deleting job.")
        return redirect(f"/result/{session['user_key']}")


if __name__ == '__main__':
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
    
    app.run(debug=app.debug, host='0.0.0.0', port=5000)

