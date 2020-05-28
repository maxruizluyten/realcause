import numpy as np

from data.lalonde import load_lalonde
from models.linear import LinearGenModel
from models.nonlinear import MLP, TrainingParams, MLPParams
from evaluation import calculate_metrics
from causal_estimators.ipw_estimator import IPWEstimator
from causal_estimators.standardization_estimator import StandardizationEstimator
from evaluation import run_model_cv

from sklearn.linear_model import LogisticRegression, LinearRegression, Lasso, Ridge, ElasticNet
from sklearn.svm import SVR, LinearSVR
from sklearn.kernel_ridge import KernelRidge
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.gaussian_process import GaussianProcessClassifier, GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import RandomForestClassifier, AdaBoostClassifier, RandomForestRegressor, AdaBoostRegressor
from sklearn.naive_bayes import GaussianNB
from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis

from data.synthetic import generate_wty_linear_multi_w_data

from sklearn.pipeline import Pipeline
from sklearn.model_selection import GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score, cross_validate


alphas = {'alpha': np.logspace(-4, 5, 10)}
# gammas = [] + ['scale']
Cs = np.logspace(-4, 5, 10)
d_Cs = {'C': Cs}
SVM = 'svm'
d_Cs_pipeline = {SVM + '__C': Cs}
max_depths = {'max_depth': list(range(2, 10 + 1)) + [None]}
Ks = {'n_neighbors': [1, 2, 3, 5, 10, 15, 20, 30, 40, 50]}

outcome_model_grid = [
    (LinearRegression(), {}),
    (Lasso(), alphas),
    (Ridge(), alphas),
    (ElasticNet(), alphas),

    (SVR(kernel='rbf'), d_Cs),
    (SVR(kernel='sigmoid'), d_Cs),
    (LinearSVR(), d_Cs),
    # (SVR(kernel='linear'), d_Cs), # doesn't seem to work (runs forever)

    # TODO: add tuning of SVM gamma, rather than using the default "scale" setting
    # SVMs are sensitive to input scale
    (Pipeline([('standard', StandardScaler()), (SVM, SVR(kernel='rbf'))]),
     d_Cs_pipeline),
    (Pipeline([('standard', StandardScaler()), (SVM, SVR(kernel='sigmoid'))]),
     d_Cs_pipeline),
    (Pipeline([('standard', StandardScaler()), (SVM, LinearSVR())]),
     d_Cs_pipeline),

    (KernelRidge(), alphas),
    # MLPRegressor(max_iter=1000),
    # MLPRegressor(alpha=1, max_iter=1000),

    # NeighborsRegressor(),
    # GaussianProcessRegressor(),
    # TODO: choose better hyperparams to cross-validate over
    (DecisionTreeRegressor(), max_depths),
    (RandomForestRegressor(), max_depths),
    # AdaBoostRegressor(),
]

prop_score_model_grid = [
    (LogisticRegression(penalty='l2'), d_Cs),
    (LogisticRegression(penalty='none'), {}),
    (LogisticRegression(penalty='l2', solver='liblinear'), d_Cs),
    (LogisticRegression(penalty='l1', solver='liblinear'), d_Cs),
    (LogisticRegression(penalty='l1', solver='saga'), d_Cs),

    # https://scikit-learn.org/stable/auto_examples/classification/plot_classifier_comparison.html
    (KNeighborsClassifier(), Ks),
    # GaussianProcessClassifier(),
    (DecisionTreeClassifier(), max_depths),
    (RandomForestClassifier(), max_depths),
    # MLPClassifier(alpha=1, max_iter=1000),
    # AdaBoostClassifier(),
    (GaussianNB(), {}),
    (QuadraticDiscriminantAnalysis(), {})
]


w, t, y = generate_wty_linear_multi_w_data(100, binary_treatment=True)
lin_gen_model = LinearGenModel(w, t, y, binary_treatment=True)

# TODO: move the loop over seeds out here (rather than in calculuate_metrics and run_model_cv)
# and then use cross_validate() and version of calculuate_metrics() to get scores for all models
# and bundle all the statistical and causal metrics into a single DataFrame with a seed column
# (bias/variance/etc. will need to be calculated from this DataFrame)
# These DataFrames can be used as a dataset for predicting causal performance from predictive performance
for outcome_model, param_grid in outcome_model_grid:
    results = run_model_cv(lin_gen_model, outcome_model, param_grid=param_grid, n_seeds=5, model_type='outcome', best_model=True)
    estimator = StandardizationEstimator(outcome_model=results['best_model'])
    metrics = calculate_metrics(lin_gen_model, estimator, n_seeds=5, conf_ints=False)
    print(type(outcome_model))
    print(metrics)

for prop_score_model, param_grid in prop_score_model_grid:
    results = run_model_cv(lin_gen_model, prop_score_model, param_grid=param_grid, n_seeds=5, model_type='prop_score', best_model=True)
    estimator = IPWEstimator(prop_score_model=results['best_model'])
    metrics = calculate_metrics(lin_gen_model, estimator, n_seeds=5, conf_ints=False)
    print(type(prop_score_model))
    print(metrics)
