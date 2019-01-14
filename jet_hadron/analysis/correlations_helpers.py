#!/usr/bin/env python

""" Helper functions for correlations.

.. codeauthor:: Raymond Ehlers <raymond.ehlers@cern.ch>, Yale University
"""

import logging
import numpy as np
import scipy
import scipy.signal
import scipy.interpolate
from typing import Tuple

from pachyderm import histogram
from pachyderm import utils
from pachyderm.utils import epsilon

from jet_hadron.base import analysis_objects
from jet_hadron.base import params
from jet_hadron.base.typing_helpers import Hist

from jet_hadron.analysis import fit as fitting

logger = logging.getLogger(__name__)

def determine_number_of_triggers(hist: Hist, jet_pt: analysis_objects.JetPtBin) -> int:
    """ Determine the number of triggers for the specific analysis parameters.

    When retrieving the number of triggers, carefully note the information below:

    .. code-block:: python

        >>> hist = ROOT.TH1D("test", "test", 10, 0, 10)
        >>> x = 2, y = 5
        >>> hist.FindBin(x)
        2
        >>> hist.FindBin(x+epsilon)
        2
        >>> hist.FindBin(y)
        6
        >>> hist.FindBin(y-epsilon)
        5

    Note:
        The bin + epsilon on the lower bin is not strictly necessary, but it is used for consistency.

    Note:
        This bin + epsilon techinque is frequently used when determining projector bin ends.

    Args:
        hist: Histogram containing the number of triggers.
        jet_pt: Jet pt for which we want to know the number of triggers.
    Returns:
        Number of triggers for the selected analysis parameters.
    """
    logger.debug(
        f"Find bin({jet_pt.range.min} + epsilon): "
        f"{hist.FindBin(jet_pt.range.min + epsilon)} to "
        f"Find bin({jet_pt.range.max} - epsilon): "
        f"{hist.FindBin(jet_pt.range.max - epsilon)}"
    )
    number_of_triggers = hist.Integral(
        hist.FindBin(jet_pt.range.min + epsilon),
        hist.FindBin(jet_pt.range.max - epsilon)
    )
    logger.info(f"n_trig for [{jet_pt.range.min}, {jet_pt.range.max}): {number_of_triggers}")

    return number_of_triggers

def post_projection_processing_for_2d_correlation(hist: Hist, normalization_factor: float, title: str,
                                                  jet_pt: analysis_objects.JetPtBin,
                                                  track_pt: analysis_objects.TrackPtBin) -> None:
    """ Basic post processing tasks for a new 2D correlation observable.

    Args:
        hist: Histogram to be post processed.
        normalization_factor: Factor by which the hist should be scaled.
        title: Histogram title.
        jet_pt: Jet pt bin.
        track_pt: Track pt bin.
    Returns:
        None. The histogram is modified in place.
    """
    # Scale
    hist.Scale(1.0 / normalization_factor)

    # Set title, axis labels
    jet_pt_bins_title = params.generate_jet_pt_range_string(jet_pt)
    track_pt_bins_title = params.generate_track_pt_range_string(track_pt)
    hist.SetTitle(f"{title} with {jet_pt_bins_title}, {track_pt_bins_title}")
    hist.GetXaxis().SetTitle("#Delta#varphi")
    hist.GetYaxis().SetTitle("#Delta#eta")

def calculate_bin_width_scale_factor(hist: Hist, additional_scale_factor: float = 1.0) -> float:
    """ Calculate the bin width scale factor of a histogram.

    Args:
        hist: Hist to use for calculating the scale factor.
        additional_scale_factor: An additional scale factor to include in the caluclation.
    Returns:
        The bin width scale factor for the hist.
    """
    # The first bin should always exist!
    bin_width_scale_factor = hist.GetXaxis().GetBinWidth(1)
    # Because of a ROOT quirk, even a TH1* hist has a Y and Z axis, with 1 bin
    # each. This bin has bin width 1, so it doesn't change anything if we multiply
    # by that bin width. So we just do it for all histograms.
    # This has the benefit that we don't need explicit dependence on an imported
    # ROOT package.
    bin_width_scale_factor *= hist.GetYaxis().GetBinWidth(1)
    bin_width_scale_factor *= hist.GetZaxis().GetBinWidth(1)

    final_scale_factor = additional_scale_factor / bin_width_scale_factor

    return final_scale_factor

def scale_by_bin_width(hist: Hist) -> None:
    """ Scale a histogram by it's bin width.

    Args:
        hist: Hist to be scaled.
    Returns:
        None. The histogram is scaled in place.
    """
    scale_factor = calculate_bin_width_scale_factor(hist)
    hist.Scale(scale_factor)

