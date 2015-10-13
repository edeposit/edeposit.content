# -*- coding: utf-8 -*-
from five import grok
from zope.component import queryUtility, getUtility, getAdapter
from z3c.relationfield import RelationValue
from zope.app.intid.interfaces import IIntIds
from z3c.form import group, field, button

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
from plone.namedfile.interfaces import IImageScaleTraversable, INamedBlobFileField
import plone.namedfile.file

from edeposit.content import MessageFactory as _
from z3c.relationfield.schema import RelationChoice, Relation
from plone.formwidget.contenttree import ObjPathSourceBinder, PathSourceBinder
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from edeposit.content.aleph_record import IAlephRecord, IAlephRecordsContainer
from Products.CMFCore.utils import getToolByName
from zope.schema.vocabulary import SimpleVocabulary
from plone.dexterity.utils import createContentInContainer
from plone.dexterity.interfaces import IDexterityFTI
from Acquisition import aq_parent, aq_inner
from plone.rfc822.interfaces import IPrimaryFieldInfo, IPrimaryField
from zope.interface import implements
from zope.component import adapts
from zope.component import getUtility
from zope.schema import getFieldsInOrder
from zope.lifecycleevent import modified
from string import Template
from plone import api
from zope.i18n import translate
from StringIO import StringIO
from subprocess import call
import os.path
from functools import partial
from .changes import IChanges, IApplicableChange
from Acquisition import aq_inner, aq_parent
import simplejson as json
from edeposit.content.behaviors import IFormat, ICalibreFormat
from operator import __or__, attrgetter, methodcaller
from urlparse import urlparse
from plone.app.content.interfaces import INameFromTitle
import re
from operator import truth
from functools import partial
from itertools import product
from zope.app.form.browser import DatetimeI18nWidget
import edeposit.amqp.marcxml2mods

from .tasks import (
    IPloneTaskSender,
    DoActionFor
)

from edeposit.content.amqp_interfaces import (
    IEmailSender
)

def urlCodeIsValid(value):
    return True

from edeposit.content.tasks import (
    IPloneTaskSender,
    CheckUpdates,
)

from edeposit.content.next_step import INextStep
from cz_urnnbn_api import (
 api as urnnbn_api,
 convert_mono_xml,
 convert_mono_volume_xml
)


@grok.provider(IContextSourceBinder)
def availableAlephRecords(context):
    path = '/'.join(context.getPhysicalPath())
    query = { "portal_type" : ("edeposit.content.alephrecord",),
              "path": {'query' :path } 
             }
    return ObjPathSourceBinder(navigation_tree_query = query).__call__(context)

@grok.provider(IContextSourceBinder)
def availableOriginalFiles(context):
    epublication = aq_parent(aq_inner(context))
    path = '/'.join(epublication.getPhysicalPath())
    query = { "portal_type" : ("edeposit.content.originalfile",),
              "path": {'query' :path } 
             }
    return ObjPathSourceBinder(navigation_tree_query = query).__call__(context)

# fields implementations

class IVoucherFileField(INamedBlobFileField):
    pass

# file source
class IOriginalFileSourceField(INamedBlobFileField):
    pass

class VoucherFile(NamedBlobFile):
    implements(IVoucherFileField)

class OriginalFileSource(NamedBlobFile):
    implements(IOriginalFileSourceField)

from edeposit.app.fields import ISBNLine

from plone.app.z3cform.widget import DatetimeWidget
class CustomDatetimeWidget(DatetimeWidget):
    pass

