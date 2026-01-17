# Pneumo Page - S. pneumoniae Genome Analysis Pipeline

Web-based bioinformatics pipeline for *Streptococcus pneumoniae* whole genome sequencing data analysis.

## 🔄 Recent Refactoring (Phase 1)

This codebase has been recently refactored with the following improvements:

### ✅ Security Enhancements
- **Eliminated SQL Injection vulnerabilities** - All database queries now use SQLAlchemy ORM with parameterized queries
- **Externalized secrets** - Secret key and sensitive configurations moved to environment variables
- **Path sanitization** - Hardcoded paths replaced with configuration-based paths

### ✅ Code Quality
- **ORM Implementation** - Added SQLAlchemy models for User and Job tables
- **Configuration Management** - Centralized config with environment-specific settings (dev/prod/test)
- **Error Handling** - Added comprehensive try-catch blocks and logging
- **Logging System** - Replaced print statements with proper logging framework

### ✅ Maintainability
- **Separation of Concerns** - Database operations isolated in db.py
- **Type Safety** - Added type hints and docstrings
- **Code Documentation** - Comprehensive inline documentation

## 📋 Prerequisites

- Python 3.8+
- Bioinformatics tools:
  - FastQC
  - Trimmomatic
  - Kraken2/Bracken
  - SPAdes
  - QUAST
  - Prokka
  - Seroba
  - PopPUNK
  - MEFinder
  - cgMLST
  - MLST
  - VirulenceFinder
  - ABRicate
  - PBP typing tools
- SLURM job scheduler (for HPC deployment)

## 🚀 Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd pneumo_page
```

2. **Create and activate conda/mamba environment**
```bash
# Using mamba (recommended - faster)
mamba env create -f environment.yml
mamba activate pneumo_page

# Or using conda
conda env create -f environment.yml
conda activate pneumo_page

# Alternative: Install with pip only
pip install -r requirements.txt
```

3. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
nano .env
```

4. **Set up Google OAuth**
   - Create a project in Google Cloud Console
   - Enable Google+ API
   - Create OAuth 2.0 credentials
   - Download `client_secret.json` to project root

5. **Initialize database**
```bash
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

6. **Create necessary directories**
```bash
mkdir -p logs user reference sample
```

## ⚙️ Configuration

Edit the `.env` file to configure:

- **Flask settings**: SECRET_KEY, FLASK_ENV, FLASK_DEBUG
- **Database**: DATABASE_NAME or DATABASE_URL
- **Google OAuth**: GOOGLE_CLIENT_SECRETS_FILE, GOOGLE_REDIRECT_URI
- **Pipeline tools**: Paths to bioinformatics tools and databases
- **SLURM**: Partition, CPUs, memory allocation
- **Admin users**: Comma-separated list of admin user keys

## 🏃 Running the Application

### Development Mode
```bash
export FLASK_ENV=development
python app.py
```

### Production Mode
```bash
export FLASK_ENV=production
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 📁 Project Structure

```
pneumo_page/
├── app.py                 # Flask application and routes
├── config.py              # Configuration management
├── models.py              # SQLAlchemy ORM models
├── db.py                  # Database operations
├── run_pipeline.py        # Bioinformatics pipeline
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (create from .env.example)
├── .env.example           # Environment template
├── templates/             # HTML templates
├── static/                # CSS, JS, images
├── logs/                  # Application logs
├── user/                  # User data and analysis results
└── reference/             # Reference genome files
```

## 🔐 Security Notes

1. **Never commit `.env` or `client_secret.json`** to version control
2. **Change SECRET_KEY** in production - use a strong random key:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
3. **Use HTTPS in production** - OAuth requires secure connections
4. **Set proper file permissions** on sensitive files:
   ```bash
   chmod 600 .env client_secret.json
   ```

## 🧪 Database Migration

If you have an existing database from the old version:

```python
# The new ORM models are backward compatible with the old schema
# Just ensure your database has the correct table structure
python -c "
from app import app, db
with app.app_context():
    db.create_all()  # Creates tables if they don't exist
"
```

## 📊 Analysis Pipeline

For each submitted job, the pipeline performs:

1. **Quality Control** - FastQC
2. **Species Identification** - Kraken2/Bracken
3. **Assembly** - SPAdes
4. **Assembly QC** - QUAST

For *S. pneumoniae* samples, additional analyses:
- Serotyping (Seroba)
- Gene annotation (Prokka)
- MLST typing
- cgMLST typing
- Virulence genes (VirulenceFinder)
- AMR genes (ABRicate)
- Plasmid detection
- PBP typing
- Global cluster assignment (PopPUNK GPS)
- Mobile genetic elements

## 🐛 Troubleshooting

### Database Issues
```bash
# Check database connection
python -c "from app import app, db; app.app_context().push(); print(db.engine)"

# Reset database (WARNING: deletes all data)
rm pneumo_service.db
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

### OAuth Issues
- Verify `client_secret.json` is present
- Check redirect URI matches Google Console settings
- In development, `OAUTHLIB_INSECURE_TRANSPORT=1` is set automatically

### Pipeline Failures
- Check logs in `logs/pneuspage.log`
- Check SLURM job output: `user/<user_id>/<job_id>/<job_id>.err`
- Verify all bioinformatics tools are in PATH

## 📝 TODO (Future Enhancements)

- [ ] Add unit tests
- [ ] Implement async task queue (Celery)
- [ ] Add API endpoints
- [ ] Improve error messages
- [ ] Add data visualization
- [ ] Implement user roles/permissions
- [ ] Add batch download functionality

## 📄 License

[Add your license here]

## 👥 Contributors

[Add contributors here]

## 📧 Contact

[Add contact information here]
