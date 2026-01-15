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
        if not db_operations.is_joined(id_info["user_key"]):
            db_operations.insert_user(id_info)
        
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
            
            job_key = db_operations.read_job_num(user_info['user_key'])
            app.logger.info(f"Creating job {job_key} for user {user_info['user_key']}")

            # Create job directory
            job_dir = app_config.USER_DATA_DIR / str(user_info['user_key']) / str(job_key)
            if job_dir.exists():
                app.logger.error(f"Job directory already exists: {job_dir}")
                flash("Job directory already exists. Please try again.")
                return redirect("/submit")
            
            job_dir.mkdir(parents=True, exist_ok=True)
            app.logger.info(f"Created job directory: {job_dir}")
            
            # Process uploaded files
            files = request.files.getlist("file[]")
            if not files or len(files) < 2:
                flash("Please upload both forward and reverse read files!")
                return redirect("/submit")
            
            job_info = {
                'user_key': user_info['user_key'],
                "jobname": jobname,
                "job_key": job_key,
                "file1": "NULL",
                "file2": "NULL"
            }
            
            # Save files
            for i, f in enumerate(files[:2]):  # Only take first 2 files
                if f and f.filename:
                    filename = secure_filename(f.filename)
                    filepath = job_dir / filename
                    f.save(str(filepath))
                    job_info[f'file{i+1}'] = filename
                    app.logger.debug(f"Saved file: {filename}")
            
            # Validate both files were uploaded
            if job_info['file1'] == "NULL" or job_info['file2'] == "NULL":
                flash("Both forward and reverse read files are required!")
                return redirect("/submit")
            
            # Insert job into database
            db_operations.insert_job(user_info, job_info)
            
            # Submit to SLURM
            run_slurm(user_info["user_key"], job_info)
            
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
        os.chdir("/home/iu98/pneumo_page")
        user_info={
            "user_key":session["user_key"],
            "username":session["name"]
            }
        
        if not os.path.exists("./user/"+str(user_info['user_key'])+"/multi"):
            os.system("mkdir ./user/"+str(user_info['user_key'])+"/multi")
            print("make ./user/"+str(user_info['user_key'])+"/multi")

        tsv =  request.files["file"]
        tsv.save(os.path.join(("./user/"+str(user_info['user_key'])),"multi",secure_filename(tsv.filename)))
        
        file_list=pd.read_table(os.path.join(("./user/"+str(user_info['user_key'])),"multi",secure_filename(tsv.filename)),sep="\t",names=["jobs","read1","read2"])
        print(file_list)
        raws =  request.files.getlist("file[]")
        raw_list=[]

        if raws:
            #파일이 모두 유효한 것들인지 확인
            for i in range(len(raws)):
                f=raws[i]
                print(list(file_list["read1"]))
                if f.filename in list(file_list["read1"]):
                    raw_list.append(f.filename)
                elif f.filename in list(file_list["read2"]):
                    raw_list.append(f.filename)
                else:
                    flash("Your file is invalid!") 
                    return redirect(f"/submit")
        else:
            flash("Your file is invalid!")    
            return redirect(f"/submit")

        job_key=db.read_job_num(user_info['user_key'])
        print("job key :",job_key)
        
        for i in range(len(file_list["jobs"])):
            print("job key :",job_key)
            job_info={'user_key':user_info['user_key'],
                    "jobname":file_list.iloc[i,0],
                    "job_key":job_key,
                    "file1":file_list.iloc[i,1],
                    "file2":file_list.iloc[i,2]
                }
            if not os.path.exists("./user/"+str(user_info['user_key'])+"/"+str(job_key)):
                os.system("mkdir ./user/"+str(user_info['user_key'])+"/"+str(job_key))
                print("make ./user/"+str(user_info['user_key'])+"/"+str(job_key))
            else :
                data = {'result': 'err'}
                return jsonpickle.encode(data)
            
            #if raws:
            idx=raw_list.index(job_info["file1"])
            f=raws[idx]
            f.save(os.path.join(("./user/"+str(user_info['user_key'])),str(job_key), secure_filename(f.filename)))

            idx=raw_list.index(job_info["file2"])
            f=raws[idx]
            f.save(os.path.join(("./user/"+str(user_info['user_key'])),str(job_key), secure_filename(f.filename)))
            
            for j in range(2):
                if job_info[f'file{str(j+1)}']=="NULL":
                    job_info[f'file{str(j+1)}']=secure_filename(f.filename)

            db.insert_job(user_info,job_info)
            run_slurm(user_info["user_key"],job_info)
            job_key+=1
                #data = {'result': 'success'} 
            #else:
            #    data = {'result': 'err'}
            #    return jsonpickle.encode(data)
            
        return redirect(f"/result/{str(user_info['user_key'])}")
    else:
        flash("your file is invalid!")    
        return redirect(f"/submit")



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
        
        # Check permission (admin can view all, others only their own)
        if (str(user_key) != session['user_key'] and 
            session['user_key'] not in app_config.ADMIN_USERS):
            flash("You do not have permission!")
            return redirect(f"/result/{session['user_key']}")
        
        # Get user's jobs
        db_info = db_operations.read_user_job(user_key)
        db_df = pd.DataFrame.from_records(
            data=db_info,
            columns=["user_key", "username", "job_num", "jobname", "input", "state", "date"]
        )
        db_df["species"] = ""
        
        # Get species for each job
        for job_id in db_df["job_num"]:
            species = rp.get_species(user_key, str(job_id))
            db_df.loc[db_df["job_num"] == job_id, "species"] = species if species else ""
        
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
def fastqc_download(user_key,job_key,file_name):
    os.chdir("/home/iu98/pneumo_page")
    file_name=file_name.split(".")[0]+"_fastqc.html"
    path=os.path.join("./user",user_key,str(job_key),"fastqc",file_name)
    return send_file(path, as_attachment=True)

