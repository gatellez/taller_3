FROM python:3.11-slim
WORKDIR /app
COPY main.py /app/
RUN pip install --no-cache-dir fastapi==0.112.2 uvicorn==0.30.5 joblib==1.4.2 scikit-learn==1.5.1 pydantic==2.8.2
ENV MODEL_PATH=/models/model.pkl
EXPOSE 8000
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8000"]
