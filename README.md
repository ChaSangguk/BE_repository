# 영업중 백엔드

영업중의 회원·토론 API를 제공하는 Django REST Framework 프로젝트다. 로컬 개발 환경은 Docker Compose로 실행하며 PostgreSQL, Redis, Celery를 사용한다.

이 README는 3번 파트와 추가 API 15개가 포함된 `feat/debate-results` 브랜치를 기준으로 작성했다.

## 로컬 실행

Docker Desktop을 실행한 뒤 저장소 루트에서 다음 명령을 실행한다. `.env`가 이미 있으면 기존 설정을 사용한다.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

처음 만든 `.env`에는 로컬 개발용 `DJANGO_SECRET_KEY`와 `POSTGRES_PASSWORD`를 설정한다. 실제 환경변수는 Git에서 제외한다.

```powershell
docker compose up -d --build
docker compose exec api python manage.py migrate
docker compose exec api python manage.py check
docker compose ps
```

- API 기본 주소는 `http://127.0.0.1:8000/v1/`이다.
- [서버 상태 확인](http://127.0.0.1:8000/health/)은 API와 PostgreSQL 연결을 확인한다.
- [Django 관리자](http://127.0.0.1:8000/admin/)에 접속하려면 관리자 권한이 있는 계정이 필요하다.
- `worker`와 `beat`는 Redis를 통해 자동 마감과 최종 통계 집계 작업을 실행한다.

## 구현된 기능

### 3번 파트

| 기능 | 경로 또는 실행 방식 |
| --- | --- |
| 내 참여 토론 목록 | `GET /v1/me/debates` |
| 내 입장 조회·변경 | `GET`·`PATCH /v1/debates/{debateId}/me/stance` |
| 내 입장 변경 이력 | `GET /v1/debates/{debateId}/me/events` |
| 타이머·읽기 전용 전환 | `GET /v1/debates/{debateId}/timing` |
| 자동 마감 | Celery가 예정 시각에 도달한 토론을 종료 |
| 최종 통계 | `GET /v1/debates/{debateId}/result` |

입장 변경 요청에는 `Idempotency-Key`가 필요하다. 다중 기기 충돌을 감지하려면 현재 입장 조회에서 받은 `version`을 함께 보낸다. 참여 목록은 20개씩 반환하고 `meta.nextCursor`로 다음 페이지를 조회한다.

최종 통계는 집계 전 `409 RESULT_NOT_READY`를 반환하고, 완료 후 인원과 비율을 제공한다. 참여자가 20명 미만이면 입장 변화 데이터는 비공개 처리한다. 인구통계 공개와 설득 보상은 정책 확정이 남아 있다.

[3번 파트 코드와 화면 연동 안내](debates/part_c/README.md)

### 추가 API

약관, 카테고리, 관심사, 인구통계 동의, 코인·크레딧·배지, 알림, 토론 추세, 근거 링크 조회를 기능별 폴더에 구현했다. 추세와 근거 링크는 저장된 스냅샷과 URL 검사 결과를 읽는다.

[추가 API 15개와 기능별 폴더 안내](features/README.md)

## 기능별 브랜치

아래 브랜치는 개인 포크 `ChaSangguk/BE_repository`에 있다. PR에서 각 기능의 변경분만 보려면 표의 기준 브랜치와 비교한다.

| 기능 | 브랜치 | 비교 기준 |
| --- | --- | --- |
| 참여 목록 | [feat/joined-debates-api](https://github.com/ChaSangguk/BE_repository/tree/feat/joined-debates-api) | `develop` |
| 입장 변경 | [feat/part-c-stance-change](https://github.com/ChaSangguk/BE_repository/tree/feat/part-c-stance-change) | `develop` |
| 입장 변경 이력 | [feat/part-c-stance-history](https://github.com/ChaSangguk/BE_repository/tree/feat/part-c-stance-history) | `feat/part-c-stance-change` |
| 타이머 | [feat/part-c-timing](https://github.com/ChaSangguk/BE_repository/tree/feat/part-c-timing) | `develop` |
| 자동 마감 | [feat/part-c-auto-close](https://github.com/ChaSangguk/BE_repository/tree/feat/part-c-auto-close) | `develop` |
| 최종 통계 | [feat/part-c-final-result](https://github.com/ChaSangguk/BE_repository/tree/feat/part-c-final-result) | `feat/part-c-auto-close` |

## 코드 위치

| 위치 | 내용 |
| --- | --- |
| [config](config) | Django 설정, API 연결, Celery 예약 |
| [accounts](accounts) | 회원·약관·본인 확인 데이터 모델 |
| [debates](debates) | 토론·참여·입장·통계 모델과 3번 파트 API |
| [discussions](discussions) | 의견·근거 링크·AI 요약 데이터 모델 |
| [economy](economy), [engagement](engagement), [moderation](moderation) | 재화·알림·신고 데이터 모델 |
| [features](features) | 기능별 추가 API와 테스트 |

## 테스트와 로그

Django 테스트는 PostgreSQL에 별도 테스트 DB를 만들어 실행한다.

```powershell
docker compose exec -T api python manage.py test
docker compose exec -T api python manage.py test debates
docker compose exec -T api python manage.py test features
docker compose logs --tail 100 api worker beat
```