def _peak_finding_objects_from_mixed_event(mixed_event: Hist, eta_limits: Tuple[float, float]) -> Tuple[Hist, np.ndarray]:
    """ Get the peak finding hist and array from the mixed event.

    Used for studying and determining the mixed event normalization.

    We need to project over a range of constant eta to be able to use the extracted max in the 2D
    mixed event. Joel uses [-0.4, 0.4], but it really seems to drop in the 0.4 bin, so instead I'll
    use 0.3 This value also depends on the max track eta. For 0.9, it should be 0.4 (0.9-0.5), but
    for 0.8, it should be 0.3 (0.8-0.5)

    Note:
        This assumes that the delta eta axis is the y axis. This is fairly standard for mixed events,
        so it should be fine.

    Args:
        mixed_event: The mixed event hist.
        eta_limits: Eta limits of which the mixed event should be projection into 1D.
    Returns:
        1D peak finding histogram, numpy array of 1D y values.
    """
    # Scale the 1D norm by the eta range.
    eta_limit_bins = [
        mixed_event.GetYaxis().FindBin(eta_limits[0] + epsilon),
        mixed_event.GetYaxis().FindBin(eta_limits[1] - epsilon),
    ]
    # This is basically just a sanity check that the selected values align with the binning
    projection_length = mixed_event.GetYaxis().GetBinUpEdge(eta_limit_bins[1]) - mixed_event.GetYaxis().GetBinLowEdge(eta_limit_bins[0])
    logger.info(f"Scale factor from 1D to 2D: {mixed_event.GetYaxis().GetBinWidth(1) / projection_length}")
    peak_finding_hist = mixed_event.ProjectionX(
        f"{mixed_event.GetName()}_peak_finding_hist",
        eta_limit_bins[0], eta_limit_bins[1]
    )
    peak_finding_hist.Scale(mixed_event.GetYaxis().GetBinWidth(1) / projection_length)
    peak_finding_hist_array = histogram.Histogram1D(peak_finding_hist).y
    #logger.debug("peak_finding_hist_array: {}".format(peak_finding_hist_array))

    return peak_finding_hist, peak_finding_hist_array

def measure_mixed_event_normalization(mixed_event: Hist, eta_limits: Tuple[float, float]) -> float:
    """ Determine normalization of the mixed event.

    The normalization is determined by using the moving average of half of the histogram.

    We need to project over a range of constant eta to be able to use the extracted max in the 2D
    mixed event. Joel uses [-0.4, 0.4], but it really seems to drop in the 0.4 bin, so instead I'll
    use 0.3 This value also depends on the max track eta. For 0.9, it should be 0.4 (0.9-0.5), but
    for 0.8, it should be 0.3 (0.8-0.5)

    Args:
        mixed_event: Mixed event histogram.
        eta_limits: Min and max eta range limits.
    """
    # Project to 1D delta phi so it can be used with the signal finder
    peak_finding_hist, peak_finding_hist_array = _peak_finding_objects_from_mixed_event(
        mixed_event = mixed_event,
        eta_limits = eta_limits
    )

    # Using moving average
    moving_avg = utils.moving_average(peak_finding_hist_array, n = 36)
    max_moving_avg = max(moving_avg)

    # Finally determine the mixed event normalziation.
    mixed_event_normalization = max_moving_avg
    # Watch out for a zero would could cause problems.
    if not mixed_event_normalization != 0:
        logger.warning(f"Could not normalize the mixed event hist \"{mixed_event.GetName()}\" due to no data at (0,0)!")
        mixed_event_normalization = 1

    return mixed_event_normalization