class IOriginalFile(form.Schema, IImageScaleTraversable):
    """
    E-Deposit Original File
    """
    isbn = ISBNLine ( #schema.ASCIILine(
        title=_("ISBN"),
        required = False,
        )

    generated_isbn = schema.Bool(
        title = u"Přidělit ISBN agenturou",
        required = False,
        default = False,
        missing_value = False,
    )

    form.primary('file')
    file = OriginalFileSource (
        title=_(u"Original File of an ePublication"),
        required = False,
        )
    
    zpracovatel_zaznamu = schema.TextLine(
        title = u'Zpracovatel záznamu',
        required = True,
    )

    url = schema.ASCIILine(
        title=u"URL (pokud je publikace ke stažení z internetu)",
        constraint=urlCodeIsValid,
        required = False,
        )

    related_aleph_record = RelationChoice( title=u"Odpovídající záznam v Alephu",
                                           required = False,
                                           source = availableAlephRecords)
    thumbnail = NamedBlobFile(
        title=_(u"PDF kopie"),
        required = False,
        )

    voucher = VoucherFile (
        title = u"Ohlašovací lístek",
        required = False,
    )

    isClosed= schema.Bool (
        title = _(u'is closed out by Catalogizators'),
        description = u"",
        required = False,
        default = False,
    )

    summary_aleph_record = RelationChoice( title=u"Souborný záznam v Alephu",
                                           required = False,
                                           source = availableAlephRecords )

    primary_originalfile = RelationChoice( title=u"Primární originál",
                                           required = False,
                                           source = availableOriginalFiles)
                            
    isWellFormedForLTP = schema.Bool (
        title = u"Originál je ve formátu vhodném pro LTP",
        default = False,
        required = False
    )

    manuallyChoosenSysNumber = schema.ASCIILine (
        title = u"Systémové číslo přiděleného záznamu",
        required = False,
    )

    shouldBeFullyCatalogized = schema.Bool (
        title = u"Tento dokument musí projít celou katalogizační linkou",
        default = False,
        required = False
    )
    
    anotace = schema.Text(
        title=u"Anotace",
        required=False,
        missing_value=u'',
    )
    urnnbn = schema.ASCIILine (
        title = u"URN:NBN číslo",
        required = False,
    )
    storage_download_url = schema.ASCIILine (
        title = u"Linka do úložiště",
        required = False,
    )
    storage_path = schema.ASCIILine (
        title = u"Cesta v úložišti",
        required = False,
    )
    lastProcessingStart = schema.TextLine(
        title = u"Začátek posledního zpracování",
        required = False,
        readonly=True,
        )
    
@form.default_value(field=IOriginalFile['zpracovatel_zaznamu'])
def zpracovatelDefaultValue(data):
    member = api.user.get_current()
    return member.fullname or member.id

# Custom content-type class; objects created for this content type will
# be instances of this class. Use this class to add content-type specific
# methods and properties. Put methods that are mainly useful for rendering
# in separate view classes.

