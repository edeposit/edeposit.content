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

from edeposit.content import MessageFactory as _

# Interface class; used to define content-type schema.
class IAlephRecordsContainer(form.Schema):
    """ marker interface for containers that can contain aleph records:
    IOriginalFile
    IBook
    """
    pass

class IAlephRecord(form.Schema, IImageScaleTraversable):
    """
    E-Deposit Aleph Record
    """
    isbn = schema.ASCIILine(
        title=_("ISBN"),
        description=_(u"Value of ISBN"),
        required = True,
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

    cast = schema.TextLine (
        title = u"Část, díl",
        required = False,
    )

    nazev_casti = schema.TextLine (
        title = u"Název části, dílu",
        required = False,
        )

    rok_vydani = schema.ASCIILine (
        title = u"Rok vydání",
        required = True,
    )

    aleph_sys_number = schema.ASCIILine (
        title = _(u'Aleph SysNumber'),
        description = _(u'Internal SysNumber that Aleph refers to metadata of this ePublication'),
        required = True,
    )
    
    aleph_library = schema.ASCIILine (
        title = _(u'Aleph Library'),
        description = _(u'Library that Aleph refers to metadata of this ePublication'),
        required = True,
    )
    acquisitionFields= schema.List (
        title = _(u'has Acquisition Fields'),
        #description = _(u'This record has acquisition fields.'),
        required = False,
        default = None,
        value_type = schema.TextLine(),
    )
    ISBNAgencyFields= schema.List (
        title = _(u'ISBN Agency Fields'),
        #description = _(u'This record has ISBN Agency fields'),
        required = False,
        default = None,
        value_type = schema.TextLine(),
    )
    descriptiveCataloguingFields= schema.List (
        title = _(u'Descriptive Cataloguing Fields'),
        #description = u"",
        required = False,
        default = None,
        value_type = schema.TextLine(),
    )
    descriptiveCataloguingReviewFields= schema.List (
        title = _(u'Descriptive Cataloguing Review Fields'),
        #description = u"",
        required = False,
        default = None,
        value_type = schema.TextLine(),
    )
    subjectCataloguingFields= schema.List (
        title = _(u'Subject Cataloguing Fields'),
        #description = u"",
        required = False,
        default = None,
        value_type = schema.TextLine(),
    )
    subjectCataloguingReviewFields= schema.List (
        title = _(u'Subject Cataloguing Review Fields'),
        #description = u"",
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
        description = _(u'Internal SysNumber of a Summary Aleph Record for this ePublication'),
        required = False,
    )
    summary_record_info = schema.ASCIILine (
        title = _(u'Info about Summary Record'),
        description = _(u'Informations about Summary Aleph Record for this ePublication'),
        required = False,
    )
    internal_url = schema.ASCIILine (
        title = _(u'Internal URL'),
        description = _(u'link to eDeposit'),
        required = False,
    )
    internal_urls = schema.List (
        title = _(u'Internal URLs'),
        description = _(u'links to eDeposit'),
        value_type = schema.ASCIILine(),
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

# Custom content-type class; objects created for this content type will
# be instances of this class. Use this class to add content-type specific
# methods and properties. Put methods that are mainly useful for rendering
# in separate view classes.

class AlephRecord(Item):
    grok.implements(IAlephRecord)
    
    def lastChangeOfFields(self, fieldNames):
        revisions = self.revisionsOfFields(fieldNames)
        return None

    def fieldIsYoungerThan(self, fieldName,time):
        fieldValue = getattr(self,fieldName,None)
        fieldRevisions = self.revisionsOfFields([fieldName])
        def diff(current, previous):
            return (bool(current and previous and (current[0] != previous[0])), current[1])

        def isYounger(item):
            (isDiff, modification_date) = item
            return (isDiff and modification_date > time)
        
        diffs = map(diff, fieldRevisions, fieldRevisions[1:])
        #if "3363" in self.aleph_sys_number:
        result = bool(filter(isYounger,diffs))
        print "... field is younger than", fieldName, time, result
        return result

        #return fieldValue

    def revisionsOfFields(self, fieldNames):
        def getFields(vd):
            getField = partial(getattr, vd.object)
            return map(getField, fieldNames + ['modification_date',])
        
        return map(getFields, self.portal_repository.getHistory(self))

    def findAndLoadChanges(self, data):
        def isChanged(attr):
            return getattr(self,attr,None) != data.get(attr,None)

        changedAttrs = filter(isChanged, data.keys())
        print "... changedAttrs", changedAttrs
        print "... data", data
        for attr in changedAttrs:
            setattr(self, attr, data.get(attr,None) )

        importantAttrs = frozenset(changedAttrs) - frozenset(['xml','aleph_library'])
        if importantAttrs:
            print "... sent modified event"
            modified(self)
            #self.set_new_version()

        return changedAttrs

    def set_new_version(self, comment=""):
        try:
            self.portal_repository.save(obj=self, comment=comment)
        except FileTooLargeToVersionError:
            pass # the on edit save will emit a warning


# View class
# The view will automatically use a similarly named template in
# aleph_record_templates.
# Template filenames should be all lower case.
# The view will render when you request a content object with this
# interface with "/@@sampleview" appended.
# You may make this the default view for content objects
# of this type by uncommenting the grok.name line below or by
# changing the view class name and template filename to View / view.pt.

class SampleView(grok.View):
    """ sample view class """

    grok.context(IAlephRecord)
    grok.require('zope2.View')

    # grok.name('view')

    # Add view methods here
