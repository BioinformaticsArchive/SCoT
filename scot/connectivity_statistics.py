# Released under The MIT License (MIT)
# http://opensource.org/licenses/MIT
# Copyright (c) 2013-2014 SCoT Development Team

""" Routines for statistical evaluation of connectivity.
"""

import numpy as np
import scipy as sp
from .datatools import randomize_phase
from .connectivity import connectivity
from . import config


def surrogate_connectivity(measure_names, data, var, nfft=512, repeats=100):
    """ Calculates surrogate connectivity for a multivariate time series by phase randomization [1]_.

    .. note:: Parameter `var` will be modified by the function. Treat as undefined after the function returned.

    Parameters
    ----------
    measure_names : {str, list of str}
        Name(s) of the connectivity measure(s) to calculate. See :class:`Connectivity` for supported measures.
    data : ndarray, shape = [n_samples, n_channels, (n_trials)]
        Time series data (2D or 3D for multiple trials)
    var : VARBase-like object
        Instance of a VAR model.
    nfft : int, optional
        Number of frequency bins to calculate. Note that these points cover the range between 0 and half the
        sampling rate.
    repeats : int, optional
        How many surrogate samples to take.

    Returns
    -------
    result : array, shape = [`repeats`, n_channels, n_channels, nfft]
            Values of the connectivity measure for each surrogate. If `measure_names` is a list of strings a dictionary
            is returned, where each key is the name of the measure, and the corresponding values are ndarrays of shape
            [`repeats`, n_channels, n_channels, nfft].

    .. [1] J. Theiler et al. "Testing for nonlinearity in time series: the method of surrogate data", Physica D,
           vol 58, pp. 77-94, 1992
    """
    output = []
    for r in range(repeats):
        surrogate_data = randomize_phase(data)
        var.fit(surrogate_data)
        c = connectivity(measure_names, var.coef, var.rescov, nfft)
        output.append(c)
    return convert_output_(output, measure_names)


def jackknife_connectivity(measure_names, data, var, nfft=512, leaveout=1):
    """ Calculates Jackknife estimates of connectivity.

    For each Jackknife estimate a block of trials is left out. This is repeated until each trial was left out exactly
    once. The number of estimates depends on the number of trials and the value of `leaveout`. It is calculated by
    repeats = n_trials // leaveout.

    .. note:: Parameter `var` will be modified by the function. Treat as undefined after the function returned.

    Parameters
    ----------
    measure_names : {str, list of str}
        Name(s) of the connectivity measure(s) to calculate. See :class:`Connectivity` for supported measures.
    data : ndarray, shape = [n_samples, n_channels, (n_trials)]
        Time series data (2D or 3D for multiple trials)
    var : VARBase-like object
        Instance of a VAR model.
    nfft : int, optional
        Number of frequency bins to calculate. Note that these points cover the range between 0 and half the
        sampling rate.
    leaveout : int, optional
        Number of trials to leave out in each estimate.

    Returns
    -------
    result : array, shape = [`repeats`, n_channels, n_channels, nfft]
            Values of the connectivity measure for each surrogate. If `measure_names` is a list of strings a dictionary
            is returned, where each key is the name of the measure, and the corresponding values are ndarrays of shape
            [`repeats`, n_channels, n_channels, nfft].
    """
    data = np.atleast_3d(data)
    n, m, t = data.shape

    if leaveout < 1:
        leaveout = int(leaveout * t)

    num_blocks = int(t / leaveout)

    output = []
    for b in range(num_blocks):
        mask = [i for i in range(t) if i < b*leaveout or i >= (b+1)*leaveout]
        data_used = data[:, :, mask]
        var.fit(data_used)
        c = connectivity(measure_names, var.coef, var.rescov, nfft)
        output.append(c)
    return convert_output_(output, measure_names)


def bootstrap_connectivity(measures, data, var, nfft=512, repeats=100, num_samples=None):
    """ Calculates Bootstrap estimates of connectivity.

    To obtain a bootstrap estimate trials are sampled randomly with replacement from the data set.

    .. note:: Parameter `var` will be modified by the function. Treat as undefined after the function returned.

    Parameters
    ----------
    measure_names : {str, list of str}
        Name(s) of the connectivity measure(s) to calculate. See :class:`Connectivity` for supported measures.
    data : ndarray, shape = [n_samples, n_channels, (n_trials)]
        Time series data (2D or 3D for multiple trials)
    var : VARBase-like object
        Instance of a VAR model.
    repeats : int, optional
        How many bootstrap estimates to take.
    num_samples : int, optional
        How many samples to take for each bootstrap estimates. Defaults to the same number of trials as present in
        the data.

    Returns
    -------
    measure : array, shape = [`repeats`, n_channels, n_channels, nfft]
        Values of the connectivity measure for each bootstrap estimate. If `measure_names` is a list of strings a
        dictionary is returned, where each key is the name of the measure, and the corresponding values are
        ndarrays of shape [`repeats`, n_channels, n_channels, nfft].
    """
    data = np.atleast_3d(data)
    n, m, t = data.shape

    if num_samples is None:
        num_samples = t

    output = []
    for r in range(repeats):
        mask = np.random.random_integers(0, t-1, num_samples)
        data_used = data[:, :, mask]
        var.fit(data_used)
        c = connectivity(measures, var.coef, var.rescov, nfft)
        output.append(c)
    return convert_output_(output, measures)