class OriginalFile(Container):
    grok.implements(IOriginalFile)

    folder_full_view_item_template = Template(u"""
 <div class="item visualIEFloatFix originalfile_folder_full_view_item">
    <h2 class="headline"> <a href="$href" class="summary url $typeClass $stateClass">$title</a> </h2>
    <div class="documentByLine" id="plone-document-byline">
        <span class="ObjectStatus">Stav: <a class="$stateClass" href="$stateCollectionHREF">$stateTitle</a></span>
        <span class="documentModified"> <span>Poslední změna:</span>$lastModified</span> </span>
        <span class="documentAuthor"> Ohlásil: <a href="$authorHref">$authorTitle</a></span>
    </div>
</div>
""")

    state_view_template = Template(u"""
    <div class="document-state-viewlet">
        <span class="ObjectStatus">Stav: <a class="$stateClass" href="$stateCollectionHREF">$stateTitle</a></span>
    </div>
""")

    def hasVoucher(self):
        return bool(self.voucher)

    def getCurrentStateCollectionHREF(self):
        return self.getStateCollectionHREF(api.content.get_state(self))

    def getStateCollectionHREF(self,state):
        prefix = '/producents/prehledy/originaly'
        print "getStateCollectionHREF for: ", state
        stateHREFs = dict(
            acquisition = '/producents/prehledy/originaly/akvizice/cekaji-na-akvizici',
            ISBNSubjectValidation = '/producents/prehledy/originaly/isbn-agentura/cekaji-na-vecnou-kontrolu-isbn',
            chooseProperAlephRecord = '/producents/prehledy/originaly/akvizice/cekaji-na-vyber-spravneho-zaznamu-z-alephu',
            declarationWithError = '/producent/problemy-pri-zpracovani/chyba-v-zadani',
            fileProblem = '/producent/problemy-pri-zpracovani/problem-s-originalem',
            wrongISBNError = '/producent/problemy-pri-zpracovani/chyba-v-isbn',
            onlyCzechISBNAceptedError = '/producent/problemy-pri-zpracovani/jsou-prijimana-pouze-ceska-isbn',
            isbnAlreadyExistsError = '/producent/problemy-pri-zpracovani/isbn-jiz-existuje',
            zpracovatelIsRequiredError = '/producent/problemy-pri-zpracovani/zpracovatel-je-povinny',
            middlewareProblem = '/producent/problemy-pri-zpracovani/chyba-v-systemu',
            DatumVydaniIsRequired = '/producent/problemy-pri-zpracovani/datum-vydani-je-povinne'
            )
        stateHREF = stateHREFs.get(state, "/")
        return api.portal.get().absolute_url() + prefix + stateHREF

    def folder_full_view_item(self):
        state = api.content.get_state(obj=self)
        creators = self.listCreators()
        mtool = self.portal_membership
        author = creators and creators[0]
        member = api.user.get(username=author)
        plone_utils = self.plone_utils
        stateTitle = translate(self.portal_workflow.getTitleForStateOnType(state, self.portal_type),
                               domain='plone',context = self.REQUEST)
        data = dict(
            href = self.absolute_url(),
            title = self.title,
            typeClass = 'contenttype-' + plone_utils.normalizeString(self.portal_type),
            stateClass = 'state-' + plone_utils.normalizeString(state),
            stateTitle = stateTitle,
            stateCollectionHREF = self.getStateCollectionHREF(state),
            authorHref = author and mtool.getHomeUrl(author),
            authorTitle = member and member.getProperty('fullname') or member.id,
            lastModified = self.toLocalizedTime(self.ModificationDate(),1),
            )
        return OriginalFile.folder_full_view_item_template.substitute(data)

    def state_viewlet(self):
        state = api.content.get_state(obj=self)
        stateTitle = translate(self.portal_workflow.getTitleForStateOnType(state, self.portal_type),
                               domain='plone',context = self.REQUEST)
        data = dict(
            stateClass = 'state-' + self.plone_utils.normalizeString(state),
            stateTitle = stateTitle,
            stateCollectionHREF = self.getStateCollectionHREF(state),
            )
        return OriginalFile.state_view_template.substitute(data)
        
    def updateFormat(self):
        data = self.file and self.file.data
        if data:
            mregistry = api.portal.get_tool('mimetypes_registry')
            mimetype = mregistry.classify(data).normalized()
            self.file.contentType = mimetype
        pass

    def getParentTitle(self):
        return aq_parent(aq_inner(self)).title

    def getNakladatelVydavatel(self):
        return aq_parent(aq_inner(self)).nakladatel_vydavatel

    def getZpracovatelZaznamu(self):
        return self.zpracovatel_zaznamu

    def getPodnazev(self):
        return aq_parent(aq_inner(self)).podnazev

    def getCast(self):
        return aq_parent(aq_inner(self)).cast

    def getNazevCasti(self):
        return aq_parent(aq_inner(self)).nazev_casti

    def needsThumbnailGeneration(self):
        parts = self.file and os.path.splitext(self.file.filename) or None
        isPdf = parts and parts[-1] and 'pdf' in parts[-1].lower()
        return self.file and not isPdf

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

    def wasStoredAtStorage(self):
        return bool(self.storage_path)

    def makeInternalURL(self):
        internal_url = "/".join([api.portal.get().absolute_url(), '@@redirect-to-uuid', self.UID()])
        return internal_url

    def makeDocumentURL(self):
        format = getAdapter(self,IFormat).format or ""
        internal_url = "/".join([api.portal.get().absolute_url(), '@@redirect-to-accessing', self.UID()])
        return dict(internal_url=internal_url,format=format)

    def makeAllRelatedDocumentsURLs(self):
        def getAllDocumentURLs(summary_record_aleph_sys_number):
            catalog = api.portal.get_tool('portal_catalog')
            brains = catalog(portal_type="edeposit.content.originalfile",
                             summary_record_aleph_sys_number = summary_record_aleph_sys_number)
            return map(methodcaller('makeDocumentURL'),
                       filter(methodcaller('wasStoredAtStorage'),
                              map(methodcaller('getObject'), brains)))

        urls = (self.summary_record_aleph_sys_number and getAllDocumentURLs(self.summary_record_aleph_sys_number)) \
            or [ self.makeDocumentURL() ]
        return urls

    @property
    def isWellFormedForLTP(self):
        result = self.isValidEPub2() or self.isValidPDFA()
        return result

    @property
    def hasResultsFromValidationForLTP(self):
        """
        """
        responses = [ii[1] for ii in self.items() 
                     if ii[1].portal_type == 'edeposit.content.pdfboxvalidationresponse'
                     or ii[1].portal_type == 'edeposit.content.epubcheckvalidationresponse'
                     ]
        return bool(responses)

    def latestValidationResponseURL(self):
        response = self.latestValidationResponse
        return response and response.absolute_url()

    @property
    def latestValidationResponse(self):
        responses = [ii[1] for ii in self.items() 
                     if ii[1].portal_type == 'edeposit.content.pdfboxvalidationresponse'
                     or ii[1].portal_type == 'edeposit.content.epubcheckvalidationresponse'
        ]
        #responses.sort(index=lambda item: item.created())
        return responses and responses[0]

    def submitValidationsForLTP(self):
        format = getAdapter(self,IFormat).format or ""
        print "submit ValidationsForLTP, format:\"%s\"\n" % (format,)
        if format == 'PDF':
            IPloneTaskSender(DoActionFor(transition='submitPDFBoxValidation', uid=self.UID())).send()

        if format == 'EPub':
            IPloneTaskSender(DoActionFor(transition='submitEPubCheckValidation', uid=self.UID())).send()

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

    def hasSomeAlephRecords(self):
        alephRecords = self.listFolderContents(contentFilter={'portal_type':'edeposit.content.alephrecord'})
        return len(alephRecords)
        
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

        """
./bin/instance80 debug

of = app['edeposit']['producents']['ostre-nakladatelstvi-c-18']['epublications']['sherlock-holmes-a-pripad-dvou-zmizelych']['sh_a_pripad_dvou_zmizelych_epub.epub']

of.SearchableText()

"""

    def SearchableText(self):
        texts = filter(bool,(self.title, 
                             self.getParentTitle(), 
                             self.getPodnazev(),
                             self.isbn, 
                             self.isbn and self.isbn.replace('-',''),
                             self.aleph_sys_number,
                             self.summary_record_aleph_sys_number
                             )
                       )
        return " ".join(texts)

    @property
    def lastProcessingStart(self):
        # if "3368" in self.aleph_sys_number:
        #     import pdb; pdb.set_trace()
        #     pass

        states = ["antivirus", "exportToAleph"]
        wft = api.portal.get_tool('portal_workflow')
        workflowHistory = wft.getHistoryOf('edeposit_originalfile_workflow',self)
        times = filter(bool,
                       map(lambda item: item['time'],  
                           filter(lambda item: item['review_state'] in states, workflowHistory)))
        result =  (times and max(times)) or min(map(lambda item: item['time'], workflowHistory))
        return result

        
    def lastExportToAlephStartedAt(self):
        wft = api.portal.get_tool('portal_workflow')
        workflowHistory = wft.getHistoryOf('edeposit_originalfile_workflow',self)
        exportToAleph = filter(lambda item: item['review_state']=='exportToAleph', workflowHistory)
        return exportToAleph and exportToAleph[-1]['time']

    # Add your class methods and properties here
    def updateOrAddAlephRecord(self, dataForFactory):
        sysNumber = dataForFactory.get('aleph_sys_number',None)
        alephRecords = self.listFolderContents(contentFilter={'portal_type':'edeposit.content.alephrecord'})

        # exist some record with the same sysNumber?
        arecordWithTheSameSysNumber = filter(lambda arecord: arecord.aleph_sys_number == sysNumber,
                                             alephRecords)
        print dataForFactory
        if arecordWithTheSameSysNumber:
            print "a record with the same sysnumber"
            # update this record
            alephRecord = arecordWithTheSameSysNumber[0]

            # def isChangedFactory(alephRecord,data):
            #     def isChanged(attr):
            #         return getattr(alephRecord,attr,None) != data.get(attr,None)
            #     return isChanged

            # changedAttrs = filter(isChangedFactory(alephRecord,dataForFactory), dataForFactory.keys())
            # print "changedAttrs", changedAttrs
            # for attr in changedAttrs:
            #     setattr(alephRecord,attr,dataForFactory.get(attr,None))

            changedAttrs = alephRecord.findAndLoadChanges(dataForFactory)
            importantAttrs = frozenset(changedAttrs) - frozenset(['xml','aleph_library'])
            if importantAttrs:
                print "... changed important attrs: ", importantAttrs
                IPloneTaskSender(CheckUpdates(uid=self.UID())).send()

        else:
            alephRecord = createContentInContainer(self, 'edeposit.content.alephrecord', **dataForFactory)

            # if dataForFactory.get('isClosed',False):
            #     self.related_aleph_record = None
            # else:
            #     related_aleph_record = self.related_aleph_record and \
            #                            getattr(self.related_aleph_record,'to_object',None)
            #     if related_aleph_record and not related_aleph_record.isClosed:
            #         self.related_aleph_record = None
                    
            IPloneTaskSender(CheckUpdates(uid=self.UID())).send()


    # Add your class methods and properties here
    def updateOrAddAlephSummaryRecord(self, dataForFactory):
        sysNumber = dataForFactory.get('aleph_sys_number',None)
        alephRecords = self.listFolderContents(contentFilter={'portal_type':'edeposit.content.alephrecord'})

        # exist some record with the same sysNumber?
        arecordWithTheSameSysNumber = filter(lambda arecord: arecord.aleph_sys_number == sysNumber,
                                             alephRecords)
        print dataForFactory
        if arecordWithTheSameSysNumber:
            print "a record with the same sysnumber"
            # update this record
            alephRecord = arecordWithTheSameSysNumber[0]
            changedAttrs = alephRecord.findAndLoadChanges(dataForFactory)

            # def isChangedFactory(alephRecord,data):
            #     def isChanged(attr):
            #         return getattr(alephRecord,attr,None) != data.get(attr,None)
            #     return isChanged

            # changedAttrs = filter(isChangedFactory(alephRecord,dataForFactory), dataForFactory.keys())
            # print "changedAttrs", changedAttrs
            # for attr in changedAttrs:
            #     setattr(alephRecord,attr,dataForFactory.get(attr,None))
            importantAttrs = frozenset(changedAttrs) - frozenset(['xml','aleph_library'])
            if importantAttrs:
                print "... changed important attrs: ", importantAttrs
                IPloneTaskSender(CheckUpdates(uid=self.UID())).send()
        else:
            alephRecord = createContentInContainer(self, 'edeposit.content.alephrecord', **dataForFactory)

            # if dataForFactory.get('isClosed',False):
            #     self.related_aleph_record = None
            # else:
            #     related_aleph_record = self.related_aleph_record and \
            #                            getattr(self.related_aleph_record,'to_object',None)
            #     if related_aleph_record and not related_aleph_record.isClosed:
            #         self.related_aleph_record = None

            IPloneTaskSender(CheckUpdates(uid=self.UID())).send()

    @property
    def isbnAppearsAtRelatedAlephRecord(self):
        if self.related_aleph_record:
            record = getattr(self.related_aleph_record, 'to_object',None)
            if record:
                isbn_from_record = record.isbn
                # if record.aleph_sys_number == '000003043':
                #     isbn_from_record = '978-80-904739-3-5'

                isbn_from_original = self.isbn

                if isbn_from_original.replace('-','') == isbn_from_record.replace('-',''):
                    return True

                return False

        return False

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
    def summary_record_aleph_sys_number(self):
        if self.summary_aleph_record:
            record = getattr(self.summary_aleph_record, 'to_object',None)
            return record and record.aleph_sys_number
        return None

    @property
    def summary_record_id_number(self):
        if self.summary_aleph_record:
            record = getattr(self.summary_aleph_record, 'to_object',None)
            return record and record.id_number
        return None

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

    @property
    def is_public(self):
        return aq_parent(aq_inner(self)).is_public

    def some_not_closed_originalfile_exists(self):
        pcatalog = api.portal.get_tool('portal_catalog')
        getAttr = partial(getattr,self)
        numbers = filter(truth, map(getAttr,('summary_record_id_number','summary_record_aleph_sys_number')))

        searchNotClosed = partial(pcatalog, portal_type='edeposit.content.originalfile', isClosed=False)

        brains = numbers and (searchNotClosed(id_number = dict(query = numbers)) \
                                  + searchNotClosed(aleph_sys_number = dict(query = numbers)))
        return bool(brains)

    def fully_catalogized_closed_originalfile_exists(self):
        getAttr = partial(getattr,self)
        numbers = filter(truth, map(getAttr,['summary_record_aleph_sys_number','summary_record_id_number']))

        pcatalog = api.portal.get_tool('portal_catalog')
        searchClosed = partial(pcatalog, 
                               portal_type='edeposit.content.originalfile',
                               shouldBeFullyCatalogized=True,
                               isClosed=True)
        brains = numbers and (searchClosed(summary_record_aleph_sys_number = dict( query = numbers )) \
                                  +  searchClosed(summary_record_id_number = dict( query = numbers )))
        return bool(brains)

    def refersToThisOriginalFile(self,aleph_record):
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
        alephRecords = self.listFolderContents(contentFilter={'portal_type':'edeposit.content.alephrecord'})

        self.related_aleph_record = None
        self.summary_aleph_record = None
        self.primary_originalfile = None
        
        related_aleph_record = None

        intids = getUtility(IIntIds)
        recordsThatRefersToThis = filter(lambda rr: self.refersToThisOriginalFile(rr), alephRecords)
        if len(recordsThatRefersToThis) == 1:
            related_aleph_record = recordsThatRefersToThis[0]
            self.related_aleph_record = RelationValue(intids.getId(related_aleph_record))
            self.reindexObject(idxs=['isClosed','id_number'])
        else:
            closedAlephRecords = filter(lambda rr: rr.isClosed, recordsThatRefersToThis)
            if len(closedAlephRecords) == 1:
                related_aleph_record = closedAlephRecords[0]
                self.related_aleph_record = RelationValue(intids.getId(related_aleph_record))
                self.reindexObject(idxs=['isClosed','id_number'])

        if related_aleph_record and related_aleph_record.isClosed:
            reference = related_aleph_record.summary_record_aleph_sys_number
            refersTo = lambda rr,reference: rr.id_number == reference or re.sub(r'^0+','',rr.aleph_sys_number) in reference
            properSummaryRecords = [rr for rr in alephRecords if refersTo(rr,reference)]
            if len(properSummaryRecords) == 1:
                summary_aleph_record = properSummaryRecords[0]
                self.summary_aleph_record = RelationValue(intids.getId(summary_aleph_record))
                self.reindexObject(idxs=['summary_record_aleph_sys_number','summary_record_id_number'])
            pass

        # if related_aleph_record and related_aleph_record.isClosed:
        #     # doplnime souborny zaznam
        #     #import pdb; pdb.set_trace()
        #     related_aleph_record.summary_record_info
            
        # if len(alephRecords) == 1:
        #     self.related_aleph_record = RelationValue(intids.getId(alephRecords[0]))

        # if len(alephRecords) > 1:
        #     recordsThatRefersToThis = filter(lambda rr: self.refersToThisOriginalFile(rr), alephRecords)
        #     if len(recordsThatRefersToThis) == 1:
        #         self.related_aleph_record = RelationValue(intids.getId(recordsThatRefersToThis[0]))
        #     else:
        #         isClosedRecords = filter(lambda rr: rr.isClosed, recordsThatRefersToThis)
        #         if len(isClosedRecords) == 1:
        #             self.related_aleph_record = RelationValue(intids.getId(isClosedRecords[0]))

        #         summaryRecords = filter(lambda rr: rr.isSummaryRecord, recordsThatRefersToThis)
        #         if len(summaryRecords) == 1:
        #             self.summary_aleph_record = RelationValue(intids.getId(summaryRecords[0]))

        #     # isClosedRecords = filter(lambda rr: rr.isClosed, alephRecords)
        #     # if len(isClosedRecords) == 1:
        #     #     self.related_aleph_record = RelationValue(intids.getId(isClosedRecords[0]))

        #     # summaryRecords = filter(lambda item: item.isSummaryRecord, alephRecords)
        #     # if summaryRecords:
        #     #     self.summary_aleph_record = RelationValue(intids.getId(summaryRecords[0]))
        #     #     # TODO
        #     #     # doplnil zarazeni primary_originalfile
                
    def properAlephRecordsChoosen(self):
        # the method says that there is no need to manualy choose
        # related_aleph_record and summary_aleph_record
        # alephRecords = self.listFolderContents(contentFilter={'portal_type':'edeposit.content.alephrecord'})
        # if len(alephRecords) == 1:
        #     return bool(self.related_aleph_record)
        # else:
        #     isClosedRecords = filter(lambda item: item.isClosed, alephRecords)
        #     summaryRecords = filter(lambda item: item.isSummaryRecord, alephRecords)
        #     if isClosedRecords:
        #         if summaryRecords:
        #             return bool(self.related_aleph_record) and bool(self.summary_aleph_record)
        #         else:
        #             return bool(self.related_aleph_record)
        return bool(self.related_aleph_record)

    def dataForContributionPDF(self):
        keys = [ii for ii in IOriginalFile.names() if ii not in ('file','thumbnail')]
        return dict(zip(keys,map(partial(getattr,self), keys)))

    def removeInappropriateAlephRecords(self):
        """ remove aleph records that does not refer to this original file """
        alephRecords = self.listFolderContents(contentFilter={'portal_type':'edeposit.content.alephrecord'})

        toBeRemoved = [rec for rec in alephRecords if not self.refersToThisOriginalFile(rec)]
        for record in toBeRemoved:
            api.content.delete(obj=record)
        pass

    def checkUpdates(self):
        """ it tries to decide whether some changes appeared in aleph records. 
        The function loads the changes from a proper aleph record into its own attributes.
        The function will plan producent notification.
        """

        # self.removeInappropriateAlephRecords()
        self.updateAlephRelatedData()

        changes = IChanges(self).getChanges()
        for change in changes:
            IApplicableChange(change).apply()

        if changes:
            getAdapter(self, IEmailSender, name="originalfile-has-been-changed").send()
            #self.informProducentAboutChanges = True

        for ii in range(20):
            wasNextState=INextStep(self).doActionFor()
            if not wasNextState:
                break

    def getAMQPErrors(self):
        wft = self.portal_workflow
        review_history=wft.getInfoFor(self, 'review_history')
        amqpErrors = filter(lambda rh: rh['action'] == 'amqpError', review_history)
        return amqpErrors

    def applyContentFromStorage(self, storage_publication):
        raise "Not implemented"

