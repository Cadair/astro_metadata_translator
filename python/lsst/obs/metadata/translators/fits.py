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

"""Metadata translation code for standard FITS headers"""

__all__ = ("FitsTranslator", )

from astropy.time import Time
from astropy.coordinates import EarthLocation
import astropy.units as u

from ..translator import MetadataTranslator


class FitsTranslator(MetadataTranslator):
    """Metadata translator for FITS standard headers.

    Understands:

    - DATE-OBS
    - INSTRUME
    - TELESCOP
    - OBSGEO-[X,Y,Z]

    """

    # Direct translation from header key to standard form
    _trivialMap = dict(instrument="INSTRUME",
                       telescope="TELESCOP")

    @classmethod
    def canTranslate(cls, header):
        """Indicate whether this translation class can translate the
        supplied header.

        Checks the instrument value and compares with the supported
        instruments in the class

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
        if cls.supportedInstrument is None:
            return False

        # Protect against being able to always find a standard
        # header for instrument
        try:
            translator = cls(header)
            instrument = translator.to_instrument()
        except KeyError:
            return False

        return instrument == cls.supportedInstrument

    @classmethod
    def _from_fits_date_string(cls, dateStr, scale='utc', timeStr=None):
        """Parse standard FITS ISO-style date string and return time object

        Parameters
        ----------
        dateStr : `str`
            FITS format date string to convert to standard form. Bypasses
            lookup in the header.
        scale : `str`, optional
            Override the time scale from the TIMESYS header. Defaults to
            UTC.
        timeStr : `str`, optional
            If provided, overrides any time component in the ``dateStr``,
            retaining the YYYY-MM-DD component and appending this time
            string, assumed to be of format HH:MM::SS.ss.

        Returns
        -------
        date : `astropy.time.Time`
            `~astropy.time.Time` representation of the date.
        """
        if timeStr is not None:
            dateStr = "{}T{}".format(dateStr[:10], timeStr)

        return Time(dateStr, format="isot", scale=scale)

    def _from_fits_date(self, dateKey):
        """Calculate a date object from the named FITS header

        Uses the TIMESYS header if present to determine the time scale,
        defaulting to UTC.

        Parameters
        ----------
        dateKey : `str`
            The key in the header representing a standard FITS
            ISO-style date.

        Returns
        -------
        date : `astropy.time.Time`
            `~astropy.time.Time` representation of the date.
        """
        used = [dateKey, ]
        if "TIMESYS" in self._header:
            scale = self._header["TIMESYS"].lower()
            used.append("TIMESYS")
        else:
            scale = "utc"
        dateStr = self._header[dateKey]
        value = self._from_fits_date_string(dateStr, scale=scale)
        self._used_these_cards(*used)
        return value

    def to_datetime_begin(self):
        """Calculate start time of observation.

        Uses FITS standard ``DATE-OBS`` and ``TIMESYS`` headers.

        Returns
        -------
        start_time : `astropy.time.Time`
            Time corresponding to the start of the observation.
        """
        return self._from_fits_date("DATE-OBS")

    def to_datetime_end(self):
        """Calculate end time of observation.

        Uses FITS standard ``DATE-END`` and ``TIMESYS`` headers.

        Returns
        -------
        start_time : `astropy.time.Time`
            Time corresponding to the end of the observation.
        """
        return self._from_fits_date("DATE-END")

    def to_location(self):
        """Calculate the observatory location.

        Uses FITS standard ``OBSGEO-`` headers.

        Returns
        -------
        location : `astropy.coordinates.EarthLocation`
            An object representing the location of the telescope.
        """
        cards = [f"OBSGEO-{c}" for c in ("X", "Y", "Z")]
        coords = [self._header[c] for c in cards]
        value = EarthLocation.from_geocentric(*coords, unit=u.m)
        self._used_these_cards(*cards)
        return value
