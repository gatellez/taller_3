FROM apache/airflow:2.9.2
USER airflow
COPY --chown=airflow:0 requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
ENV PATH="/home/airflow/.local/bin:${PATH}"
