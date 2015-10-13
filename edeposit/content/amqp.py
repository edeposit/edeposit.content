# -*- coding: utf-8 -*-

from plone import api
from zope.interface import Interface, Attribute, implements, classImplements
from zope.component import getUtility, getAdapter, getMultiAdapter, adapts, provideAdapter
from Acquisition import aq_parent, aq_inner
from plone.namedfile.file import NamedBlobFile
from base64 import b64encode, b64decode
from plone.dexterity.utils import createContentInContainer, addContentToContainer, createContent
import transaction
import simplejson as json
from Products.CMFCore.WorkflowCore import WorkflowException

from functools import partial
from itertools import product
from edeposit.content.behaviors import IFormat, ICalibreFormat
from operator import attrgetter,itemgetter, methodcaller
from edeposit.content.next_step import INextStep
from AccessControl import Unauthorized

from edeposit.content.amqp_interfaces import (
    IEmailSender
)

from edeposit.content.utils import normalizeISBN, readCollection, sendHTMLMultipartEmail
from normalize_cz_unicode import normalize

import lxml
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from  cz_urnnbn_api import api as urnnbn_api

# (occur-1 "class " nil (list (current-buffer)) "*amqp: class*")
# (occur-1 "def " nil (list(current-buffer)) "*amqp: def*")

from edeposit.amqp.aleph import (
    ISBNQuery, 
    GenericQuery, 
    CountRequest, 
    SearchRequest, 
    DocumentQuery,
    ICZQuery,
    ISBNValidationRequest,
    ExportRequest
)

from edeposit.amqp.serializers import (
    serialize,
    deserialize
)
from edeposit.amqp.aleph.datastructures.epublication import (
    EPublication,
    Author
)

from edeposit.amqp.aleph.datastructures.semanticinfo import (
    SemanticInfo
)

from edeposit.amqp.aleph.datastructures.alephrecord import (
    AlephRecord
)

from edeposit.amqp.aleph.datastructures.results import (
    ISBNValidationResult,
    CountResult,
    SearchResult,
    ExportResult,
)

from edeposit.amqp.antivirus.structures import (
    ScanResult,
    ScanFile
)

from edeposit.amqp.calibre.structures import (
    ConversionRequest,
    ConversionResponse
)
from edeposit.amqp.pdfgen.structures import (
    GenerateContract,
    GenerateReview,
    PDF
)

from edeposit.amqp.storage import (    
    Publication,
    Archive,
    SaveRequest,
)

import edeposit.amqp.ltp as ltp
# from  edeposit.amqp.ltp import (
#     ExportRequest,
#     TrackingRequest
# )


from edeposit.amqp.aleph_link_export import (
    LinkUpdateRequest,
    LinkUpdateResponse,
    LinkDescription
)

from edeposit.user.producent import IProducent

from collective.zamqp.producer import Producer
from collective.zamqp.consumer import Consumer
from collective.zamqp.connection import BlockingChannel
from collective.zamqp.interfaces import (
    IProducer, 
    IConsumer
)

from five import grok
import json
import base64
from zope.component import getUtility

from edeposit.content.tasks import *
from edeposit.content.amqp_folder import IAMQPFolder

"""
(add-hook 'after-save-hook 'restart-pdb-instance nil t)
"""


class AntivirusCheckRequestProducent(Producer):
    grok.name('amqp.antivirus-request')

    connection_id = "antivirus"
    exchange = "antivirus"
    serializer = "text/plain"
    exchange_type = "topic"
    exchange_durable = True
    auto_delete = False
    durable = True
    routing_key = "request"
    pass

class ISBNValidationRequestProducent(Producer):
    grok.name('amqp.isbn-validation')

    connection_id = "aleph"
    exchange = "validate"
    serializer = "text/plain"
    exchange_type = "topic"
    exchange_durable = True
    auto_delete = False
    durable = True
    routing_key = "request"
    pass

class ISBNSearchRequestProducent(Producer):
    grok.name('amqp.isbn-search-request')

    connection_id = "aleph"
    exchange = "search"
    serializer = "text/plain"
    exchange_type = "topic"
    exchange_durable = True
    auto_delete = False
    durable = True
    routing_key = "request"
    pass

class CalibreConvertProducent(Producer):
    grok.name('amqp.calibre-convert-request')

    connection_id = "calibre"
    exchange = "convert"
    serializer = "text/plain"
    exchange_type = "topic"
    exchange_durable = True
    auto_delete = False
    durable = True
    routing_key = "request"
    pass

class PDFGenerationProducent(Producer):
    grok.name('amqp.pdfgen-request')

    connection_id = "pdfgen"
    exchange = "pdfgen"
    serializer = "text/plain"
    exchange_type = "topic"
    exchange_durable = True
    auto_delete = False
    durable = True
    routing_key = "request"
    pass

class PDFBoxProducent(Producer):
    grok.name('amqp.pdfbox-validation-request')

    connection_id = "pdfbox"
    exchange = "validate"
    serializer = "text/plain"
    exchange_type = "topic"
    exchange_durable = True
    auto_delete = False
    durable = True
    routing_key = "request"
    pass

class EPubCheckProducent(Producer):
    grok.name('amqp.epubcheck-validation-request')

    connection_id = "epubcheck"
    exchange = "validate"
    serializer = "text/plain"
    exchange_type = "topic"
    exchange_durable = True
    auto_delete = False
    durable = True
    routing_key = "request"
    pass

class PloneTaskRunProducent(Producer):
    grok.name('amqp.plone-task-request')

    connection_id = "plone"
    exchange = "task"
    serializer = "text/plain"
    exchange_type = "topic"
    exchange_durable = True
    auto_delete = False
    durable = True
    routing_key = "request"
    pass

class IScanResult(Interface):
    result = Attribute("")
    filename = Attribute("")
classImplements(ScanResult, IScanResult)

class IISBNValidationResult(Interface):
    is_valid = Attribute("")
classImplements(ISBNValidationResult, IISBNValidationResult)

class ICountResult(Interface):
    num_of_records = Attribute("")
classImplements(CountResult, ICountResult)

class IAlephExportResult(Interface):
    ISBN = Attribute("")
classImplements(ExportResult, IAlephExportResult)

class IAlephSearchResult(Interface):
    records = Attribute("List os AlephRecords")
classImplements(SearchResult, IAlephSearchResult)

class IAlephSearchDocumentResult(Interface):
    record = Attribute("Aleph Record")

class AlephSearchDocumentResult(namedtuple('AlephSearchDocumentResult',['record'])):
    pass
classImplements(AlephSearchDocumentResult, IAlephSearchDocumentResult)

class IAlephSearchSummaryRecordResult(Interface):
    record = Attribute("Aleph Record")

class AlephSearchSummaryRecordResult(namedtuple('AlephSearchSummaryRecordResult',['record'])):
    pass
classImplements(AlephSearchSummaryRecordResult, IAlephSearchSummaryRecordResult)

class ICalibreConversionResult(Interface):
    type = Attribute("")
    b64_data = Attribute("")
    protocol = Attribute("")
classImplements(ConversionResponse, ICalibreConversionResult)

class IPDFGenerationResult(Interface):
    b64_content = Attribute("")
classImplements(PDF, IPDFGenerationResult)

class IStoragePublication(Interface):
    title = Attribute("")
    author = Attribute("")
    pub_year = Attribute("")
    isbn = Attribute("")
    urnnbn = Attribute("")
    uuid = Attribute("")
    aleph_id = Attribute("")
    producent_id = Attribute("")
    is_public = Attribute("")
    filename = Attribute("")
    b64_data = Attribute("")
    url = Attribute("")
    file_pointer = Attribute("")
classImplements(Publication,IStoragePublication)

class IStorageArchive(Interface):
    isbn = Attribute("")
    uuid = Attribute("")
    aleph_id = Attribute("")
    b64_data = Attribute("")
    dir_pointer = Attribute("")
classImplements(Archive,IStorageArchive)

class IAlephLinkStatusResponse(Interface):
    status = Attribute("")
    session_id = Attribute("")

class AlephLinkStatusResult(namedtuple('AlephLinkStatusResult',[])):
    pass
classImplements(LinkUpdateResponse, IAlephLinkStatusResponse)

class IAMQPSender(Interface):
    """
    """
    
    def send():
        pass
    

class IAMQPHandler(Interface):
    """
    """

    def handle():
        return None

def make_headers(context, session_data):
    return {
        'UUID': json.dumps({'context_UID': str(context.UID()),
                            'session_data': session_data
                        })
    }

def parse_headers(headers):
    uuid = headers and headers.get('UUID',None)

    if not uuid:
        return (None,{})

    try:
        data = json.loads(uuid)
        uid = data.get('context_UID',None)
        context = uid and api.content.get(UID=uid)
        return (context, data['session_data'])
    except ValueError,e:
        print "parse headers - error with headers UUID parsing", str(e)
        return (None,{})