@app.route('/result/<user_key>/<job_key>/assembled_fasta/download')
def assembled_fasta_download(user_key,job_key):
    os.chdir("/home/iu98/pneumo_page")
    path=os.path.join("./user",user_key,str(job_key),"spades","scaffolds.fasta")
    return send_file(path, as_attachment=True)

@app.route('/result/<user_key>/<job_key>/gene_anot/download')
def gene_annot_download(user_key,job_key):
    os.chdir("/home/iu98/pneumo_page")
    path=os.path.join("./user",user_key,str(job_key),"prokka","prokka.tsv")
    return send_file(path, as_attachment=True)

@app.route('/submit/tsv/download')
def ex_tsv_download():
    path=os.path.join(".","sample","file_list.tsv")
    return send_file(path, as_attachment=True)

@app.route('/submit/forward/download')
def ex_forward_download():
    path=os.path.join(".","sample","ERR11640752_1.fastq.gz")
    return send_file(path, as_attachment=True)

@app.route('/submit/reverse/download')
def ex_reverse_download():
    path=os.path.join(".","sample","ERR11640752_2.fastq.gz")
    return send_file(path, as_attachment=True)
    

@app.route('/mypage')
def mypage():
    try:
        if protected() == False:
            return redirect("/login")
        
        date_info = db_operations.read_user_db(session['user_key'])
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


def run_slurm(user_key, job_info):
    """Submit analysis job to SLURM scheduler."""
    try:
        job_dir = app_config.USER_DATA_DIR / str(user_key) / str(job_info["job_key"])
        sbatch_file = job_dir / "sbatch.sh"
        
        # Create SLURM batch script
        with open(sbatch_file, "w") as f:
            f.write("#!/bin/sh\n\n")
            f.write(f"#SBATCH -J pne_{job_info['job_key']}\n")
            f.write(f"#SBATCH --cpus-per-task={app_config.SLURM_CPUS}\n")
            f.write(f"#SBATCH --mem {app_config.SLURM_MEMORY}\n")
            f.write(f"#SBATCH -p {app_config.SLURM_PARTITION}\n")
            f.write(f"#SBATCH -o {job_info['job_key']}.out\n")
            f.write(f"#SBATCH -e {job_info['job_key']}.err\n\n")
            f.write(f"python {app_config.BASE_DIR}/run_pipeline.py ")
            f.write(f"{user_key} {job_info['job_key']} {job_info['file1']} {job_info['file2']}\n")
        
        # Submit to SLURM
        current_dir = os.getcwd()
        os.chdir(job_dir)
        result = os.system("sbatch sbatch.sh")
        os.chdir(current_dir)
        
        if result == 0:
            app.logger.info(f"Submitted job {job_info['job_key']} to SLURM")
        else:
            app.logger.error(f"Failed to submit job {job_info['job_key']} to SLURM")
        
    except Exception as e:
        app.logger.error(f"Error submitting to SLURM: {e}")


@app.route('/result/<user_key>/<job_key>/delete')
def delete_job(user_key, job_key):
    try:
        if protected() == False:
            return redirect("/login")
        
        # Check permission
        if str(user_key) != session['user_key']:
            flash("You do not have permission to delete this job!")
            return redirect(f"/result/{session['user_key']}")
        
        # Delete job directory
        job_dir = app_config.USER_DATA_DIR / str(user_key) / str(job_key)
        if job_dir.exists():
            import shutil
            shutil.rmtree(job_dir)
            app.logger.info(f"Deleted job directory: {job_dir}")
        
        # Delete from database
        db_operations.delete_user_job(user_key, int(job_key))
        
        flash(f"Job {job_key} deleted successfully.")
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

