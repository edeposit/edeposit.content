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

from functools import partial
from edeposit.content.behaviors import IFormat, ICalibreFormat

from edeposit.content.next_step import INextStep

from edeposit.content.amqp_interfaces import (
    IEmailSender
)

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

    data = json.loads(uuid)
    uid = data.get('context_UID',None)
    context = uid and api.content.get(UID=uid)
    return (context, data['session_data'])

from collections import namedtuple

class OriginalFileThumbnailRequestSender(namedtuple('ThumbnailGeneratingRequest',['context'])):
    implements(IAMQPSender)
    def send(self):
        print "-> Thumbnail Generating Request for: ", str(self.context)
        originalfile = self.context
        fileName = originalfile.file.filename

        inputFormat = ICalibreFormat(self.context).format
        request = ConversionRequest(inputFormat, "pdf", base64.b64encode(originalfile.file.data))
        producer = getUtility(IProducer, name="amqp.calibre-convert-request")
        msg = ""
        session_data =  { 'isbn': str(self.context.isbn),
                          'filename': fileName,
                          'msg': msg
        }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request), content_type = 'application/json', headers = headers )
    pass

class OriginalFileAntivirusRequestSender(namedtuple('AntivirusRequest',['context'])):
    implements(IAMQPSender)
    def send(self):
        print "-> Antivirus Request for: ", str(self.context)
        originalfile = self.context
        fileName = originalfile.file.filename
        request = ScanFile(fileName, base64.b64encode(originalfile.file.data))
        producer = getUtility(IProducer, name="amqp.antivirus-request")
        msg = ""
        session_data =  { 'isbn': str(self.context.isbn),
                          'msg': msg
        }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request), content_type = 'application/json', headers = headers )
    pass

class OriginalFileISNBValidateRequestSender(namedtuple('ISBNValidateRequest',['context'])):
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

