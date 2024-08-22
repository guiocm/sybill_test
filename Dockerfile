FROM python:3.11
WORKDIR /usr/local/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy in the source code
COPY app ./app
EXPOSE 5000

# Setup an app user so the container doesn't run as the root user
RUN useradd appuser
USER appuser

CMD ["fastapi", "run", "app/main.py"]