from collections import namedtuple

class OriginalFileThumbnailRequestSender(namedtuple('ThumbnailGeneratingRequest',['context'])):
    implements(IAMQPSender)
    def send(self):
        print "-> Thumbnail Generating Request for: ", str(self.context)
        originalfile = self.context
        fileName = originalfile.file.filename

        inputFormat = getAdapter(self.context,ICalibreFormat).format.lower()
        fileNameExt = fileName.split(".")[-1].lower()
        from edeposit.amqp.calibre.structures import INPUT_FORMATS
        supportedFormat = fileName and ((inputFormat in INPUT_FORMATS and inputFormat)
                                        or
                                        (fileNameExt in INPUT_FORMATS and fileNameExt))
        request = ConversionRequest(supportedFormat, "pdf", base64.b64encode(originalfile.file.data))
        producer = getUtility(IProducer, name="amqp.calibre-convert-request")
        msg = ""
        session_data =  { 'isbn': str(self.context.isbn),
                          'filename': fileName,
                          'msg': msg
        }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request), content_type = 'application/json', headers = headers )
    pass

class AntivirusRequestSender(namedtuple('AntivirusRequest',['context'])):
    implements(IAMQPSender)
    def send(self):
        print "-> Antivirus Request for: ", str(self.context)
        context = self.context
        fileName = context.file.filename
        request = ScanFile(fileName, base64.b64encode(context.file.data))
        producer = getUtility(IProducer, name="amqp.antivirus-request")
        msg = ""
        session_data =  { 'isbn': str(self.context.isbn),
                          'msg': msg
        }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request), content_type = 'application/json', headers = headers )
    pass

class ISBNValidateRequestSender(namedtuple('ISBNValidateRequest',['context'])):
    """ context will be original file """
    implements(IAMQPSender)
    def send(self):
        print "-> ISBN Validation Request for: ", str(self.context)
        request = ISBNValidationRequest(self.context.isbn)
        producer = getUtility(IProducer, name="amqp.isbn-validate-request")
        msg = ""
        session_data =  { 'isbn': str(self.context.isbn),
                          'msg': msg
        }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
        pass

class ISBNDuplicityCheckRequestSender(namedtuple('ISBNDuplicityCheckRequest',['context'])):
    """ context will be original file """
    implements(IAMQPSender)
    def send(self):
        print "-> ISBN Duplicity Check Request for: ", str(self.context)
        request = CountRequest(ISBNQuery(self.context.isbn))
        producer = getUtility(IProducer, name="amqp.isbn-count-request")
        msg = ""
        session_data =  { 'isbn': str(self.context.isbn),
                          'msg': msg
        }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
        pass


class OriginalFileExportToAlephRequestSender(namedtuple('ExportToAlephRequest',['context'])):
    """ context will be original file """
    implements(IAMQPSender)
    def send(self):
        print "-> ISBN Export To Aleph Request for: ", str(self.context)
        originalFile = self.context
        epublication = aq_parent(aq_inner(originalFile))

        authors = map(lambda aa: Author(lastName = aa.fullname, firstName="", title = ""), 
                      epublication.authors.results())
        owners = map(lambda mm: mm.fullname or mm.id, 
                     map(api.user.get, 
                         [ii[0] for ii in originalFile.get_local_roles() if 'Owner' in ii[1]]))

        epublicationRecord =  EPublication (
            ISBN = normalizeISBN(originalFile.isbn or ""),
            invalid_ISBN = "",
            nazev = normalize(epublication.title or ""),
            podnazev = normalize(epublication.podnazev or ""),
            vazba = "online",
            cena = normalize(str(epublication.cena or "")),
            castDil = normalize(epublication.cast or ""),
            nazevCasti = normalize(epublication.nazev_casti or ""),
            nakladatelVydavatel = normalize(epublication.nakladatel_vydavatel or ""),
            datumVydani = normalize(str(epublication.rok_vydani)),
            poradiVydani = normalize(epublication.poradi_vydani or ""),
            zpracovatelZaznamu = normalize(originalFile.zpracovatel_zaznamu or (owners and owners[0]) or ""),
            format = normalize(getAdapter(originalFile,IFormat).format or ""),
            url = normalize(originalFile.url or ""),
            mistoVydani = normalize(epublication.misto_vydani),
            ISBNSouboruPublikaci = normalizeISBN(epublication.isbn_souboru_publikaci or ""),
            autori = map(lambda author: normalize(author.lastName), filter(lambda author: author.lastName, authors)),
            originaly = [],
            internal_url = originalFile.makeInternalURL() or "",
            id_number = getattr(originalFile,'id_number',None),
            anotace = normalize(getattr(originalFile,'anotace',"")),
        )
        request = ExportRequest(epublication=epublicationRecord)
        producer = getUtility(IProducer, name="amqp.aleph-export-request")
        msg = ""
        session_data =  { 'isbn': str(self.context.isbn),
                          'msg': msg
        }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
        pass

class OriginalFileSysNumberSearchRequestSender(namedtuple('SysNumberSearchRequest',['context'])):
    """ context will be original file """
    implements(IAMQPSender)
    def send(self):
        print "-> SysNumber search Request for: ", str(self.context), self.context.isbn
        request = SearchRequest(ISBNQuery(self.context.isbn))
        producer = getUtility(IProducer, name="amqp.isbn-search-request")
        msg = ""
        session_data =  { 'isbn': str(self.context.isbn),
                          'msg': msg,
        }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
        pass

class OriginalFileSearchRequestSender(namedtuple('OriginalFileSearchRequest',['context'])):
    """ context will be original file """
    implements(IAMQPSender)
    def send(self):
        print "-> SysNumber search Request for: ", str(self.context), self.context.isbn
        request = SearchRequest(ISBNQuery(self.context.isbn))
        producer = getUtility(IProducer, name="amqp.isbn-search-request")
        msg = ""
        session_data =  { 'isbn': str(self.context.isbn),
                          'msg': msg,
        }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
        pass


class RenewAlephRecordsRequestSender(namedtuple('RenewAlephRecordsRequest',['context'])):
    """ context will be original file """
    implements(IAMQPSender)
    def send(self):
        print "-> Renew Aleph Records Request for: ", str(self.context), self.context.isbn
        request = SearchRequest(ISBNQuery(self.context.isbn))
        producer = getUtility(IProducer, name="amqp.isbn-search-request")
        msg = ""
        session_data =  { 'isbn': str(self.context.isbn),
                          'msg': msg,
        }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
        pass

class RenewAlephRecordsBySysNumberRequestSender(namedtuple('RenewAlephRecordsBySysNumberRequest',['context'])):
    """ context will be original file """
    implements(IAMQPSender)
    def send(self):
        print "-> Renew Aleph Records By SysNumber Request for: ", str(self.context)
        alephRecords = self.context.listFolderContents(contentFilter={'portal_type':'edeposit.content.alephrecord'})
        for alephRecord in alephRecords:
            print "... renew Aleph Record: ", str(alephRecord)
            sysnumber = alephRecord.aleph_sys_number

            if not sysnumber:
                print "... no related_aleph_record found, skipping"
                continue

            request = SearchRequest(DocumentQuery(sysnumber))
            producer = getUtility(IProducer, name="amqp.isbn-search-request")
            msg = ""
            session_data =  { 'isbn': str(self.context.isbn),
                              'msg': msg,
                              'uuid-of-originalfile': self.context.UID(),
                              'renew-records-for-sysnumber': str(sysnumber)
                          }
            headers = make_headers(alephRecord, session_data)
            producer.publish(serialize(request),  content_type = 'application/json', headers = headers)

class RenewAlephRecordsByICZSysNumberRequestSender(namedtuple('RenewAlephRecordsByICZSysNumberRequest',['context'])):
    """ context will be original file """
    implements(IAMQPSender)
    def send(self):
        print "-> Renew Aleph Records By ICZ SysNumber Request for: ", str(self.context)
        alephRecords = self.context.listFolderContents(contentFilter={'portal_type':'edeposit.content.alephrecord'})
        for alephRecord in filter(lambda rr: rr.isClosed, alephRecords):
            print "... renew Summary record for closed Aleph Record: ", str(alephRecord)
            icznumber = alephRecord.summary_record_aleph_sys_number

            if not icznumber:
                print "... no icz sysnumber found, skipping"
                continue

            request = SearchRequest(ICZQuery(icznumber))
            producer = getUtility(IProducer, name="amqp.isbn-search-request")
            msg = ""
            session_data =  { 'isbn': str(self.context.isbn),
                              'msg': msg,
                              'renew-records-for-icz-sysnumber': str(icznumber) }
            headers = make_headers(self.context, session_data)
            producer.publish(serialize(request),  content_type = 'application/json', headers = headers)