class OriginalFileISNBDuplicityCheckRequestSender(namedtuple('ISBNDuplicityCheckRequest',['context'])):
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
        authors = map(lambda aa: Author(lastName = aa.fullname, firstName="", title = ""), epublication.authors.results())
        epublicationRecord =  EPublication (
            ISBN = originalFile.isbn or "",
            nazev = epublication.title or "",
            podnazev = epublication.podnazev or "",
            vazba = "online",
            cena = str(epublication.cena or ""),
            castDil = epublication.cast or "",
            nazevCasti = epublication.nazev_casti or "",
            nakladatelVydavatel = epublication.nakladatel_vydavatel or "",
            datumVydani = str(epublication.rok_vydani),
            poradiVydani = epublication.poradi_vydani or "",
            zpracovatelZaznamu = originalFile.zpracovatel_zaznamu or "",
            format = IFormat(originalFile).format or "",
            url = originalFile.url or "",
            mistoVydani = epublication.misto_vydani,
            ISBNSouboruPublikaci = epublication.isbn_souboru_publikaci or "",
            autori = map(lambda author: author.lastName, filter(lambda author: author.lastName, authors)),
            originaly = [],
            internal_url = originalFile.absolute_url() or "",
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
        request = SearchRequest(ISBNQuery(self.context.isbn, 'cze-dep'))
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
        request = SearchRequest(ISBNQuery(self.context.isbn, 'cze-dep'))
        producer = getUtility(IProducer, name="amqp.isbn-search-request")
        msg = ""
        session_data =  { 'isbn': str(self.context.isbn),
                          'msg': msg,
        }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
        pass


class OriginalFileRenewAlephRecordsRequestSender(namedtuple('RenewAlephRecordsRequest',['context'])):
    """ context will be original file """
    implements(IAMQPSender)
    def send(self):
        print "-> Renew Aleph Records Request for: ", str(self.context), self.context.isbn
        request = SearchRequest(ISBNQuery(self.context.isbn,'cze-dep'))
        producer = getUtility(IProducer, name="amqp.isbn-search-request")
        msg = ""
        session_data =  { 'isbn': str(self.context.isbn),
                          'msg': msg,
        }
        headers = make_headers(self.context, session_data)
        producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
        pass

class OriginalFileRenewAlephRecordsBySysNumberRequestSender(namedtuple('RenewAlephRecordsBySysNumberRequest',['context'])):
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

            request = SearchRequest(DocumentQuery(sysnumber,'cze-dep'))
            producer = getUtility(IProducer, name="amqp.isbn-search-request")
            msg = ""
            session_data =  { 'isbn': str(self.context.isbn),
                              'msg': msg,
                              'uuid-of-originalfile': self.context.UID(),
                              'renew-records-for-sysnumber': str(sysnumber)
                          }
            headers = make_headers(alephRecord, session_data)
            producer.publish(serialize(request),  content_type = 'application/json', headers = headers)

class OriginalFileRenewAlephRecordsByICZSysNumberRequestSender(namedtuple('RenewAlephRecordsByICZSysNumberRequest',['context'])):
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

            request = SearchRequest(ICZQuery(icznumber,'cze-dep'))
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

#         request = SearchRequest(DocumentQuery(sysnumber,'cze-dep'))
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
        # request = SearchRequest(ISBNQuery(self.context.isbn,'cze-dep'))
        # producer = getUtility(IProducer, name="amqp.isbn-search-request")
        # msg = ""
        # session_data =  { 'isbn': str(self.context.isbn),
        #                   'msg': msg,
        # }
        # headers = make_headers(self.context, session_data)
        # producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
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
                transition =  context.needsThumbnailGeneration() and 'antivirusOKThumbnail' \
                              or (context.isbn and  ( context.hasSomeAlephRecords() and 
                                                      'antivirusOKSkipExportToAleph' or 'antivirusOKAleph') 
                                  or 'antivirusOKISBNGeneration')
                print "transition: %s" % (transition,)
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
        epublication=aq_parent(aq_inner(self.context))
        with api.env.adopt_user(username="system"):
            bfile = NamedBlobFile(data=b64decode(self.result.b64_data),  filename=u"thumbnail.pdf")
            self.context.thumbnail = bfile
            transaction.savepoint(optimistic=True)
            wft.doActionFor(self.context, self.context.isbn and (self.context.hasSomeAlephRecords() 
                                                                 and 'thumbnailOKSkipExportToAleph'
                                                                 or  'thumbnailOKAleph')
                            or 'thumbnailOKISBNGeneration')
        pass


class OriginalFileISBNValidateResultHandler(namedtuple('ISBNValidateResult',['context', 'result'])):
    """ 
    context: originalfile
    result:  ISBNValidationResult
    """
    def handle(self):
        print "<- ISBN Validation result for: ", str(self.context)
        wft = api.portal.get_tool('portal_workflow')
        epublication=aq_parent(aq_inner(self.context))
        with api.env.adopt_user(username="system"):
            wft.doActionFor(self.context, self.result.is_valid and 'ISBNIsValid' or 'ISBNIsNotValid')
        pass

class OriginalFileCountResultHandler(namedtuple('ISBNCountResult',['context', 'result'])):
    """ 
    context: originalfile
    result:  CountResult
    """
    def handle(self):
        print "<- Aleph Count result for: ", str(self.context)
        wft = api.portal.get_tool('portal_workflow')
        epublication=aq_parent(aq_inner(self.context))
        is_duplicit = bool(int(self.result.num_of_records))
        with api.env.adopt_user(username="system"):
            wft.doActionFor(self.context, is_duplicit and 'ISBNIsDuplicit' or 'ISBNIsUnique')
        pass


class OriginalFileAlephExportResultHandler(namedtuple('AlephResultResult',['context', 'result'])):
    """ 
    context: originalfile
    result:  CountResult
    """
    def handle(self):
        print "<- Aleph Export result for: ", str(self.context)
        wft = api.portal.get_tool('portal_workflow')
        epublication=aq_parent(aq_inner(self.context))
        with api.env.adopt_user(username="system"):
            print "\tepublication state: ", api.content.get_state(obj=epublication)
            print "\toriginalfile state: ", api.content.get_state(obj=self.context)
            print "\taction for done: ", 'notifySystemAction'
            wft.doActionFor(self.context, 'exportToAlephOK')
            print "\taction for done: ",'exportToAlephOK'
        pass

class OriginalFileAlephSearchResultHandler(namedtuple('AlephSearchtResult',['context', 'result'])):
    """ 
    context: originalfile
    result:  SearchResult
    """
    def handle(self):
        print "<- Aleph Search result for: ", str(self.context)
        with api.env.adopt_user(username="system"):
            print "num of records: ", len(self.result.records)
            for record in self.result.records:
                epublication = record.epublication
                internal_url = getattr(epublication,'internal_url',None)
                internal_urls = getattr(epublication,'internal_urls', None) \
                                or (internal_url and [internal_url]) or []
                if record.docNumber in ['000003035','000003043']:
                    internal_urls = [ api.portal.getSite().portal_url() + '/producents/nakladatelstvi-gama/epublications/pasivni-domy-2013/pd2013_sbornik.pdf', 'some url', ]

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
                    'hasAcquisitionFields': record.semantic_info.hasAcquisitionFields,
                    'hasISBNAgencyFields': record.semantic_info.hasISBNAgencyFields,
                    'hasAcquisitionFields': record.semantic_info.hasAcquisitionFields,
                    'hasDescriptiveCataloguingFields': record.semantic_info.hasDescriptiveCatFields,
                    'hasDescriptiveCataloguingReviewFields': record.semantic_info.hasDescriptiveCatReviewFields,
                    'hasSubjectCataloguingFields': record.semantic_info.hasSubjectCatFields,
                    'hasSubjectCataloguingReviewFields': record.semantic_info.hasSubjectCatReviewFields,
                    'isClosed': record.semantic_info.isClosed,
                    'summary_record_info' : record.semantic_info.summaryRecordSysNumber,
                    'summary_record_aleph_sys_number' : record.semantic_info.parsedSummaryRecordSysNumber,
                    #'internal_url': record.epublication.internal_url,
                    'internal_urls': internal_urls,
                    'isSummaryRecord': record.semantic_info.isSummaryRecord or False,
                    'xml': NamedBlobFile(record.xml, filename=u"marc21.xml"),
                    }
                self.context.updateOrAddAlephRecord(dataForFactory)

                # submit next search, if record is closed
                if record.semantic_info.isClosed:
                    sysnumber = record.semantic_info.parsedSummaryRecordSysNumber
                    request = SearchRequest(ICZQuery(sysnumber,'cze-dep'))
                    producer = getUtility(IProducer, name="amqp.isbn-search-request")
                    msg = ""
                    session_data =  { 'isbn': str(self.context.isbn),
                                      'msg': msg,
                                      'load-record-by-parsed-sysnumber': str(sysnumber) }
                    headers = make_headers(self.context, session_data)
                    producer.publish(serialize(request),  content_type = 'application/json', headers = headers)
                pass

        pass

