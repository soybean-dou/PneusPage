#!/usr/bin/env python3.8

import os
import sys
import logging
from pathlib import Path
import pandas as pd
import subprocess
import zipfile
import json
import ast

# Import configuration
from config import Config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import db operations (only for standalone script usage)
import db as db_operations

def run_fastqc(file1,file2):
    if not(os.path.exists("./fastqc")):
        os.mkdir("./fastqc")
    
    command = ["fastqc","-o",f"./fastqc","-f","fastq",f"./{file1}",f"./{file2}"]
    subprocess.run(command, check=True)  

def read_qc(file1,file2):
    prefix1=file1.split(".")[0]
    prefix2=file2.split(".")[0]

    qcfile1=f"{prefix1}_fastqc.zip"
    qcfile2=f"{prefix2}_fastqc.zip"
    
    command = ["unzip",f"./fastqc/{qcfile1}","-d",f"./fastqc/"]
    subprocess.run(command, check=True)
    with open(os.path.join("fastqc",f"{prefix1}_fastqc","fastqc_data.txt"),"r") as f:
        data=[]
        flag=False
        for line in f :
            if ">>Adapter Content" in line:
                flag=True
            if flag:
                data.append(line)
    
    for d in data:
        if d.startswith("#"):
            header=d.lstrip("#").split("\t")
            continue
        cont=d.split("\t")    

    command = ["unzip",f"./fastqc/{qcfile2}","-d",f"./fastqc/"]
    subprocess.run(command, check=True) 
    return False

def run_trim(file1, file2):
    """Run Trimmomatic for read trimming."""
    try:
        file1_name = file1.split(".")[0]
        file2_name = file2.split(".")[0]
        
        command = [
            "java", "-jar", str(Config.TRIMMOMATIC_PATH),
            "PE", "-threads", str(Config.DEFAULT_THREADS),
            f"./{file1}", f"./{file2}",
            f"./{file1_name}_trim.fastq.gz", "./trim_R1_unpaired.fastq.gz",
            f"./{file2_name}_trim.fastq.gz", "./trim_R2_unpaired.fastq.gz",
            f"ILLUMINACLIP:{Config.TRIMMOMATIC_ADAPTERS}:2:30:10:2:True",
            "LEADING:3", "TRAILING:3", "MINLEN:36"
        ]
        subprocess.run(command, check=True)
        logger.info("Trimmomatic completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Trimmomatic failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error running Trimmomatic: {e}")
        raise  


