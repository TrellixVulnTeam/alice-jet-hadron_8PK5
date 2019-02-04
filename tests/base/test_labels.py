#!/usr/bin/env python

""" Tests for analysis labels.

.. codeauthor:: Raymond Ehlers <raymond.ehlers@cern.ch>, Yale University
"""

import logging
import pytest

from jet_hadron.base import analysis_objects
from jet_hadron.base import labels
from jet_hadron.base import params

# Setup logger
logger = logging.getLogger(__name__)

@pytest.mark.parametrize("value, expected", [
    (r"\textbf{test}", r"#textbf{test}"),
    (r"$\mathrm{test}$", r"#mathrm{test}")
], ids = ["just latex", "latex in math mode"])
def test_root_latex_conversion(logging_mixin, value, expected):
    """ Test converting latex to ROOT compatiable latex. """
    assert labels.use_label_with_root(value) == expected

class TestTrackPtString:
    track_pt_bins = [0.15, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 10.0]

    def test_track_pt_strings(self, logging_mixin):
        """ Test the track pt string generation functions. Each bin is tested.  """
        pt_bins = []
        for i, (min, max) in enumerate(zip(self.track_pt_bins[:-1], self.track_pt_bins[1:])):
            pt_bins.append(
                analysis_objects.TrackPtBin(
                    bin = i,
                    range = params.SelectedRange(min, max)
                )
            )

        for pt_bin, expected_min, expected_max in zip(pt_bins, self.track_pt_bins[:-1], self.track_pt_bins[1:]):
            logger.debug(f"Checking bin {pt_bin}, {pt_bin.range}, {type(pt_bin)}")
            assert labels.track_pt_range_string(pt_bin) == r"$%(lower)s < \mathit{p}_{\mathrm{T}}^{\mathrm{assoc}} < %(upper)s\:\mathrm{GeV/\mathit{c}}$" % {"lower": expected_min, "upper": expected_max}

class TestJetPtString:
    # NOTE: The -1 is important for the final bin to be understood correctly as the last bin!
    jet_pt_bins = [15.0, 20.0, 40.0, 60.0, -1]

    def test_jet_pt_string(self, logging_mixin):
        """ Test the jet pt string generation functions. Each bin (except for the last) is tested.

        The last pt bin is left for a separate test because it is printed differently
        (see ``test_jet_pt_string_for_last_pt_bin()`` for more).
        """
        pt_bins = []
        for i, (min, max) in enumerate(zip(self.jet_pt_bins[:-2], self.jet_pt_bins[1:-1])):
            pt_bins.append(
                analysis_objects.JetPtBin(
                    bin = i,
                    range = params.SelectedRange(min, max)
                )
            )

        for pt_bin, expected_min, expected_max in zip(pt_bins, self.jet_pt_bins[:-2], self.jet_pt_bins[1:-1]):
            logger.debug(f"Checking bin {pt_bin}, {pt_bin.range}, {type(pt_bin)}")
            assert labels.jet_pt_range_string(pt_bin) == r"$%(lower)s < \mathit{p}_{\mathrm{T \,unc,jet}}^{\mathrm{ch+ne}} < %(upper)s\:\mathrm{GeV/\mathit{c}}$" % {"lower": expected_min, "upper": expected_max}

    def test_jet_pt_string_for_last_pt_bin(self, logging_mixin):
        """ Test the jet pt string generation function for the last jet pt bin.

        In the case of the last pt bin, we only want to show the lower range.
        """
        pt_bin = len(self.jet_pt_bins) - 2
        jet_pt_bin = analysis_objects.JetPtBin(
            bin = pt_bin,
            range = params.SelectedRange(
                self.jet_pt_bins[pt_bin],
                self.jet_pt_bins[pt_bin + 1]
            )
        )
        assert labels.jet_pt_range_string(jet_pt_bin) == r"$%(lower)s < \mathit{p}_{\mathrm{T \,unc,jet}}^{\mathrm{ch+ne}}\:\mathrm{GeV/\mathit{c}}$" % {"lower": self.jet_pt_bins[-2]}

