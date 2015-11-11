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
from edeposit.app.fields import PeriodicityChoice
import z3c.form.browser.radio
from edeposit.content.epublication import librariesAccessing

"""
Denně
1x týdně
2x týdně
3x týdně
1x měsíčně
2x měsíčně
1x za 2 týdny
3x měsíčně
2x ročně
3x ročně
4x ročně
6x ročně
10x ročně
Ročenka
1x za 2 roky
1x za 3 roky
"""

periodicityChoices = [
    ['denne',u"Denně",356],
    ['1x tydne', u"1x týdně",52],
    ['2x tydne',u"2x týdně",104],
    ['3x tydne',u'3x týdně',156],
    ['1x mesicne',u'1x měsíčně',12],
    ['2x mesicne',u'2x měsíčně',24],
    ['1x za 2 tydny',u'1x za 2 týdny', 26],
    ['3x mesicne',u'3x měsíčně', 36],
    ['2x rocne',u'2x ročně',2],
    ['3x rocne',u'3x ročně',3],
    ['4x rocne',u'4x ročně',4],
    ['6x rocne',u'6x ročně',6],
    ['10x rocne',u'10x ročně',10],
    ['rocenka',u'Ročenka',1],
    ['1x za 2 roky',u'1x za 2 roky',1],
    ['1x za 3 roky',u'1x za 3 roky',1],
    ['nepravidelne',u"nepravidelně",0]
]

def getNumOfPartsAYear(periodicity):
    nums = [ii[2] for ii in periodicityChoices if ii[0] == periodicity]
    return nums and nums[0] or 0

def getPeriodicityLabel(num):
    return u"%d. číslo" % (num,)

@grok.provider(IContextSourceBinder)
def periodicityChoicesSource(context):
    def getTerm(item):
        title = item[1].encode('utf-8')
        return SimpleVocabulary.createTerm(item[0], item[0], title)

    return SimpleVocabulary(map(getTerm, periodicityChoices))

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
        required = False,
    )

    cetnost_vydani = PeriodicityChoice (
        title = u"Četnost (periodicita) vydání",
        required = True,
        source = periodicityChoicesSource,
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

    form.fieldset('Publishing',
                  label=_(u"Publishing"),
                  fields = [ 'poradi_vydani',
                             'misto_vydani',
                             'rok_vydani',
                             ]
                  )

    poradi_vydani = schema.TextLine(
        title = u'Pořadí vydání',
        required = True,
    )

    misto_vydani = schema.TextLine(
        title = u'Místo vydání',
        required = True,
    )

    rok_vydani = schema.TextLine (
        title = u"Rok vydání",
        required = True,
    )

    vazba = schema.TextLine (
        title = u"Vazba",
        required = False,
        default = u"online",
    )

    form.fieldset('accessing',
                  label=_(u'Accessing'),
                  fields = [ 'is_public',
                             'libraries_accessing',
                             'libraries_that_can_access',
                             ])

    is_public = schema.Bool(
        title = u'vydání je veřejné',
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
    )

    libraries_that_can_access = RelationList(
        title = u"Knihovny které mají přístup k vydání ePeriodika",
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
                  fields = [ 'aleph_doc_number', ]
                  )

    aleph_doc_number = schema.ASCIILine(
        title = _(u'Aleph DocNumber'),
        description = _(u'Internal DocNumber that Aleph refers to metadata of this ePeriodical part'),
        required = False,
        readonly = False,
        default = None,
        missing_value = None,
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
    label = u"Oznámení vydávání ePeriodika"
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