class OriginalFilePrimaryFieldInfo(object):
    implements(IPrimaryFieldInfo)
    adapts(IOriginalFile)
    
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

def tryPrimaryOriginalGetterFactory(getter):
    def tryGetter(self):
        if self.primary_originalfile:
            obj = getattr(self.primary_originalfile,'to_object',None)
            if obj:
                return getter(obj)
        return getter(self)
    return tryGetter

def getAssignedPersonFactory(roleName):
    def getAssignedPerson(self):
        local_roles = self.get_local_roles()
        # print "... get assigned person %s, %s" % (roleName, str(local_roles))
        pairs = filter(lambda pair: roleName in pair[1], local_roles)
        return pairs and pairs[0][0] or None

    return getAssignedPerson

OriginalFile.getAssignedDescriptiveCataloguer = tryPrimaryOriginalGetterFactory(
    getAssignedPersonFactory('E-Deposit: Descriptive Cataloguer')
)

OriginalFile.getAssignedDescriptiveCataloguingReviewer = tryPrimaryOriginalGetterFactory(
    getAssignedPersonFactory('E-Deposit: Descriptive Cataloguing Reviewer')
)

OriginalFile.getAssignedSubjectCataloguer = tryPrimaryOriginalGetterFactory(
    getAssignedPersonFactory('E-Deposit: Subject Cataloguer')
)

