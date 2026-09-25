"""
高校实验室设备预约运维系统 —— Django 配置
"""
from datetime import timedelta
from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-default-key")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = [h for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h]

# --------------------------------------------------------------------------
# 应用
# --------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # 第三方
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_filters",
    # 业务应用
    "apps.accounts",
    "apps.labs",
    "apps.reservations",
    "apps.notifications",
    "apps.auditlog",
    "apps.statistics",
    "apps.maintenance",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.auditlog.middleware.AuditLogMiddleware",
]

ROOT_URLCONF = "labsys.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "labsys.wsgi.application"
ASGI_APPLICATION = "labsys.asgi.application"

# --------------------------------------------------------------------------
# 数据库
# --------------------------------------------------------------------------
DB_ENGINE = os.getenv("DB_ENGINE", "mysql")
if DB_ENGINE == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "lab_booking"),
            "USER": os.getenv("DB_USER", "root"),
            "PASSWORD": os.getenv("DB_PASSWORD", "12345"),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 6}},
]

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = False

# --------------------------------------------------------------------------
# 静态与媒体文件
# --------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# REST framework / JWT
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "apps.accounts.pagination.StandardPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
    "EXCEPTION_HANDLER": "apps.accounts.exceptions.custom_exception_handler",
    "DATETIME_FORMAT": "%Y-%m-%d %H:%M:%S",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# --------------------------------------------------------------------------
# 跨域
# --------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = os.getenv("CORS_ALLOW_ALL", "True").lower() == "true"
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = ["*"]

# --------------------------------------------------------------------------
# 业务参数（可在后台调整）
# --------------------------------------------------------------------------
# 各角色单次预约时长上限（小时）
ROLE_MAX_RESERVE_HOURS = {
    "student": 4,
    "teacher": 8,
    "lab_admin": 8,
    "sys_admin": 8,
}
# 预约需提前多少分钟提交
RESERVE_MIN_ADVANCE_MINUTES = 1
# 提醒：预约开始前多少分钟提醒签到
REMIND_SIGN_IN_BEFORE_MINUTES = 30
# 提醒：预约结束前多少分钟提醒归还
REMIND_RETURN_BEFORE_MINUTES = 30
# 提醒：超过结束时间多少分钟判定为逾期
OVERDUE_GRACE_MINUTES = 10

# 日志保留：记录查阅/修改操作
AUDIT_LOG_ENABLED = True

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
