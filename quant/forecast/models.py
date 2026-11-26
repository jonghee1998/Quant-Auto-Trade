"""예측 모델(학습 창에서만 fit). 결측 대체·스케일링도 파이프라인 안에서 학습 창으로만 맞춘다."""
from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

SEEDS = (0, 1, 2)  # 신경망·숲은 시드 여러 개 평균(한 번 운에 기대지 않기)


class _Avg:
    """같은 모델을 시드만 바꿔 여러 개 학습하고 예측을 평균."""

    def __init__(self, makers):
        self.makers, self.models = makers, []

    def fit(self, X, y):
        self.models = [m().fit(X, y) for m in self.makers]
        return self

    def predict(self, X):
        return np.mean([m.predict(X) for m in self.models], axis=0)


class _AvgProba(_Avg):
    def predict(self, X):
        return np.mean([m.predict_proba(X)[:, 1] for m in self.models], axis=0)


class _Proba:
    def __init__(self, model):
        self.model = model

    def fit(self, X, y):
        self.model.fit(X, y)
        return self

    def predict(self, X):
        return self.model.predict_proba(X)[:, 1]


class _RankEnsemble:
    """여러 모델 예측을 날짜 안 순위로 바꿔 평균(크기가 다른 모델을 공평하게)."""

    def __init__(self, names):
        self.names, self.models = names, []

    def fit(self, X, y):
        self.models = [make(n).fit(X, y) for n in self.names]
        return self

    def predict(self, X):
        ps = [m.predict(X) for m in self.models]
        return np.mean([np.argsort(np.argsort(p)) / max(len(p) - 1, 1) for p in ps], axis=0)


def _pre():
    return [SimpleImputer(strategy="median", keep_empty_features=True), StandardScaler()]


def make(name: str):
    """회귀(앞으로 초과수익 예측) 모델."""
    if name == "ridge":
        return make_pipeline(*_pre(), Ridge(alpha=10.0))
    if name == "hgb":  # 얕은 트리·강한 규제(작은 표본에서 외우지 않게)
        return HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=50,
                                             l2_regularization=1.0, random_state=0)
    if name == "rf":
        return make_pipeline(SimpleImputer(strategy="median", keep_empty_features=True),
                             RandomForestRegressor(n_estimators=150, max_depth=5, min_samples_leaf=50, n_jobs=-1, random_state=0))
    if name == "mlp":  # 딥러닝(다층 신경망): 종목×날짜 표본을 묶어 학습, 조기 종료·가중치 규제
        return _Avg([lambda s=s: make_pipeline(*_pre(), MLPRegressor(hidden_layer_sizes=(32, 16), alpha=1e-2, learning_rate_init=1e-3, max_iter=300,
                                                                     early_stopping=True, n_iter_no_change=15, random_state=s))
                     for s in SEEDS])
    if name == "ens":
        return _RankEnsemble(["ridge", "hgb", "mlp"])
    raise ValueError(f"모델 이름: {name}")


def make_clf(name: str):
    """분류(앞으로 시장이 현금보다 나을 확률) 모델."""
    if name == "logit":
        return _Proba(make_pipeline(*_pre(), LogisticRegression(C=0.1, max_iter=500)))
    if name == "hgb":
        return _Proba(HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, min_samples_leaf=40,
                                                     l2_regularization=1.0, random_state=0))
    if name == "mlp":
        return _AvgProba([lambda s=s: make_pipeline(*_pre(), MLPClassifier(hidden_layer_sizes=(16, 8), alpha=1e-2, max_iter=400, early_stopping=True,
                                                                           n_iter_no_change=20, random_state=s)) for s in SEEDS])
    raise ValueError(f"분류 모델 이름: {name}")
