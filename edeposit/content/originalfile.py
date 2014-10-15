# -*- coding: utf-8 -*-
from five import grok
from zope.component import queryUtility, getUtility
from z3c.relationfield import RelationValue
from zope.app.intid.interfaces import IIntIds

from z3c.form import group, field
from zope import schema
from zope.interface import invariant, Invalid
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from plone.supermodel import model

from plone.dexterity.content import Container
from plone.directives import dexterity, form
from plone.app.textfield import RichText
from plone.namedfile.field import NamedBlobImage, NamedBlobFile
from plone.namedfile.interfaces import IImageScaleTraversable

from edeposit.content import MessageFactory as _
from z3c.relationfield.schema import RelationChoice, Relation
from plone.formwidget.contenttree import ObjPathSourceBinder, PathSourceBinder

from edeposit.content.aleph_record import IAlephRecord
from Products.CMFCore.utils import getToolByName
from zope.schema.vocabulary import SimpleVocabulary
from plone.dexterity.utils import createContentInContainer
from Acquisition import aq_parent, aq_inner

def urlCodeIsValid(value):
    return True

@grok.provider(IContextSourceBinder)
def availableAlephRecords(context):
    path = '/'.join(context.getPhysicalPath())
    query = { "portal_type" : ("edeposit.content.alephrecord",),
              "path": {'query' :path } 
             }
    return ObjPathSourceBinder(navigation_tree_query = query).__call__(context)

class IOriginalFile(form.Schema, IImageScaleTraversable):
    """
    E-Deposit Original File
    """

    url = schema.ASCIILine(
        title=_("URL"),
        constraint=urlCodeIsValid,
        required = False,
        )

    isbn = schema.ASCIILine(
        title=_("ISBN"),
        description=_(u"Value of ISBN"),
        required = False,
        )

    form.primary('file')
    file = NamedBlobFile(
        title=_(u"Original File of an ePublication"),
        required = False,
        )
    
    format = schema.Choice(
        title=_(u"Format of a file."),
        vocabulary="edeposit.content.fileTypes",
        required = False,
    )

    generated_isbn = schema.Bool(
        title = _(u'Generate ISBN'),
        description = _(u'Whether ISBN agency should generate ISBN number.'),
        required = False,
        default = False,
        missing_value = False,
    )

    related_aleph_record = RelationChoice( title=u"Odpovídající záznam v Alephu",
                                           required = False,
                                           source = availableAlephRecords)
    thumbnail = NamedBlobFile(
        title=_(u"Thumbnail File of an ePublication"),
        required = False,
        )
                                           
# Custom content-type class; objects created for this content type will
# be instances of this class. Use this class to add content-type specific
# methods and properties. Put methods that are mainly useful for rendering
# in separate view classes.