OriginalFile.getAssignedSubjectCataloguingReviewer = tryPrimaryOriginalGetterFactory(
    getAssignedPersonFactory('E-Deposit: Subject Cataloguing Reviewer')
)

class ThumbnailView(grok.View):
    grok.context(IOriginalFile)
    grok.require('zope2.View')
    grok.name("thumbnail")

    def __call__(self):
        thumbnail = self.context.thumbnail
        url = thumbnail and "/".join(thumbnail.getPhysicalPath()) \
            or "/".join(self.context.getPhysicalPath() + ("documentviewer",))
        self.request.response.redirect(url)


import plone.namedfile

# class folder_full_view_item(grok.View):
#     grok.context(IOriginalFile)
#     grok.require('zope2.View')
#     grok.name('folder_full_view_item')
    
class Download(plone.namedfile.browser.Download):
    pass

class DisplayFile(plone.namedfile.browser.DisplayFile):
    pass

class HasVoucherView(grok.View):
    grok.context(IOriginalFile)
    grok.require('zope2.View')
    grok.name('has-voucher')
    
    def render(self):
        return json.dumps(dict(hasVoucher = bool(self.context.voucher)))


class IChangeSourceForm(form.Schema):
    file = NamedBlobFile(
        title=u"Připojit soubor s ePublikací",
        required = False,
        )
    
