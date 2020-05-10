import numpy as np
import pandas as pd
from itertools import combinations
from math import factorial
import torch
from torch.autograd import Variable
from types import FunctionType, MethodType
import warnings

W = 'w'
T = 't'
Y = 'y'

PANDAS = 'pandas'
TORCH = 'torch'
NUMPY = 'numpy'


def to_data_format(data_format, w, t, y):
    format_to_func = {
        PANDAS: to_pandas_df,
        TORCH: to_tensors,
        NUMPY: to_np_arrays
    }
    if data_format in format_to_func.keys():
        return format_to_func[data_format](w, t, y)
    else:
        raise ValueError('Invalid data format: {} ... Valid formats: {}'.format(data_format, list(format_to_func.keys())))


def to_pandas_df(w, t, y):
    """
    Convert array-like w, t, and y to Pandas DataFrame
    :param w: 1d or 2d np array, list, or tuple of covariates
    :param t: 1d np array, list, or tuple of treatments
    :param y: 1d np array, list, or tuple of outcomes
    :return: Pandas DataFrame of w, t, and y
    """
    if isinstance(w, (list, tuple)):
        if any(isinstance(w_i, list, tuple) for w_i in w):
            d = {get_wlabel(i + 1): w_i for i, w_i in enumerate(w)}
        elif any(isinstance(w_i, np.ndarray) for w_i in w):
            assert all(w_i.ndim == 1 or w_i.shape[1] == 1 for w_i in w)
            d = {get_wlabel(i + 1): w_i for i, w_i in enumerate(w)}
        else:
            d = {W: w}
    elif isinstance(w, np.ndarray):
        if w.ndim == 1:
            d = {W: w}
        elif w.ndim == 2:
            # Assumes the examples are in the rows and covariates in the columns
            d = {get_wlabel(i + 1): w_i for i, w_i in enumerate(w.T)}
        else:
            raise ValueError('Unexpected w.ndim: {}'.format(w.ndim))
    else:
        warnings.warn(' unexpected w type: {}'.format(type(w)), Warning)
    d[T] = t
    d[Y] = y
    return pd.DataFrame(d)


def to_tensor(x):
    if isinstance(x, (pd.DataFrame, pd.Series)):
        x = x.values
    return torch.tensor(x, dtype=torch.float)


def to_torch_variable(x):
    return Variable(to_tensor(x))


def to_tensors(*args):
    if len(args) == 1:
        if isinstance(args[0], (tuple, list)):
            args = args[0]
        else:
            return to_tensor(args[0])
    return tuple(to_tensor(arg) for arg in args)


def to_np_arrays(*args):
    if len(args) == 1:
        if isinstance(args[0], (tuple, list)):
            args = args[0]
        else:
            return np.array(args[0], dtype=np.float)
        return np.array(args[0], dtype=np.float)
    return tuple(np.array(arg, dtype=np.float) for arg in args)


def to_np_vector(x, by_column=False, thin_interval=None, column_vector=False):
    if not isinstance(x, (torch.Tensor, np.ndarray)):
        raise ValueError('Invalid input type: {}'.format(type(x)))
    if isinstance(x, torch.Tensor):
        x = x.detach().numpy()
    if by_column:
        order = 'F'
    else:
        order = 'C'  # by row
    if column_vector:
        np_vect = x.reshape(-1, 1, order=order)
    else:
        np_vect = x.reshape(-1, order=order)
    if thin_interval is not None:
        return np_vect[::thin_interval]
    else:
        return np_vect


def to_np_vectors(tensors, by_column=False, thin_interval=None, column_vector=False):
    if not isinstance(tensors, (list, tuple)):
        tensors = (tensors,)
    np_vects = tuple(to_np_vector(x, by_column=by_column, thin_interval=thin_interval, column_vector=column_vector)
                     for x in tensors)
    if len(np_vects) == 1:
        return np_vects[0]
    else:
        return np_vects


