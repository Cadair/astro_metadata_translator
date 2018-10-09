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

"""Classes and support code for metadata translation"""

__all__ = ("MetadataTranslator",)

from abc import abstractmethod
import logging
import math

import astropy.units as u

log = logging.getLogger(__name__)


class MetadataMeta(type):
    """Register all subclasses with the base class and create dynamic
    translator methods.

    The metaclass provides two facilities.  Firstly, every subclass
    of `MetadataTranslator` that includes a ``name`` class property is
    registered as a translator class that could be selected when automatic
    header translation is attempted.  Only name translator subclasses that
    correspond to a complete instrument.  Translation classes providing
    generic translation support for multiple instrument translators should
    not be named.

    The second feature of this metaclass is to convert simple translations
    to full translator methods.  Sometimes a translation is fixed (for
    example a specific instrument name should be used) and rather than provide
    a full ``to_property()`` translation method the mapping can be defined
    in a class variable named ``_constMap``.  Similarly, for one-to-one
    trivial mappings from a header to a property, ``_trivialMap`` can be
    defined.  Trivial mappings are a dict mapping a generic property
    to either a header keyword, or a tuple consisting of the header keyword
    and a dict containing key value pairs suitable for the
    `MetadataTranslator.quantity_from_card()` method.
    """

    @staticmethod
    def _makeConstMapping(standardKey, constant):
        """Make a translator method that returns a constant value.

        Parameters
        ----------
        standardKey : `str`
            Name of the property to be calculated (for the docstring).
        constant : `str` or `numbers.Number`
            Value to return for this translator.

        Returns
        -------
        f : `function`
            Function returning the constant.
        """
        def constant_translator(self):
            return constant
        constant_translator.__doc__ = f"""Returns constant value for '{standardKey}' property

        Returns
        -------
        translation : `{type(constant).__name__}`
            Always returns {constant!r}.
        """
        return constant_translator

    @staticmethod
    def _makeTrivialMapping(standardKey, headerKey, default=None, minimum=None, maximum=None, unit=None):
        """Make a translator method returning a header value.

        The header value can be converted to a `~astropy.units.Quantity`
        if desired, and can also have its value validated.

        See `MetadataTranslator.validate_value()` for details on the use
        of default parameters.

        Parameters
        ----------
        standardKey : `str`
            Name of the translator to be constructed (for the docstring).
        headerKey : `str`
            Name of the key to look up in the header.
        default : `numbers.Number` or `astropy.units.Quantity`, optional
            If not `None`, default value to be used if the parameter read from
            the header is not defined.
        minimum : `numbers.Number` or `astropy.units.Quantity`, optional
            If not `None`, and if ``default`` is not `None`, minimum value
            acceptable for this parameter.
        maximum : `numbers.Number` or `astropy.units.Quantity`, optional
            If not `None`, and if ``default`` is not `None`, maximum value
            acceptable for this parameter.
        unit : `astropy.units.Unit`, optional
            If not `None`, the value read from the header will be converted
            to a `~astropy.units.Quantity`.  Only supported for numeric values.

        Returns
        -------
        t : `function`
            Function implementing a translator with the specified
            parameters.
        """
        def trivial_translator(self):
            if unit is not None:
                return self.quantity_from_card(headerKey, unit,
                                               default=default, minimum=minimum, maximum=maximum)
            value = self._header[headerKey]
            if default is not None:
                value = self.validate_value(value, default, minimum=minimum, maximum=maximum)
            self._used_these_cards(headerKey)
            return value
        trivial_translator.__doc__ = f"""Map '{headerKey}' header keyword to '{standardKey}' property

        Returns
        -------
        translation : `str` or `numbers.Number`
            Translated header value derived directly from the {headerKey}
            header value.
        """
        return trivial_translator

    def __init__(cls, name, bases, dct):
        super().__init__(name, bases, dct)

        if hasattr(cls, "name") and cls.name is not None:
            MetadataTranslator.translators[cls.name] = cls

        for standardKey, headerKey in cls._trivialMap.items():
            kwargs = {}
            if type(headerKey) == tuple:
                kwargs = headerKey[1]
                headerKey = headerKey[0]
            translator = cls._makeTrivialMapping(standardKey, headerKey, **kwargs)
            setattr(cls, f"to_{standardKey}", translator)

        for standardKey, constant in cls._constMap.items():
            translator = cls._makeConstMapping(standardKey, constant)
            setattr(cls, f"to_{standardKey}", translator)


