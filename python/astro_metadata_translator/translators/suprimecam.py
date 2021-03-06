# This file is part of astro_metadata_translator.
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

"""Metadata translation code for SuprimeCam FITS headers"""

__all__ = ("SuprimeCamTranslator", )

import re
import logging

import astropy.units as u
from astropy.coordinates import SkyCoord, AltAz, Angle

from ..translator import cache_translation
from .subaru import SubaruTranslator

log = logging.getLogger(__name__)


class SuprimeCamTranslator(SubaruTranslator):
    """Metadata translator for HSC standard headers.
    """

    name = "SuprimeCam"
    """Name of this translation class"""

    supported_instrument = "SuprimeCam"
    """Supports the SuprimeCam instrument."""

    _const_map = {"boresight_rotation_coord": "unknown"}
    """Constant mappings"""

    _trivial_map = {"observation_id": "EXP-ID",
                    "object": "OBJECT",
                    "science_program": "PROP-ID",
                    "detector_num": "DET-ID",
                    "detector_name": "DETECTOR",
                    "boresight_airmass": "AIRMASS",
                    "relative_humidity": "OUT-HUM",
                    "temperature": ("OUT-TMP", dict(unit=u.K)),
                    "pressure": ("OUT-PRS", dict(unit=u.hPa)),
                    "exposure_time": ("EXPTIME", dict(unit=u.s)),
                    "dark_time": ("EXPTIME", dict(unit=u.s)),  # Assume same as exposure time
                    }
    """One-to-one mappings"""

    # Zero point for SuprimeCam dates: 2004-01-01
    _DAY0 = 53005

    @classmethod
    def can_translate(cls, header):
        """Indicate whether this translation class can translate the
        supplied header.

        Parameters
        ----------
        header : `dict`-like
           Header to convert to standardized form.

        Returns
        -------
        can : `bool`
            `True` if the header is recognized by this class. `False`
            otherwise.
        """
        if "INSTRUME" in header:
            return header["INSTRUME"] == "SuprimeCam"

        for k in ("EXP-ID", "FRAMEID"):
            if k in header:
                if header[k].startswith("SUP"):
                    return True
        return False

    def _get_adjusted_mjd(self):
        """Calculate the modified julian date offset from reference day

        Returns
        -------
        offset : `int`
            Offset day count from reference day.
        """
        mjd = self._header["MJD"]
        self._used_these_cards("MJD")
        return int(mjd) - self._DAY0

    @cache_translation
    def to_physical_filter(self):
        # Docstring will be inherited. Property defined in properties.py
        value = self._header["FILTER01"].strip().upper()
        self._used_these_cards("FILTER01")
        return value

    @cache_translation
    def to_datetime_begin(self):
        # Docstring will be inherited. Property defined in properties.py
        # We know it is UTC
        value = self._from_fits_date_string(self._header["DATE-OBS"],
                                            time_str=self._header["UT"], scale="utc")
        self._used_these_cards("DATE-OBS", "UT")
        return value

    @cache_translation
    def to_datetime_end(self):
        # Docstring will be inherited. Property defined in properties.py
        # We know it is UTC
        value = self._from_fits_date_string(self._header["DATE-OBS"],
                                            time_str=self._header["UT-END"], scale="utc")
        self._used_these_cards("DATE-OBS", "UT-END")
        return value

    @cache_translation
    def to_exposure_id(self):
        """Calculate unique exposure integer for this observation

        Returns
        -------
        visit : `int`
            Integer uniquely identifying this exposure.
        """
        exp_id = self._header["EXP-ID"].strip()
        m = re.search(r"^SUP[A-Z](\d{7})0$", exp_id)
        if not m:
            raise RuntimeError("Unable to interpret EXP-ID: %s" % exp_id)
        exposure = int(m.group(1))
        if int(exposure) == 0:
            # Don't believe it
            frame_id = self._header["FRAMEID"].strip()
            m = re.search(r"^SUP[A-Z](\d{7})\d{1}$", frame_id)
            if not m:
                raise RuntimeError("Unable to interpret FRAMEID: %s" % frame_id)
            exposure = int(m.group(1))
        self._used_these_cards("EXP-ID", "FRAMEID")
        return exposure

    @cache_translation
    def to_visit_id(self):
        """Calculate the unique integer ID for this visit.

        Assumed to be identical to the exposure ID in this implementation.

        Returns
        -------
        exp : `int`
            Unique visit identifier.
        """
        if self.to_observation_type() == "science":
            return self.to_exposure_id()
        return None

    @cache_translation
    def to_observation_type(self):
        """Calculate the observation type.

        Returns
        -------
        typ : `str`
            Observation type. Normalized to standard set.
        """
        obstype = self._header["DATA-TYP"].strip().lower()
        self._used_these_cards("DATA-TYP")
        if obstype == "object":
            return "science"
        return obstype

    @cache_translation
    def to_tracking_radec(self):
        # Docstring will be inherited. Property defined in properties.py
        radec = SkyCoord(self._header["RA2000"], self._header["DEC2000"],
                         frame="icrs", unit=(u.hourangle, u.deg),
                         obstime=self.to_datetime_begin(), location=self.to_location())
        self._used_these_cards("RA2000", "DEC2000")
        return radec

    @cache_translation
    def to_altaz_begin(self):
        # Docstring will be inherited. Property defined in properties.py
        altitude = self._header["ALTITUDE"]
        if altitude > 90.0:
            log.warning("Clipping altitude (%f) at 90 degrees", altitude)
            altitude = 90.0

        altaz = AltAz(self._header["AZIMUTH"] * u.deg, altitude * u.deg,
                      obstime=self.to_datetime_begin(), location=self.to_location())
        self._used_these_cards("AZIMUTH", "ALTITUDE")
        return altaz

    @cache_translation
    def to_boresight_rotation_angle(self):
        # Docstring will be inherited. Property defined in properties.py
        angle = Angle(self.quantity_from_card("INR-STR", u.deg))
        angle = angle.wrap_at("360d")
        return angle

    @cache_translation
    def to_detector_exposure_id(self):
        # Docstring will be inherited. Property defined in properties.py
        return self.to_exposure_id() * 10 + self.to_detector_num()
