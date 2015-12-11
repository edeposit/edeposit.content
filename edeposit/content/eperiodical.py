# -*- coding: utf-8 -*-
from five import grok

from z3c.form import group, field
from zope import schema
from zope.interface import invariant, Invalid
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from z3c.form import group, field, button
from zope.component import queryUtility, getUtility, getAdapter
from z3c.relationfield import RelationValue
from zope.app.intid.interfaces import IIntIds
from urlparse import urlparse
from operator import __or__, attrgetter, methodcaller

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
from plone.formwidget.contenttree import ObjPathSourceBinder, PathSourceBinder

from .tasks import (
    IPloneTaskSender,
    DoActionFor,
    CheckUpdates,
)

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

@grok.provider(IContextSourceBinder)
def availableAlephRecords(context):
    path = '/'.join(context.getPhysicalPath())
    query = { "portal_type" : ("edeposit.content.alephrecordforeperiodical",),
              "path": {'query' :path } 
             }
    return ObjPathSourceBinder(navigation_tree_query = query).__call__(context)


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
                  fields = [ 'misto_vydani',
                             'rok_vydani',
                             ]
                  )

    misto_vydani = schema.TextLine(
        title = u'Místo vydání',
        required = True,
    )

    rok_vydani = schema.TextLine (
        title = u"Rok vydání",
        required = True,
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
                  fields = ['related_aleph_record', 'isClosed' ]
                  )
    
    related_aleph_record = RelationChoice( title=u"Odpovídající záznam v Alephu",
                                           required = False,
                                           source = availableAlephRecords)

    isClosed= schema.Bool (
        title = _(u'is closed out by Catalogizators'),
        description = u"",
        required = False,
        default = False,
    )



# Custom content-type class; objects created for this content type will
# be instances of this class. Use this class to add content-type specific
# methods and properties. Put methods that are mainly useful for rendering
# in separate view classes.

class ePeriodical(Container):
    grok.implements(IePeriodical)

    # Add your class methods and properties here

    # Add your class methods and properties here
    def updateOrAddAlephRecord(self, dataForFactory):
        sysNumber = dataForFactory.get('aleph_sys_number',None)
        alephRecords = self.listFolderContents(contentFilter={'portal_type':'edeposit.content.alephrecordforeperiodical'})

        # exist some record with the same sysNumber?
        arecordWithTheSameSysNumber = filter(lambda arecord: arecord.aleph_sys_number == sysNumber,
                                             alephRecords)
        print dataForFactory
        if arecordWithTheSameSysNumber:
            print "a record with the same sysnumber"
            # update this record
            alephRecord = arecordWithTheSameSysNumber[0]
            changedAttrs = alephRecord.findAndLoadChanges(dataForFactory)
            #importantAttrs = frozenset(changedAttrs) - frozenset(['xml','aleph_library'])
            #if importantAttrs:
            #    print "... changed important attrs: ", importantAttrs
            IPloneTaskSender(CheckUpdates(uid=self.UID())).send()

        else:
            alephRecord = createContentInContainer(self, 'edeposit.content.alephrecordforeperiodical', **dataForFactory)
            IPloneTaskSender(CheckUpdates(uid=self.UID())).send()

    def makeInternalURL(self):
        internal_url = "/".join([api.portal.get().absolute_url(), '@@redirect-to-uuid', self.UID()])
        return internal_url

    def refersToThis(self,aleph_record):
        # older records can have
        # absolute_url as internal url
        absolute_path = urlparse(self.absolute_url()).path
        internal_path = urlparse(self.makeInternalURL()).path

        def startsWithProperURL(url):
            path = urlparse(url).path
            result = absolute_path in path or internal_path in path
            return result

        result = reduce(__or__, map(startsWithProperURL, aleph_record.internal_urls), False)
        return result

    def updateAlephRelatedData(self):
        # try to choose related_aleph_record
        print "... update Aleph Related Data"
        alephRecords = self.listFolderContents(contentFilter={'portal_type':'edeposit.content.alephrecordforeperiodical'})

        self.related_aleph_record = None
        related_aleph_record = None

        intids = getUtility(IIntIds)
        recordsThatRefersToThis = filter(lambda rr: self.refersToThis(rr), alephRecords)
        if len(recordsThatRefersToThis) == 1:
            related_aleph_record = recordsThatRefersToThis[0]
            self.related_aleph_record = RelationValue(intids.getId(related_aleph_record))
            self.reindexObject(idxs=['id_number',])

    def checkUpdates(self):
        self.updateAlephRelatedData()
        if self.related_aleph_record:
            obj = getattr(self.related_aleph_record,'to_object',None)
            if obj and obj.acquisitionFields:
                wft=api.portal.get_tool('portal_workflow')
                transitions = wft.getTransitionsFor(self)
                available = len(filter(lambda tr: 'acquisitionOK' in tr['id'], transitions))
                if available:
                    wft.doActionFor(self,'acquisitionOK')
        pass
        

    @property
    def sysNumber(self):
        if self.related_aleph_record:
            record = getattr(self.related_aleph_record, 'to_object', None)
            return record and record.aleph_sys_number or ""
        return None

    @property
    def id_number(self):
        if self.related_aleph_record:
            record = getattr(self.related_aleph_record, 'to_object', None)
            return record and record.aleph_sys_number or ""
        return None

    @property
    def isClosed(self):
        if self.related_aleph_record:
            record = getattr(self.related_aleph_record, 'to_object',None)
            return record and record.isClosed
        return False

    @property
    def aleph_sys_number(self):
        if self.related_aleph_record:
            record = getattr(self.related_aleph_record, 'to_object',None)
            return record and record.aleph_sys_number
        return None

    @property
    def id_number(self):
        if self.related_aleph_record:
            record = getattr(self.related_aleph_record, 'to_object',None)
            return record and record.id_number
        return None
        


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
