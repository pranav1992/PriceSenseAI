import mlflow
from mlflow.tracking import MlflowClient

EXPERIMENT_PATH = "/Shared/pricesense-ai/price_optimization"
MODEL_NAME = "PriceOptimizationModel"


def setup_experiment() -> None:
    mlflow.set_experiment(EXPERIMENT_PATH)


def get_latest_model_version(stage: str = "None") -> object:
    client = MlflowClient()
    versions = client.get_latest_versions(MODEL_NAME, stages=[stage])
    if not versions:
        raise ValueError(f"No '{MODEL_NAME}' versions found in stage '{stage}'")
    return versions[0]


def promote_model(version: str, target_stage: str = "Production") -> None:
    client = MlflowClient()
    client.transition_model_version_stage(
        name=MODEL_NAME,
        version=version,
        stage=target_stage,
        archive_existing_versions=True,
    )
    print(f"✓ {MODEL_NAME} v{version} → {target_stage}")


def load_production_model() -> object:
    return mlflow.xgboost.load_model(f"models:/{MODEL_NAME}/Production")