class AlephRecordAlephSearchResultHandler(namedtuple('AlephSearchtResult',['context', 'result'])):
    """ 
    context: alephRecord
    result:  SearchResult
    """
    def handle(self):
        print "<- Aleph Search result for: ", str(self.context)
        with api.env.adopt_user(username="system"):
            print "num of records: ", len(self.result.records)
            for record in self.result.records:
                epublication = record.epublication

                internal_url = getattr(epublication,'internal_url',None)
                internal_urls = getattr(epublication,'internal_urls', None) \
                                or (internal_url and [internal_url]) or []

                if record.docNumber in ['000003035','000003043']:
                    internal_urls = [ api.portal.getSite().portal_url() + '/producents/nakladatelstvi-gama/epublications/pasivni-domy-2013/pd2013_sbornik.pdf', 'some url', ]
                
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
                    'hasAcquisitionFields': record.semantic_info.hasAcquisitionFields,
                    'hasISBNAgencyFields': record.semantic_info.hasISBNAgencyFields,
                    'hasAcquisitionFields': record.semantic_info.hasAcquisitionFields,
                    'hasDescriptiveCataloguingFields': record.semantic_info.hasDescriptiveCatFields,
                    'hasDescriptiveCataloguingReviewFields': record.semantic_info.hasDescriptiveCatReviewFields,
                    'hasSubjectCataloguingFields': record.semantic_info.hasSubjectCatFields,
                    'hasSubjectCataloguingReviewFields': record.semantic_info.hasSubjectCatReviewFields,
                    'isClosed': record.semantic_info.isClosed,
                    'summary_record_info' : record.semantic_info.summaryRecordSysNumber,
                    'summary_record_aleph_sys_number' : record.semantic_info.parsedSummaryRecordSysNumber,
                    #'internal_url': record.epublication.internal_url,
                    'internal_urls': internal_urls,
                    'isSummaryRecord': record.semantic_info.isSummaryRecord or False,
                    'xml': NamedBlobFile(record.xml, filename=u"marc21.xml"),
                    }
                self.context.findAndLoadChanges(dataForFactory)

                if not self.result.records:
                    # drop context
                    api.content.delete(obj=self.context)
                    
            originalfile = aq_parent(aq_inner(self.context))
            for ii in range(20):
                wasNextState=INextStep(originalfile).doActionFor()
                if not wasNextState:
                    break

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
#                 'hasAcquisitionFields': record.semantic_info.hasAcquisitionFields,
#                 'hasISBNAgencyFields': record.semantic_info.hasISBNAgencyFields,
#                 'hasAcquisitionFields': record.semantic_info.hasAcquisitionFields,
#                 'hasDescriptiveCataloguingFields': record.semantic_info.hasDescriptiveCatFields,
#                 'hasDescriptiveCataloguingReviewFields': record.semantic_info.hasDescriptiveCatReviewFields,
#                 'hasSubjectCataloguingFields': record.semantic_info.hasSubjectCatFields,
#                 'hasSubjectCataloguingReviewFields': record.semantic_info.hasSubjectCatReviewFields,
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
#                 'hasAcquisitionFields': record.semantic_info.hasAcquisitionFields,
#                 'hasISBNAgencyFields': record.semantic_info.hasISBNAgencyFields,
#                 'hasAcquisitionFields': record.semantic_info.hasAcquisitionFields,
#                 'hasDescriptiveCataloguingFields': record.semantic_info.hasDescriptiveCatFields,
#                 'hasDescriptiveCataloguingReviewFields': record.semantic_info.hasDescriptiveCatReviewFields,
#                 'hasSubjectCataloguingFields': record.semantic_info.hasSubjectCatFields,
#                 'hasSubjectCataloguingReviewFields': record.semantic_info.hasSubjectCatReviewFields,
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


