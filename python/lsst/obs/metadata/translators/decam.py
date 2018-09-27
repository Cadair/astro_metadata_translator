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

"""Metadata translation code for DECam FITS headers"""

__all__ = ("DecamTranslator", )

import re

from astropy.coordinates import EarthLocation

from .fits import FitsTranslator


class DecamTranslator(FitsTranslator):
    """Metadata translator for DECam standard headers.
    """

    name = "DECam"
    """Name of this translation class"""

    supportedInstrument = "DECam"
    """Supports the DECam instrument."""

    _trivialMap = {"exposure_time": "EXPTIME",
                   "dark_time": "DARKTIME",
                   "boresight_airmass": "AIRMASS",
                   "obsid": "OBSID",
                   "detector_num": "CCDNUM",
                   "detector_name": "DETPOS",
                   "exposure": "EXPNUM",
                   "visit": "EXPNUM"}

    def to_datetime_end(self):
        return self._from_fits_date("DTUTC")

    def _translateFromCalibId(self, field):
        """Fetch the ID from the CALIB_ID header.

        Calibration products made with constructCalibs have some metadata
        saved in its FITS header CALIB_ID.
        """
        data = self._header["CALIB_ID"]
        match = re.search(".*%s=(\S+)" % field, data)
        self._used_these_cards("CALIB_ID")
        return match.groups()[0]

    def to_abstract_filter(self):
        """Calculate the abstract filter.

        Returns
        -------
        filter : `str`
            The abstract filter name.

        """
        # The abstract filter can be derived from the first word in the
        # physical filter description
        physical = self.to_physical_filter()
        if physical:
            return physical.split()[0]

    def to_physical_filter(self):
        """Calculate physical filter.

        Return `None` if the keyword FILTER does not exist in the header,
        which can happen for some valid Community Pipeline products.

        Returns
        -------
        filter : `str`
            The full filter name.
        """
        if "FILTER" in self._header:
            if "OBSTYPE" in self._header and "zero" in self._header["OBSTYPE"].strip().lower():
                return "NONE"
            value = self._header["FILTER"].strip()
            self._used_these_cards("FILTER")
            return value
        elif "CALIB_ID" in self._header:
            return self._translateFromCalibId("filter")
        else:
            return None

    def to_location(self):
        """Calculate the observatory location.

        Returns
        -------
        location : `astropy.coordinates.EarthLocation`
            An object representing the location of the telescope.
        """
        # OBS-LONG has west-positive sign so must be flipped
        lon = self._header["OBS-LONG"] * -1.0
        value = EarthLocation.from_geodetic(lon, self._header["OBS-LAT"], self._header["OBS-ELEV"])
        self._used_these_cards("OBS-LONG", "OBS-LAT", "OBS-ELEV")
        return value
