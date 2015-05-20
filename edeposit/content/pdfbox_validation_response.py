# -*- coding: utf-8 -*-
from five import grok

from z3c.form import group, field
from zope import schema
from zope.interface import invariant, Invalid
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm

from plone.dexterity.content import Item

from plone.directives import dexterity, form
from plone.app.textfield import RichText
from plone.namedfile.field import NamedImage, NamedFile
from plone.namedfile.field import NamedBlobImage, NamedBlobFile
from plone.namedfile.interfaces import IImageScaleTraversable
from lxml import etree

from edeposit.content import MessageFactory as _


# Interface class; used to define content-type schema.

class IPDFBoxValidationResponse(form.Schema, IImageScaleTraversable):
    """
    Response from AMQP PDFBox validation service
    """

    # If you want a schema-defined interface, delete the model.load
    # line below and delete the matching file in the models sub-directory.
    # If you want a model-based interface, edit
    # models/pdfbox_validation_response.xml to define the content type.

    isValidPDF = schema.Bool(
        title = u"Je to PDF",
        default = False,
        required = False
    )

    isValidPDFA = schema.Bool(
        title = u"Vyhovuje normě PDF/A",
        default = False,
        required = False
    )

    xml = NamedBlobFile (
        title=_(u"XML file with full response"),
        required = True,
    )


# Custom content-type class; objects created for this content type will
# be instances of this class. Use this class to add content-type specific
# methods and properties. Put methods that are mainly useful for rendering
# in separate view classes.

class PDFBoxValidationResponse(Item):
    grok.implements(IPDFBoxValidationResponse)

    @property
    def isValidPDF(self):
        if self.xml:
            elements = etree.fromstring(self.xml.data).xpath('//validation/isValidPDF')
            isValidPDF = elements and elements[0].text.lower() == 'true'
            return isValidPDF

        return False

    @property
    def isValidPDFA(self):
        if self.xml:
            elements = etree.fromstring(self.xml.data).xpath('//validation/isValidPDFA')
            isValidPDFA = elements and elements[0].text.lower() == 'true'
            return isValidPDFA

        return False



# View class
# The view will automatically use a similarly named template in
# pdfbox_validation_response_templates.
# Template filenames should be all lower case.
# The view will render when you request a content object with this
# interface with "/@@sampleview" appended.
# You may make this the default view for content objects
# of this type by uncommenting the grok.name line below or by
# changing the view class name and template filename to View / view.pt.