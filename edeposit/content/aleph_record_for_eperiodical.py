# -*- coding: utf-8 -*-
from five import grok

from z3c.form import group, field
from zope import schema
from zope.interface import invariant, Invalid
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm

from plone.dexterity.content import Item
from zope.lifecycleevent import modified
from plone.directives import dexterity, form
from plone.app.textfield import RichText
from plone.namedfile.field import NamedImage, NamedFile
from plone.namedfile.field import NamedBlobImage, NamedBlobFile
from plone.namedfile.interfaces import IImageScaleTraversable
from functools import partial

from edeposit.content.aleph_record import AlephRecordBase
from edeposit.content import MessageFactory as _

class IAlephRecordForEPeriodical(form.Schema, IImageScaleTraversable):
    """
    E-Deposit Aleph Record for ePeriodical
    """
    issn = schema.ASCIILine(
        title=_("ISSN"),
        description=_(u"Value of ISSN"),
        required = False,
    )

    def getNazev(self):
        return self.title

    nazev = schema.TextLine (
        title = u"Název",
        required = False,
    )

    podnazev = schema.TextLine (
        title = u"Podnázev",
        required = False,
    )

    misto_vydani = schema.TextLine (
        title = u"Místo vydání",
        required = False,
    )

    datum_vydani = schema.ASCIILine (
        title = u"Rok vydání",
        required = False,
    )

    url = schema.ASCIILine (
        title = _(u'URL to an ePeriodical source'),
        required = False,
    )

    anotace = schema.Text(
        title = u"Anotace",
        required = False,
        max_length = 500,
    )

    internal_urls = schema.List (
        title = _(u'Internal URLs'),
        description = _(u'links to eDeposit'),
        value_type = schema.ASCIILine(),
        required = False,
    )

    aleph_sys_number = schema.ASCIILine (
        title = _(u'Aleph SysNumber'),
        description = _(u'Internal SysNumber that Aleph refers to metadata of this ePeriodical'),
        required = True,
    )
    
    aleph_library = schema.ASCIILine (
        title = _(u'Aleph Library'),
        description = _(u'Library that Aleph refers to metadata of this ePeriodical'),
        required = True,
    )

    acquisitionFields= schema.List (
        title = _(u'has Acquisition Fields'),
        required = False,
        default = None,
        value_type = schema.TextLine(),
    )

    isClosed= schema.Bool (
        title = _(u'is closed out by Catalogizators'),
        #description = u"",
        required = False,
        default = False,
    )

    isSummaryRecord= schema.Bool (
        title = _(u'is summary record'),
        description = u"summaries other aleph records into one",
        required = False,
        default = False,
    )

    summary_record_aleph_sys_number  = schema.ASCIILine (
        title = _(u'Aleph SysNumber of Summary Record'),
        description = _(u'Internal SysNumber of a Summary Aleph Record for this ePeriodical'),
        required = False,
    )

    summary_record_info = schema.ASCIILine (
        title = _(u'Info about Summary Record'),
        description = _(u'Informations about Summary Aleph Record for this ePeriodical'),
        required = False,
    )

    xml = NamedBlobFile (
        title=_(u"XML file with MARC21"),
        required = False,
    )

    id_number = schema.ASCIILine(
        title = u"Interní číslo",
        required = False
    )

class AlephRecordForEPeriodical(AlephRecordBase):
    grok.implements(IAlephRecordForEPeriodical)
