# -*- coding: utf-8 -*-
from five import grok

from z3c.form import group, field
from zope import schema
from zope.interface import invariant, Invalid
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from z3c.form import group, field, button

from plone.dexterity.content import Container
from plone.directives import dexterity, form
from plone.app.textfield import RichText
from plone.namedfile.field import NamedImage, NamedFile
from plone.namedfile.field import NamedBlobImage, NamedBlobFile
from plone.namedfile.interfaces import IImageScaleTraversable
from z3c.relationfield.schema import RelationChoice, RelationList
from plone.formwidget.contenttree import ObjPathSourceBinder, UUIDSourceBinder
from plone.formwidget.autocomplete import AutocompleteFieldWidget, AutocompleteMultiFieldWidget
from plone.dexterity.utils import createContentInContainer, addContentToContainer, createContent
from edeposit.content.library import ILibrary
from edeposit.content.eperiodicalfolder import IePeriodicalFolder
from edeposit.content import MessageFactory as _
from plone import api

# Interface class; used to define content-type schema.

class IePeriodical(form.Schema, IImageScaleTraversable):
    """
    E-Deposit - ePeriodical
    """
    title = schema.TextLine(
        title=u'Název periodického tisku',
        required=True
    )

    issn = schema.ASCIILine (
        title = u"ISSN",
        required = True,
    )

    cetnost_vydani = schema.TextLine (
        title = u"Četnost (periodicita) vydání",
        required = True,
    )

    misto_vydani = schema.TextLine (
        title = u"Místo vydáni",
        required = True,
    )

    obsahove_zamereni = schema.TextLine (
        title = u"Obsahové zaměření",
        required = False,
    )

    description = schema.Text(
        title=u"Poznámka",
        required=False,
        missing_value=u'',
    )


# Custom content-type class; objects created for this content type will
# be instances of this class. Use this class to add content-type specific
# methods and properties. Put methods that are mainly useful for rendering
# in separate view classes.

class ePeriodical(Container):
    grok.implements(IePeriodical)

    # Add your class methods and properties here


# View class
# The view will automatically use a similarly named template in
# eperiodical_templates.
# Template filenames should be all lower case.
# The view will render when you request a content object with this
# interface with "/@@sampleview" appended.
# You may make this the default view for content objects
# of this type by uncommenting the grok.name line below or by
# changing the view class name and template filename to View / view.pt.

#  http://www.mkcr.cz/scripts/detail.php?id=353

class AddAtOnceForm(form.SchemaForm):
    grok.name('add-at-once')
    grok.require('edeposit.AddEPeriodical')
    grok.context(IePeriodicalFolder)
    schema = IePeriodical
    ignoreContext = True
    label = u"Oznámení vydávání periodického tisku"
    enable_form_tabbing = False
    autoGroups = False
    
    @button.buttonAndHandler(u"Odeslat", name='save')
    def handleAdd(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return

        newEPeriodical = createContentInContainer(self.context, 'edeposit.content.eperiodical', **data)
        wft = api.portal.get_tool('portal_workflow')
        api.content.get_state(newEPeriodical)
        wft.doActionFor(newEPeriodical, 'toAcquisition', comment='handled automatically')
        self.request.response.redirect(newEPeriodical.absolute_url())


# class SampleView(grok.View):
#     """ sample view class """

#     grok.context(IePeriodical)
#     grok.require('zope2.View')

#     # grok.name('view')

#     # Add view methods here