def run_kraken2(file1, file2):
    """Run Kraken2 for species identification."""
    try:
        kraken_dir = Path("./kraken")
        kraken_dir.mkdir(exist_ok=True)
        
        command = (
            f"kraken2 --paired --threads {Config.DEFAULT_THREADS} "
            f"--db {Config.KRAKEN_DB_PATH} "
            f"--report ./kraken/result.kreport "
            f"./{file1} ./{file2} > ./kraken/kraken.txt"
        )
        subprocess.run(command, check=True, shell=True)
        
        command = [
            "bracken",
            "-d", str(Config.KRAKEN_DB_PATH),
            "-i", "./kraken/result.kreport",
            "-o", "./kraken/result.bracken",
            "-r", "100"
        ]
        subprocess.run(command, check=True)
        logger.info("Kraken2 completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"Kraken2 failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error running Kraken2: {e}")
        raise  

        
def run_spades(file1,file2):
    command = ["spades.py","-t","8","-1",f"./{file1}","-2",f"./{file2}","-o","./spades"]
    subprocess.run(command, check=True)  

def run_quast():
    """Run QUAST for assembly quality assessment."""
    try:
        command = [
            "quast.py",
            "./spades/scaffolds.fasta",
            "-m", str(Config.QUAST_MIN_CONTIG),
            "-r", str(Config.REFERENCE_GENOME),
            "-g", str(Config.REFERENCE_GTF),
            "-t", "4",
            "-o", "./quast"
        ]
        subprocess.run(command, check=True)
        logger.info("QUAST completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"QUAST failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error running QUAST: {e}")
        raise  

def run_prokka():
    command = ["prokka","-o","prokka","--force","--prefix","prokka","./spades/scaffolds.fasta"]
    subprocess.run(command, check=True)  

def run_MGE():
    if(os.path.exists("/tmp/mge_finder")):
        os.system("rm -r /tmp/mge_finder")
    if not(os.path.exists("./mge")):
        os.mkdir("./mge")
    command = ["mefinder","find","-c","./spades/scaffolds.fasta","--temp-dir","./mge/tmp","./mge/mge" ]
    subprocess.run(command, check=True)  

def run_cgMLST():
    """Run cgMLST for strain typing."""
    try:
        cgmlst_dir = Path("./cgMLST")
        cgmlst_dir.mkdir(exist_ok=True)
        
        command = [
            "cgMLST.py",
            "-i", "./spades/scaffolds.fasta",
            "-s", "spneumoniae",
            "-db", str(Config.CGMLST_DB_PATH),
            "-o", "./cgMLST"
        ]
        subprocess.run(command, check=True)
        logger.info("cgMLST completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"cgMLST failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error running cgMLST: {e}")
        raise  

def run_poppunk():
    """Run PopPUNK for global pneumococcal sequencing cluster assignment."""
    try:
        with open("path.txt", "w") as f:
            f.write("S1\t./spades/scaffolds.fasta\n")
        
        command = [
            "poppunk_assign",
            "--db", str(Config.POPPUNK_DB_PATH),
            "--distance", str(Config.POPPUNK_DIST_PATH),
            "--query", "path.txt",
            "--output", "poppunk",
            "--external-clustering", str(Config.POPPUNK_CLUSTERS_PATH),
            "--threads", str(Config.DEFAULT_THREADS)
        ]
        subprocess.run(command, check=True)
        logger.info("PopPUNK completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"PopPUNK failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error running PopPUNK: {e}")
        raise  

def run_virulencefinder():
    """Run VirulenceFinder for virulence gene detection."""
    try:
        vir_dir = Path("./virulence")
        vir_dir.mkdir(exist_ok=True)
        
        command = [
            "virulencefinder.py",
            "-i", "./spades/scaffolds.fasta",
            "-d", "s.pneumoniae",
            "-p", str(Config.VIRULENCEFINDER_DB_PATH),
            "-x",
            "-o", "./virulence"
        ]
        subprocess.run(command, check=True)
        logger.info("VirulenceFinder completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"VirulenceFinder failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error running VirulenceFinder: {e}")
        raise  


def run_abricate():
    if not(os.path.exists("./AMR")):
        os.mkdir("./AMR")
    command = "abricate --db card ./spades/scaffolds.fasta > ./AMR/abricate_result.tsv"
    subprocess.run(command, check=True, shell=True)  


def run_MLST():
    if not(os.path.exists("./mlst")):
        os.mkdir("./mlst")
    command = "mlst -csv -nopath --scheme spneumoniae ./spades/scaffolds.fasta > ./mlst/mlst.csv"
    subprocess.run(command, check=True, shell=True)

def run_plasmidfinder():
    if not(os.path.exists("./plasmid")):
        os.mkdir("./plasmid")
    #command = f"plasmidfinder.py -i ./{file1} ./{file2} -p /home/iu98/toolkit/plasmidfinder_db -o ./plasmid > ./plasmid/result.json"
    command = f"abricate --csv --nopath --quiet --db plasmidfinder spades/scaffolds.fasta > plasmid/plasmid.csv"
    
    subprocess.run(command, check=True, shell=True) 

def run_pbpfinder():
    """Run PBP finder for penicillin-binding protein typing."""
    try:
        job_path = os.path.abspath(os.curdir)
        logger.info(f"Running PBP finder in: {job_path}")
        
        os.chdir(str(Config.PBP_SCRIPT_DIR))
        command = [
            "cnpbp.sh",
            "-s", f"{job_path}/spades/scaffolds.fasta",
            "-n", "pbp",
            "-o", f"{job_path}/pbptyping"
        ]
        subprocess.run(command, check=True)
        os.chdir(job_path)
        
        # Parse output files
        with open("./pbptyping/pbp_final_result.tsv") as f:
            for line in f:
                if line.startswith(">PBP_Category"):
                    f1 = open("./pbptyping/pbp_Category.txt", "w")
                    f1.write(line.lstrip(">"))
                elif line.startswith(">Agent"):
                    f1.close()
                    f2 = open("./pbptyping/pbp_agent.txt", "w")
                    f2.write(line.lstrip(">"))
                    break
                else:
                    f1.write(line)
            for line in f:
                f2.write(line)
            f2.close()
        
        logger.info("PBP finder completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error(f"PBP finder failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Error running PBP finder: {e}")
        raise

def run_seroba(file1,file2):
    print(os.path.abspath(os.path.curdir))
    os.system(f"mv ./{file1} ./read_1.fq.gz")
    os.system(f"mv ./{file2} ./read_2.fq.gz")
    command = ["seroba","runSerotyping", f"./{file1}",f"./{file2}","seroba"]
    subprocess.run(command, check=True) 
    os.system(f"mv ./read_1.fq.gz ./{file1}")
    os.system(f"mv ./read_2.fq.gz ./{file2}")
    

def run_blast():
    if not(os.path.exists("./blast")):
        os.mkdir("./blast")
    command = ["blastn","-query","./spades/scaffolds.fasta","-db","nt"
                ,"-outfmt",'6 qseqid sseqid scomnames length qstart qend sstart send evalue pident',"-out","./blast/blast_result.txt"]
    subprocess.run(command, check=True)  

def get_species(user_key, job_key):
    """Get species identification from Kraken2 results."""
    try:
        path_name = Config.USER_DATA_DIR / str(user_key) / str(job_key)
        os.chdir(str(path_name))
        
        kraken_file = path_name / "kraken" / "result.bracken"
        if not kraken_file.exists():
            logger.warning(f"Kraken results not found for job {user_key}:{job_key}")
            return None
        
        kraken = pd.read_csv(str(kraken_file), sep="\t", keep_default_na=False)[0:5]
        species = kraken.iloc[0, 0]
        return species
    except Exception as e:
        logger.error(f"Error getting species: {e}")
        return None
    finally:
        os.chdir(str(Config.BASE_DIR))

def get_info(user_key,job_key):
    os.chdir("/home/iu98/pneumo_page")
    path_name="./user/"+user_key+"/"+job_key
    print(path_name)
    path_name=str(path_name)
    os.chdir(path_name)
    kraken=pd.read_csv(("./kraken/result.bracken"),sep="\t",keep_default_na=False)[0:5].applymap(str)
    species=kraken.iloc[0,0]
    
    quast=pd.read_csv(("./quast/transposed_report.tsv"),sep="\t",keep_default_na=False).applymap(str)
    quast=quast.loc[:,["# contigs","Largest contig","Total length","GC (%)","N50","N90"]]

    if species!="Streptococcus pneumoniae":
        return kraken, quast
    
    sero_txt=[]
    if os.path.exists("./seroba/detailed_serogroup_info.txt"):
        with open("./seroba/detailed_serogroup_info.txt","r") as f:
            for i in range(0,3):
                line=f.readline().rstrip("\n")
                line=line.replace("\t"," ")
                sero_txt.append(line)
        seroba=pd.read_csv(("./seroba/detailed_serogroup_info.txt"),sep="\t",skiprows=[0,1,2])
        sero_bool=True
    else :
        sero_txt.append(open("./seroba/pred.tsv").read().split("\t")[1])
        sero_bool=False
        seroba=False
    
    vir=pd.read_csv(("./virulence/results_tab.tsv"),sep="\t",keep_default_na=False).applymap(str)
    
    mlst=pd.read_csv("./mlst/mlst.csv",header=None).applymap(str)
    mlst.loc[1]=None
    mlst.iloc[1,2]=mlst.iloc[0,2]
    for i in range(3,len(mlst.columns)):
        print(mlst.iloc[0,i])
        mlst.iloc[1,i]=str(mlst.iloc[0,i]).split("(")[1].rstrip(")")
        mlst.iloc[0,i]=str(mlst.iloc[0,i]).split("(")[0]
    mlst=mlst.iloc[:,2:len(mlst.columns)]
    mlst_info=mlst.iloc[0,1:len(mlst.columns)].to_list()
    mlst_val=mlst.iloc[1,0:len(mlst.columns)].to_list()
    
    mge=pd.read_csv(("./mge/mge.csv"),skiprows=[0,1,2,3,4]).applymap(str)

    cgmlst=pd.read_csv(("./cgMLST/spneumoniae_summary.txt"),sep="\t").applymap(str)
    cgmlst.iloc[:,1:len(cgmlst.columns)]
    cgmlst=cgmlst[['cgST',"Total_number_of_loci","Number_of_called_alleles","%_Called_alleles","Allele_matches_in_cgST","%_Allele_matches"]]
    for col in cgmlst.columns:
        cgmlst.rename(columns={col:col.replace("_"," ")},inplace=True)
    
    kraken=pd.read_csv(("./kraken/result.bracken"),sep="\t",keep_default_na=False)[0:5].applymap(str)
    amr=pd.read_csv(("./AMR/abricate_result.tsv"),sep="\t",keep_default_na=False).applymap(str)
    amr=amr.loc[:,["SEQUENCE","START","END","STRAND","GENE","%COVERAGE","%IDENTITY","RESISTANCE"]]
    quast=pd.read_csv(("./quast/transposed_report.tsv"),sep="\t",keep_default_na=False).applymap(str)
    quast=quast.loc[:,["# contigs","Largest contig","Total length","GC (%)","N50","N90"]]
    prokka=pd.read_csv(("./prokka/prokka.tsv"),sep="\t",keep_default_na=False)[0:20].applymap(str)
    poppunk=pd.read_csv(("./poppunk/poppunk_external_clusters.csv"),keep_default_na=False,names=["sample","The Global Pneumococcal Sequencing Project Cluster"],header=0).applymap(str)
    poppunk=poppunk.loc[:,["The Global Pneumococcal Sequencing Project Cluster"]]
    plasmid=pd.read_csv(("./plasmid/plasmid.csv"),keep_default_na=False).applymap(str)
    plasmid=plasmid.loc[:,["SEQUENCE","START","END","STRAND","GENE","%COVERAGE","%IDENTITY","PRODUCT"]]
    
    pbp_category=pd.read_csv("./pbptyping/pbp_Category.txt",sep="\t")
    pbp_agent=pd.read_csv("./pbptyping/pbp_agent.txt",sep="\t")

    #with open("./plasmid/result.json") as j:
    #    data=j.read()
    #    plasmid=ast.literal_eval(data)
    #    plasmid=plasmid["plasmidfinder"]["results"]
    #blast=pd.read_excel(("./blast/blast_result_summary.xlsx"))
    #blast.columns = ['contig', 'top1', 'top2', 'top3', 'top4', 'top5']
    return species, quast, sero_bool, sero_txt, seroba, vir, mlst_info, mlst_val, mge, cgmlst, kraken, plasmid, amr, prokka, poppunk, pbp_category, pbp_agent

    
def run_pipeline(path_name, file1, file2, home_path=None):
    """
    Run complete analysis pipeline.
    
    Args:
        path_name: Path to job directory
        file1: Forward read file name
        file2: Reverse read file name
        home_path: Home directory to return to (defaults to Config.BASE_DIR)
    
    Returns:
        True if S. pneumoniae and full analysis completed, False otherwise
    """
    if home_path is None:
        home_path = str(Config.BASE_DIR)
    
    try:
        os.chdir(path_name)
        logger.info(f"Starting pipeline in: {path_name}")
        
        # Clean up old directories
        os.system("ls -l | grep ^d | awk '{print $NF}' | xargs rm -rf\n")
        
        # Run FastQC
        run_fastqc(file1, file2)
        
        # Run Kraken2 for species identification
        run_kraken2(file1, file2)
        
        # Check species
        kraken = pd.read_csv("./kraken/result.bracken", sep="\t", keep_default_na=False)[0:1]
        species = kraken.loc[0, "name"]
        logger.info(f"Identified species: {species}")
        
        # Always run assembly and QC
        run_spades(file1, file2)
        run_quast()
        
        # If not S. pneumoniae, stop here
        if species != "Streptococcus pneumoniae":
            logger.info(f"Not S. pneumoniae ({species}), stopping after basic assembly")
            return False
        
        # Full S. pneumoniae analysis
        logger.info("Running full S. pneumoniae analysis")
        run_seroba(file1, file2)
        run_prokka()
        run_poppunk()
        run_MGE()
        run_cgMLST()
        run_MLST()
        run_virulencefinder()
        run_abricate()
        run_plasmidfinder()
        run_pbpfinder()
        
        logger.info("Pipeline completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        raise
    finally:
        os.chdir(home_path)

def run_with_web(user_key, job_info):
    """
    Run pipeline and update database status.
    Called by SLURM job scheduler.
    
    Args:
        user_key: User identifier
        job_info: Dictionary with job_key, file1, file2
    """
    job_key = job_info["job_key"]
    
    try:
        path_name = Config.USER_DATA_DIR / str(user_key) / str(job_key)
        file1 = job_info["file1"]
        file2 = job_info["file2"]
        
        logger.info(f"Starting job {user_key}:{job_key}")
        
        # Update status to running
        db_operations.update_db(user_key, int(job_key), "running")
        
        # Run pipeline
        result = run_pipeline(str(path_name), file1, file2)
        
        if not result:
            logger.warning(f"Job {user_key}:{job_key} completed but not S. pneumoniae")
            db_operations.update_db(user_key, int(job_key), "complete")
        else:
            logger.info(f"Job {user_key}:{job_key} completed successfully")
            db_operations.update_db(user_key, int(job_key), "complete")
            
    except Exception as e:
        logger.error(f"Job {user_key}:{job_key} failed: {e}")
        db_operations.update_db(user_key, int(job_key), "fail")
        raise


if __name__ == '__main__':
    if len(sys.argv) < 5:
        print("Usage: run_pipeline.py <user_key> <job_key> <file1> <file2>")
        sys.exit(1)
    
    user_key = sys.argv[1]
    job_key = sys.argv[2]
    file1 = sys.argv[3]
    file2 = sys.argv[4]
    
    job_info = {
        "job_key": job_key,
        "file1": file1,
        "file2": file2
    }
    
    logger.info("=" * 80)
    logger.info("Starting S. pneumoniae analysis pipeline")
    logger.info(f"User: {user_key}, Job: {job_key}")
    logger.info(f"Files: {file1}, {file2}")
    logger.info("=" * 80)
    
    run_with_web(user_key, job_info)
    
    logger.info("=" * 80)
    logger.info("Pipeline execution completed")
    logger.info("=" * 80)