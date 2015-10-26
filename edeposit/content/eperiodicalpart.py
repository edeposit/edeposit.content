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
    
    book_binding = schema.ASCIILine(
        title = _(u"Book Binding"),
        description = _(u"Fill in binding of a book."),
        required = False,
        )
    
    subtitle = schema.ASCIILine (
        title = _(u"Subtitle"),
        required = False,
        )

    edition = schema.ASCIILine (
        title = _(u"Edition"),
        required = False,
        )

    form.fieldset('Publishing',
                  label=_(u"Publishing"),
                  fields = [ 'date_of_publishing',
                             'published_with_coedition',
                             'published_at_order',
                             'place_of_publishing',
                             ]
                  )
    place_of_publishing = schema.ASCIILine (
        title = _(u"Place of Publishing"),
        required = False,
        )

    date_of_publishing = schema.Date (
        title = _(u"Publishing Date"),
        required = False,
        )
    
    published_with_coedition = schema.ASCIILine(
        title = _(u'Published with Coedition'),
        description = _(u'Fill in a coedition of an ePublication'),
        required = False,
        readonly = False,
        default = None,
        missing_value = None,
        )

    published_at_order = schema.ASCIILine(
        title = _(u'Published at order'),
        description = _(u'Fill in an order an ePublication was published at.'),
        required = False,
        readonly = False,
        default = None,
        missing_value = None,
        )
    

    form.fieldset('volume',
                  label=_(u'Volume'),
                  fields = ['volume','volume_title','volume_number']
                  )
    volume = schema.ASCIILine (
        title = _(u"Volume"), # svazek
        required = False,
        )
    
    volume_title = schema.ASCIILine (
        title = _(u"Volume Title"),
        required = False,
        )
    
    volume_number = schema.ASCIILine (
        title = _(u"Volume Number"),
        required = False,
        )

    price = schema.Decimal(
        title = _(u"Price"),
        required = False,
        )

    currency = schema.Choice(
        title = _(u'Currency'),
        description = _(u'Fill in currency of a price.'),
        vocabulary='edeposit.content.currencies'
        )

    form.fieldset('original',
                  label='Soubor',
                  fields = [ 'file',]
                  )

    form.primary('file')
    file = EPeriodicalPartFile (
        title=_(u"Original File of an ePeriodical Part"),
        required = False,
        )

    form.fieldset('accessing',
                  label=_(u'Accessing'),
                  fields = [ 'is_public',
                             'libraries_accessing',
                             'libraries_that_can_access',
                             ])

    is_public = schema.Bool(
        title = u'ePublikace je veřejná',
        required = False,
        default = False,
        missing_value = False,
        )

    form.widget(libraries_accessing=z3c.form.browser.radio.RadioFieldWidget)
    libraries_accessing = schema.Choice (
        title = u"Oprávnění knihovnám",
        required = False,
        readonly = False,
        default = None,
        missing_value = None,
        source = librariesAccessing,
        #vocabulary = 'edeposit.content.librariesAccessingChoices'
    )

    #form.widget(libraries_that_can_access=AutocompleteMultiFieldWidget)    
    libraries_that_can_access = RelationList(
        title = _(u'Libraries that can access this ePublication'),
        #description = _(u'Choose libraries that can show an ePublication at its terminal.'),
        required = False,
        readonly = False,
        default = [],
        value_type = RelationChoice(
            title = _(u'Related libraries'),
            source = ObjPathSourceBinder(object_provides=ILibrary.__identifier__),
            )
        )

    form.fieldset('riv',
                  label=_(u'RIV'),
                  fields = ['category_for_riv',
                            ])

    category_for_riv = schema.ASCIILine(
        title = _(u'RIV category'),
        description = _(u'Category of an ePublication for RIV'),
        required = False,
        readonly = False,
        default = None,
        missing_value = None,
        )

    form.fieldset('technical',
                  label=_('Technical'),
                  fields = [ 'person_who_processed_this',
                             'thumbnail',
                             'aleph_doc_number',
                             'storage_download_url',
                             'storage_path'
                             ]
                  )
    person_who_processed_this = schema.ASCIILine(
        title = _(u'Person who processed this.'),
        description = _(u'Fill in a name of a person who processed this ePeriodical part.'),
        required = False,
        readonly = False,
        default = None,
        missing_value = None,
        )

    thumbnail = NamedBlobFile(
        title=_(u"PDF kopie"),
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