# class OriginalFileLoadSummaryRecordRequestSender(namedtuple('LoadSummaryRecordRequest',['context'])):
#     """ context will be original file """
#     implements(IAMQPSender)
#     def send(self):
#         print "-> Load Summary Record from Aleph for: ", str(self.context), self.context.related_aleph_record
#         sysnumber = self.context.related_aleph_record and self.context.related_aleph_record.summary_record_aleph_sys_number
        
#         if not sysnumber:
#             print "... no sysnumber for summary record found at related_aleph_record, quit"
#             return

#         request = SearchRequest(DocumentQuery(sysnumber))
#         producer = getUtility(IProducer, name="amqp.isbn-search-request")
#         msg = ""
#         session_data =  { 'isbn': str(self.context.isbn),
#                           'msg': msg,
#                           'load-summary-record-for-sysnumber': str(sysnumber)
#         }
#         headers = make_headers(self.context, session_data)
#         producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
#         pass

class OriginalFileContributionPDFGenerateRequestSender(namedtuple('PDFGenerateRequest',['context'])):
    """ context will be original file """
    implements(IAMQPSender)
    def send(self):
        print "-> Contribution PDF Generate Request for: ", str(self.context)

        epublication = aq_parent(aq_inner(self.context))
        dataFromEPublication = epublication.dataForContributionPDF()
        dataFromOriginalFile = self.context.dataForContributionPDF()
        data = dict(dataFromEPublication.items() + dataFromOriginalFile.items())
        #open("/tmp/data-for-pdf.json","wb").write(json.dumps(data,ensure_ascii=False))
        # request = SearchRequest(ISBNQuery(self.context.isbn))
        # producer = getUtility(IProducer, name="amqp.isbn-search-request")
        # msg = ""
        # session_data =  { 'isbn': str(self.context.isbn),
        #                   'msg': msg,
        # }
        # headers = make_headers(self.context, session_data)
        # producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
        pass
        
class B64FileData(namedtuple('B64FileData',['b64_data','filename'])):
    pass

class IXML(Interface):
    xml = Attribute("")

class XML(namedtuple('XML',['xml',])):
    pass
classImplements(XML, IXML)

class IPDFBoxResponse(IXML):
    pass

class PDFBoxResponse(XML):
    pass
classImplements(PDFBoxResponse, IPDFBoxResponse)

class IEPubCheckResponse(Interface):
    isWellFormedEPUB2 = Attribute("")
    isWellFormedEPUB3 = Attribute("")
    validationMessages = Attribute("")
    xml = Attribute("")

class EPubCheckResponse(namedtuple("EPubCheckResponse",
                                   ['isWellFormedEPUB2','isWellFormedEPUB3','validationMessages','xml'])):
    pass
classImplements(EPubCheckResponse, IEPubCheckResponse)
                    
def PDFBoxResponseFactory():
    def factory(xml):
        print "factory calling"
        return PDFBoxResponse(xml=xml)
    return factory

class OriginalFilePDFBoxValidationRequestSender(namedtuple('PDFBoxValidationRequest',['context'])):
    implements(IAMQPSender)
    def send(self):
        print "-> PDFBox Validation Request for: ", str(self.context)
        originalfile = self.context
        fileName = originalfile.file.filename
        request = B64FileData(b64_data = base64.b64encode(originalfile.file.data), filename = fileName)
        producer = getUtility(IProducer, name="amqp.pdfbox-validation-request")
        msg = ""
        session_data =  { 'isbn': str(self.context.isbn),
                          'filename': fileName,
                          'msg': msg
        }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request), 
                         content_encoding = "application/json",
                         content_type = 'edeposit/pdfbox-validate',
                         headers = headers)
    pass

class OriginalFileEPubCheckValidationRequestSender(namedtuple('EPubCheckValidationRequest',['context'])):
    implements(IAMQPSender)
    def send(self):
        print "-> EPubCheck Validation Request for: ", str(self.context)
        originalfile = self.context
        fileName = originalfile.file.filename
        request = B64FileData(b64_data = base64.b64encode(originalfile.file.data), filename = fileName)
        producer = getUtility(IProducer, name="amqp.epubcheck-validation-request")
        msg = ""
        session_data =  { 'isbn': str(self.context.isbn),
                          'filename': fileName,
                          'msg': msg
        }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request), 
                         content_encoding = "application/json",
                         content_type = 'edeposit/epubcheck-validate',
                         headers = headers)
    pass

class IPublishPloneTask(namedtuple("IPublishPloneTask",['context'])):
    adapts(IPloneTask)
    implements(IAMQPSender)
    def send(self):
        print "-> Generic Plone Task send"
        payload = IJSONEncoder(self.context).encode()
        producer = getUtility(IProducer, name="amqp.edeposit-plone-task")
        producer.publish(payload, content_type="application/json", headers={})
        pass

provideAdapter(IPublishPloneTask)

class OriginalFilePDFGenerationResultHandler(namedtuple('PDFGenerationResult',['context', 'result'])):
    implements(IAMQPHandler)
    def handle(self):
        print "<- PDF Generation Result for: ", str(self.context)
        wft = api.portal.get_tool('portal_workflow')
        result = self.result
        context = self.context
        epublication=aq_parent(aq_inner(context))
        with api.env.adopt_user(username="system"):
            if result.result: # some virus found
                comment =u"v souboru %s je virus: %s" % (context.file.filename, str(result.result))
                wft.doActionFor(context, 'antivirusError', comment=comment)
            else:
                transition =  context.needsThumbnailGeneration() and 'antivirusOKThumbnail' \
                              or (context.isbn and (context.hasSomeAlephRecords() and 
                                                    'antivirusOKSkipExportToAleph' or 'antivirusOKAleph') 
                                  or 'antivirusOKISBNGeneration')
                print "transition: %s" % (transition,)
                wft.doActionFor(context, transition)
            pass
        pass

class OriginalFilePDFBoxValidationResultHandler(namedtuple('PDFBoxValidationResult',['context', 'result'])):
    implements(IAMQPHandler)
    def handle(self):
        print "<- PDFBox Validation Result for: ", str(self.context)
        wft = api.portal.get_tool('portal_workflow')
        result = self.result
        context = self.context
        with api.env.adopt_user(username="system"):
            context.updateOrAddPDFBoxResponse(result.xml)
            #wft.doActionFor(context, 'pdfboxResponse')
            IPloneTaskSender(DoActionFor(transition='pdfboxResponse', uid=context.UID())).send()
        pass

class OriginalFileEPubCheckValidationResultHandler(namedtuple('EPubCheckValidationResult',
                                                              ['context', 'result'])):
    implements(IAMQPHandler)
    def handle(self):
        print "<- EPubCheck Validation Result for: ", str(self.context)
        wft = api.portal.get_tool('portal_workflow')
        result = self.result
        context = self.context
        with api.env.adopt_user(username="system"):
            context.updateOrAddEPubCheckResponse(result)
            wft.doActionFor(context, 'epubcheckResponse')
        pass

class OriginalFileAntivirusResultHandler(namedtuple('AntivirusResult',['context', 'result'])):
    implements(IAMQPHandler)
    def handle(self):
        print "<- Antivirus Result for: ", str(self.context)
        wft = api.portal.get_tool('portal_workflow')
        result = self.result
        context = self.context
        epublication=aq_parent(aq_inner(context))
        with api.env.adopt_user(username="system"):
            if result.result: # some virus found
                comment =u"v souboru %s je virus: %s" % (context.file.filename, str(result.result))
                wft.doActionFor(context, 'antivirusError', comment=comment)
            else:
                print "current state: ", api.content.get_state(self.context)
                transition =  context.needsThumbnailGeneration() and 'antivirusOKThumbnail' \
                              or (context.isbn and  ( context.hasSomeAlephRecords() and 
                                                      'antivirusOKSkipExportToAleph' or 'antivirusOKAleph') 
                                  or 'antivirusOKISBNGeneration')
                print "transition: %s" % (transition,)
                context.submitValidationsForLTP()
                wft.doActionFor(context, transition)
            pass
        pass


class OriginalFileThumbnailGeneratingResultHandler(namedtuple('ThumbnailGeneratingResult',
                                                              ['context','result'])):
    """ 
    context: originalfile
    result:  ThumbnailGeneratingResult
    """
    def handle(self):
        print "<- Calibre Thumbnail Generating Result for: ", str(self.context)
        wft = api.portal.get_tool('portal_workflow')
        with api.env.adopt_user(username="system"):
            bfile = NamedBlobFile(data=b64decode(self.result.b64_data),  filename=u"thumbnail.pdf")
            self.context.thumbnail = bfile
            transaction.savepoint(optimistic=True)
            transition =  self.context.isbn and (self.context.hasSomeAlephRecords() 
                                                 and 'thumbnailOKSkipExportToAleph'
                                                 or  'thumbnailOKAleph')  or 'thumbnailOKISBNGeneration'
            try:
                wft.doActionFor(self.context,transition)
            except WorkflowException:
                comment = u"akce: '%s' neni ve stavu '%s' povolena" %(transition, api.content.get_state(obj=self.context))
                print "... Thumbnail Generating Result  error", comment
        pass


