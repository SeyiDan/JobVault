FROM python:3.12-slim

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as an unprivileged user. Without this the process is root inside the
# container, so any code-execution bug becomes container-level control. The
# application files stay owned by root, which also stops the app rewriting its
# own code at runtime.
RUN useradd -m -u 1000 appuser
USER appuser

# No --reload: it is a development-only file watcher that has no place in an
# image and widens the runtime surface.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