class ChangeSourceView(form.SchemaForm):
    grok.context(IOriginalFile)
    grok.require('cmf.ModifyPortalContent')
    grok.name('change-source')

    schema = IChangeSourceForm
    ignoreContext = False
    enable_form_tabbing = False
    autoGroups = False
    template = ViewPageTemplateFile('originalfile_templates/changesource.pt')
    prefix = 'sourceform'

    @button.buttonAndHandler(u"Odeslat", name="save")
    def handleAdd(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return

        self.context.file = data['file']
        newId = INameFromTitle(self.context).title
        api.content.rename(obj=self.context, new_id = str(newId), safe_id=True)
        newTitle = "%s (%s)" % (self.context.getParentTitle(), self.context.file and self.context.file.filename or "")
        self.context.title = newTitle
        if self.context.file:
            # If originalfile has aleph records and ISBN is at Aleph Records
            # skip ISBN validation
            # remove thumbnail
            self.context.thumbnail = None
            wft = api.portal.get_tool('portal_workflow')
            wft.doActionFor(self.context, (self.context.isbn and (\
                self.context.isbnAppearsAtRelatedAlephRecord and 'submitDeclarationSkipISBNValidation' or
                'submitDeclarationToISBNValidation')) or ('submitDeclarationToAntivirus'))

        self.request.response.redirect(self.context.absolute_url())


class OriginalFileChangeSource(object):
    implements(IChangeSourceForm)
    adapts(IOriginalFile)

    def __init__(self, context):
        self.context = context
    
    @property
    def file(self):
        return self.context.file