class ISBNValidateResultHandler(namedtuple('ISBNValidateResult',['context', 'result'])):
    """ 
    context: originalfile or book
    result:  ISBNValidationResult
    """
    def handle(self):
        print "<- ISBN Validation result for: ", str(self.context)
        wft = api.portal.get_tool('portal_workflow')
        with api.env.adopt_user(username="system"):
            wft.doActionFor(self.context, self.result.is_valid and 'ISBNIsValid' or 'ISBNIsNotValid')
        pass

class CountResultHandler(namedtuple('ISBNCountResult',['context', 'result'])):
    """ 
    context: originalfile, book
    result:  CountResult
    """
    def handle(self):
        print "<- Aleph Count result for: ", str(self.context)
        wft = api.portal.get_tool('portal_workflow')
        is_duplicit = bool(int(self.result.num_of_records))
        with api.env.adopt_user(username="system"):
            wft.doActionFor(self.context, is_duplicit and 'ISBNIsDuplicit' or 'ISBNIsUnique')
        pass


class AlephExportResultHandler(namedtuple('AlephResultResult',['context', 'result'])):
    """ 
    context: originalfile, book
    result:  CountResult
    """
    def handle(self):
        print "<- Aleph Export result for: ", str(self.context)
        wft = api.portal.get_tool('portal_workflow')
        with api.env.adopt_user(username="system"):
            print "\tobj state: ", api.content.get_state(obj=self.context)
            wft.doActionFor(self.context, 'exportToAlephOK')
            print "\taction for done: ",'exportToAlephOK'
        pass

class AlephSearchResultHandler(namedtuple('AlephSearchtResult',['context', 'result'])):
    """ 
    context: originalfile, book
    result:  SearchResult
    """
    def handle(self):
        print "<- Aleph Search result for: ", str(self.context)
        with api.env.adopt_user(username="system"):
            print "num of records: ", len(self.result.records)
            for record in self.result.records:
                epublication = record.epublication
                internal_url = getattr(epublication,'internal_url',None)
                internal_urls = getattr(epublication,'internal_urls', None)  or internal_url or []
                # if record.docNumber in ['000003035','000003043']:
                #     internal_urls = [ api.portal.getSite().portal_url() + '/producents/nakladatelstvi-gama/epublications/pasivni-domy-2013/pd2013_sbornik.pdf', 'some url', ]

                # if record.docNumber in ['000003099']:
                #     internal_urls += [ self.context.makeInternalURL() ]

                dataForFactory = {
                    'title': "".join([u"Záznam v Alephu: ",
                                      str(epublication.nazev), 
                                      '(', 
                                      str(record.docNumber),
                                      ')']),
                    'nazev':  str(epublication.nazev),
                    'isbn': epublication.ISBN and epublication.ISBN[0],
                    'podnazev': epublication.podnazev,
                    'cast': epublication.castDil,
                    'nazev_casti': epublication.nazevCasti,
                    'rok_vydani': epublication.datumVydani,
                    'aleph_sys_number': record.docNumber,
                    'aleph_library': record.library,
                    'acquisitionFields': record.semantic_info.acquisitionFields,
                    'ISBNAgencyFields': record.semantic_info.ISBNAgencyFields,
                    'descriptiveCataloguingFields': record.semantic_info.descriptiveCatFields,
                    'descriptiveCataloguingReviewFields': record.semantic_info.descriptiveCatReviewFields,
                    'subjectCataloguingFields': record.semantic_info.subjectCatFields,
                    'subjectCataloguingReviewFields': record.semantic_info.subjectCatReviewFields,
                    'isClosed': record.semantic_info.isClosed,
                    'summary_record_info' : record.semantic_info.summaryRecordSysNumber,
                    'summary_record_aleph_sys_number' : record.semantic_info.parsedSummaryRecordSysNumber,
                    #'internal_url': record.epublication.internal_url,
                    'internal_urls': internal_urls,
                    'isSummaryRecord': record.semantic_info.isSummaryRecord or False,
                    'xml': NamedBlobFile(record.xml, filename=u"marc21.xml"),
                    'id_number': getattr(epublication,'id_number',None),
                    }
                self.context.updateOrAddAlephRecord(dataForFactory)

                # submit next search, if record is closed
                if record.semantic_info.isClosed:
                    sysnumber = record.semantic_info.parsedSummaryRecordSysNumber
                    request = SearchRequest(ICZQuery(sysnumber))
                    producer = getUtility(IProducer, name="amqp.isbn-search-request")
                    msg = ""
                    session_data =  { 'isbn': str(self.context.isbn),
                                      'msg': msg,
                                      'load-record-by-parsed-sysnumber': str(sysnumber) }
                    headers = make_headers(self.context, session_data)
                    producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
                pass
            
            if api.content.get_state(self.context) == 'tryToFindAtAleph':
                wft = self.context.portal_workflow
                transition = len(self.result.records) and 'someRecordsFoundAtAleph' or 'noRecordFoundAtAleph'
                print '... transition: ', transition
                wft.doActionFor(self.context, transition)
                
            IPloneTaskSender(CheckUpdates(uid=self.context.UID())).send()
        pass

class AlephRecordAlephSearchResultHandler(namedtuple('AlephSearchtResult',['context', 'result'])):
    """ 
    context: alephRecord
    result:  SearchResult
    """
    def handle(self):
        print "<- Aleph Record Aleph Search result for: ", str(self.context)
        with api.env.adopt_user(username="system"):
            print "num of records: ", len(self.result.records)
            for record in self.result.records:
                epublication = record.epublication
                internal_url = getattr(epublication,'internal_url',None) # this is a list of urls
                internal_urls = getattr(epublication,'internal_urls', None) or internal_url or []

                # if record.docNumber in ['000003035','000003043']:
                #     internal_urls = [ api.portal.getSite().portal_url() + '/producents/nakladatelstvi-gama/epublications/pasivni-domy-2013/pd2013_sbornik.pdf', 'some url', ]
                
                # if record.docNumber in ['000003099']:
                #     internal_urls += [ self.context.makeInternalURL() ]

                dataForFactory = {
                    'title': "".join([u"Záznam v Alephu: ",
                                      str(epublication.nazev), 
                                      '(', 
                                      str(record.docNumber),
                                      ')']),
                    'nazev':  str(epublication.nazev),
                    'isbn': epublication.ISBN and epublication.ISBN[0],
                    'podnazev': epublication.podnazev,
                    'cast': epublication.castDil,
                    'nazev_casti': epublication.nazevCasti,
                    'rok_vydani': epublication.datumVydani,
                    'aleph_sys_number': record.docNumber,
                    'aleph_library': record.library,
                    'ISBNAgencyFields': record.semantic_info.ISBNAgencyFields,
                    'acquisitionFields': record.semantic_info.acquisitionFields,
                    'descriptiveCataloguingFields': record.semantic_info.descriptiveCatFields,
                    'descriptiveCataloguingReviewFields': record.semantic_info.descriptiveCatReviewFields,
                    'subjectCataloguingFields': record.semantic_info.subjectCatFields,
                    'subjectCataloguingReviewFields': record.semantic_info.subjectCatReviewFields,
                    'isClosed': record.semantic_info.isClosed,
                    'summary_record_info' : record.semantic_info.summaryRecordSysNumber,
                    'summary_record_aleph_sys_number' : record.semantic_info.parsedSummaryRecordSysNumber,
                    #'internal_url': record.epublication.internal_url,
                    'internal_urls': internal_urls,
                    'isSummaryRecord': record.semantic_info.isSummaryRecord or False,
                    'xml': NamedBlobFile(record.xml, filename=u"marc21.xml"),
                    'id_number': getattr(epublication,'id_number',None),
                    }

                self.context.findAndLoadChanges(dataForFactory)

                if not self.result.records:
                    # drop context - no appropriate record at Aleph exists
                    api.content.delete(obj=self.context)
                    
            originalfile = aq_parent(aq_inner(self.context))
            IPloneTaskSender(CheckUpdates(uid=originalfile.UID())).send()
        pass

