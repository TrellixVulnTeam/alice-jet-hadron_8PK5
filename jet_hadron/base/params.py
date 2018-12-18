#!/usr/bin/env python

""" Jet-Hadron analysis parameters.

Also contains methods to access that information.

.. codeauthor:: Raymond Ehlers <raymond.ehlers@cern.ch>, Yale University
"""

from builtins import range

import dataclasses
from dataclasses import dataclass
import enum
import logging
import numbers
import numpy as np
import re
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple, Union

from pachyderm import generic_class

logger = logging.getLogger(__name__)

# Bins
# eta is absolute value!
eta_bins = [0, 0.4, 0.6, 0.8, 1.2, 1.5]
track_pt_bins = [0.15, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 10.0]
jet_pt_bins = [15.0, 20.0, 40.0, 60.0, 200.0]
phi_bins = [-1. * np.pi / 2., np.pi / 2., 3. * np.pi / 2]

########
# Utility functions
#######
PtBinIteratorConfig = Optional[Dict[str, Dict[str, Iterable[float]]]]
def iterate_over_pt_bins(name: str, bins: Union[np.ndarray, Sequence[float]], config: PtBinIteratorConfig = None) -> Iterable[float]:
    """ Create a generator of the bins in a requested list.

    Bin skipping should be specified as:

    .. code-block:: python

        >>> config = {
        ...     "skipPtBins" : {
        ...         "name" : [bin1, bin2]
        ...     }
        ... }

    Args:
        name: Name of the skip bin entries in the config.
        bins: Bin edges for determining the bin indices.
        config: Containing information regarding bins to skip, as specified above.
    Returns:
        pt bins generated according to the given arguments.
    """
    # Create a default dict if none is available
    if not config:
        config = {}
    skipPtBins = config.get("skipPtBins", {}).get(name, [])
    # Sanity check on skip pt bins
    for val in skipPtBins:
        if val >= len(bins) - 1:
            raise ValueError(val, "Pt bin to skip {val} is outside the range of the {name} list".format(val = val, name = name))

    for ptBin in range(0, len(bins) - 1):
        if ptBin in skipPtBins:
            continue

        yield ptBin

def iterate_over_jet_pt_bins(config: PtBinIteratorConfig = None) -> Iterable[float]:
    """ Iterate over the available jet pt bins. """
    return iterate_over_pt_bins(config = config, name = "jet", bins = jet_pt_bins)

def iterate_over_track_pt_bins(config: PtBinIteratorConfig = None) -> Iterable[float]:
    """ Iterate over the available track pt bins. """
    return iterate_over_pt_bins(config = config, name = "track", bins = track_pt_bins)

def iterate_over_jet_and_track_pt_bins(config: PtBinIteratorConfig = None) -> Iterable[Tuple[float, float]]:
    """ Iterate over all possible combinations of jet and track pt bins. """
    for jet_pt_bin in iterate_over_jet_pt_bins(config):
        for track_pt_bin in iterate_over_track_pt_bins(config):
            yield (jet_pt_bin, track_pt_bin)

def use_label_with_root(label: str) -> str:
    """ Automatically convert LaTeX to something that is mostly ROOT compatiable.

    Args:
        label: Label to be converted.
    Returns:
        Converted label.
    """
    # Remove "$" and map "\" -> "#""
    return label.replace("$", "").replace("\\", "#")

def uppercase_first_letter(s: str) -> str:
    """ Convert the first letter to uppercase.

    NOTE: Cannot use `str.capitalize()` or `str.title()` because they lowercase the rest of the string.

    Args:
        s: String to be convert
    Returns:
        String with first letter converted to uppercase.
    """
    return s[:1].upper() + s[1:]

#########
# Parameter information (access and display)
#########
class AliceLabel(enum.Enum):
    """ ALICE label types. """
    work_in_progress = "ALICE Work in Progress"
    preliminary = "ALICE Preliminary"
    final = "ALICE"
    thesis = "This thesis"

    def __str__(self) -> str:
        """ Return the value. This is just a convenience function.

        Note:
            This is backwards of the usual convention of returning the name, but the value is
            more meaningful here. The name can always be accessed with ``.name``.
        """
        return str(self.value)