def get_num_positional_args(f):
    if isinstance(f, FunctionType):
        n_args = f.__code__.co_argcount
    elif isinstance(f, MethodType):
        # Get corresponding function of class method and remove 'self' argument
        f = f.__func__
        n_args = f.__code__.co_argcount - 1
    else:
        raise ValueError('Invalid argument type: {}'.format(type(f)))

    if f.__defaults__ is not None:  # in case there are no kwargs
        n_kwargs = len(f.__defaults__)
    else:
        n_kwargs = 0

    n_positional_args = n_args - n_kwargs
    return n_positional_args


def get_wlabel(i=None, wlabel=W):
    return wlabel if i is None else wlabel + str(i)


def permutation_test(x, y, func='x_mean != y_mean', method='approximate',
                     num_rounds=1000, seed=None):
    """
    Nonparametric permutation test
    Adapted from http://rasbt.github.io/mlxtend/user_guide/evaluate/permutation_test/

    Parameters
    -------------
    x : 2D numpy array of the first sample
        (e.g., the treatment group).
    y : 2D numpy array of the second sample
        (e.g., the control group).
    func : custom function or str (default: 'x_mean != y_mean')
        function to compute the statistic for the permutation test.
        - If 'x_mean != y_mean', uses
          `func=lambda x, y: np.abs(np.mean(x) - np.mean(y)))`
           for a two-sided test.
        - If 'x_mean > y_mean', uses
          `func=lambda x, y: np.mean(x) - np.mean(y))`
           for a one-sided test.
        - If 'x_mean < y_mean', uses
          `func=lambda x, y: np.mean(y) - np.mean(x))`
           for a one-sided test.
    method : 'approximate' or 'exact' (default: 'approximate')
        If 'exact' (default), all possible permutations are considered.
        If 'approximate' the number of drawn samples is
        given by `num_rounds`.
        Note that 'exact' is typically not feasible unless the dataset
        size is relatively small.
    num_rounds : int (default: 1000)
        The number of permutation samples if `method='approximate'`.
    seed : int or None (default: None)
        The random seed for generating permutation samples if
        `method='approximate'`.

    Returns
    ----------
    p-value under the null hypothesis
    """

    if method not in ('approximate', 'exact'):
        raise AttributeError('method must be "approximate"'
                             ' or "exact", got %s' % method)

    if isinstance(func, str):

        if func not in (
                'x_mean != y_mean', 'x_mean > y_mean', 'x_mean < y_mean'):
            raise AttributeError('Provide a custom function'
                                 ' lambda x,y: ... or a string'
                                 ' in ("x_mean != y_mean", '
                                 '"x_mean > y_mean", "x_mean < y_mean")')

        elif func == 'x_mean != y_mean':
            def func(x, y):
                return np.abs(np.mean(x) - np.mean(y))

        elif func == 'x_mean > y_mean':
            def func(x, y):
                return np.mean(x) - np.mean(y)

        else:
            def func(x, y):
                return np.mean(y) - np.mean(x)

    rng = np.random.RandomState(seed)

    m, n = len(x), len(y)
    combined = np.vstack((x, y))

    more_extreme = 0.
    reference_stat = func(x, y)
    print('reference_stat:', reference_stat)

    # Note that whether we compute the combinations or permutations
    # does not affect the results, since the number of permutations
    # n_A specific objects in A and n_B specific objects in B is the
    # same for all combinations in x_1, ... x_{n_A} and
    # x_{n_{A+1}}, ... x_{n_A + n_B}
    # In other words, for any given number of combinations, we get
    # n_A! x n_B! times as many permutations; hoewever, the computed
    # value of those permutations that are merely re-arranged combinations
    # does not change. Hence, the result, since we divide by the number of
    # combinations or permutations is the same, the permutations simply have
    # "n_A! x n_B!" as a scaling factor in the numerator and denominator
    # and using combinations instead of permutations simply saves computational
    # time

    if method == 'exact':
        for indices_x in combinations(range(m + n), m):

            indices_y = [i for i in range(m + n) if i not in indices_x]
            diff = func(combined[list(indices_x)], combined[indices_y])

            if diff > reference_stat:
                more_extreme += 1.

        num_rounds = factorial(m + n) / (factorial(m) * factorial(n))

    else:
        for i in range(num_rounds):
            rng.shuffle(combined)
            if func(combined[:m], combined[m:]) > reference_stat:
                more_extreme += 1.

    return more_extreme / num_rounds
