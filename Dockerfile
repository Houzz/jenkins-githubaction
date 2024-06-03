# Use a base image that includes a shell for debugging
FROM python:3.8-slim AS builder
ADD . /app
WORKDIR /app

# Install dependencies directly into our app source dir
RUN pip install --target=/app api4jenkins==1.15.0 requests==2.28.1

# Use the same base image to include a shell for debugging
FROM python:3.8-slim
COPY --from=builder /app /app
WORKDIR /app
ENV PYTHONPATH /app
CMD ["python","/app/main.py"]