class OriginalFile(Container):
    grok.implements(IOriginalFile)

    def getParentTitle(self):
        return aq_parent(aq_inner(self)).title

    def getNakladatelVydavatel(self):
        return aq_parent(aq_inner(self)).nakladatel_vydavatel

    def getZpracovatelZaznamu(self):
        return aq_parent(aq_inner(self)).zpracovatel_zaznamu

    def getPodnazev(self):
        return aq_parent(aq_inner(self)).podnazev

    def getCast(self):
        return aq_parent(aq_inner(self)).cast

    def getNazevCasti(self):
        return aq_parent(aq_inner(self)).nazev_casti

    def needsThumbnailGeneration(self):
        isPdf = self.file and self.file.contentType == "application/pdf"
        return self.file and not isPdf

    def getThumbnail(self):
        previewfiles = self.listFolderContents(contentFilter={"portal_type" : "edeposit.content.previewfile"})
        return previewfiles and previewfiles[0]

    def urlToAleph(self):
        record = self.related_aleph_record and getattr(self.related_aleph_record,'to_object',None)
        if not record:
            return ""
        return "http://aleph.nkp.cz/F?func=find-b&find_code=SYS&x=0&y=0&request=%s&filter_code_1=WTP&filter_request_1=&filter_code_2=WLN&adjacent=N" % (record.aleph_sys_number,)

    def urlToAlephMARCXML(self):
        record = self.related_aleph_record and getattr(self.related_aleph_record,'to_object',None)
        if not record:
            return ""
        return "http://aleph.nkp.cz/X?op=find_doc&doc_num=%s&base=nkc" % (record.aleph_sys_number,)

    def urlToKramerius(self):
        return "some"

    def hasSomeAlephRecords(self):
        alephRecords = self.listFolderContents(contentFilter={'portal_type':'edeposit.content.alephrecord'})
        return len(alephRecords)
        
    # Add your class methods and properties here
    def updateOrAddAlephRecord(self, dataForFactory):
        sysNumber = dataForFactory.get('aleph_sys_number',None)
        alephRecords = self.listFolderContents(contentFilter={'portal_type':'edeposit.content.alephrecord'})

        # exist some record with the same sysNumber?
        arecordWithTheSameSysNumber = filter(lambda arecord: arecord.aleph_sys_number == sysNumber,
                                             alephRecords)
        if arecordWithTheSameSysNumber:
            # update this record
            alephRecord = arecordWithTheSameSysNumber[0]
            def isChangedFactory(alephRecord,data):
                def isChanged(attr):
                    return getattr(alephRecord,attr,None) != data.get(attr,None)
                return isChanged
            changedAttrs = filter(isChangedFactory(alephRecord,dataForFactory), dataForFactory,keys())
            if changedAttrs:
                def setAttrFactory(alephRecord,data):
                    def setAttr(attr):
                        newValue = data.get(newValue,None)
                        setattr(alephRecord,attr,newValue)
                    return setAttr
                map(setAttrFactory(alephRecord,dataForFactory), changedAttrs)
                alephRecord.save()
            pass
        else:
            createContentInContainer(self, 'edeposit.content.alephrecord', **dataForFactory)

    def updateAlephRelatedData(self):
        # try to choose related_aleph_record
        alephRecords = self.listFolderContents(contentFilter={'portal_type':'edeposit.content.alephrecord'})
        if len(alephRecords) == 1:
            intids = getUtility(IIntIds)
            self.related_aleph_record = RelationValue(intids.getId(alephRecords[0]))
        if len(alephRecords) > 1:
            self.related_aleph_record = None
    

def getAssignedPersonFactory(roleName):
    def getAssignedPerson(self):
        local_roles = self.get_local_roles()
        pairs = filter(lambda pair: roleName in pair[1], local_roles)
        return pairs and pairs[0][0] or None

    return getAssignedPerson

OriginalFile.getAssignedDescriptiveCataloguer = getAssignedPersonFactory('E-Deposit: Descriptive Cataloguer')
OriginalFile.getAssignedDescriptiveCataloguingReviewer = getAssignedPersonFactory('E-Deposit: Descriptive Cataloguing Reviewer')
OriginalFile.getAssignedSubjectCataloguer = getAssignedPersonFactory('E-Deposit: Subject Cataloguer')
OriginalFile.getAssignedSubjectCataloguingReviewer = getAssignedPersonFactory('E-Deposit: Subject Cataloguing Reviewer')

class ThumbnailView(grok.View):
    grok.context(IOriginalFile)
    grok.require('zope2.View')
    grok.name("thumbnail")

    def __call__(self):
        thumbnail = self.context.getThumbnail()
        url = thumbnail and "/".join(thumbnail.getPhysicalPath()) \
            or "/".join(self.context.getPhysicalPath() + ("documentviewer",))
        self.request.response.redirect(url)


import plone.namedfile

class Download(plone.namedfile.browser.Download):
    pass

class DisplayFile(plone.namedfile.browser.DisplayFile):
    pass