# class OriginalFileAlephSearchDocumentResultHandler(namedtuple('AlephSearchDocumentResult',
#                                                               ['context', 'result'])):
#     """ 
#     context: originalfile
#     result:  SearchDocumentResult
#     """
#     def handle(self):
#         print "<- Aleph Search Document result for: ", str(self.context)
#         with api.env.adopt_user(username="system"):
#             record = self.result.record
#             epublication = record.epublication
#             dataForFactory = {
#                 'title': "".join([u"Záznam v Alephu: ",
#                                   str(epublication.nazev), 
#                                   '(', 
#                                   str(record.docNumber),
#                                   ')']),
#                 'nazev':  str(epublication.nazev),
#                 'isbn': epublication.ISBN and epublication.ISBN[0],
#                 'podnazev': epublication.podnazev,
#                 'cast': epublication.castDil,
#                 'nazev_casti': epublication.nazevCasti,
#                 'rok_vydani': epublication.datumVydani,
#                 'aleph_sys_number': record.docNumber,
#                 'aleph_library': record.library,
#                 'ISBNAgencyFields': record.semantic_info.ISBNAgencyFields,
#                 'acquisitionFields': record.semantic_info.acquisitionFields,
#                 'descriptiveCataloguingFields': record.semantic_info.descriptiveCatFields,
#                 'descriptiveCataloguingReviewFields': record.semantic_info.descriptiveCatReviewFields,
#                 'subjectCataloguingFields': record.semantic_info.subjectCatFields,
#                 'subjectCataloguingReviewFields': record.semantic_info.subjectCatReviewFields,
#                 'isClosed': record.semantic_info.isClosed,
#                 'summary_record_info' : record.semantic_info.summaryRecordSysNumber,
#                 'summary_record_aleph_sys_number' : record.semantic_info.parsedSummaryRecordSysNumber,
#                 'xml': NamedBlobFile(record.xml, filename=u"marc21.xml"),
#             }
#             self.context.updateOrAddAlephRecord(dataForFactory)
#             for ii in range(20):
#                 wasNextState=INextStep(self.context).doActionFor()
#                 if not wasNextState:
#                     break
#         pass

# class OriginalFileAlephSearchSummaryRecordResultHandler(namedtuple('AlephSearchSummaryRecordResult',
#                                                                    ['context', 'result'])):
#     """ 
#     context: originalfile
#     result:  SearchSummaryRecordResult
#     """
#     def handle(self):
#         print "<- Aleph Search Summary Record result for: ", str(self.context)
#         with api.env.adopt_user(username="system"):
#             record = self.result.record
#             epublication = record.epublication
#             dataForFactory = {
#                 'title': "".join([u"Záznam v Alephu: ",
#                                   str(epublication.nazev), 
#                                   '(', 
#                                   str(record.docNumber),
#                                   ')']),
#                 'nazev':  str(epublication.nazev),
#                 'isbn': epublication.ISBN[0],
#                 'podnazev': epublication.podnazev,
#                 'cast': epublication.castDil,
#                 'nazev_casti': epublication.nazevCasti,
#                 'rok_vydani': epublication.datumVydani,
#                 'aleph_sys_number': record.docNumber,
#                 'aleph_library': record.library,
#                 'ISBNAgencyFields': record.semantic_info.ISBNAgencyFields,
#                 'acquisitionFields': record.semantic_info.acquisitionFields,
#                 'descriptiveCataloguingFields': record.semantic_info.descriptiveCatFields,
#                 'descriptiveCataloguingReviewFields': record.semantic_info.descriptiveCatReviewFields,
#                 'subjectCataloguingFields': record.semantic_info.subjectCatFields,
#                 'subjectCataloguingReviewFields': record.semantic_info.subjectCatReviewFields,
#                 'isClosed': record.semantic_info.isClosed,
#                 'summary_record_info' : record.semantic_info.summaryRecordSysNumber,
#                 'summary_record_aleph_sys_number' : record.semantic_info.parsedSummaryRecordSysNumber,
#                 'xml': NamedBlobFile(record.xml, filename=u"marc21.xml"),
#             }
#             self.context.updateOrAddAlephRecord(dataForFactory)
#             for ii in range(20):
#                 wasNextState=INextStep(self.context).doActionFor()
#                 if not wasNextState:
#                     break
#         pass


class ExceptionHandler(namedtuple('ExceptionHandler',['context', 'result'])):
    """ 
    context: originalfile, book
    result:  AMQPError
    """
    def handle(self):
        print "<- AMQP Exception for: ", self.context.absolute_url()
        wft = api.portal.get_tool('portal_workflow')
        print self.result
        with api.env.adopt_user(username="system"):
            wft.doActionFor(self.context,'amqpError', comment=str(self.result.payload))
        pass

class AlephRecordExceptionHandler(namedtuple('ExceptionHandler',['context', 'result'])):
    """ 
    context: alephRecord
    result:  AMQPError
    """
    def handle(self):
        print "<- AMQP Exception for: ", self.context.absolute_url()
        wft = api.portal.get_tool('portal_workflow')
        with api.env.adopt_user(username="system"):
            originalfile = aq_parent(aq_inner(self.context))
            if self.result.exception_name == 'DocumentNotFoundException':
                print "... remove aleph record: ", self.context
                api.content.delete(self.context)
                print "... state: ", api.content.get_state(originalfile)
                wft.doActionFor(originalfile,'amqpWarning', comment=str(self.result.payload))
                IPloneTaskSender(CheckUpdates(uid=originalfile.UID())).send()
            else:
                wft.doActionFor(originalfile,'amqpError', comment=str(self.result.payload))                
        pass

class AgreementGenerationRequestSender(namedtuple('AgreementGeneration',['context'])):
    implements(IAMQPSender)
    def send(self):
        print "-> Agreement Generation Request for: ", str(self.context)
        producent = self.context
        get = partial(getattr,producent)
        request = GenerateContract (
            firma = get('title') or "",
            pravni_forma = get('pravni_forma') or "",
            sidlo = get('domicile') or "",
            ic = get('ico') or "",
            dic = get('dic') or "",
            zastoupen = get('zastoupen') or "",
        )
        #open("/tmp/request-for-pdfgen.json","wb").write(json.dumps(request,ensure_ascii=False))
        producer = getUtility(IProducer, name="amqp.pdfgen-request")
        session_data =  { 'id': str(self.context.id), }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
        pass
    pass

class AgreementGenerationResultHandler(namedtuple('AgreementGenerationResult',['context', 'result'])):
    """ 
    context: IProducent
    result:  IPDF
    """
    def handle(self):
        print "<- PDFGen Agreement Generation Response for: ", str(self.context)
        wft = api.portal.get_tool('portal_workflow')
        with api.env.adopt_user(username="system"):
            lastName = self.context.absolute_url().split('/')[-1]
            bfile = NamedBlobFile(data=b64decode(self.result.b64_content),
                                  filename=u"smlouva-s-narodni-knihovnou-%s.pdf" %(lastName,))
            self.context.agreement = bfile
            transaction.savepoint(optimistic=True)
            wft.doActionFor(self.context,'pdfGenerated')
            pass
        pass

class AgreementGenerationExceptionHandler(namedtuple('ExceptionHandler',['context', 'result'])):
    """ 
    context: IProducent
    result:  AMQPError
    """
    def handle(self):
        print "<- AMQP Exception at pdfgen for: ", str(self.context)
        wft = api.portal.get_tool('portal_workflow')
        print self.result
        with api.env.adopt_user(username="system"):
            wft.doActionFor(self.context,'amqpError', comment=str(self.result.payload))
        pass


