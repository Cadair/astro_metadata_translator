# This file is part of obs_metadata.
#
# Developed for the LSST Data Management System.
# This product includes software developed by the LSST Project
# (http://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Represent standard metadata from instrument headers"""

__all__ = ("ObservationInfo", )

import logging
import copy

from .translator import MetadataTranslator

log = logging.getLogger(__name__)


class ObservationInfo:
    """Standardized representation of an instrument header for a single
    exposure observation.

    Parameters
    ----------
    header : `dict`-like
        Representation of an instrument header accessible as a `dict`.
    translator_class : `MetadataTranslator`-class, `optional`
        If not `None`, the class to use to translate the supplied headers
        into standard form. Otherwise each registered translator class will
        be asked in turn if it knows how to translate the supplied header.

    Raises
    ------
    ValueError
        The supplied header was not recognized by any of the registered
        translators.
    TypeError
        The supplied translator class was not a MetadataTranslator.
    """

    _PROPERTIES = {"telescope": ("Full name of the telescope", "str"),
                   "instrument": ("The instrument used to observe the Exposure", "str"),
                   "location": ("Location of the observatory", "astropy.coordinates.EarthLocation"),
                   "exposure": ("Unique (with instrument) integer identifier for this observation", "int"),
                   "visit": ("""ID of the Visit this Exposure is associated with.

    Science observations should essentially always be
    associated with a visit, but calibration observations
    may not be.""", "int"),
                   "abstract_filter": ("Generic name of this filter", "str"),
                   "physical_filter": ("The bandpass filter used for all exposures in this Visit.", "str"),
                   "datetime_begin": ("Timestamp of the start of the Exposure.", "astropy.time.Time"),
                   "datetime_end": ("Timestamp of the end of the Exposure.", "astropy.time.Time"),
                   "exposure_time": ("Duration of the Exposure with shutter open (seconds).", "float"),
                   "dark_time": ("Duration of the Exposure with shutter closed (seconds).", "float"),
                   "boresight_airmass": ("Airmass of the boresight of the telescope", "float"),
                   "boresight_rotation_angle": ("Angle of the instrument in boresight_rotation_coord frame",
                                                "astropy.coordinates.Angle"),
                   "boresight_rotation_coord": ("Coordinate frame of the instrument rotation angle"
                                                " (options: sky, unknown)", "str"),
                   "detector_num": ("Unique (for instrument) integer identifier for the sensor", "int"),
                   "detector_name": ("Name of the detector within the instrument (might not be unique)",
                                     "str"),
                   "detector_exposure_id": ("Unique integer identifier for this detector in this exposure",
                                            "int"),
                   "object": ("Object of interest or field name", "str"),
                   "temperature": ("Temperature outside the dome", "astropy.units.Quantity"),
                   "pressure": ("Atmospheric pressure outside the dome", "astropy.units.Quantity"),
                   "relative_humidity": ("Relative humidity outside the dome", "float"),
                   "tracking_radec": ("Requested RA/Dec to track", "astropy.coordinates.SkyCoord"),
                   "altaz_begin": ("Telescope boresight azimuth and elevation at start of observation",
                                   "astropy.coordinates.AltAz"),
                   "science_program": ("Observing program (survey or proposal) identifier", "str"),
                   "obstype": ("Type of observation (currently: science, dark, flat, bias, focus)",
                               "str"),
                   "obsid": ("Label uniquely identifying this observation (can be related to 'exposure')",
                             "str")}

    """All the properties supported by this class with associated
    documentation."""

    def __init__(self, header, translator_class=None):

        # Store the supplied header for later stripping
        self._header = header

        # PropertyList is not dict-like so force to a dict here to simplify
        # the translation code.
        if hasattr(header, "toOrderedDict"):
            header = header.toOrderedDict()

        if translator_class is None:
            translator_class = MetadataTranslator.determineTranslator(header)
        elif not issubclass(translator_class, MetadataTranslator):
            raise TypeError(f"Translator class must be a MetadataTranslator, not {translator_class}")

        # Create an instance for this header
        translator = translator_class(header)

        # Store the translator
        self._translator = translator

        # Loop over each translation (not final form -- this should be
        # defined in one place and consistent with translation classes)

        for t in self._PROPERTIES:
            # prototype code
            method = f"to_{t}"
            property = f"_{t}"

            try:
                setattr(self, property, getattr(translator, method)())
            except AttributeError:
                log.warning("No translation exists for property %s using translator %s",
                            t, translator.__class__)
            except KeyError:
                log.warning("Error calculating property %s using translator %s",
                            t, translator.__class__, exc_info=1)

    @property
    def cards_used(self):
        return self._translator.cards_used()

    def strippedHeader(self):
        """Return a copy of the supplied header with used keywords removed.

        Returns
        -------
        stripped : `dict`-like
            Same class as header supplied to constructor, but with the
            headers used to calculate the generic information removed.
        """
        hdr = copy.copy(self._header)
        used = self._translator.cards_used()
        for c in used:
            del hdr[c]
        return hdr


# Method to add the standard properties
def _makeProperty(property, doc, return_type):
    """Create a getter method with associated docstring

    Parameters
    ----------
    property : `str`
        Name of the property getter to be created.
    doc : `str`
        Description of this property.
    return_type : `str`
        Type of this property (used in the doc string).

    Returns
    -------
    p : `function`
        Getter method for this property.
    """
    def getter(self):
        return getattr(self, f"_{property}")

    getter.__doc__ = f"""{doc}

    Returns
    -------
    {property} : `{return_type}`
        Access the property.
    """
    return getter


# Initialize the internal properties (underscored) and add the associated
# getter methods.
for name, description in ObservationInfo._PROPERTIES.items():
    setattr(ObservationInfo, f"_{name}", None)
    setattr(ObservationInfo, name, property(_makeProperty(name, *description)))
