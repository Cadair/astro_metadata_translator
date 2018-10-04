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

"""Metadata translation code for HSC FITS headers"""

__all__ = ("HscTranslator", )

import re
import logging

import astropy.units as u
from astropy.coordinates import Angle

from .suprimecam import SuprimeCamTranslator

log = logging.getLogger(__name__)


class HscTranslator(SuprimeCamTranslator):
    """Metadata translator for HSC standard headers.
    """

    name = "HSC"
    """Name of this translation class"""

    supportedInstrument = "HSC"
    """Supports the HSC instrument."""

    _constMap = {"instrument": "HSC",
                 "boresight_rotation_coord": "sky"}
    """Hard wire HSC even though modern headers call it Hyper Suprime-Cam"""

    _trivialMap = {"detector_name": "T_CCDSN",
                   }
    """One-to-one mappings"""

    @classmethod
    def canTranslate(cls, header):
        """Indicate whether this translation class can translate the
        supplied header.

        There is no ``INSTRUME`` header in early HSC files, so this method
        looks for HSC mentions in other headers.  In more recent files the
        instrument is called "Hyper Suprime-Cam".

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
            return header["INSTRUME"] == "Hyper Suprime-Cam"

        for k in ("EXP-ID", "FRAMEID"):
            if k in header:
                if header[k].startswith("HSC"):
                    return True
        return False

    def to_abstract_filter(self):
        physical = self.to_physical_filter()
        if physical.startswith("HSC-"):
            return physical[4].lower()
        return None

    def to_exposure(self):
        """Calculate unique exposure integer for this observation

        Returns
        -------
        visit : `int`
            Integer uniquely identifying this exposure.
        """
        expId = self._header["EXP-ID"].strip()
        m = re.search("^HSCE(\d{8})$", expId)  # 2016-06-14 and new scheme
        if m:
            self._used_these_cards("EXP-ID")
            return int(m.group(1))

        # Fallback to old scheme
        m = re.search("^HSC([A-Z])(\d{6})00$", expId)
        if not m:
            raise RuntimeError(f"Unable to interpret EXP-ID: {expId}")
        letter, visit = m.groups()
        visit = int(visit)
        if visit == 0:
            # Don't believe it
            frameId = self._header["FRAMEID"].strip()
            m = re.search("^HSC([A-Z])(\d{6})\d{2}$", frameId)
            if not m:
                raise RuntimeError(f"Unable to interpret FRAMEID: {frameId}")
            letter, visit = m.groups()
            visit = int(visit)
            if visit % 2:  # Odd?
                visit -= 1
        self._used_these_cards("EXP-ID", "FRAMEID")
        return visit + 1000000*(ord(letter) - ord("A"))

    def to_boresight_rotation_angle(self):
        # Rotation angle formula determined empirically from visual inspection
        # of HSC images.  See DM-9111.
        angle = Angle(270.*u.deg) - Angle(self.quantity_from_card("INST-PA", u.deg))
        angle = angle.wrap_at("360d")
        return angle
