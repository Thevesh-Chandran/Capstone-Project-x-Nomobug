def purged_split(frame: pd.DataFrame, test_start: str,
                 test_end: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Keep mature past labels and remove every test property from training."""
    start = pd.Timestamp(test_start)
    test_mask = frame["anchor_date"] >= start
    if test_end is not None:
        test_mask &= frame["anchor_date"] < pd.Timestamp(test_end)
    test = frame[test_mask].copy()
    immature = ((frame["anchor_date"] < start)
                & (frame["outcome_end_date"] >= start))
    train = frame[frame["outcome_end_date"] < start].copy()
    shared = train["validation_group"].isin(set(test["validation_group"]))
    audit = {"embargoed_training_rows": int(immature.sum()),
             "property_purged_training_rows": int(shared.sum())}
    train = train[~shared].copy()
    assert set(train["validation_group"]).isdisjoint(test["validation_group"])
    assert_package_property_disjoint(train, test)
    assert (train["outcome_end_date"] < start).all()
    return train, test, audit

def make_model(name: str, numeric: list[str]) -> Pipeline:
    if name.startswith("catboost_"):
        from catboost import CatBoostClassifier
        depth = int(name.split("_")[1][-1])
        classifier = CatBoostClassifier(
            depth=depth, iterations=250, learning_rate=0.04,
            l2_leaf_reg=8 if depth == 3 else 12,
            auto_class_weights="Balanced" if name.endswith("balanced") else None,
            cat_features=[f"categorical__{column}" for column in CATEGORICAL],
            random_seed=42, thread_count=2, verbose=False, allow_writing_files=False,
            loss_function="Logloss")
        preprocess = ColumnTransformer([
            ("numeric", SimpleImputer(strategy="median", add_indicator=True,
                                       keep_empty_features=True), numeric),
            ("categorical", SimpleImputer(strategy="constant", fill_value="UNKNOWN"),
             CATEGORICAL),
        ]).set_output(transform="pandas")
        return Pipeline([("preprocess", preprocess), ("classifier", classifier)])
    if name.startswith("lr_"):
        parts = name.split("_")
        classifier = LogisticRegression(
            C=float(parts[1][1:]), class_weight=("balanced" if parts[2]
                                               == "balanced" else None),
            max_iter=2000, random_state=42)
    elif name.startswith("rf_"):
        classifier = RandomForestClassifier(
            n_estimators=160, max_depth=int(name[-1]), min_samples_leaf=10,
            class_weight="balanced_subsample", random_state=42, n_jobs=-1)
    elif name == "extra_trees_depth6":
        classifier = ExtraTreesClassifier(
            n_estimators=160, max_depth=6, min_samples_leaf=10,
            class_weight="balanced", random_state=42, n_jobs=-1)
    elif name.startswith("hist_"):
        classifier = HistGradientBoostingClassifier(
            max_depth=int(name[-1]), min_samples_leaf=20, max_iter=140,
            learning_rate=0.05, l2_regularization=3.0, random_state=42)
    elif name == "dummy_prior":
        classifier = DummyClassifier(strategy="prior")
    else:
        raise ValueError(f"Unknown model family: {name}")
    preprocess = ColumnTransformer([
        ("numeric", Pipeline([
            ("impute", SimpleImputer(strategy="median", add_indicator=True,
                                      keep_empty_features=True)),
            ("scale", StandardScaler()),
        ]), numeric),
        ("categorical", OneHotEncoder(handle_unknown="ignore", min_frequency=5,
                                      sparse_output=False), CATEGORICAL),
    ])
    return Pipeline([("preprocess", preprocess), ("classifier", classifier)])

def select_threshold(y, probability) -> float:
    """Use development out-of-fold predictions only; report ties conservatively."""
    candidates = np.linspace(0.02, 0.98, 97)
    values = [f1_score(y, np.asarray(probability) >= threshold, zero_division=0)
              for threshold in candidates]
    best = max(values)
    return float(max(threshold for threshold, value in zip(candidates, values)
                     if value >= best - 1e-12))

def fit_calibrator(y, raw_probability) -> tuple[LogisticRegression | None, dict]:
    """Fit a monotonic Platt mapping using pre-reporting OOF scores only."""
    clipped = np.clip(np.asarray(raw_probability, dtype=float),
                      np.nextafter(0.0, 1.0), np.nextafter(1.0, 0.0))
    logits = (np.log(clipped) - np.log1p(-clipped)).reshape(-1, 1)
    fitted = LogisticRegression(C=1.0, max_iter=2000, random_state=42).fit(logits, y)
    slope = float(fitted.coef_[0, 0])
    metadata = {"method": "platt_on_pre2026_purged_walk_forward_oof",
                "fitted_rows": len(clipped), "slope": slope,
                "intercept": float(fitted.intercept_[0]),
                "development_calibrated_brier_is_in_sample_for_calibration": True,
                "ranking_invariant": True}
    if slope <= 0:
        metadata["method"] = "skipped_nonpositive_platt_slope"
        metadata["applied"] = False
        return None, metadata
    metadata["applied"] = True
    return fitted, metadata