class VoucherGenerationRequestSender(namedtuple('VoucherGeneration',['context'])):
    implements(IAMQPSender)

    def availableLibraries(self):
        path = '/libraries'
        query = { "portal_type" : ("edeposit.content.library",),
                  "path": {'query' :path } 
              }
        libraries = api.portal.get_tool('portal_catalog')(portal_type='edeposit.content.library')
        return libraries

    def send(self):
        print "-> Voucher Generation Request for: ", str(self.context)
        originalfile = self.context
        epublication = aq_parent(aq_inner(self.context))
        get = partial(getattr,originalfile)

        autori = [aa.fullname for aa in epublication.authors.results()]
        (autor1, autor2, autor3) = (autori + [None, None, None])[:3]

        from edeposit.content.epublication import (   librariesAccessingChoices,
                                                      availableLibraries
                                                      )
        #vocab = availableLibraries(self.context)
        def accessingTranslate(token):
            results = [aa for aa in librariesAccessingChoices if aa[0] == token]
            return results and results[0][1] or ""

        libraries_accessing = accessingTranslate(epublication.libraries_accessing \
                                                 or librariesAccessingChoices[0][0])
        #libraries_by_value = dict([(aa.id,aa.Title) for aa in self.availableLibraries()])
        libraries_that_can_access = [ dict( id = aa.to_object.id, title=aa.to_object.Title())
                                      for aa in (epublication.libraries_that_can_access or []) ]

        fullAccess = reduce(lambda ii, result: ii[0] == 'vsechny knihovny maji pristup' and ii or result, 
                            librariesAccessingChoices)
        if epublication.libraries_accessing in fullAccess:
            libraries_that_can_access = [{'id':ii.token,'title':ii.title} for ii in availableLibraries(epublication)]

        filename = originalfile.file and originalfile.file.filename or ""
        nakladatel_vydavatel =  aq_parent(aq_inner(self.context)).nakladatel_vydavatel

        def toUTF8(value):
            if type(value) is unicode:
                return value.encode('utf-8')
            return value

        internal_url = "/".join([api.portal.get().absolute_url(),
                                 '@@redirect-to-uuid',        
                                 originalfile.UID()])
        itemsForReview = dict(
            nazev = epublication.title or "",
            podnazev = epublication.podnazev or "",
            cast = epublication.cast or "",
            nazev_casti = epublication.nazev_casti or "",
            isbn = get('isbn') or "",
            isbn_souboru_publikaci = epublication.isbn_souboru_publikaci or "",
            generated_isbn = get('generated_isbn') or "",
            poradi_vydani = epublication.poradi_vydani or "",
            misto_vydani = epublication.misto_vydani or "",
            rok_vydani = epublication.rok_vydani or "",
            nakladatel_vydavatel = nakladatel_vydavatel or "",
            vydano_v_koedici_s = epublication.vydano_v_koedici_s or "",
            cena = str(epublication.cena) or "",
            offer_to_riv = epublication.offer_to_riv,
            category_for_riv  = epublication.category_for_riv,
            is_public = epublication.is_public,
            libraries_accessing = libraries_accessing,
            libraries_that_can_access = libraries_that_can_access,
            zpracovatel_zaznamu = get('zpracovatel_zaznamu') or "",
            url = get('url') or "",
            format = getAdapter(originalfile,IFormat).format or "",
            filename = filename or "",
            author1 = autor1 or "",
            author2 = autor2 or "",
            author3 = autor3 or "",
            internal_url = internal_url,
            anotace = get('anotace') or "",
        )
        request = GenerateReview(**itemsForReview)
        #open("/tmp/request-for-pdfgen.json","wb").write(json.dumps(request,ensure_ascii=False))
        producer = getUtility(IProducer, name="amqp.pdfgen-request")
        session_data =  { 'id': str(self.context.id), }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
        pass
    pass

class VoucherGenerationResultHandler(namedtuple('VoucherGenerationResult',['context', 'result'])):
    """ 
    context: IProducent
    result:  IPDF
    """
    def handle(self):
        print "<- PDFGen Voucher Generation Response for: ", str(self.context)
        wft = api.portal.get_tool('portal_workflow')
        with api.env.adopt_user(username="system"):
            isbn = self.context.isbn or self.context.UID()
            filename = u"ohlasovaci-listek-%s.pdf" % (isbn,)
            bfile = NamedBlobFile(data=b64decode(self.result.b64_content),  filename=filename)
            self.context.voucher = bfile
            transaction.savepoint(optimistic=True)
            wft.doActionFor(self.context,'pdfGenerated')
            pass
        pass

class SendEmailsWithCollectionToAllProducentsHandler(
        namedtuple('SendEmailsWithCollectionToAllProducentsHandler',['context','result'])):
        
    def handle(self):
        print "<- Plone AMQP Task: ", str(self.result)
        with api.env.adopt_user(username="system"):
            producents = api.portal.get_tool('portal_catalog')(portal_type='edeposit.user.producent')
            for producentId in map(attrgetter('id'), producents):
            #for producentId in ['jan-stavel',]:
                path = "/".join(['','producents',producentId])
                IPloneTaskSender(
                    SendEmailWithCollectionToProperProducentMembers(
                        collectionPath = self.result.collectionPath,
                        producentPath = path,
                        subject = self.result.subject,
                        additionalEmails = self.result.additionalEmails)).send()
        pass

class SendEmailWithCollectionToProperProducentMembersHandler (
        namedtuple('SendEmailWithCollectionToProperProducentMembersHandler',['context','result'])):

    def handle(self):
        print "<- Plone AMQP Task: ", str(self.result)

        collectionPath = filter(bool,self.result.collectionPath.split("/"))
        producentPath = filter(bool,self.result.producentPath.split("/"))

        collection = reduce(getattr, collectionPath, api.portal.getSite())
        producent = reduce(getattr, producentPath, api.portal.get())

        producentMembers = producent.getProducentMembers()
        for username in producentMembers:
            email = api.user.get(username=username).getProperty('email')
            if not email:
                print "... uzivatel: %s nema email. Nic neposilam." % (username,)
                continue

            with api.env.adopt_user(username=username):
                try:
                    collData = readCollection(self.context.REQUEST, collection)
                    if collData['isEmpty']:
                        print "... empty collection for user: ", username
                    else:
                        sendHTMLMultipartEmail([email] + (self.result.additionalEmails or []),
                                               self.result.subject or collData['subject'],
                                               collData['body'])
                except Unauthorized, e:
                    print "user: %s, is not authorized to read collection: %s" % (username, collection)
        
class SendEmailWithCollectionToGroupTaskHandler(namedtuple('SendEmailWithCollectionToGroupTaskHandler',
                                                           ['context','result'])):
    """
    context: IAMQPHandler
    result: ISendEmailWithCollectionToGroup
    
    It sends collection as tabular_view in an html email.
    """
    def handle(self):
        path = filter(bool,self.result.collectionPath.split("/"))
        print "collection with path: ", path
        with api.env.adopt_user(username="system"):
            collection = reduce(getattr, path, api.portal.getSite())
            collData = readCollection(self.context.REQUEST, collection)
            if collData['isEmpty']:
                print "... je prazdno, nic se odesilat nebude"
                return

            groupname = self.result.recipientsGroup
            recipients = self.result.additionalEmails
            emailsFromGroup = [aa.getProperty('email') for aa in api.user.get_users(groupname=groupname)]
            recipients = frozenset(emailsFromGroup + recipients)
            print "... zacneme rozesilat pro: ", "|".join(recipients)
            sendHTMLMultipartEmail(recipients, self.result.subject or collData['subject'], collData['body'])

            # view = api.content.get_view(name='tabular_view',context=collection, request=self.context.REQUEST)
            # htmlRoot = lxml.html.fromstring(view())
            # content = htmlRoot.get_element_by_id('content')

            # if not len(htmlRoot.xpath('//tbody/tr')):
            #     print "... je prazdno, nic se odesilat nebude"
            #     return

            # body = lxml.html.tostring(content)
            # subject = self.result.subject
            # groupname = self.result.recipientsGroup
            # recipients = self.result.additionalEmails
            # emailsFromGroup = [aa.getProperty('email') for aa in api.user.get_users(groupname=groupname)]
            # recipients = frozenset(emailsFromGroup + recipients)
            # print "... zacneme rozesilat pro: ", "|".join(recipients)
            # msg = MIMEMultipart('alternative')
            # msg.attach(MIMEText(subject,'plain'))
            # msg.attach(MIMEText(body,'html'))
            # for recipient in recipients:
            #     print "... poslal jsem email: ", subject, recipient
            #     api.portal.send_email(recipient=recipient, subject=subject, body=msg)
            # pass


class SendEmailWithWorklistToGroupTaskHandler(namedtuple('SendEmailWithWorklistToGroupTaskHandler',
                                                         ['context', 'result'])):
    """ 
    context: IAMQPHandler
    result:  ISendEmailWithWorklistToGroup
    """
    def handle(self):
        print "<- Send Email with worklist: ", str(self.result)
        with api.env.adopt_user(username="system"):
            producentsFolder = api.portal.get_tool('portal_catalog')(portal_type='edeposit.user.producentfolder')[0].getObject()
            view = api.content.get_view(name=self.result.worklist,
                                        context = producentsFolder, 
                                        request = self.context.REQUEST)
            body = view()
            subject = self.result.subject
            if view.numOfRows:
                groupname = self.result.recipientsGroup
                recipients = self.result.additionalEmails
                emailsFromGroup = [aa.getProperty('email') for aa in api.user.get_users(groupname=groupname)]
                recipients = frozenset(emailsFromGroup + recipients)
                print "... zacneme rozesilat pro: ", "|".join(recipients)
                for recipient in recipients:
                    print "... poslal jsem email: ", subject, recipient
                    api.portal.send_email(recipient=recipient, subject=subject, body=body)
            else:
                print "... zadny email jsem neposlal. prazdno. ", subject

class LoadSysNumbersFromAlephTaskHandler(namedtuple('LoadSysNumbersFromAlephTaskHandler',
                                                    ['context', 'result'])):
    """ 
    context: IAMQPHandler
    result:  ILoadSysNumbersFromAleph
    """
    def handle(self):
        print "<- Plone AMQP Task: ", str(self.result)
        with api.env.adopt_user(username="system"):
            producentsFolder = api.portal.get_tool('portal_catalog')(portal_type='edeposit.user.producentfolder')[0].getObject()
            collection = producentsFolder['originalfiles-waiting-for-aleph']
            uids = map(lambda item: item.UID, collection.results(batch=False))
            for uid in uids:
                IPloneTaskSender(DoActionFor(transition='searchSysNumber', uid=uid)).send()
            pass

