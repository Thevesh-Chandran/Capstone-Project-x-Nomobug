def make_pipeline(name, numeric):
    if name in ['extra_trees_depth6', 'rf_depth6']:
        return b.make_model(name, numeric)
    if name.startswith('cat'):
        depth = int(name[3])
        balanced = name.endswith('balanced')
        pipe = b.make_model(f'catboost_depth{depth}_' + ('balanced' if balanced else 'plain'), numeric)
        pipe.named_steps['classifier'].set_params(
            iterations=500 if depth == 4 else 450,
            l2_leaf_reg=20 if depth == 4 else 30, learning_rate=.035)
        return pipe
    pipe = b.make_model('extra_trees_depth6', numeric)
    if name == 'et10_leaf5':
        classifier = ExtraTreesClassifier(n_estimators=300, max_depth=10,
            min_samples_leaf=5, class_weight='balanced', random_state=42, n_jobs=2)
    elif name in ['rf10_leaf5', 'rf6_leaf20']:
        classifier = RandomForestClassifier(n_estimators=300,
            max_depth=10 if name == 'rf10_leaf5' else 6,
            min_samples_leaf=5 if name == 'rf10_leaf5' else 20,
            class_weight='balanced_subsample', random_state=42, n_jobs=2)
    elif name == 'hist3_balanced':
        classifier = HistGradientBoostingClassifier(max_depth=3, max_iter=250,
            min_samples_leaf=30, learning_rate=.04, l2_regularization=10,
            class_weight='balanced', random_state=42)
    else:
        raise ValueError(f'Unknown bounded candidate: {name}')
    pipe.set_params(classifier=classifier)
    return pipe

def fit_member(name, train, contracts):
    spec = SPECS[name]
    numeric = contracts[spec['feature_set']]
    features = numeric + list(b.CATEGORICAL)
    pipe = make_pipeline(spec['model'], numeric)
    if 'n_jobs' in pipe.named_steps['classifier'].get_params():
        pipe.named_steps['classifier'].set_params(n_jobs=2)
    with threadpool_limits(limits=2):
        pipe.fit(train[features], train[b.TARGET],
                 classifier__sample_weight=training_weights(train, spec['policy']))
    return {'pipeline': pipe, 'features': features, 'member_name': name}

def prepare_input(source, require_outcomes=True):
    configure_contracts(False)
    return add_contract_policy_feature(add_targeted_features(
        b.prepare_frame(source, require_outcomes=require_outcomes)))