def system_label(energy: Union[float, "CollisionEnergy"], system: Union[str, "CollisionSystem"], activity: Union[str, "EventActivity"]) -> str:
    """ Generates the collision system, event activity, and energy label.

    Args:
        energy: The collision energy
        system: The collision system.
        activity: The event activity selection.
    Returns:
        Label for the entire system, combining the avaialble information.
    """
    # Handle energy
    if isinstance(energy, numbers.Number):
        energy = CollisionEnergy(energy)
    elif isinstance(energy, str):
        try:
            e = float(energy)
            energy = CollisionEnergy(e)
        except ValueError:
            energy = CollisionEnergy[energy]  # type: ignore
    # Ensure that we've done our conversion correctly. This also helps the type system.
    assert isinstance(energy, CollisionEnergy)

    # Handle collision system
    if isinstance(system, str):
        system = CollisionSystem[system]  # type: ignore

    # Handle event activity
    if isinstance(activity, str):
        activity = EventActivity[activity]  # type: ignore

    system_label = r"$\mathrm{%(system)s}\:%(energy)s%(event_activity)s$" % {
        "energy": energy.display_str(),
        "event_activity": activity.display_str(),
        "system": system.display_str(),
    }

    logger.debug("system_label: {}".format(system_label))

    return system_label

def generate_pt_range_string(arr: Union[np.ndarray, Sequence[float]], bin_val: int, lower_label: str, upper_label: str, only_show_lower_value_for_last_bin: bool = False) -> str:
    """ Generate string to describe pt ranges for a given list.

    Args:
        arr: Bin edges for use in determining the values lower and upper values.
        bin_val: Generate the range for this bin.
        lower_label: Subscript label for pT.
        upper_label: Superscript labe for pT.
        only_show_lower_value_for_last_bin: If True, skip show the upper value.
    Returns:
        The pt range label.
    """
    # Cast as string so we don't have to deal with formatting the extra digits
    lower = "%(lower)s < " % {"lower": arr[bin_val]}
    upper = " < %(upper)s" % {"upper": arr[bin_val + 1]}
    if only_show_lower_value_for_last_bin and bin_val == len(arr) - 2:
        upper = ""
    pt_range = r"$%(lower)s\mathit{p}_{%(lower_label)s}^{%(upper_label)s}%(upper)s\:\mathrm{GeV/\mathit{c}}$" % {
        "lower": lower,
        "upper": upper,
        "lower_label": lower_label,
        "upper_label": upper_label,
    }

    return pt_range

def generate_jet_pt_range_string(jet_pt_bin: int) -> str:
    """ Generate a label for the jet pt range based on the jet pt bin.

    Args:
        jet_pt_bin: Jet pt bin.
    Returns:
        Jet pt range label.
    """
    return generate_pt_range_string(
        arr = jet_pt_bins,
        bin_val = jet_pt_bin,
        lower_label = r"\mathrm{T \,unc,jet}",
        upper_label = r"\mathrm{ch+ne}",
        only_show_lower_value_for_last_bin = True,
    )

def generate_track_pt_range_string(track_pt_bin: int, pt_bins: Optional[Union[np.ndarray, Sequence[float]]] = None) -> str:
    """ Generate a label for the track pt range based on the track pt bin.

    Args:
        track_pt_bin: Track pt bin.
        pt_bins: Track pt bins. Defaults to the default jet-h track pt bins if not specified.
    Returns:
        Track pt range label.
    """
    return generate_pt_range_string(
        arr = pt_bins if pt_bins is not None else track_pt_bins,
        bin_val = track_pt_bin,
        lower_label = r"\mathrm{T}",
        upper_label = r"\mathrm{assoc}",
    )

