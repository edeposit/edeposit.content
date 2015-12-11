# -*- coding: utf-8 -*-
from five import grok

from z3c.form import group, field
from zope import schema
from zope.interface import invariant, Invalid
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
from zope.component import getUtility, getAdapter, getMultiAdapter, adapts, provideAdapter

from plone.dexterity.content import Container
from plone.dexterity.utils import createContentInContainer
from plone.directives import dexterity, form
from plone.app.textfield import RichText
from plone.namedfile.field import NamedImage, NamedFile
from plone.namedfile.field import NamedBlobImage, NamedBlobFile
from plone.namedfile.interfaces import INamedBlobFileField
from zope.interface import implements
import plone.namedfile.file
from plone.rfc822.interfaces import IPrimaryFieldInfo, IPrimaryField

from plone.namedfile.field import NamedBlobImage, NamedBlobFile
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
import os.path
from edeposit.content.behaviors import IFormat, ICalibreFormat
from Acquisition import aq_parent, aq_inner
from plone.app.layout.navigation.root import getNavigationRootObject

from .tasks import (
    IPloneTaskSender,
    DoActionFor
)
from plone.dexterity.interfaces import IDexterityFTI

@grok.provider(IContextSourceBinder)
def availableAlephRecords(context):
    path = '/'.join(context.getPhysicalPath())
    query = { "portal_type" : ("edeposit.content.alephrecord","edeposit.content.alephrecordforeperiodical"),
              "path": {'query' :path } }
    return ObjPathSourceBinder(navigation_tree_query = query).__call__(context)

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
    
    # cast = schema.TextLine (
    #     title = u"Část (svazek,díl)",
    #     required = False,
    # )
    
    # nazev_casti = schema.TextLine (
    #     title = u"Název části, dílu",
    #     required = False,
    #     )

    form.primary('file')
    file = EPeriodicalPartFile (
        title=_(u"Original File of an ePeriodical Part"),
        required = False,
        )

    form.fieldset('technical',
                  label=_('Technical'),
                  fields = [ 'thumbnail',
                             'storage_download_url',
                             'storage_path',
                             'related_aleph_record',
                             'rest_id',
                             ]
                  )

    thumbnail = NamedBlobFile(
        title=u"PDF kopie",
        required = False,
        )

    isWellFormedForLTP = schema.Bool (
        title = u"Vydání je ve formátu vhodném pro LTP",
        default = False,
        readonly = True,
        required = False
    )

    storage_download_url = schema.ASCIILine (
        title = u"Linka do úložiště",
        required = False,
    )

    storage_path = schema.ASCIILine (
        title = u"Cesta v úložišti",
        required = False,
    )
    
    related_aleph_record = RelationChoice( title=u"Odpovídající záznam v Alephu",
                                           required = False,
                                           source = availableAlephRecords)
    
    rest_id = schema.ASCIILine (
        title = u"ID objektu v REST API serveru",
        required = False,
    )

# Custom content-type class; objects created for this content type will
# be instances of this class. Use this class to add content-type specific
# methods and properties. Put methods that are mainly useful for rendering
# in separate view classes.