class RenewAlephRecordsTaskHandler(namedtuple('RenewAlephRecordsTaskHandler',
                                              ['context', 'result'])):
    """ 
    context: IAMQPHandler
    result:  IRenewAlephRecords
    """
    def handle(self):
        print "<- Plone AMQP Task: ", str(self.result)
        with api.env.adopt_user(username="system"):
            producentsFolder = api.portal.get_tool('portal_catalog')(portal_type='edeposit.user.producentfolder')[0].getObject()
            collection = producentsFolder['originalfiles-waiting-for-renew-aleph-records']
            uids = map(lambda item: item.UID, collection.results(batch=False))
            for uid in uids:
                IPloneTaskSender(DoActionFor(transition='renewAlephRecords', uid=uid)).send()

class DoActionForTaskHandler(namedtuple('DoActionForTaskHandler',
                                        ['context','result'])):
    def handle(self):
        print "<- Plone AMQP Task: ", str(self.result)
        with api.env.adopt_user(username="system"):
            wft = api.portal.get_tool('portal_workflow')
            obj = api.content.get(UID = self.result.uid)
            try:
                wft.doActionFor(obj,self.result.transition)
            except WorkflowException:
                comment = u"akce: '%s' neni ve stavu '%s' povolena" %( self.result.transition, api.content.get_state(obj=obj))
                print "... amqp error", comment
                wft.doActionFor(obj,'amqpError',comment=comment)


class SendEmailWithUserWorklistTaskHandler(namedtuple('SendEmailWithUserWorklistTaskHandler',
                                                      ['context', 'result'])):
    """ 
    context: IAMQPHandler
    result:  ISendEmailWithUserWorklist
    """

    """ doplnit mapovani collections, co je potreba vytvorit
    """

    collectionsMap = {
        'Descriptive Cataloguers' :  dict(indexName="getAssignedDescriptiveCataloguer",
                                          states=["descriptiveCataloguing", "closedDescriptiveCataloguing",],
                                          readerGroup = "Descriptive Cataloguing Administrators"),
        'Descriptive Cataloguing Reviewers' : dict(indexName="getAssignedDescriptiveCataloguingReviewer",
                                                   states=["descriptiveCataloguingReview","closedDescriptiveCataloguingReview"],
                                                   readerGroup = "Descriptive Cataloguing Administrators"),
        'Subject Cataloguers' : dict( indexName="getAssignedSubjectCataloguer",
                                      states=["subjectCataloguing","closedSubjectCataloguing",],
                                      readerGroup = "Subject Cataloguing Administrators"),
        'Subject Cataloguing Reviewers': dict( indexName="getAssignedSubjectCataloguingReviewer",
                                               states=["subjectCataloguingReview","closedSubjectCataloguingReview",],
                                               readerGroup = "Subject Cataloguing Administrators")
    }
    def handle(self):
        print "<- Send Email with user worklist: ", str(self.result)
        with api.env.adopt_user(username="system"):
            producentsFolder = api.portal.get_tool('portal_catalog')(portal_type='edeposit.user.producentfolder')[0].getObject()
            get = partial(getattr,self.result)
            (groupname,title,additionalEmails) = map(get,['groupname','title','additionalEmails'])

            item = self.collectionsMap.get(groupname)
            if not item:
                print "... nenasel jsem definici pro vytvoreni kolekci pro skupinu: ", groupname 
                return
            
            (indexName, states, readerGroup) = map(item.get, ['indexName','states','readerGroup'])
            for (member,state) in product(api.user.get_users(groupname=groupname), states):
                username = member.id
                #producentsFolder.recreateUserCollectionIfEmpty(username, indexName, state, readerGroup)
                email = member.getProperty('email')
                #view_name = 'worklist-waiting-for-user'
                view_name = 'worklist-by-state-waiting-for-user'
                subject = ('closed' in state and "Zamcene dokumenty - " or "") + title + " pro: " + username
                request = self.context.REQUEST
                request['userid']=username
                request['review_state']=state
                request['assigned_person_index'] = indexName
                view = api.content.get_view(name=view_name,
                                            context = producentsFolder,
                                            request = request)

                body = view()
                if view.numOfRows:
                    recipients = frozenset(self.result.additionalEmails + [email,])
                    for recipient in recipients:
                        print u"... odesilam email pro: " + recipient + " (" + state + ")"
                        api.portal.send_email(recipient=recipient, subject=subject, body=body)
                else:
                    print u"... nic neodesilame pro: " + username + " (" + state + ")"



class CheckUpdatesTaskHandler(namedtuple('CheckUpdatesTaskHandler', ['context','result'])):
    def handle(self):
        print "<- Plone AMQP Task: ", str(self.result)
        with api.env.adopt_user(username="system"):
            obj = api.content.get(UID = self.result.uid)
            obj.checkUpdates()

class EPublicationsWithErrorEmailNotifyTaskHandler(
        namedtuple('EPublicationsWithErrorEmailNotifyTaskHandler', ['context','result'])):
    def handle(self):
        print "<- Plone AMQP Task: ", str(self.result)
        with api.env.adopt_user(username="system"):
            obj = api.content.get(UID = self.result.uid)
            obj.notifyProducentAboutEPublicationsWithError()


class OriginalFileHasBeenChangedSendEmail(namedtuple('OriginalFileHasBeenChangedSendEmail',['context',])):
    def send(self):
        of = self.context
        print "send email notification"

class EnsureProducentsRolesConsistencyTaskHandler(namedtuple('EnsureProducentsRolesConsistencyTaskHandler',
                                                             ['context', 'result'])):
    """ 
    context: IAMQPHandler
    result:  IEnsureProducentsRolesConsistency
    """
    def handle(self):
        print "<- Plone AMQP Task: ", str(self.result)
        with api.env.adopt_user(username="system"):
            producents = api.portal.get_tool('portal_catalog')(portal_type='edeposit.user.producent')
            uids = map(lambda item: item.UID, producents)
            for uid in uids:
                IPloneTaskSender(DoActionFor(transition='ensureRolesConsistency', uid=uid)).send()

class AlephLinkUpdateResponseHandler(namedtuple('AlephLinkUpdateResponseHandler',['context','result'])):
    def handle(self):
        print "<- Aleph Link Update Response: ", str(self.result)
        with api.env.adopt_user(username="system"):
            context = api.content.get(UID=self.result.session_id)
            wft = api.portal.get_tool('portal_workflow')
            if 'OK' in self.result.status:
                wft.doActionFor(context, 'alephLinkUpdateResponseOK')
            else:
                wft.doActionFor(context, 'alephLinkUpdateResponseError', comment=str(self.result))

class EPublicationsWithErrorEmailNotifyForAllProducentsHandler(namedtuple('EPublicationsWithErrorEmailNotifyForAllProducentsHandler',
                                                                    ['context', 'result'])):
    """ 
    context: IAMQPHandler
    result:  IEPublicationsWithErrorEmailNotifyForAllProducents
    """
    def handle(self):
        print "<- Plone AMQP Task: ", str(self.result)
        with api.env.adopt_user(username="system"):
            producents = api.portal.get_tool('portal_catalog')(portal_type='edeposit.user.producent')
            uids = map(lambda item: item.UID, producents)
            for uid in uids:
                IPloneTaskSender(EPublicationsWithErrorEmailNotifyo(uid=uid)).send()

class BookAntivirusResultHandler(namedtuple('BookAntivirusResult',['context', 'result'])):
    implements(IAMQPHandler)
    def handle(self):
        print "<- Antivirus Result for: ", str(self.context)
        wft = api.portal.get_tool('portal_workflow')
        result = self.result
        context = self.context
        with api.env.adopt_user(username="system"):
            if result.result: # some virus found
                comment =u"v souboru %s je virus: %s" % (context.file.filename, str(result.result))
                wft.doActionFor(context, 'antivirusError', comment=comment)
            else:
                transition =  context.needsThumbnailGeneration() and 'antivirusOKThumbnail' \
                              or (context.isbn and 'antivirusOKTryToFindAtAleph') \
                              or 'antivirusOKISBNGeneration'
                print "transition: %s" % (transition,)
                wft.doActionFor(context, transition)
                context.submitValidationsForLTP()
            pass
        pass

