# 리팩토링 요약 및 마이그레이션 가이드

## 📋 변경 사항 요약

### 1. 새로 추가된 파일

- **`config.py`** - 환경별 설정 관리 (Development/Production/Testing)
- **`models.py`** - SQLAlchemy ORM 모델 (User, Job)
- **`.env`** - 환경 변수 (민감한 정보 저장, .gitignore에 포함)
- **`.env.example`** - 환경 변수 템플릿
- **`README.md`** - 프로젝트 문서
- **`REFACTORING_SUMMARY.md`** - 이 파일

### 2. 백업된 파일

- **`db_old.py`** - 기존 db.py 백업 (안전을 위해 보관)

### 3. 주요 변경된 파일

#### **app.py**
**변경 전:**
```python
app.secret_key = "minory"  # 하드코딩된 비밀키
os.chdir("/home/iu98/pneumo_page")  # 여러 곳에 하드코딩된 경로
db.read_user_job(user_key)  # 직접 DB 함수 호출
```

**변경 후:**
```python
app.config.from_object(app_config)  # 설정 객체 사용
app_config.USER_DATA_DIR / str(user_key)  # Config 기반 경로
db_operations.read_user_job(user_key)  # 명확한 네이밍
```

**주요 개선:**
- ✅ 하드코딩된 비밀키 제거 → 환경변수로 관리
- ✅ 설정 관리 시스템 도입 (Config 클래스)
- ✅ 로깅 시스템 개선 (print → logging)
- ✅ 에러 처리 강화 (try-except 블록 추가)
- ✅ 경로 관리 개선 (하드코딩 → Config 사용)

#### **db.py**
**변경 전:**
```python
query = f"SELECT * FROM user WHERE user_key = '{user_key}'"  # SQL Injection 취약
c.execute(query)
```

**변경 후:**
```python
user = db.session.query(User).filter_by(user_key=user_key).first()  # ORM 사용
```

**주요 개선:**
- ✅ **SQL Injection 취약점 완전 제거**
- ✅ SQLAlchemy ORM 도입
- ✅ 커넥션 풀링 자동 관리
- ✅ 트랜잭션 관리 개선
- ✅ 타입 힌트 및 docstring 추가

#### **run_pipeline.py**
**변경 전:**
```python
command = ["java", "-jar", trimmomatic, ...]  # trimmomatic 환경변수 의존
os.chdir("/home/iu98/pneumo_page")  # 하드코딩된 경로
print("All Done!")  # print 사용
```

**변경 후:**
```python
command = ["java", "-jar", str(Config.TRIMMOMATIC_PATH), ...]  # Config 사용
os.chdir(str(Config.BASE_DIR))  # Config 기반 경로
logger.info("Pipeline completed successfully!")  # logging 사용
```

**주요 개선:**
- ✅ 하드코딩된 경로 제거
- ✅ Config 기반 도구 경로 관리
- ✅ 로깅 시스템 통합
- ✅ 에러 처리 강화
- ✅ 함수 docstring 추가

#### **requirements.txt**
**변경 전:**
```
Flask
google-auth
pandas
```

**변경 후:**
```
Flask>=2.3.0
Flask-SQLAlchemy>=3.0.0
SQLAlchemy>=2.0.0
python-dotenv>=1.0.0
...
```

**주요 개선:**
- ✅ 버전 명시로 재현성 향상
- ✅ SQLAlchemy 관련 패키지 추가
- ✅ python-dotenv 추가

## 🚀 마이그레이션 가이드

### Step 1: 환경 변수 설정

```bash
cd /home/iu98/pneumo_page

# .env 파일 편집
nano .env
```

**반드시 변경해야 할 항목:**
```bash
# 강력한 비밀키로 변경 (절대 공유하지 말 것!)
SECRET_KEY=your-super-secret-key-here

# 프로덕션 환경이면 변경
FLASK_ENV=production
FLASK_DEBUG=False

# Google OAuth 설정 확인
GOOGLE_REDIRECT_URI=https://pneuspage.minholee.net/callback
```

### Step 2: 패키지 설치

```bash
# Mamba 환경 생성 및 활성화 (권장)
mamba env create -f environment.yml
mamba activate pneumo_page

# 또는 Conda 사용
conda env create -f environment.yml
conda activate pneumo_page

# 또는 기존 환경에서 pip으로 설치
pip install -r requirements.txt
```

### Step 3: 데이터베이스 확인

```bash
# 기존 데이터베이스가 있다면 ORM과 호환되는지 확인
python -c "
from app import app, db
with app.app_context():
    db.create_all()  # 테이블이 없으면 생성
    print('Database initialized successfully!')
"
```

### Step 4: 테스트 실행

```bash
# 개발 모드로 실행
export FLASK_ENV=development
python app.py
```

