import sys


def _add_src_to_path() -> None:
    """Resolve the databricks/ root from the running notebook path and add to sys.path."""
    try:
        nb_path: str = (
            dbutils.notebook.entry_point  # type: ignore[name-defined]  # noqa: F821
            .getDbutils()
            .notebook()
            .getContext()
            .notebookPath()
            .get()
        )
        parts = nb_path.split("/")
        dbt_idx = next(i for i, p in enumerate(parts) if p == "databricks")
        root = "/".join(parts[: dbt_idx + 1])
        if root not in sys.path:
            sys.path.insert(0, root)
    except Exception:
        pass


def get_spark():
    """Return the active SparkSession (already available in Databricks as `spark`)."""
    try:
        return spark  # type: ignore[name-defined]  # noqa: F821
    except NameError:
        from pyspark.sql import SparkSession
        return SparkSession.builder.getOrCreate()
