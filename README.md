# BE_repository

## 프로젝트 구조

현재 저장소는 Django 공통 설정과 회원 모델까지 구성한 초기 개발환경이다.
아래 구조는 실제 생성된 파일 기준이며, 토론·의견·보상 앱은 아직 만들지 않았다.

```text
BE_repository/                 # 클론한 폴더 이름은 각자 다를 수 있음
├── config/                    # 프로젝트 전체 설정
│   ├── settings.py            # 앱 등록, 환경변수, PostgreSQL, 회원 모델 지정
│   ├── urls.py                # 전체 URL 연결 (/health/, /admin/)
│   ├── views.py               # 서버·DB 연결 상태 확인
│   ├── asgi.py                # ASGI 실행 진입점
│   └── wsgi.py                # WSGI 실행 진입점
├── accounts/                  # 회원 기능 앱
│   ├── migrations/
│   │   └── 0001_initial.py    # users 테이블 생성 기록
│   ├── models.py              # User와 UserManager
│   ├── apps.py                # 앱 등록 정보
│   ├── admin.py               # 관리자 설정 위치 (현재 회원 등록 코드 없음)
│   ├── views.py               # 회원 API 작성 위치 (아직 미구현)
│   ├── tests.py               # 회원 테스트 작성 위치 (아직 미작성)
│   └── README.md              # 회원 모델 구현 결정과 남은 작업
├── manage.py                  # Django 관리 명령 진입점
├── requirements.txt           # Python 패키지 버전
├── Dockerfile                 # Django 컨테이너 이미지 정의
├── compose.yaml               # 로컬 api·db 서비스와 DB 볼륨 정의
├── .dockerignore              # 이미지 빌드에서 제외할 파일
├── .gitignore                 # Git에서 제외할 파일
├── .env.example               # 공유용 환경변수 예시
├── .env                       # 각자 생성할 실제 로컬 설정 (Git 제외)
└── README.md
```

`config`는 전체 프로젝트 설정을 담당하고 `accounts`는 회원 기능을 담당한다.
현재 앱은 프로젝트 루트에 위치한다. `apps/` 폴더 아래로 묶는 구조는 아직 적용하지 않았다.
로컬의 `.venv`와 기존 `db.sqlite3`는 공유 대상이 아니며, Docker 실행은 PostgreSQL을 사용한다.

## 유저 모델

구현 위치는 [accounts/models.py](accounts/models.py)다.
`User`는 `AbstractBaseUser`를 상속하며 DB 테이블 이름은 `users`다.
`config/settings.py`에서 `AUTH_USER_MODEL = 'accounts.User'`로 지정한다.

### 필드

| Python 필드 | DB 컬럼 | 자료형·조건 | 의미 |
|---|---|---|---|
| `id` | `id` | `BigAutoField`, 기본키 | 자동 발급 내부 회원 ID |
| `email` | `email` | `EmailField(255)`, 필수, 고유 제약 없음 | 이메일 |
| `password` | `password_hash` | `CharField(255)`, NULL 허용 | Django 비밀번호 해시 또는 비밀번호 사용 불가 표식 |
| `provider` | `provider` | `CharField(20)`, NULL 허용 | 소셜 로그인 제공자 |
| `provider_id` | `provider_id` | `CharField(255)`, NULL 허용 | 제공자가 발급한 회원 식별자 |
| `nickname` | `nickname` | `CharField(30)`, 필수, 고유 제약 없음 | 닉네임 |
| `profile_image_url` | `profile_image_url` | `URLField(500)`, NULL 허용 | 프로필 이미지 URL |
| `gender` | `gender` | `M` / `F` / `OTHER`, NULL 허용 | 선택 입력 성별 |
| `birth_year` | `birth_year` | `IntegerField`, NULL 허용 | 선택 입력 출생 연도 |
| `region` | `region` | `CharField(30)`, NULL 허용 | 선택 입력 지역 |
| `credit` | `credit` | `IntegerField`, 기본값 0 | 크레딧 저장값 |
| `coin_balance` | `coin_balance` | `IntegerField`, 기본값 0 | 코인 잔액 |
| `notification_enabled` | `notification_enabled` | `BooleanField`, 기본값 True | 알림 수신 여부 |
| `status` | `status` | `ACTIVE` / `SUSPENDED` / `DELETED`, 기본값 ACTIVE | 회원 상태 |
| `created_at` | `created_at` | `DateTimeField`, 생성 시 자동 기록 | 가입 시각 |
| `updated_at` | `updated_at` | `DateTimeField`, 일반적인 `save()` 시 자동 갱신 | 수정 시각 |
| `deleted_at` | `deleted_at` | `DateTimeField`, NULL 허용 | 탈퇴 시각; 탈퇴 처리에서 별도 기록 필요 |

위의 필수/선택 및 선택값은 모델 정의 기준이다. API 입력 검증과 상태 변경 처리는 별도 구현이 필요하다.
현재 잔액 음수 방지, 크레딧 범위, 소셜 계정 중복 방지에 대한 DB 제약은 추가하지 않았다.

### 회원 생성과 상태 처리

회원 생성은 `UserManager.create_user()`를 사용한다.
컨테이너에서 `docker compose exec api python manage.py shell`을 연 뒤 다음과 같이 호출할 수 있다.
이 예시는 회원을 실제 DB에 저장하므로 개발용 계정이 필요할 때만 실행한다.

```python
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.create_user(
    email="developer@example.com",
    nickname="개발자",
)
```

