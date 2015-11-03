# -*- coding: utf-8 -*-
from five import grok

from z3c.form import group, field
from zope import schema
from zope.interface import invariant, Invalid
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm

from plone.dexterity.content import Container
from plone.directives import dexterity, form
from plone.app.textfield import RichText
from plone.namedfile.field import NamedImage, NamedFile
from plone.namedfile.field import NamedBlobImage, NamedBlobFile
from plone.namedfile.interfaces import INamedBlobFileField
from zope.interface import implements

from plone.namedfile.interfaces import IImageScaleTraversable
from z3c.relationfield.schema import RelationChoice, RelationList
from plone.formwidget.contenttree import ObjPathSourceBinder, UUIDSourceBinder
from plone.formwidget.autocomplete import AutocompleteFieldWidget, AutocompleteMultiFieldWidget
from edeposit.content.library import ILibrary
import z3c.form.browser.radio
from edeposit.content.epublication import librariesAccessing
from edeposit.content import MessageFactory as _
from edeposit.content.originalfile import OriginalFileSource
from plone import api

# file source
class IEPeriodicalPartFileField(INamedBlobFileField):
    pass

class EPeriodicalPartFile(NamedBlobFile):
    implements(IEPeriodicalPartFileField)

# Interface class; used to define content-type schema.

class IePeriodicalPart(form.Schema, IImageScaleTraversable):
    """
    E-Deposit - ePeriodical Part
    """
    
    cast = schema.TextLine (
        title = u"Část (svazek,díl)",
        required = False,
    )
    
    nazev_casti = schema.TextLine (
        title = u"Název části, dílu",
        required = False,
        )

    cena = schema.Decimal (
        title = u'Cena v Kč',
        required = False,
    )

    form.primary('file')
    file = EPeriodicalPartFile (
        title=_(u"Original File of an ePeriodical Part"),
        required = False,
        )

    vazba = schema.TextLine (
        title = u"Vazba",
        required = False,
        default = u"online",
    )


    form.fieldset('technical',
                  label=_('Technical'),
                  fields = [ 'zpracovatel_zaznamu',
                             'thumbnail',
                             'aleph_doc_number',
                             'storage_download_url',
                             'storage_path'
                             ]
                  )

    zpracovatel_zaznamu = schema.TextLine(
        title = u'Zpracovatel záznamu',
        required = False,
    )

    thumbnail = NamedBlobFile(
        title=u"PDF kopie",
        required = False,
        )

    aleph_doc_number = schema.ASCIILine(
        title = _(u'Aleph DocNumber'),
        description = _(u'Internal DocNumber that Aleph refers to metadata of this ePeriodical part'),
        required = False,
        readonly = False,
        default = None,
        missing_value = None,
        )

    storage_download_url = schema.ASCIILine (
        title = u"Linka do úložiště",
        required = False,
    )

    storage_path = schema.ASCIILine (
        title = u"Cesta v úložišti",
        required = False,
    )

    

@form.default_value(field=IePeriodicalPart['zpracovatel_zaznamu'])
def zpracovatelDefaultValue(data):
    member = api.user.get_current()
    return member.fullname or member.id

# Custom content-type class; objects created for this content type will
# be instances of this class. Use this class to add content-type specific
# methods and properties. Put methods that are mainly useful for rendering
# in separate view classes.

class ePeriodicalPart(Container):
    grok.implements(IePeriodicalPart)

    # Add your class methods and properties here

# View class
# The view will automatically use a similarly named template in
# eperiodicalpart_templates.
# Template filenames should be all lower case.
# The view will render when you request a content object with this
# interface with "/@@sampleview" appended.
# You may make this the default view for content objects
# of this type by uncommenting the grok.name line below or by
# changing the view class name and template filename to View / view.pt.

class SampleView(grok.View):
    """ sample view class """

    grok.context(IePeriodicalPart)
    grok.require('zope2.View')

    # grok.name('view')

    # Add view methods here
