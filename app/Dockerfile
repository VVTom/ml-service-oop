FROM python:3.12.2

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app/src

COPY src/ .

CMD ["python", "api.py"]