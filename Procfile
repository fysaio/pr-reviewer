web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
worker: python -m celery -A app.tasks worker --loglevel=info --pool=solo