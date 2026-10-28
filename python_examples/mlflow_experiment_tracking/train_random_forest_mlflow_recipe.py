from datetime import datetime

import dataiku
import mlflow
import mlflow.sklearn
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

# Replace with the name of the managed folder used as the MLflow tracking store.
EXPERIMENT_TRACKING_FOLDER_NAME = "models"
# Replace with your DSS connection name for managed folders.
EXPERIMENT_TRACKING_FOLDER_CONNECTION = "filesystem_folders"
# Replace with your preferred MLflow experiment name.
EXPERIMENT_NAME = "custom_classification_model"
# Replace with the name of the code environment that has mlflow and sklearn installed.
MLFLOW_CODE_ENV_NAME = "oa-py39-ml"

# ==========================================
# 1. READ INPUT DATA FROM DATAIKU FLOW
# ==========================================
# Dataiku automatically maps recipe inputs to its native API
# Replace with the name of your input dataset in the Dataiku Flow.
dataset_input = dataiku.Dataset("master_features_for_ml")
df = dataset_input.get_dataframe()

sample_size = min(3000, len(df))
df = df.sample(n=sample_size, random_state=42).reset_index(drop=True)


print(f"Loaded {len(df)} rows from master features table (SKU-level granularity).")

# ==========================================
# 2. FEATURE HANDLING & LEAKAGE PREVENTION
# ==========================================
# Target variable
target = "is_trend_gap"

features_to_drop = [
    "sku_id",
    "vendor_id",
    "product_name",
    "date_captured",
    "trend_name",
    target,
]
X = df.drop(columns=features_to_drop)
y = df[target]

# Define numeric and categorical feature columns for preprocessing
numeric_features = [
    "market_sentiment_score",
    "on_hand_inventory",
    "units_sold_last_30d",
    "inventory_to_sales_ratio",
    "full_price_unit_velocity",
]
categorical_features = ["style_attribute", "macys_color", "store_id"]

# ==========================================
# 3. BUILD PREPROCESSING & MODELING PIPELINE
# ==========================================
# Handle missing values and string attributes cleanly inside an isolated pipeline
numeric_transformer = Pipeline(steps=[("imputer", SimpleImputer(strategy="median"))])

categorical_transformer = Pipeline(
    steps=[
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ]
)

preprocessor = ColumnTransformer(
    transformers=[
        ("num", numeric_transformer, numeric_features),
        ("cat", categorical_transformer, categorical_features),
    ]
)

# Define the tree classifier configuration
model_pipeline = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        (
            "classifier",
            RandomForestClassifier(n_estimators=10, max_depth=3, random_state=42),
        ),
    ]
)

# ==========================================
# 4. TRAIN AND EVALUATE MODEL
# ==========================================
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print("Training Custom Random Forest Model...")
model_pipeline.fit(X_train, y_train)

# Calculate performance metrics to display directly inside the job logs
train_preds = model_pipeline.predict_proba(X_train)[:, 1]
test_preds = model_pipeline.predict_proba(X_test)[:, 1]
print(f" Train AUC Score: {roc_auc_score(y_train, train_preds):.4f}")
print(f" Test AUC Score: {roc_auc_score(y_test, test_preds):.4f}")

# ==========================================
# 5. GENERATE COMPREHENSIVE OUTPUT DATASET
# ==========================================
print("Scoring production trend dataset...")
all_probabilities = model_pipeline.predict_proba(X)

df["proba_0"] = all_probabilities[:, 0]
df["proba_1"] = all_probabilities[:, 1]
df["prediction"] = np.where(df["proba_1"] >= 0.50, 1, 0)

# ==========================================
# 6. WRITE RESULTS BACK TO THE FLOW
# ==========================================
# Write data directly to the storage layout (GCP BigQuery, Snowflake, etc.)
# Replace with the name of your output dataset in the Dataiku Flow.
dataset_output = dataiku.Dataset("code_model_predictions")
dataset_output.write_with_schema(df)

print(
    "✅ Model scored successfully and saved back to Dataiku Flow without schema errors."
)

# ==========================================
# 7. LOG MODEL TO MLFLOW VIA MANAGED FOLDER
# ==========================================
client = dataiku.api_client()
project = client.get_default_project()

# Get or create the managed folder used as the MLflow tracking store
folder = None
for mf in project.list_managed_folders():
    if mf["name"] == EXPERIMENT_TRACKING_FOLDER_NAME:
        folder = project.get_managed_folder(odb_id=mf["id"])
        print(
            f"Found tracking folder '{EXPERIMENT_TRACKING_FOLDER_NAME}' (id: {mf['id']})"
        )
        break

if not folder:
    print(f"Creating tracking folder: {EXPERIMENT_TRACKING_FOLDER_NAME}")
    folder = project.create_managed_folder(
        EXPERIMENT_TRACKING_FOLDER_NAME,
        connection_name=EXPERIMENT_TRACKING_FOLDER_CONNECTION,
    )

mlflow_extension = project.get_mlflow_extension()
project.setup_mlflow(managed_folder=folder)
mlflow.set_experiment(experiment_name=EXPERIMENT_NAME)

run_name = f"run-{datetime.now().strftime('%Y%m%d%H%M%S')}"
print(f"Starting MLflow run: {run_name}")
with mlflow.start_run(run_name=run_name) as run:
    run_id = run.info.run_id
    mlflow.log_params({"n_estimators": 10, "max_depth": 3, "random_state": 42})
    mlflow.log_metric("train_auc", roc_auc_score(y_train, train_preds))
    mlflow.log_metric("test_auc", roc_auc_score(y_test, test_preds))

    artifact_path = f"RandomForestClassifier-{run_id}"
    mlflow.sklearn.log_model(sk_model=model_pipeline, artifact_path=artifact_path)

    class_labels = [str(c) for c in model_pipeline.classes_.tolist()]
    mlflow_extension.set_run_inference_info(
        run_id=run_id,
        prediction_type="BINARY_CLASSIFICATION",
        classes=class_labels,
        code_env_name=MLFLOW_CODE_ENV_NAME,
        target=target,
    )
    print(f"MLflow run complete. Artifacts at: {run.info.artifact_uri}")

print("✅ Custom Python model logged to MLflow experiment tracking folder.")
