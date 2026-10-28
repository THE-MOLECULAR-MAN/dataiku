import dataiku
from dataikuapi.dss.ml import DSSPredictionMLTaskSettings

client = dataiku.api_client()

# Replace with your MLflow experiment name.
experiment_name = "airbnb"
# Replace with the name of the managed folder used as the MLflow tracking store.
experiments_managed_folder_name = "regression experiments"
optimized_metric = "neg_root_mean_squared_error"
# Replace with the name of the Saved Model in your Dataiku Flow.
sm_name = "airbnb"
# Replace with the target column name for your model.
target_column_name = "price"

project = client.get_default_project()
mlflow_extension = project.get_mlflow_extension()
experiments_managed_folder_id = dataiku.Folder(experiments_managed_folder_name).get_id()
experiments_managed_folder = project.get_managed_folder(experiments_managed_folder_id)

with project.setup_mlflow(managed_folder=experiments_managed_folder) as mlflow:
    experiment = mlflow.set_experiment(experiment_name)
    best_run = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=[f"metrics.{optimized_metric} DESC"],
        max_results=1,
        output_format="list",
    )[0]


# Get or create SavedModel

sm_id = None
for sm in project.list_saved_models():
    if sm_name != sm["name"]:
        continue
    else:
        sm_id = sm["id"]
        print(f"Found SavedModel {sm_name} with id {sm_id}")
        break
if sm_id:
    sm = project.get_saved_model(sm_id)
else:
    sm = project.create_mlflow_pyfunc_model(
        name=sm_name, prediction_type=DSSPredictionMLTaskSettings.PredictionTypes.BINARY
    )
    sm_id = sm.id
    print(f"SavedModel not found, created new one with id {sm_id}")


# Set version ID (a Saved Model can have multiple versions).

if len(sm.list_versions()) == 0:
    version_id = "V1"
else:
    max_version_num = max([int(v["id"][1:]) for v in sm.list_versions()])
    version_id = f"V{max_version_num+1}"

# Create version in SavedModel
sm_version = sm.import_mlflow_version_from_managed_folder(
    version_id=version_id,
    managed_folder=experiments_managed_folder,
    path=best_run.info.artifact_uri.split(experiments_managed_folder_id)[1] + "/model",
)

# Evaluate the version using the previously created Dataset
# Replace with the name of your evaluation dataset in the Dataiku Flow.
sm_version.set_core_metadata(
    target_column_name=target_column_name,
    class_labels=[0, 1],
    get_features_from_dataset="airbnb_measures_train",
)

sm_version.evaluate("airbnb_measures_train")
