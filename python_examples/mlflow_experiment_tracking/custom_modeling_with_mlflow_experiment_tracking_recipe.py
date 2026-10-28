# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
import warnings
from datetime import datetime

import dataiku
import mlflow
import mlflow.sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder

warnings.filterwarnings("ignore")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Replace with the name of the managed folder used as the MLflow tracking store.
EXPERIMENT_TRACKING_FOLDER_NAME = "tracking"
# Replace with your DSS connection name for managed folders.
EXPERIMENT_TRACKING_FOLDER_CONNECTION = "filesystem_folders"
# Replace with your preferred MLflow experiment name.
EXPERIMENT_NAME = "custom-modeling"
# Replace with the name of the code environment that has mlflow and sklearn installed.
MLFLOW_CODE_ENV_NAME = "mlflow"
# Replace with the name of the Saved Model in your Dataiku Flow.
SAVED_MODEL_NAME = "custom-model"
# Replace with the name of your training dataset in the Dataiku Flow.
DATASET_TRAINING = "training"


# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
def now_str() -> str:
    """Return the current timestamp formatted as YYYYMMDDHHmmSS."""
    return datetime.now().strftime("%Y%m%d%H%M%S")


# -------------------------------------------------------------------------------- NOTEBOOK-CELL: MARKDOWN
# # Experiment tracking (scikit-learn)
#
# This notebook contains a simple example to showcase the new Experiment Tracking capabilities of Dataiku. It explains how to perform several runs with different parameters, select the best run and promote it as a Saved Model version in a Dataiku Flow. It leverages:
# * the scikit-learn package

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: MARKDOWN
# ## Loading the training data
#
# Our training data lives in the `labeled` Dataset, let's load it in a pandas DataFrame and see what it looks like:

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
client = dataiku.api_client()
project = client.get_default_project()
training_dataset = dataiku.Dataset(DATASET_TRAINING)
df = training_dataset.get_dataframe()
df.head()

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: MARKDOWN
# We are working on a *binary classification* problem here, which is to predict whether or not a given customer is high value. This outcome is reflected by the `high_value` column which can either take the "0.0" or "1.0" values.

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
target_name = "high_value"
target = df[target_name]
data = df.drop(columns=[target_name])

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Get-or-create Managed Folder
project_folders = project.list_managed_folders()
folder = None
if project_folders:
    for mf in project_folders:
        if mf["name"] == EXPERIMENT_TRACKING_FOLDER_NAME:
            print(
                f"Found experiment tracking folder {EXPERIMENT_TRACKING_FOLDER_NAME} with id {mf['id']}"
            )
            folder = project.get_managed_folder(odb_id=mf["id"])
            break
    if not folder:
        print("Experiment tracking folder not found. Creating it...")
        folder = project.create_managed_folder(
            EXPERIMENT_TRACKING_FOLDER_NAME,
            connection_name=EXPERIMENT_TRACKING_FOLDER_CONNECTION,
        )
else:
    print("No folder found in project. Creating one for experiment tracking...")
    folder = project.create_managed_folder(
        EXPERIMENT_TRACKING_FOLDER_NAME,
        connection_name=EXPERIMENT_TRACKING_FOLDER_CONNECTION,
    )

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: MARKDOWN
# ## Preparing the experiment
#
# To prepare the grounds for our experiments, we need to create a few handles and define which MLFlow experiment we'll collect our runs into:

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Create a mlflow_extension object to easily collect information for the promotion step
mlflow_extension = project.get_mlflow_extension()

project.setup_mlflow(managed_folder=folder)

mlflow.set_experiment(experiment_name=EXPERIMENT_NAME)

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: MARKDOWN
# ## Experimenting
#
# The goal of experiment tracking is to *instrument the iterative process of ML model training* by collecting all parameters and results of each trial. To be more specific, within an **experiment**, you perform multiple **runs**, each run being different from the others because of the **parameters** you use for it. You also need to specific which **metrics** to track, they will reflect the performance of the model for a given set of parameters.
#
# In this notebook example, if you want to produce experiment runs:
# * edit the parameters in the 3.1 cell and run it
# * run the 3.2 cell to effectively... perform the run 🙂

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: MARKDOWN
# ### Defining the parameters of our run

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
# Create run name
run_params = {}
run_metrics = {}

# Define run parameters
# -- Which columns to retain ?
categorical_cols = ["gender", "ip_country_code"]
run_params["categorical_cols"] = categorical_cols
numerical_cols = ["age", "price_first_item_purchased", "pages_visited", "campaign"]
run_params["numerical_cols"] = numerical_cols

# --Which algorithm to use? Which hyperparameters for this algo to try?
# --- Example: Random Forest
hparams = {
    "n_estimators": 50,
    "criterion": "gini",
    "max_depth": 5,
    "min_samples_split": 3,
    "random_state": 42,
}
clf = RandomForestClassifier(**hparams)
model_algo = type(clf).__name__
run_params["model_algo"] = model_algo
for hp in hparams:
    run_params[hp] = hparams[hp]

# --Which cross-validation settings to use?
n_cv_folds = 5
cv = StratifiedKFold(n_splits=n_cv_folds)
run_params["n_cv_folds"] = n_cv_folds
metrics = ["f1_macro", "roc_auc"]

# --Let's print all of that to get a recap:
print(f"Parameters to log:\n {run_params}")
print(100 * "-")
print(f"Metrics to log:\n {metrics}")

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: MARKDOWN
# ### Performing the run and logging parameters, metrics and the model

# -------------------------------------------------------------------------------- NOTEBOOK-CELL: CODE
run_ts = now_str()
run_name = f"run-{run_ts}"
with mlflow.start_run(run_name=run_name) as run:
    run_id = run.info.run_id
    print(f"Starting run {run_name} (id: {run_id})...")
    # --Preprocessing
    categorical_preprocessor = OneHotEncoder(handle_unknown="ignore")
    preprocessor = ColumnTransformer(
        [
            ("categorical", categorical_preprocessor, categorical_cols),
            ("numerical", "passthrough", numerical_cols),
        ]
    )

    # --Pipeline definition (preprocessing + model)
    pipeline = make_pipeline(preprocessor, clf)

    # --Cross-validation
    print("Running cross-validation...")
    scores = cross_validate(pipeline, data, target, cv=cv, scoring=metrics)
    for m in [f"test_{mname}" for mname in metrics]:
        run_metrics[f"mean_{m}"] = scores[m].mean()
        run_metrics[f"std_{m}"] = scores[m].std()

    # --Pipeline fit
    pipeline.fit(X=data, y=target)
    # --Log the order of the class label
    run_params["class_labels"] = [str(c) for c in pipeline.classes_.tolist()]

    # --Log parameters, metrics and model
    mlflow.log_params(params=run_params)
    mlflow.log_metrics(metrics=run_metrics)
    artifact_path = f"{model_algo}-{run_id}"
    mlflow.sklearn.log_model(sk_model=pipeline, artifact_path=artifact_path)

    # --Set useful information to facilitate run promotion
    mlflow_extension.set_run_inference_info(
        run_id=run_id,
        prediction_type="BINARY_CLASSIFICATION",
        classes=run_params["class_labels"],
        code_env_name=MLFLOW_CODE_ENV_NAME,
        target=target_name,
    )
    print(f"DONE! Your artifacts are available at {run.info.artifact_uri}")
