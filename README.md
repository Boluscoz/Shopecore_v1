# Shopecore_v1

Portfolio-quality e-commerce REST API built with Django and DRF (PostgreSQL).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in values
```

## Environment variables

- `SECRET_KEY`
- `DEBUG` (True/False)
- `NAME`, `USER`, `PASSWORD`, `HOST`, `PORT` (PostgreSQL)

## Database

Create the PostgreSQL database and user, then update `.env`.

## Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

## Run

```bash
python manage.py runserver
```

Health check: `GET /health/`
EOF
