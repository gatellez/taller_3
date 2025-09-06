from __future__ import annotations
import os
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine, text
from airflow import DAG
from airflow.operators.python import PythonOperator
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib

DATA_DB_HOST = os.environ.get("DATA_DB_HOST", "penguins-db")
DATA_DB_PORT = os.environ.get("DATA_DB_PORT", "3306")
DATA_DB_USER = os.environ.get("DATA_DB_USER", "penguins")
DATA_DB_PASSWORD = os.environ.get("DATA_DB_PASSWORD", "penguins")
DATA_DB_NAME = os.environ.get("DATA_DB_NAME", "penguins")

MYSQL_URL = f"mysql+pymysql://{DATA_DB_USER}:{DATA_DB_PASSWORD}@{DATA_DB_HOST}:{DATA_DB_PORT}/{DATA_DB_NAME}"
engine = create_engine(MYSQL_URL, pool_pre_ping=True)

ARTIFACT_DIR = "/opt/airflow/models"
MODEL_PATH = os.path.join(ARTIFACT_DIR, "model.pkl")

RAW_TABLE = "penguins_raw"
PREP_TABLE = "penguins_prepared"

def clear_database_tables(**_):
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {PREP_TABLE}"))
        conn.execute(text(f"DROP TABLE IF EXISTS {RAW_TABLE}"))

def load_raw_penguins(**_):
    url = "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/penguins.csv"
    df = pd.read_csv(url)
    df.to_sql(RAW_TABLE, engine, if_exists="replace", index=False)

def preprocess(**_):
    df = pd.read_sql_table(RAW_TABLE, engine)
    df = df.dropna(subset=["species"]).copy()
    X = df.drop(columns=["species"])
    y = df["species"].astype(str)
    Xy = pd.concat([X, y.rename("species")], axis=1).dropna().copy()
    Xy.to_sql(PREP_TABLE, engine, if_exists="replace", index=False)

def train_model(**_):
    data = pd.read_sql_table(PREP_TABLE, engine)
    y = data["species"].astype(str)
    X = data.drop(columns=["species"]).copy()

    numeric_cols = X.select_dtypes(include=["float64", "int64"]).columns.tolist()
    categorical_cols = X.select_dtypes(exclude=["float64", "int64"]).columns.tolist()

    preproc = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), numeric_cols),
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_cols),
        ]
    )
    clf = RandomForestClassifier(n_estimators=200, random_state=42)
    pipe = Pipeline(steps=[("preprocessor", preproc), ("model", clf)])

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    pipe.fit(X_train, y_train)
    acc = accuracy_score(y_test, pipe.predict(X_test))

    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    joblib.dump({"pipeline": pipe, "accuracy": float(acc)}, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH} with accuracy={acc:.4f}")

with DAG(
    dag_id="penguins_etl_train",
    description="ETL + Train + Save model for Penguins dataset",
    start_date=datetime(2024, 1, 1),
    schedule_interval="0 3 * * *",
    catchup=False,
    tags=["penguins","ml","mysql"],
) as dag:
    t_clear = PythonOperator(task_id="clear_database_tables", python_callable=clear_database_tables)
    t_load  = PythonOperator(task_id="load_raw_penguins", python_callable=load_raw_penguins)
    t_pre   = PythonOperator(task_id="preprocess", python_callable=preprocess)
    t_train = PythonOperator(task_id="train_model", python_callable=train_model)
    t_clear >> t_load >> t_pre >> t_train
