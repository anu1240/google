FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt* pyproject.toml ./
RUN pip install fastapi uvicorn[standard] httpx pydantic networkx numpy scipy python-dotenv pyyaml
COPY . .
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
