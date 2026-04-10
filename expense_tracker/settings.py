"""
Django settings for expense_tracker project.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# BASE DIRECTORY
BASE_DIR = Path(__file__).resolve().parent.parent

# ======================
# 🔐 SECURITY
# ======================

SECRET_KEY = os.environ.get("SECRET_KEY", "fallback-secret-key")

DEBUG = os.getenv("DEBUG", "True") == "True"

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

# ======================
# 📦 APPLICATIONS
# ======================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Your app
    'tracker',
]

# ======================
# ⚙️ MIDDLEWARE
# ======================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',

    # WhiteNoise for static files (IMPORTANT for deployment)
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'expense_tracker.urls'

# ======================
# 🖥️ TEMPLATES
# ======================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',

        # Global templates folder
        'DIRS': [BASE_DIR / 'templates'],

        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'expense_tracker.wsgi.application'

# ======================
# 🗄️ DATABASE
# ======================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ======================
# 🔑 PASSWORD VALIDATION
# ======================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ======================
# 🌍 LANGUAGE & TIME
# ======================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# ======================
# 📁 STATIC FILES
# ======================

STATIC_URL = 'static/'

# Required for deployment
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# WhiteNoise static optimization
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ======================
# 🔢 DEFAULT PRIMARY KEY
# ======================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ======================
# 🔐 AUTH REDIRECTS
# ======================

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'

# ======================
# 🤖 API KEYS
# ======================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")