@pytest.mark.parametrize("energy, system, activity, expected", [
    (2.76, "pp", "inclusive", r"$\mathrm{pp}\:\sqrt{s_{\mathrm{NN}}} = 2.76\:\mathrm{TeV}$"),
    (2.76, "PbPb", "central", r"$\mathrm{Pb\mbox{-}Pb}\:\sqrt{s_{\mathrm{NN}}} = 2.76\:\mathrm{TeV},\:0\mbox{-}10\mbox{\%}$"),
    (2.76, "PbPb", "semi_central", r"$\mathrm{Pb\mbox{-}Pb}\:\sqrt{s_{\mathrm{NN}}} = 2.76\:\mathrm{TeV},\:30\mbox{-}50\mbox{\%}$"),
    (5.02, "PbPb", "central", r"$\mathrm{Pb\mbox{-}Pb}\:\sqrt{s_{\mathrm{NN}}} = 5.02\:\mathrm{TeV},\:0\mbox{-}10\mbox{\%}$"),
    ("five_zero_two", "PbPb", "central", r"$\mathrm{Pb\mbox{-}Pb}\:\sqrt{s_{\mathrm{NN}}} = 5.02\:\mathrm{TeV},\:0\mbox{-}10\mbox{\%}$"),
    ("5.02", "PbPb", "central", r"$\mathrm{Pb\mbox{-}Pb}\:\sqrt{s_{\mathrm{NN}}} = 5.02\:\mathrm{TeV},\:0\mbox{-}10\mbox{\%}$"),
    (params.CollisionEnergy.five_zero_two, params.CollisionSystem.PbPb, params.EventActivity.central, r"$\mathrm{Pb\mbox{-}Pb}\:\sqrt{s_{\mathrm{NN}}} = 5.02\:\mathrm{TeV},\:0\mbox{-}10\mbox{\%}$")
], ids = ["Inclusive pp", "Central PbPb", "Semi-central PbPb", "Central PbPb at 5.02", "Energy as string five_zero_two", "Energy as string \"5.02\"", "Using enums directly"])
def test_system_label(logging_mixin, energy, system, activity, expected):
    """ Test system labels. """
    assert labels.system_label(energy = energy, system = system, activity = activity) == expected

def test_jet_properties_labels(logging_mixin):
    """ Test the jet properties labels. """
    jet_pt_bin = analysis_objects.JetPtBin(bin = 1, range = params.SelectedRange(20.0, 40.0))
    (jet_finding_expected, constituent_cuts_expected, leading_hadron_expected, jet_pt_expected) = (
        r"$\mathrm{anti\mbox{-}k}_{\mathrm{T}}\;R=0.2$",
        r"$\mathit{p}_{\mathrm{T}}^{\mathrm{ch}}\:\mathrm{\mathit{c},}\:\mathrm{E}_{\mathrm{T}}^{\mathrm{clus}} > 3\:\mathrm{GeV}$",
        r"$\mathit{p}_{\mathrm{T}}^{\mathrm{lead,ch}} > 5\:\mathrm{GeV/\mathit{c}}$",
        r"$20.0 < \mathit{p}_{\mathrm{T \,unc,jet}}^{\mathrm{ch+ne}} < 40.0\:\mathrm{GeV/\mathit{c}}$"
    )

    (jet_finding, constituent_cuts, leading_hadron, jet_pt) = labels.jet_properties_label(jet_pt_bin)

    assert jet_finding == jet_finding_expected
    assert constituent_cuts == constituent_cuts_expected
    assert leading_hadron == leading_hadron_expected
    assert jet_pt == jet_pt_expected

@pytest.mark.parametrize("upper_label, expected", [
    ("", r"\mathit{p}_{\mathrm{T,jet}}^{}"),
    (r"\mathrm{det}", r"\mathit{p}_{\mathrm{T,jet}}^{\mathrm{det}}")
], ids = ["Base test", "Superscript"])
def test_jet_pt_range_string(logging_mixin, upper_label, expected):
    """ Test for generating jet pt labels. """
    # Determine args. Only call with an argument if we've specified one so we can test the default args.
    kwargs = {}
    if upper_label != "":
        kwargs["upper_label"] = upper_label

    output = labels.jet_pt_display_label(**kwargs)
    assert output == expected

def test_gev_momentum_units_label(logging_mixin):
    """ Test generating GeV/c label in latex. """
    output = labels.momentum_units_label_gev()
    expected = r"\mathrm{GeV/\mathit{c}}"
    assert output == expected