def jet_properties_label(jet_pt_bin: int) -> Tuple[str, str, str, str]:
    """ Return the jet finding properties based on the jet pt bin.

    Args:
        jet_pt_bin (int): Jet pt bin
    Returns:
        tuple: (jet_finding, constituent_cuts, leading_hadron, jet_pt)
    """
    jet_finding = r"$\mathrm{anti\mbox{-}k}_{\mathrm{T}}\;R=0.2$"
    constituent_cuts = r"$\mathit{p}_{\mathrm{T}}^{\mathrm{ch}}\:\mathrm{\mathit{c},}\:\mathrm{E}_{\mathrm{T}}^{\mathrm{clus}} > 3\:\mathrm{GeV}$"
    leading_hadron = r"$\mathit{p}_{\mathrm{T}}^{\mathrm{lead,ch}} > 5\:\mathrm{GeV/\mathit{c}}$"
    jet_pt = generate_jet_pt_range_string(jet_pt_bin)
    return (jet_finding, constituent_cuts, leading_hadron, jet_pt)

##################
# Analysis Options
##################
# These options specify the base of what is necessary to
# define an analysis.
##################

#########################
## Helpers and containers
#########################
@dataclass
class SelectedRange:
    min: float
    max: float

#########
# Classes
#########
class CollisionEnergy(enum.Enum):
    """ Define the available collision system energies. """
    twoSevenSix = 2.76
    fiveZeroTwo = 5.02

    def __str__(self) -> str:
        """ Returns a string of the value. """
        return str(self.value)

    def display_str(self) -> str:
        """ Return a formatted string for display in plots, etc. Includes latex formatting. """
        return r"\sqrt{s_{\mathrm{NN}}} = %(energy)s\:\mathrm{TeV}" % {"energy": self.value}

# NOTE: Usually, "Pb--Pb" is used in latex, but ROOT won't render it properly...
PbPbLatexLabel = r"Pb\mbox{-}Pb"

class CollisionSystem(enum.Enum):
    """ Define the collision system """
    NA = "Invalid collision system"
    pp = "pp"
    pythia = "PYTHIA"
    embedPP = r"pp \bigotimes %(PbPb)s" % {"PbPb": PbPbLatexLabel}
    embedPythia = r"PYTHIA \bigotimes %(PbPb)s" % {"PbPb": PbPbLatexLabel}
    pPb = r"pPb"
    PbPb = "%(PbPb)s" % {"PbPb": PbPbLatexLabel}

    def __str__(self) -> str:
        """ Return a string of the name of the system. """
        return self.name

    def display_str(self) -> str:
        """ Return a formatted string for display in plots, etc. Includes latex formatting. """
        return self.value

class EventActivity(enum.Enum):
    """ Define the event activity.

    Object value are of the form (index, (centLow, centHigh)), where index is the expected
    enumeration index, and cent{low,high} define the low and high values of the centrality.
    -1 is defined as the full range!
    """
    inclusive = SelectedRange(min = -1, max = -1)
    central = SelectedRange(min = 0, max = 10)
    semiCentral = SelectedRange(min = 30, max = 50)

    @property
    def value_range(self) -> SelectedRange:
        """ Return the event activity range.

        Returns:
            SelectedRange : namedtuple containing the mix and max of the range.
        """
        return self.value

    def __str__(self) -> str:
        """ Name of the event activity range. """
        return str(self.name)

    def display_str(self) -> str:
        """ Get the event activity range as a formatted string. Includes latex formatting. """
        ret_val = ""
        # For inclusive, we want to return an empty string.
        if self != EventActivity.inclusive:
            logger.debug(f"asdict: {dataclasses.asdict(self.value_range)}")
            ret_val = r",\:%(min)s\mbox{-}%(max)s\mbox{\%%}" % dataclasses.asdict(self.value_range)
        return ret_val

