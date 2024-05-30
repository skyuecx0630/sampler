FROM python:3.9-slim

RUN apt update && apt install curl -y
RUN addgroup --gid 2001 mygroup && adduser --uid 1001 --gid 2001 --disabled-password myuser < /dev/null

USER 1001
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app.py .
COPY main.py .
EXPOSE 8080

CMD ["python", "main.py"]