class BookExportToAlephRequestSender(namedtuple('ExportToAlephRequest',['context'])):
    """ context will be original file """
    implements(IAMQPSender)
    def send(self):
        print "-> Export To Aleph Request for: ", str(self.context)
        obj = self.context
        authors = map(lambda lastName: Author(lastName = lastName, firstName ="", title=""),
                      map(attrgetter('fullname'),
                          map(methodcaller('getObject'),
                              obj.portal_catalog(portal_type = 'edeposit.content.author',
                                                 path = {'query': '/'.join(obj.getPhysicalPath()),
                                                         'depth': 1})
                          )
                      )
                  )

        owners = map(lambda mm: mm.fullname or mm.id, 
                     map(api.user.get, 
                         [ii[0] for ii in obj.get_local_roles() if 'Owner' in ii[1]]
                     )
                 )

        epublicationRecord =  EPublication (
            ISBN = normalizeISBN(obj.isbn or ""),
            invalid_ISBN = "",
            nazev = normalize(obj.nazev or ""),
            podnazev = normalize(obj.podnazev or ""),
            vazba = normalize(obj.vazba or ""),
            cena = normalize(str(obj.cena or "")),
            castDil = normalize(obj.cast or ""),
            nazevCasti = normalize(obj.nazev_casti or ""),
            nakladatelVydavatel = normalize(obj.nakladatel_vydavatel or ""),
            datumVydani = normalize(str(obj.rok_vydani)),
            poradiVydani = normalize(obj.poradi_vydani or ""),
            zpracovatelZaznamu = normalize(obj.zpracovatel_zaznamu or (owners and owners[0]) or ""),
            format = normalize(getAdapter(obj,IFormat).format or ""),
            url = normalize(getattr(obj,'url',None) or ""),
            mistoVydani = normalize(obj.misto_vydani),
            ISBNSouboruPublikaci = normalizeISBN(obj.isbn_souboru_publikaci or ""),
            autori = map(normalize, filter(bool, map(attrgetter('lastName'), authors))),
            originaly = [],
            internal_url = obj.makeInternalURL() or "",
            id_number = getattr(obj,'id_number',None),
            anotace = normalize(getattr(obj,'anotace',"")),
        )
        request = ExportRequest(epublication=epublicationRecord)
        producer = getUtility(IProducer, name="amqp.aleph-export-request")
        msg = ""
        session_data =  { 'isbn': str(self.context.isbn),
                          'msg': msg
        }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
        pass

# ---
class LinkUpdateRequestSender(namedtuple('LinkUpdateRequestSender',['context'])):
    """ context will be original file """
    implements(IAMQPSender)
    def send(self):
        print "-> Update links at Aleph for: ", str(self.context)
        urnnbn = self.context.getURNNBN()
        if not urnnbn:
            print "no urnnbn exists, no action"
            return

        def documentURLToLinkFormat(pair):
            result=LinkDescription(url=pair['internal_url'], format=pair['format'])
            return result

        request = LinkUpdateRequest(
            uuid = self.context.UID(),
            urn_nbn = urnnbn,
            doc_number = self.context.summary_record_aleph_sys_number or self.context.aleph_sys_number,
            document_urls = map(documentURLToLinkFormat, self.context.makeAllRelatedDocumentsURLs() or []),
            kramerius_url = self.context.urlToKramerius(),
            session_id = self.context.UID(),
            )

        producer = getUtility(IProducer, name="amqp.aleph-link-update-request")
        session_data =  { 'isbn': str(self.context.isbn), }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
        pass

class EmptyResultHandler(namedtuple('EmptyResultHandler',['context', 'result'])):
    implements(IAMQPHandler)
    def handle(self):
        print "<- Empty message result from aleph amqp: ", str(self.context)
        pass
# ----
class ExportToStorageRequestSender(namedtuple('ExportToStorageRequest',['context'])):
    """ context will be original file """
    implements(IAMQPSender)
    def send(self):
        print "-> Export To Storage Request for: ", str(self.context)
        #urnnbn = self.context.getURNNBN()
        #if not urnnbn:
        #    return
        urnnbn = ""
        record = Publication(
            title = self.context.title,
            author = "",
            pub_year = "",
            isbn = self.context.isbn,            
            urnnbn = urnnbn,
            uuid = self.context.UID(),
            aleph_id = self.context.aleph_sys_number,
            producent_id = "",
            is_public = self.context.is_public,
            filename = self.context.file.filename,
            b64_data = base64.b64encode(self.context.file.data),
            url = "",
            file_pointer = "",
            )
        
        request = SaveRequest(record=record)
        producer = getUtility(IProducer, name="amqp.storage-export-request")
        session_data =  { 'isbn': str(self.context.isbn), }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
        pass

class PublicationExportToStorageResultHandler(namedtuple('PublicationExportToStorageResult',['context', 'result'])):
    implements(IAMQPHandler)
    def handle(self):
        print "<- Export of Publication to Storage Result for: ", str(self.context)
        self.context.storage_download_url = self.result.url
        self.context.storage_path = self.result.file_pointer
        with api.env.adopt_user(username="system"):
            wft = api.portal.get_tool('portal_workflow')
            transition = self.context.isWellFormedForLTP and "exportToStorageOKToLTP" \
                or "exportToStorageOKSkipLTP"
            print "... transition: ", transition, api.content.get_state(obj=self.context)
            # wft.doActionFor(self.context, transition)
            pass
        pass
        IPloneTaskSender(DoActionFor(transition='submitUpdateLinksAtAleph', uid=self.context.UID())).send()

class SearchStorageRequestSender(namedtuple('SearchStorageRequest',['context'])):
    """ context will be original file """
    implements(IAMQPSender)
    def send(self):
        print "-> Search Storage Request for: ", str(self.context)
        publication = Publication(
            urnnbn = self.context.getURNNBN(),
            uuid = self.context.UID(),
            title = self.context.title,
            isbn = self.context.isbn,
            aleph_id = self.context.aleph_sys_number,
            is_public = self.context.is_public,
            filename = self.context.file.filename,
            b64_data = base64.b64encode(self.context.file.data),
            )
        
        request = SearchRequest(pub=publication)
        producer = getUtility(IProducer, name="amqp.storage-search-request")
        session_data =  { 'isbn': str(self.context.isbn), }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
        pass

class SearchStorageResultHandler(namedtuple('SearchStorageResult',['context', 'result'])):
    implements(IAMQPHandler)
    def handle(self):
        print "<- Search Storage Result for: ", str(self.context)
        wft = api.portal.get_tool('portal_workflow')
        with api.env.adopt_user(username="system"):
            for publication in self.result.publications:
                uuid = publication.uuid
                originalfile = api.content.get(UID=uuid)
                if originalfile:
                    originalfile.applyContentFromStorage(publication)
                
            wft.doActionFor(self.context, "searchStorageOK")
            pass
        pass

class ExportToLTPRequestSender(namedtuple('ExportToLTPRequest',['context'])):
    """ context will be original file, book """
    implements(IAMQPSender)
    def send(self):
        print "-> Export To LTP Request for: ", str(self.context)
        aleph_record = getattr(self.context.related_aleph_record,'to_object',None)
        if not aleph_record:
            print "... chyba exportu do LTP, chybi related aleph zaznam"
            return

        url = self.context.absolute_url()
        request = ltp.ExportRequest (
            aleph_record = aleph_record.xml.data,
            book_uuid = self.context.UID(),
            urn_nbn = self.context.getURNNBN(),
            url = url,
            filename = self.context.file.filename,
            b64_data = base64.b64encode(self.context.file.data),
            )

        producer = getUtility(IProducer, name="amqp.ltp-export-request")
        session_data =  { 'isbn': str(self.context.isbn), }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
        pass

class ExportToLTPResultHandler(namedtuple('ExportToLTPResult',['context', 'result'])):
    implements(IAMQPHandler)
    def handle(self):
        print "<- Export to LTP Result for: ", str(self.context)
        wft = api.portal.get_tool('portal_workflow')
        result = self.result
        context = self.context
        with api.env.adopt_user(username="system"):
            transition = "exportToLTPOK"
            wft.doActionFor(context, transition)
            pass
        pass

class ExportToKrameriusRequestSender(namedtuple('ExportToKrameriusRequest',['context'])):
    """ context will be original file, book """
    implements(IAMQPSender)
    def send(self):
        print "-> Export To Kramerius Request for: ", str(self.context)
        # publication = Publication(
        #     urnnbn = self.context.urnnbn,
        #     uuid = self.context.UID(),
        #     title = self.context.title,
        #     isbn = self.context.isbn,
        #     aleph_id = self.context.aleph_sys_number,
        #     is_public = self.context.is_public,
        #     filename = self.context.file.filename,
        #     b64_data = base64.b64encode(self.context.file.data),
        #     )
        
        # request = SaveRequest(pub=publication)
        # producer = getUtility(IProducer, name="amqp.kramerius-export-request")
        # session_data =  { 'isbn': str(self.context.isbn), }
        # headers = make_headers(self.context, session_data)
        # producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
        pass

class ExportToKrameriusResultHandler(namedtuple('ExportToKrameriusResult',['context', 'result'])):
    implements(IAMQPHandler)
    def handle(self):
        print "<- Export to Kramerius Result for: ", str(self.context)
        wft = api.portal.get_tool('portal_workflow')
        result = self.result
        context = self.context
        with api.env.adopt_user(username="system"):
            transition = "exportToKrameriusOK"
            wft.doActionFor(context, transition)
            pass
        pass