class LeadingHadronBiasType(enum.Enum):
    """ Leading hadron bias type """
    NA = -1
    track = 0
    cluster = 1
    both = 2

    def __str__(self) -> str:
        """ Return the name of the bias. It must be just the name for the config override to work properly. """
        return self.name

########################
# Final anaylsis options
########################
# These classes are used for final analysis specification, building
# on the analysis specification objects specified above.
########################
class LeadingHadronBias(generic_class.EqualityMixin):
    """ Full leading hadron bias class, which specifies both the type as well as the value.

    The class exists to be specified when creating an analysis object, and then the value is
    determined by the selected analysis options (including that enum). This object then
    supercedes the leadingHadronBiasType enum, storing both the type and value.

    For determining the actual value, see anaylsisConfig.determineLeadingHadronBias(...)

    Args:
        type (params.leadingHadronBiasType): Type of leading hadron bias.
        value (float): Value of the leading hadron bias.
    """
    def __init__(self, type, value):
        self.type = type
        # If the leadingHadronBias is disabled, then the value is irrelevant and
        # should be set to 0.
        if self.type == LeadingHadronBiasType.NA:
            value = 0
        self.value = value

    def __str__(self) -> str:
        """ Return a string representation.

        Return the type and value, such as "clusterBias6" or "trackBias5". In the case of the bias
        as NA, it simply returns "NA".
        """
        if self.type != LeadingHadronBiasType.NA:
            return "{type}Bias{value}".format(type = self.type, value = self.value)
        else:
            return "{type}".format(type = self.type, value = self.value)

@dataclass
class SelectedAnalysisOptions:
    collision_energy: CollisionEnergy
    collision_system: CollisionSystem
    event_activity: EventActivity
    leading_hadron_bias: Union[LeadingHadronBias, LeadingHadronBiasType]

    def asdict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    def __iter__(self) -> Iterable[Any]:
        return iter(dataclasses.astuple(self))

# For use with overriding configuration values
SetOfPossibleOptions = SelectedAnalysisOptions(CollisionEnergy,  # type: ignore
                                               CollisionSystem,
                                               EventActivity,
                                               LeadingHadronBiasType)

##############################
# Additional selection options
##############################
# These are distinct from the above because they do not need to be used
# to specify a configuration. Thus, they don't need to be looped over.
# Instead, they are stored in a particular analysis object and used as
# analysis options.
##############################
class EventPlaneAngle(enum.Enum):
    """ Selects the event plane angle in the sparse. """
    all = 0
    inPlane = 1
    midPlane = 2
    outOfPlane = 3

    def __str__(self) -> str:
        """ Returns the event plane angle name, as is. """
        return self.name

    def display_str(self) -> str:
        """ For example, turns outOfPlane into "Out-of-plane".

        Note:
            We want the capitalize call to lowercase all other letters.
        """
        # See: https://stackoverflow.com/a/2277363
        tempList = re.findall("[a-zA-Z][^A-Z]*", str(self))
        return "-".join(tempList).capitalize()

class QVector(enum.Enum):
    """ Selection based on the Q vector. """
    all = SelectedRange(min = 0, max = 100)
    bottom10 = SelectedRange(min = 0, max = 10)
    top10 = SelectedRange(min = 90, max = 100)

    @property
    def value_range(self) -> SelectedRange:
        """ Return the q vector range.

        Returns:
            dataclass containing the mix and max of the range.
        """
        return self.value

    def __str__(self) -> str:
        """ Returns the name of the selection range. """
        return self.name

    def display_str(self) -> str:
        """ Turns "bottom10" into "Bottom 10%". """
        # This also works for "all" -> "All"
        match = re.match("([a-z]*)([0-9]*)", self.name)
        if not match:
            raise ValueError("Could not extract Q Vector value \"{self.name}\" for printing.")
        temp_list = match.groups()
        ret_val = uppercase_first_letter(" ".join(temp_list))
        if self.name != "all":
            ret_val += "%"
        # rstrip() is to remove entra space after "All". Doesn't matter for the other values.
        return ret_val.rstrip(" ")