브라우저에서 `http://localhost:5000` 접속하여 다음 확인:
- [ ] 로그인 페이지 표시
- [ ] Google OAuth 로그인 작동
- [ ] 기존 작업 목록 표시
- [ ] 새 작업 제출 가능

### Step 5: 프로덕션 배포

```bash
# .env를 프로덕션 설정으로 변경
FLASK_ENV=production
FLASK_DEBUG=False

# Gunicorn으로 실행 (권장)
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## ⚠️ 주의사항

### 1. 백워드 호환성

- ✅ 기존 데이터베이스와 **완전히 호환됨**
- ✅ 기존 사용자 데이터 유지
- ✅ 기존 작업 기록 유지
- ⚠️ `db_old.py`는 당분간 보관 (롤백 가능)

### 2. 환경 변수

**절대 커밋하지 말 것:**
- `.env` 파일
- `client_secret.json` 파일
- `pneumo_service.db` 파일

**커밋해야 할 것:**
- `.env.example` 파일
- 모든 `.py` 파일
- `requirements.txt`

### 3. 보안

```bash
# 민감한 파일 권한 설정
chmod 600 .env
chmod 600 client_secret.json
chmod 600 pneumo_service.db

# 비밀키 생성 (강력한 랜덤 키)
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. 로그 확인

```bash
# 애플리케이션 로그 확인
tail -f logs/pneuspage.log

# SLURM 작업 로그 확인
tail -f user/<user_id>/<job_id>/<job_id>.err
```

## 🐛 문제 해결

### 문제: Import 에러

```python
ImportError: No module named 'config'
```

**해결:**
```bash
# Mamba 사용 (권장)
mamba install python-dotenv Flask-SQLAlchemy

# 또는 pip 사용
pip install -r requirements.txt
```

### 문제: 데이터베이스 연결 실패

```python
sqlalchemy.exc.OperationalError: unable to open database file
```

**해결:**
```bash
# 데이터베이스 파일 경로 확인
ls -la pneumo_service.db

# 권한 확인
chmod 644 pneumo_service.db

# 재생성
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

### 문제: OAuth 실패

```
OAuth flow not initialized
```

**해결:**
```bash
# client_secret.json 파일 존재 확인
ls -la client_secret.json

# .env에서 경로 확인
grep GOOGLE_CLIENT_SECRETS_FILE .env
```

### 문제: 경로 오류

```
FileNotFoundError: [Errno 2] No such file or directory: '/home/iu98/pneumo_page/...'
```

**해결:**
```bash
# .env 파일에서 BASE_DIR 확인
nano .env

# 필요한 디렉토리 생성
mkdir -p logs user reference sample
```

## 📊 성능 개선 사항

| 항목 | 변경 전 | 변경 후 |
|------|---------|---------|
| SQL Injection | ❌ 취약 | ✅ 안전 |
| DB 커넥션 | 매번 생성/삭제 | 풀링 사용 |
| 에러 처리 | 거의 없음 | 포괄적 |
| 로깅 | print() 사용 | logging 모듈 |
| 설정 관리 | 하드코딩 | 환경변수 |
| 코드 가독성 | 중 | 상 |

## 📈 다음 단계 (Phase 2 이후)

Phase 1에서 완료한 보안 및 기본 구조 개선 후, 다음 단계로 진행 가능:

1. **서비스 레이어 분리** - 비즈니스 로직을 라우트에서 분리
2. **비동기 작업 큐** - Celery 도입으로 파이프라인 작업 관리
3. **API 엔드포인트** - RESTful API 추가
4. **테스트 코드** - 단위 테스트 및 통합 테스트
5. **프론트엔드 개선** - 모던 JavaScript 프레임워크 도입

## 📞 도움이 필요하면

1. 로그 파일 확인: `logs/pneuspage.log`
2. 에러 메시지 전체 복사
3. 실행 환경 정보 확인:
   ```bash
   python --version
   mamba list | grep -E "(Flask|SQLAlchemy|python-dotenv)"
   # 또는
   pip list | grep -E "(Flask|SQLAlchemy|python-dotenv)"
   ```

## ✅ 체크리스트

마이그레이션 완료 전 확인사항:

- [ ] `.env` 파일 생성 및 설정 완료
- [ ] `SECRET_KEY` 변경 완료
- [ ] Mamba/Conda 환경 생성 및 패키지 설치 완료
- [ ] 데이터베이스 정상 작동 확인
- [ ] Google OAuth 로그인 테스트 완료
- [ ] 기존 데이터 정상 표시 확인
- [ ] 새 작업 제출 테스트 완료
- [ ] 로그 파일 정상 생성 확인
- [ ] 파일 권한 설정 완료 (`.env`, `client_secret.json`)
- [ ] 프로덕션 환경 설정 검토 완료

---

**리팩토링 완료일**: 2026년 1월 16일  
**주요 변경**: Phase 1 - 보안 강화 및 ORM 도입