def compare_mixed_event_normalization_options(mixed_event: Hist,
                                              eta_limits: Tuple[float, float]) -> tuple:
    """ Compare mixed event normalization options.

    The large window over which the normalization is extracted seems to be important to avoid fluctatuions.

    Also allows for comparison of:
        - Continuous wave transform with width ~ pi
        - Smoothing data assuming the points are distributed as a gaussian with options of:
            - Max of smoothed function
            - Moving average over pi of smoothed function
        - Moving average over pi
        - Linear 1D fit
        - Linear 2D fit

    All of the above were also performed over a 2 bin rebin except for the gaussian smoothed function.

    Args:
        mixed_event: The 2D mixed event histogram.
        eta_limits: Eta limits of which the mixed event should be projection into 1D.
    Returns:
        A very complicated tuple containing all of the various compared options. See the code.
    """
    # Create projected histograms
    peak_finding_hist, peak_finding_hist_array = _peak_finding_objects_from_mixed_event(
        mixed_event = mixed_event,
        eta_limits = eta_limits
    )
    # Determine max via the moving average
    # This is what is implemented in the mixed event normalization, but in principle, this could change.
    # Since it's easy to calculate, we do it by hand again here.
    max_moving_avg = max(utils.moving_average(peak_finding_hist_array, n = 36))

    # Create rebinned hist
    # The rebinned hist may be less susceptible to noise, so it should be compared.
    # Only rebin the 2D in delta phi because otherwise the delta eta bins will not align with the limits
    # NOTE: By passing a new name, it will create a new rebinned histogram.
    mixed_event_rebin = mixed_event.Rebin2D(2, 1, f"{mixed_event.GetName()}Rebin")
    # Scale back down to account for the rebin.
    mixed_event_rebin.Scale(1. / 2.)
    peak_finding_hist_rebin = peak_finding_hist.Rebin(2, peak_finding_hist.GetName() + "Rebin")
    # Scale back down to account for the rebin.
    peak_finding_hist_rebin.Scale(1. / 2.)
    # Note that peak finding will only be performed on the 1D hist
    peak_finding_hist_array_rebin = histogram.Histogram1D(peak_finding_hist_rebin).y

    # Define points where the plots and functions can be evaluted
    lin_space = np.linspace(-0.5 * np.pi, 3. / 2 * np.pi, len(peak_finding_hist_array))
    lin_space_rebin = np.linspace(-0.5 * np.pi, 3. / 2 * np.pi, len(peak_finding_hist_array_rebin))

    # Using CWT
    # See: https://docs.scipy.org/doc/scipy-0.14.0/reference/generated/scipy.signal.find_peaks_cwt.html
    # and: https://stackoverflow.com/a/42285002
    peak_locations = scipy.signal.find_peaks_cwt(peak_finding_hist_array, widths = np.arange(20, 50, .1))
    peak_locations_rebin = scipy.signal.find_peaks_cwt(peak_finding_hist_array_rebin, widths = np.arange(10, 25, .05))
    logger.info(f"peak_locations: {peak_locations}, values: {peak_finding_hist_array[peak_locations]}")

    # Using gaussian smoothing
    # See: https://stackoverflow.com/a/22291860
    f = scipy.interpolate.interp1d(lin_space, peak_finding_hist_array)
    # Resample for higher resolution
    lin_space_resample = np.linspace(-0.5 * np.pi, 3. / 2 * np.pi, 7200)
    f_resample = f(lin_space_resample)
    # Gaussian
    # std deviation is in x!
    window = scipy.signal.gaussian(1000, 300)
    smoothed_array = scipy.signal.convolve(f_resample, window / window.sum(), mode="same")
    #max_smoothed = np.amax(smoothed_array)
    #logger.debug("max_smoothed: {}".format(max_smoothed))
    # Moving average on smoothed curve
    smoothed_moving_avg = utils.moving_average(smoothed_array, n = int(len(smoothed_array) // 2))
    max_smoothed_moving_avg = max(smoothed_moving_avg)

    # Moving average with rebin
    moving_avg_rebin = utils.moving_average(peak_finding_hist_array_rebin, n = 18)
    max_moving_avg_rebin = max(moving_avg_rebin)

    # Fit using TF1 over some range
    # Fit the deltaPhi away side
    fit1D = fitting.fit_1d_mixed_event_normalization(peak_finding_hist, [1. / 2. * np.pi, 3. / 2. * np.pi])
    max_linear_fit1D = fit1D.GetParameter(0)
    fit1D_rebin = fitting.fit_1d_mixed_event_normalization(peak_finding_hist_rebin, [1. / 2. * np.pi, 3. / 2. * np.pi])
    max_linear_fit1D_rebin = fit1D_rebin.GetParameter(0)
    fit2D = fitting.fit_2d_mixed_event_normalization(mixed_event, [1. / 2. * np.pi, 3. / 2. * np.pi], eta_limits)
    max_linear_fit2D = fit2D.GetParameter(0)
    fit2D_rebin = fitting.fit_2d_mixed_event_normalization(mixed_event_rebin, [1. / 2. * np.pi, 3. / 2. * np.pi], eta_limits)
    max_linear_fit2D_rebin = fit2D_rebin.GetParameter(0)

    logger.debug(f"linear1D: {max_linear_fit1D}, linear1D_rebin: {max_linear_fit1D_rebin}")
    logger.debug(f"linear2D: {max_linear_fit2D}, linear2D_rebin: {max_linear_fit2D_rebin}")

    return (
        peak_finding_hist,
        # Basic data
        lin_space, peak_finding_hist_array,
        lin_space_rebin, peak_finding_hist_array_rebin,
        # CWT
        peak_locations,
        peak_locations_rebin,
        # Moving Average
        max_moving_avg,
        max_moving_avg_rebin,
        # Smoothed gaussian
        lin_space_resample,
        smoothed_array,
        max_smoothed_moving_avg,
        # Linear fits
        max_linear_fit1D,
        max_linear_fit1D_rebin,
        max_linear_fit2D,
        max_linear_fit2D_rebin,
    )