class OriginalFileExceptionHandler(namedtuple('ExceptionHandler',['context', 'result'])):
    """ 
    context: originalfile
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
            wft.doActionFor(originalfile,'amqpError', comment=str(self.result.payload))
            if self.result.exception_name == 'DocumentNotFoundException':
                print "... remove aleph record: ", self.context
                api.content.delete(self.context)
                IPloneTaskSender(CheckUpdates(uid=originalfile.UID())).send()
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
            bfile = NamedBlobFile(data=b64decode(self.result.b64_content),  filename=u"smlouva-s-narodni-knihovnou.pdf")
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
        libraries_accessing = epublication.libraries_accessing
        #libraries_by_value = dict([(aa.id,aa.Title) for aa in self.availableLibraries()])
        libraries_that_can_access = [ dict( id = aa.to_object.id, title=aa.to_object.Title())
                                      for aa in (epublication.libraries_that_can_access or [])]
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
            format = IFormat(originalfile).format or "",
            filename = filename or "",
            author1 = autor1 or "",
            author2 = autor2 or "",
            author3 = autor3 or "",
            internal_url = internal_url,
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
            wft.doActionFor(obj,self.result.transition)


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
                                          state="descriptiveCataloguing",
                                          readerGroup = "Descriptive Cataloguing Administrators"),
        'Descriptive Cataloguing Reviewers' : dict(indexName="getAssignedDescriptiveCataloguingReviewer",
                                                   state="descriptiveCataloguingReview",
                                                   readerGroup = "Descriptive Cataloguing Administrators"),
        'Subject Cataloguers' : dict( indexName="getAssignedSubjectCataloguer",
                                      state="subjectCataloguing",
                                      readerGroup = "Subject Cataloguing Administrators"),
        'Subject Cataloguing Reviewers': dict( indexName="getAssignedSubjectCataloguingReviewer",
                                               state="subjectCataloguingReview",
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
            
            (indexName, state, readerGroup) = map(item.get, ['indexName','state','readerGroup'])
            
            for member in api.user.get_users(groupname=groupname):
                username = member.id
                producentsFolder.recreateUserCollectionIfEmpty(username, indexName, state, readerGroup)
                email = member.getProperty('email')
                view_name = 'worklist-waiting-for-user'
                subject = title + " pro: " + username
                request = self.context.REQUEST
                request['userid']=username
                view = api.content.get_view(name=view_name,
                                            context = producentsFolder,
                                            request = request)

                body = view()
                if view.numOfRows:
                    recipients = frozenset(self.result.additionalEmails + [email,])
                    for recipient in recipients:
                        print u"... odesilam email pro: " + recipient
                        api.portal.send_email(recipient=recipient, subject=subject, body=body)
                else:
                    print u"... nic neodesilame pro: " + username



class CheckUpdatesTaskHandler(namedtuple('CheckUpdatesTaskHandler', ['context','result'])):
    def handle(self):
        print "<- Plone AMQP Task: ", str(self.result)
        with api.env.adopt_user(username="system"):
            obj = api.content.get(UID = self.result.uid)
            obj.checkUpdates()



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

