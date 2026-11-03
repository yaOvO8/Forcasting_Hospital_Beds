"""Model lead's area: the PyTorch quantile forecaster and MLflow runs.

To plug a model into `uv run beds regenerate`:
  1. train on panel rows with split='train' AND NOT holdout_hosp
     (tune on split='val'),
  2. predict every test row,
  3. call beds.evaluate.save_predictions(df, "<model_name>") with columns
     hospital_pk, collection_week, model, quantile, y_pred.
Then add the call to cli._baselines (or a new step) so regenerate runs it.
"""
