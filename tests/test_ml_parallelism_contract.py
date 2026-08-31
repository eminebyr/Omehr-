from __future__ import annotations

from model_benchmark import _pipelines


def test_tree_models_do_not_start_nested_joblib_pools():
    """Dış CV paralelken iç modeller tek iş parçacığında kalmalı.

    Aksi halde sklearn/joblib her tahmin görevi için uyarı üretir ve CPU
    aşırı paylaştırılır.
    """
    regression, classification = _pipelines(["sayisal"], ["kategori"])
    models = [pipeline.named_steps["model"] for pipeline in [
        *regression.values(), *classification.values(),
    ]]
    tree_ensembles = [
        model for model in models
        if model.__class__.__name__.startswith(("RandomForest", "ExtraTrees"))
    ]
    assert len(tree_ensembles) == 4
    assert all(model.get_params()["n_jobs"] == 1 for model in tree_ensembles)