- `create_user()`는 이메일과 닉네임이 비어 있으면 거절하고 이메일 도메인을 정규화한다.
- 비밀번호를 생략하면 `set_password(None)`을 통해 비밀번호 로그인이 불가능한 표식을 저장한다.
  비밀번호를 전달하면 Django 방식으로 해시한다. 이메일/비밀번호 로그인 API는 아직 없다.
- `USERNAME_FIELD`는 내부 기본키인 `id`다. 이메일을 고유 로그인 ID로 사용하지 않는다.
- `is_active`는 DB 컬럼이 아닌 속성이며 `DELETED`에서만 False다.
  `SUSPENDED` 회원의 쓰기 제한은 각 API의 권한 검사에서 구현해야 한다.
- `is_staff`도 DB 컬럼이 아닌 속성이며 항상 False다. 관리자 권한 구조와
  `create_superuser()`가 없어 현재 `createsuperuser`와 Django Admin 로그인을 지원하지 않는다.
- 다른 앱에서 회원을 연결할 때는 기본 `django.contrib.auth.models.User`를 직접 참조하지 않고
  모델 관계에는 `settings.AUTH_USER_MODEL`, 실행 코드에는 `get_user_model()`을 사용한다.

### ERD 대응 및 남은 작업

- ERD에 ID 발급 방식이 없어 `id`를 자동 증가 기본키로 구현했다.
- Python의 `password`를 ERD의 `password_hash` 컬럼에 연결했다.
  소셜 회원 생성 시 NULL 대신 Django의 비밀번호 사용 불가 표식을 저장한다.
- ERD에 없는 `last_login` 컬럼은 제거했다. 별도 `SocialAccount`나 `UserProfile` 테이블은 만들지 않았다.
- 카카오 인증 API는 미구현이다. 서버에서 카카오 인증 결과를 검증하고
  `provider`와 `provider_id`로 회원을 찾는 흐름과 이 조합의 유일성 제약이 필요하다.
- 가입 시 코인 10개·크레딧 30점 지급은 미구현이다. 모델 기본값 0과 구분하며,
  가입 서비스에서 지급 내역과 함께 한 번만 처리해야 한다.
- 소수 크레딧을 정수 컬럼에 저장하는 단위·반올림 규칙은 아직 정하지 않았다.
- 본인 확인·동일인 판별·재가입 승계와 실제 탈퇴 처리도 미구현이다.

회원 관련 상세 메모는 [accounts/README.md](accounts/README.md)를 참고한다.
`accounts/migrations/0001_initial.py`는 공유 대상이다. 각 팀원은 자신의 DB에
마이그레이션을 적용하며, DB 데이터와 `.env`를 GitHub로 공유하지 않는다.

## 로컬 개발환경

Docker Desktop을 실행한 상태에서 사용한다. Windows에서도 Linux 컨테이너를 사용한다.
호스트의 Python/가상환경 대신 컨테이너의 Python으로 실행한다.

- Python 3.11 계열 (`python:3.11-slim`)
- Django/DRF/psycopg: `requirements.txt`에 정확한 버전 지정
- PostgreSQL 17 계열 (`postgres:17-bookworm`)

기반 이미지는 계열 태그를 사용해 패치 업데이트를 받을 수 있다. 이미지 digest까지 고정한 구성은 아니다.

### 처음 실행

```powershell
Copy-Item .env.example .env
```

`.env`의 `DJANGO_SECRET_KEY`와 `POSTGRES_PASSWORD`를 각자 다른 임의 값으로 바꾼다.
`.env`는 Git과 이미지 빌드에서 제외되며 `.env.example`만 공유한다.
Compose가 `.env`를 읽어 컨테이너에 전달한다. Django 자체에서 `.env`를 읽는 코드는 없다.

```powershell
docker compose up -d --build
docker compose exec api python manage.py migrate
docker compose exec api python manage.py check
docker compose ps
```

브라우저에서 <http://localhost:8000/health/>에 접속한다.
정상 응답은 `{"status": "ok", "database": "ok"}`다.
기본 `/` 주소에는 아직 화면/API가 없으므로 404가 나오는 것이 정상이다.

API는 PC의 `127.0.0.1:8000`으로만 공개한다. DB는 호스트에 포트를 공개하지 않는다.
컨테이너 사이에서는 서비스 이름 `db`로 PostgreSQL에 연결한다.

### 자주 쓰는 명령

```powershell
# 로그 확인
docker compose logs --tail 100 api

# Django 명령 실행
docker compose exec api python manage.py showmigrations
docker compose exec api python manage.py makemigrations
docker compose exec api python manage.py migrate

# PostgreSQL 접속
docker compose exec db psql -U ye -d ye

# 종료 (DB 데이터 유지)
docker compose down

# 다시 시작
docker compose up -d

# requirements.txt나 Dockerfile 변경 후 다시 빌드
docker compose up -d --build
```

프로젝트 폴더를 `/app`에 연결했으므로 Python 코드 수정은 개발 서버에 자동 반영된다.
DB 데이터는 `postgres_data` 볼륨에 저장된다. `docker compose down -v`는 데이터를 삭제하므로 일반 종료에 사용하지 않는다.
DB가 초기화된 뒤 `.env`의 DB 비밀번호만 바꿔도 기존 DB 비밀번호는 바뀌지 않는다.

현재는 로컬 개발용 Django 개발 서버다. AWS 배포, Redis/Celery, 카카오 로그인 API,
관리자 권한 구조는 아직 포함하지 않는다. 회원 모델 관련 결정은 `accounts/README.md`에 정리했다.
