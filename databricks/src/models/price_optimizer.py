import pandas as pd
import xgboost as xgb


class PriceOptimizer:
    def __init__(self, params: dict):
        self.params = params
        self.model: xgb.XGBRegressor | None = None

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame | None = None,
        y_val: pd.Series | None = None,
    ) -> "PriceOptimizer":
        eval_set = [(X_val, y_val)] if X_val is not None else None
        self.model = xgb.XGBRegressor(**self.params)
        self.model.fit(X_train, y_train, eval_set=eval_set, verbose=False)
        return self

    def predict(self, X: pd.DataFrame) -> pd.Series:
        if self.model is None:
            raise RuntimeError("Model has not been trained yet. Call fit() first.")
        return self.model.predict(X)

    def feature_importances(self, feature_names: list[str]) -> pd.Series:
        if self.model is None:
            raise RuntimeError("Model has not been trained yet.")
        return pd.Series(self.model.feature_importances_, index=feature_names).sort_values(ascending=False)