class ePeriodicalPart(Container):
    grok.implements(IePeriodicalPart)

    def canModify(self):
        return api.user.has_permission('Modify portal content',obj=self)

    @property
    def related_aleph_record(self):
        results = api.portal.get_tool('portal_catalog')(UID=self.UID())
        obj = results and results[0].getObject()
        parent = getattr(obj,'aq_parent',None)
        while parent and parent.portal_type != 'edeposit.content.eperiodical': 
            parent = getattr(parent,'aq_parent',None)

        return getattr(parent,'related_aleph_record',None)

    def needsThumbnailGeneration(self):
        fileformat  = (getAdapter(self,IFormat).format or "")
        return self.file and (fileformat != 'PDF')

    def submitValidationsForLTP(self):
        format = getAdapter(self,IFormat).format or ""
        print "submit ValidationsForLTP, format:\"%s\"\n" % (format,)
        if format == 'PDF':
            IPloneTaskSender(DoActionFor(transition='submitPDFBoxValidation', uid=self.UID())).send()

        if format == 'EPub':
            IPloneTaskSender(DoActionFor(transition='submitEPubCheckValidation', uid=self.UID())).send()

    def updateOrAddPDFBoxResponse(self, xmldata):
        responses = self.listFolderContents(contentFilter={'portal_type':'edeposit.content.pdfboxvalidationresponse'})
        for resp in responses:
            api.content.delete(obj=resp)

        # create new one
        bfile = plone.namedfile.file.NamedBlobFile(data=xmldata,  filename=u"pdfbox-response.xml")
        createContentInContainer(self, 'edeposit.content.pdfboxvalidationresponse', xml=bfile, title="PDFBox Response" )

    def updateOrAddEPubCheckResponse(self, result):
        responses = self.listFolderContents(contentFilter={'portal_type':'edeposit.content.epubcheckvalidationresponse'})
        # drop all previous responses
        for resp in responses:
            api.content.delete(obj=resp)

        # create new one
        bfile = plone.namedfile.file.NamedBlobFile(result.xml,  filename=u"epubcheck-response.xml")
        createContentInContainer(self,'edeposit.content.epubcheckvalidationresponse',
                                 xml=bfile, 
                                 title="EPubCheck Response",
                                 isWellFormedEPub2 = result.isWellFormedEPUB2,
                                 isWellFormedEPub3 = result.isWellFormedEPUB3
        )

    def isApprovedByAcquisition(self):
        alephRecord = getattr(self.related_aleph_record,'to_object',None)
        return alephRecord and getattr(alephRecord,'acquisitionFields',False)
        
    def checkUpdates(self):
        state = api.content.get_state(self)
        if state == 'acquisition' and self.isApprovedByAcquisition():
            wft = api.portal.get_tool('plone_workflow')
            wft.doActionFor(self,'submitAcquisition')
        pass

    def isValidPDFA(self):
        responses = [ii[1] for ii in self.items() if ii[1].portal_type == 'edeposit.content.pdfboxvalidationresponse']
        if responses:
            response = responses[0]
            return response.isValidPDFA

        return False

    def isValidEPub2(self):
        responses = [ii[1] for ii in self.items() if ii[1].portal_type == 'edeposit.content.epubcheckvalidationresponse']
        if responses:
            response = responses[0]
            return response.isWellFormedEPub2

        return False

    @property
    def isWellFormedForLTP(self):
        result = self.isValidEPub2() or self.isValidPDFA()
        return result

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
        return None

    def makeInternalURL(self):
        internal_url = "/".join([api.portal.get().absolute_url(), '@@redirect-to-uuid', self.UID()])
        return internal_url

    def getMODS(self):
        aleph_record = getattr(self.related_aleph_record,'to_object',None)
        summary_aleph_record = getattr(self.summary_aleph_record, 'to_object',None)

        if not aleph_record and not summary_aleph_record:
            return None
        
        result = edeposit.amqp.marcxml2mods.marcxml2mods(
            marc_xml=(summary_aleph_record or aleph_record).xml.data, 
            uuid = self.UID(), 
            url = self.makeInternalURL())
        mods = result and result[0]
        return mods

    def getURNNBN(self):
        mods = self.getMODS()
        if not self.urnnbn:
            try:
                # import datetime
                # prefix = datetime.datetime.now().strftime("%s-%f")
                # open("/tmp/%s-mods.txt" % (prefix,),"wb").write(str(mods))
                request = convert_mono_xml(mods,getAdapter(self,IFormat).format or "")
                self.urnnbn = urnnbn_api.register_document(request)
            except ValueError,e:
                wft = api.portal.get_tool('portal_workflow')
                wft.doActionFor(self,'amqpError',comment='error from urnnbn resolver: ' + str(e))

        return self.urnnbn

    # Add your class methods and properties here


class PrimaryFieldInfo(object):
    implements(IPrimaryFieldInfo)
    adapts(IePeriodicalPart)
    
    def __init__(self, context):
        self.context = context
        fti = getUtility(IDexterityFTI, name=context.portal_type)
        self.schema = fti.lookupSchema()
        thumbnail = self.schema['thumbnail']
        if thumbnail.get(self.context):
            self.fieldname = 'thumbnail'
            self.field = thumbnail
        else:
            self.fieldname = 'file'
            self.field = self.schema['file']
    
    @property
    def value(self):
        return self.field.get(self.context)

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