def test_bootstrap_difference(a, b):
    """ Test mean difference between two bootstrap estimates.

    This function calculates the probability `p` of observing a more extreme mean difference between `a` and `b` under the
    null hypothesis that `a` and `b` come from the same distribution.

    If p is smaller than e.g. 0.05 we can reject the null hypothesis at an alpha-level of 0.05 and conclude that `a` and
    `b` are likely to come from different distributions.

    .. note:: *p*-values are calculated along the first dimension. Thus, n_channels * n_channels * nfft individual
              *p*-values are obtained. To determine if a difference is significant it is important to correct for
              multiple testing.

    Parameters
    ----------
    a, b : ndarray, shape = [`repeats`, n_channels, n_channels, nfft]
        Two bootstrap estimates to compare. The number of repetitions (first dimension) does not have be equal.

    Returns
    -------
    p : ndarray, shape = [n_channels, n_channels, nfft]
        *p*-values

    Notes
    -----
    The function estimates the distribution of `b[j]` - `a[i]` by calculating the difference for each combination of `i`
    and `j`. The total number of difference samples available is therefore a.shape[0] * b.shape[0].
    The *p*-value is calculated as the smallest percentile of that distribution that does not contain 0.

    See also
    --------
    :func:`significance_fdr` : Correct for multiple testing by controlling the false discovery rate.
    """
    old_shape = a.shape[1:]
    a = np.asarray(a).reshape((a.shape[0], -1))
    b = np.asarray(b).reshape((b.shape[0], -1))

    n = a.shape[0]

    s1, s2 = 0, 0
    for i in config.backend['utils'].cartesian((np.arange(n), np.arange(n))):
        c = b[i[1], :] - a[i[0], :]

        s1 += c >= 0
        s2 += c <= 0

    p = np.minimum(s1, s2) / (n*n)

    return p.reshape(old_shape)


def test_rank_difference_a(a, b):
    """ Test for difference between two statistics with Mann-Whitney-U test.
        Samples along first dimension. p-values returned.
    """
    old_shape = a.shape[1:]
    assert(b.shape[1:] == old_shape)
    a = np.asarray(a).reshape((a.shape[0], -1))
    b = np.asarray(b).reshape((b.shape[0], -1))

    p = np.zeros(a.shape[1])

    for i in range(a.shape[1]):
        #u, pr = sp.stats.mannwhitneyu(a[:,i], b[:,i])
        t, pr = sp.stats.ttest_ind(a[:,i], b[:,i], equal_var=False)
        p[i] = pr

    return p.reshape(old_shape)


def significance_fdr(p, alpha):
    """ Calculate significance by controlling for the false discovery rate.

    This function determines which of the *p*-values in `p` can be considered significant. Correction for multiple
    comparisons is performed by controlling the false discovery rate (FDR). The FDR is the maximum fraction of
    *p*-values that are wrongly considered significant [1]_.

    Parameters
    ----------
    p : ndarray, shape = [n_channels, n_channels, nfft]
        *p*-values
    alpha : float
        Maximum false discovery rate.

    Returns
    -------
    s : ndarray, dtype=bool, shape = [n_channels, n_channels, nfft]
        Significance of each *p*-value.

    References
    ----------
    .. [1] Y. Benjamini, Y. Hochberg, "Controlling the false discovery rate: a practical and powerful approach to
           multiple testing", Journal of the Royal Statistical Society, Series B 57(1), pp 289-300, 1995
    """
    i = np.argsort(p, axis=None)
    m = i.size - np.sum(np.isnan(p))

    j = np.empty(p.shape, int)
    j.flat[i] = np.arange(1, i.size+1)

    mask = p <= alpha*j/m

    if np.sum(mask) == 0:
        return mask

    # find largest k so that p_k <= alpha*k/m
    k = np.max(j[mask])

    # reject all H_i for i = 0...k
    s = j <= k

    return s


def convert_output_(output, measures):
    if isinstance(measures, str):
        return np.array(output)
    else:
        repeats = len(output)
        output = {m: np.array([output[r][m] for r in range(repeats)]) for m in measures}
        return output