class MetadataTranslator(metaclass=MetadataMeta):
    """Per-instrument metadata translation support

    Parameters
    ----------
    header : `dict`-like
        Representation of an instrument header that can be manipulated
        as if it was a `dict`.
    """

    _trivialMap = {}
    """Dict of one-to-one mappings for header translation from standard
    property to corresponding keyword."""

    _constMap = {}
    """Dict defining a constant for specified standard properties."""

    translators = dict()
    """All registered metadata translation classes."""

    supportedInstrument = None
    """Name of instrument understood by this translation class."""

    def __init__(self, header):
        self._header = header
        self._used_cards = set()

    @classmethod
    @abstractmethod
    def canTranslate(cls, header):
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
        raise NotImplementedError()

    @classmethod
    def determineTranslator(cls, header):
        """Determine a translation class by examining the header

        Parameters
        ----------
        header : `dict`-like
            Representation of a header.

        Returns
        -------
        translator : `MetadataTranslator`
            Translation class that knows how to extract metadata from
            the supplied header.
        """
        for name, trans in cls.translators.items():
            if trans.canTranslate(header):
                log.debug(f"Using translation class {name}")
                return trans
        else:
            raise ValueError("None of the registered translation classes understood this header")

    def _used_these_cards(self, *args):
        """Indicate that the supplied cards have been used for translation.

        Parameters
        ----------
        args : sequence of `str`
            Keywords used to process a translation.
        """
        self._used_cards.update(set(args))

    def cards_used(self):
        """Cards used during metadata extraction.

        Returns
        -------
        used : `frozenset`
            Cards used when extracting metadata.
        """
        return frozenset(self._used_cards)

    @staticmethod
    def validate_value(value, default, minimum=None, maximum=None):
        """Validate the supplied value, returning a new value if out of range

        Parameters
        ----------
        value : `float`
            Value to be validated.
        default : `float`
            Default value to use if supplied value is invalid or out of range.
            Assumed to be in the same units as the value expected in the
            header.
        minimum : `float`
            Minimum possible valid value, optional.  If the calculated value
            is below this value, the default value will be used.
        maximum : `float`
            Maximum possible valid value, optional.  If the calculated value
            is above this value, the default value will be used.

        Returns
        -------
        value : `float`
            Either the supplied value, or a default value.
        """
        if value is None or math.isnan(value):
            value = default
        else:
            if minimum is not None and value < minimum:
                value = default
            elif maximum is not None and value > maximum:
                value = default
        return value

    def quantity_from_card(self, keyword, unit, default=None, minimum=None, maximum=None):
        """Calculate a Astropy Quantity from a header card and a unit.

        Parameters
        ----------
        keyword : `str`
            Keyword to use from header.
        unit : `astropy.units.UnitBase`
            Unit of the item in the header.
        default : `float`, optional
            Default value to use if the header value is invalid.  Assumed
            to be in the same units as the value expected in the header.  If
            None, no default value is used.
        minimum : `float`
            Minimum possible valid value, optional.  If the calculated value
            is below this value, the default value will be used.
        maximum : `float`
            Maximum possible valid value, optional.  If the calculated value
            is above this value, the default value will be used.

        Returns
        -------
        q : `astropy.units.Quantity`
            Quantity representing the header value.
        """
        value = self._header[keyword]
        if isinstance(value, str):
            # Sometimes the header has the wrong type in it but this must
            # be a number if we are creating a quantity.
            value = float(value)
        self._used_these_cards(keyword)
        if default is not None:
            value = self.validate_value(value, default, maximum=maximum, minimum=minimum)
        return u.Quantity(value, unit=unit)
