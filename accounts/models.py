from django.db import models
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager


class UserManager(BaseUserManager):
    def create_user(self, email, nickname, password=None, **extra_fields):
        if not email:
            raise ValueError("이메일이 필요합니다.")
        if not nickname:
            raise ValueError("닉네임이 필요합니다.")

        user = self.model(
            email=self.normalize_email(email),
            nickname=nickname,
            **extra_fields,
        )
        # 소셜 회원은 비밀번호 로그인을 사용할 수 없도록 저장한다.
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    class Gender(models.TextChoices):
        MALE = "M", "남성"
        FEMALE = "F", "여성"
        OTHER = "OTHER", "기타"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "정상"
        SUSPENDED = "SUSPENDED", "이용 제한"
        DELETED = "DELETED", "탈퇴"

    # ERD에 없는 AbstractBaseUser의 기본 컬럼을 제거한다.
    last_login = None

    id = models.BigAutoField(primary_key=True)
    email = models.EmailField(max_length=255)
    password = models.CharField(
        max_length=255,
        db_column="password_hash",
        null=True,
        blank=True,
    )
    provider = models.CharField(max_length=20, null=True, blank=True)
    provider_id = models.CharField(max_length=255, null=True, blank=True)
    nickname = models.CharField(max_length=30)
    profile_image_url = models.URLField(max_length=500, null=True, blank=True)
    gender = models.CharField(
        max_length=5, choices=Gender.choices, null=True, blank=True
    )
    birth_year = models.IntegerField(null=True, blank=True)
    region = models.CharField(max_length=30, null=True, blank=True)
    credit = models.IntegerField(default=0)
    coin_balance = models.IntegerField(default=0)
    notification_enabled = models.BooleanField(default=True)
    status = models.CharField(
        max_length=9, choices=Status.choices, default=Status.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    # 내부 ID는 Django 회원 식별용이며, 카카오 인증은 provider/provider_id로 조회한다.
    USERNAME_FIELD = "id"
    REQUIRED_FIELDS = ["email", "nickname"]

    class Meta:
        db_table = "users"

    @property
    def is_active(self):
        # 제한 회원도 로그인 후 삭제·신고·탈퇴는 가능해야 한다.
        return self.status != self.Status.DELETED

    @property
    def is_staff(self):
        # 현재 ERD에는 관리자 권한이 없어 관리자 로그인을 허용하지 않는다.
        return False

    def __str__(self):
        return self.nickname
