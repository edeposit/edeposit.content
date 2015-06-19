# -*- coding: utf-8 -*-
from five import grok

from z3c.form import group, field, button
from zope import schema
from zope.interface import invariant, Invalid
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm

from plone.dexterity.content import Container
from plone.directives import dexterity, form
from plone.app.textfield import RichText
from plone.namedfile.field import NamedImage, NamedFile
from plone.namedfile.field import NamedBlobImage, NamedBlobFile
from plone.namedfile.interfaces import IImageScaleTraversable

from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage
from functools import partial
from plone.dexterity.utils import createContentInContainer, addContentToContainer, createContent
from z3c.form.interfaces import WidgetActionExecutionError, ActionExecutionError, IObjectFactory, IValidator, IErrorViewSnippet, INPUT_MODE

from edeposit.content.printingfile import IPrintingFile
from edeposit.content.browser.contribute import (
    LoadFromSimilarForBookForm,
    LoadFromSimilarForBookView,
    LoadFromSimilarForBookSubView,
)

from z3c.relationfield import RelationValue
from z3c.relationfield.schema import RelationChoice, Relation

from edeposit.content import MessageFactory as _

from plone.formwidget.contenttree import ObjPathSourceBinder, PathSourceBinder
from edeposit.content.behaviors import IFormat, ICalibreFormat

from edeposit.content.bookfolder import IBookFolder
from edeposit.content.utils import loadFromAlephByISBN
from edeposit.content.utils import is_valid_isbn
from edeposit.content.utils import getISBNCount
from edeposit.content.aleph_record import IAlephRecordsContainer
# import edeposit.content.mock
# getAlephRecord = edeposit.content.mock.getAlephRecord
# loadFromAlephByISBN = partial(edeposit.content.mock.loadFromAlephByISBN, num_of_records=1)
# is_valid_isbn = partial(edeposit.content.mock.is_valid_isbn,result=True)
# getISBNCount = partial(edeposit.content.mock.getISBNCount,result=0)
from urlparse import urlparse
from .author import IAuthor
from plone import api
from edeposit.content.book_states import StatesGenerator
from operator import methodcaller, attrgetter, __or__
from zope.component import getUtility
from zope.app.intid.interfaces import IIntIds

# Interface class; used to define content-type schema.

from edeposit.content.originalfile import OriginalFile, VoucherFile
from edeposit.content.next_step import INextStep

vazbaChoices = [
    ['brozovano',u"brožováno"],
    ['vazano', u"vázáno"],
    ['mapa',u"mapa"],
]

@grok.provider(IContextSourceBinder)
def vazbaSource(context):
    def getTerm(item):
        title = item[1].encode('utf-8')
        return SimpleVocabulary.createTerm(item[0], item[0], title)

    return SimpleVocabulary(map(getTerm, vazbaChoices))

@grok.provider(IContextSourceBinder)
def availableAlephRecords(context):
    path = '/'.join(context.getPhysicalPath())
    query = { "portal_type" : ("edeposit.content.alephrecord",),
              "path": {'query' :path } 
             }
    return ObjPathSourceBinder(navigation_tree_query = query).__call__(context)

class IBook(form.Schema, IImageScaleTraversable):
    """
    E-Deposit - Book
    """
    
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

    isbn = schema.ASCIILine(
        title=_("ISBN"),
        description=_(u"Value of ISBN"),
        required = False,
    )

    generated_isbn = schema.Bool(
        title = u"Přidělit ISBN agenturou",
        required = False,
        default = False,
        missing_value = False,
    )

    isbn_souboru_publikaci = schema.ASCIILine (
        title = u"ISBN souboru publikací",
        description = u"pro vícesvazkové publikace, ISBN celého souboru publikací.",
        required = False,
    )

    vazba = schema.Choice(
        title = u"Vazba",
        required = True,
        source = vazbaSource
    )

    poradi_vydani = schema.TextLine(
        title = u'Pořadí vydání, verze',
        description = u"Podle titulní stránky publikace",
        required = True,
    )

    misto_vydani = schema.TextLine(
        title = u'Místo vydání',
        description = u"Podle titulní stránky publikace",
        required = True,
    )

    rok_vydani = schema.TextLine (
        title = u"Rok vydání",
        description = u"Podle titulní stránky publikace",
        required = True,
    )

    form.mode(nakladatel_vydavatel='display')
    nakladatel_vydavatel = schema.TextLine (
        title = u"Nakladatel",
        description = u"Vyplněno automaticky podle profilu uživatele.",
        required = True,
        )

    vydano_v_koedici_s = schema.TextLine(
        title = u'Vydáno v koedici s',
        required = False,
        )

    cena = schema.Decimal (
        title = u'Cena v Kč',
        required = False,
    )

    form.fieldset('riv',
                  label=_(u'RIV'),
                  fields = [
                      'offer_to_riv',
                      'category_for_riv',
                  ])

    offer_to_riv = schema.Bool(
        title = u'Zpřístupnit pro RIV',
        required = False,
        default = False,
        missing_value = False,
        )

    category_for_riv = schema.Choice (
        title = u"Kategorie pro RIV",
        description = u"Vyberte ze seznamu kategorií pro RIV.",
        required = False,
        readonly = False,
        default = None,
        missing_value = None,
        vocabulary="edeposit.content.categoriesForRIV",
    )

    zpracovatel_zaznamu = schema.TextLine(
        title = u'Zpracovatel záznamu',
        required = True,
    )

    anotace = schema.Text(
        title = u"Anotace",
        description = u"Anotace se objeví v Alephu",
        required = False,
        )

    form.primary('file')
    file = NamedBlobFile(
        title=u"Tisková předloha",
        required = False,
    )
    
    voucher = VoucherFile (
        title = u"Ohlašovací lístek",
        required = False,
    )

    can_be_modified = schema.Bool(
        title = u'Může být tisková předloha upravena pro vnitřní potřeby knihovny?',
        required = False,
        default = False,
        missing_value = False,
    )

    form.fieldset('internal',
                  label=_(u'Interní'),
                  fields = [
                      'thumbnail',
                      'related_aleph_record',
                      'summary_aleph_record',
                      'shouldBeFullyCatalogized',
                      'isWellFormedForLTP',
                      'isClosed',
                  ])

    thumbnail = NamedBlobFile(
        title=_(u"PDF kopie"),
        required = False,
    )
    

    related_aleph_record = RelationChoice( title=u"Odpovídající záznam v Alephu",
                                           required = False,
                                           source = availableAlephRecords)

    summary_aleph_record = RelationChoice( title=u"Souborný záznam v Alephu",
                                           required = False,
                                           source = availableAlephRecords )
    shouldBeFullyCatalogized = schema.Bool (
        title = u"Tento dokument musí projít celou katalogizační linkou",
        default = False,
        required = False
    )
    isWellFormedForLTP = schema.Bool (
        title = u"Originál je ve formátu vhodném pro LTP",
        default = False,
        required = False
    )
    isClosed= schema.Bool (
        title = _(u'is closed out by Catalogizators'),
        description = u"",
        required = False,
        default = False,
    )



@form.default_value(field=IBook['zpracovatel_zaznamu'])
def zpracovatelDefaultValue(data):
    member = api.user.get_current()
    return member.fullname or member.id


@form.default_value(field=IBook['nakladatel_vydavatel'])
def nakladatelDefaultValue(data):
    context = (getattr(data,'view',None) and getattr(data.view,'context',None)) or getattr(data,'context',None)
    if context:
        producent = context.aq_parent
        return producent.title or producent.id
    return ""


class Book(Container):
    grok.implements(IBook)

    def hasVoucher(self):
        return bool(self.voucher)

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

    def needsThumbnailGeneration(self):
        return False

    def updateOrAddAlephRecord(self, dataForFactory):
        sysNumber = dataForFactory.get('aleph_sys_number',None)
        alephRecords = self.listFolderContents(contentFilter={'portal_type':'edeposit.content.alephrecord'})

        def hasTheSameSysNumber(arecord):
            return arecord.aleph_sys_number == sysNumber

        arecordWithTheSameSysNumber = filter(hasTheSameSysNumber, alephRecords)

        if arecordWithTheSameSysNumber:
            print "a record with the same sysnumber"
            # update this record
            alephRecord = arecordWithTheSameSysNumber[0]
            changedAttrs = alephRecord.findAndLoadChanges(dataForFactory)
            # if changedAttrs and changedAttrs != ['xml']:
            #     IPloneTaskSender(CheckUpdates(uid=self.UID())).send()
        else:
            createContentInContainer(self, 'edeposit.content.alephrecord', **dataForFactory)
            #self.reindexObject()
            #IPloneTaskSender(CheckUpdates(uid=self.UID())).send()

    def makeInternalURL(self):
        internal_url = "/".join([api.portal.get().absolute_url(), '@@redirect-to-uuid', self.UID()])
        return internal_url

    @property
    def sysNumber(self):
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

    def submitValidationsForLTP(self):
        format = IFormat(self).format or ""
        if format == 'PDF':
            IPloneTaskSender(DoActionFor(transition='submitPDFBoxValidation', uid=self.UID())).send()

        if format == 'EPub':
            IPloneTaskSender(DoActionFor(transition='submitEPubCheckValidation', uid=self.UID())).send()

    def properAlephRecordsChoosen(self):
        return bool(self.related_aleph_record)

    def refersToThisOriginalFile(self, aleph_record):
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

    def hasSomeAlephRecords(self):
        alephRecords = self.listFolderContents(contentFilter={'portal_type':'edeposit.content.alephrecord'})
        return len(alephRecords)

    def updateAlephRelatedData(self):
        # try to choose related_aleph_record
        print "... update Aleph Related Data"
        alephRecords = self.listFolderContents(contentFilter={'portal_type':'edeposit.content.alephrecord'})

        self.related_aleph_record = None
        self.summary_aleph_record = None
        
        related_aleph_record = None

        intids = getUtility(IIntIds)
        recordsThatRefersToThis = filter(self.refersToThisOriginalFile, alephRecords)
        if len(recordsThatRefersToThis) == 1:
            related_aleph_record = recordsThatRefersToThis[0]
            self.related_aleph_record = RelationValue(intids.getId(related_aleph_record))
        else:
            closedAlephRecords = filter(attrgetter('isClosed'), recordsThatRefersToThis)
            if len(closedAlephRecords) == 1:
                related_aleph_record = closedAlephRecords[0]
                self.related_aleph_record = RelationValue(intids.getId(related_aleph_record))

        if related_aleph_record and related_aleph_record.isClosed:
            reference = related_aleph_record.summary_record_aleph_sys_number
            def refersTo(rr):
                return rr.id_number == reference or re.sub(r'^0+','',rr.aleph_sys_number) in reference

            properSummaryRecords = filter(refersTo, alephRecords)
            if len(properSummaryRecords) == 1:
                summary_aleph_record = properSummaryRecords[0]
                self.summary_aleph_record = RelationValue(intids.getId(summary_aleph_record))
            pass

        pass

    def checkUpdates(self):
        """ it tries to decide whether some changes appeared in aleph records. 
        The function loads the changes from a proper aleph record into its own attributes.
        The function will plan producent notification.
        """

        # self.removeInappropriateAlephRecords()
        self.updateAlephRelatedData()

        # changes = IChanges(self).getChanges()
        # for change in changes:
        #     IApplicableChange(change).apply()
            
        # if changes:
        #     getAdapter(self, IEmailSender, name="book-has-been-changed").send()
        #     #self.informProducentAboutChanges = True

        for ii in range(20):
            wasNextState=INextStep(self).doActionFor()
            if not wasNextState:
                break

        last_check_name = StatesGenerator(self)()
        state = ""
        if state != api.content.get_state(self):
            # some movement
            pass
        pass
                

from edeposit.content.originalfile import (
    getAssignedPersonFactory,
)

Book.getAssignedDescriptiveCataloguer =  getAssignedPersonFactory('E-Deposit: Descriptive Cataloguer')
Book.getAssignedDescriptiveCataloguingReviewer = getAssignedPersonFactory('E-Deposit: Descriptive Cataloguing Reviewer')
Book.getAssignedSubjectCataloguer =  getAssignedPersonFactory('E-Deposit: Subject Cataloguer')
Book.getAssignedSubjectCataloguingReviewer = getAssignedPersonFactory('E-Deposit: Subject Cataloguing Reviewer')

class SampleView(grok.View):
    """ sample view class """
    grok.context(IBook)
    grok.require('zope2.View')


class IBookAddAtOnce(form.Schema):
    author1 = schema.TextLine(
        title=u"Autor (příjmení, rodné jméno)",
        description = u"Příjmení a jméno oddělené čárkou",
        required = False,
        )
    
    author2 = schema.TextLine(
        title=u"Autor 2",
        description = u"Příjmení a jméno oddělené čárkou",
        required = False,
        )
    
    author3 = schema.TextLine(
        title=u"Autor 3",
        description = u"Příjmení a jméno oddělené čárkou",
        required = False,
        )

    # form.mode(book_uid='hidden')
    # book_uid = schema.ASCIILine(
    #     required = False,
    # )

class AddAtOnceForm(form.Form):
    grok.name('add-at-once')
    grok.require('edeposit.AddEPublication')
    grok.context(IBookFolder)

    fields = field.Fields(IBook) + field.Fields(IBookAddAtOnce)

    ignoreContext = True
    label = u"Ohlásit knihu / tiskovou předlohu"
    enable_form_tabbing = False
    autoGroups = False
    template = ViewPageTemplateFile('book_templates/addatonce.pt')

    def checkISBN(self, data):
        if (not data['isbn'] and not data['generated_isbn']) or \
           (data['isbn'] and data['generated_isbn']):
            raise ActionExecutionError(Invalid(u"Buď zadejte ISBN, nebo vyberte \"Přiřadit ISBN agenturou\""))

    def loadValuesFromAlephRecord(self, record):
        epublication = record.epublication
        if epublication:
            widgets = self.widgets
            theSameNames = (frozenset(widgets.keys()) & frozenset(epublication._fields)) - frozenset(['format'])
            for name in theSameNames:
                widgets[name].value = getattr(epublication,name)

            # authors
            for author,index in zip(epublication.autori, range(1,4)):
                name = "author%d" % (index,)
                getter = partial(getattr, author)
                value = " ".join(filter(lambda value: value, map(getter,['title','firstName','lastName'])))
                widgets[name].value = value
                
            get = partial(getattr,epublication)
            widgets['cast'].value = get('castDil')
            widgets['nazev_casti'].value = get('nazevCasti')
            widgets['isbn_souboru_publikaci'].value = get('ISBNSouboruPublikaci') and get('ISBNSouboruPublikaci')[0] or None
            widgets['isbn'].value = get('ISBN') and get('ISBN')[0] or None
            widgets['poradi_vydani'].value = get('poradiVydani')
            widgets['rok_vydani'].value = get('datumVydani')
            widgets['poradi_vydani'].value = get('poradiVydani')
            widgets['misto_vydani'].value = get('mistoVydani')
            widgets['anotace'].value = get('anotace')
        pass

    def update(self):
        form = LoadFromSimilarForBookForm(self.context, self.request)
        view = LoadFromSimilarForBookSubView(self.context, self.request)
        view = view.__of__(self.context)
        view.form_instance = form
        self.loadsimilarform = view
        form.parent_form = self
        hiddenFields = ['related_aleph_record',
                        'summary_aleph_record',
                        'isClosed',
                        'thumbnail',
                        'shouldBeFullyCatalogized',
                        'isWellFormedForLTP',
                        'voucher']
        
        for field in hiddenFields:
            if field in self.fields:
                del self.fields[field]

        super(AddAtOnceForm,self).update()
        sdm = self.context.session_data_manager
        session = sdm.getSessionData(create=True)
        proper_record = session.get('proper_record',None)
        # proper_record = getAlephRecord()
        if proper_record:
            messages = IStatusMessage(self.request)
            messages.addStatusMessage(u"Formulář je předvyplněn vybraným záznamem z Alephu.", type="info")
            self.loadValuesFromAlephRecord(proper_record)
            session.set('proper_record',None)

    def extractData(self):
        def getErrorView(widget,error):
            view = zope.component.getMultiAdapter( (error, 
                                                    self.request, 
                                                    widget, 
                                                    widget.field, 
                                                    widget.form, 
                                                    self.context), 
                                                   IErrorViewSnippet)
            view.update()
            widget.error = view
            return view

        data, errors = super(AddAtOnceForm,self).extractData()
        isbn = data.get('isbn',None)
        if isbn:
            isbnWidget = self.widgets.get('isbn',None)
            valid = is_valid_isbn(isbn)
            if not valid:
                # validity error
                errors += (getErrorView(isbnWidget, zope.interface.Invalid(u'Chyba v ISBN')),)

        return (data,errors)

    def addBook(self, data):
        theSameKeys = frozenset(IBook.names()).intersection(data.keys())
        dataForFactory = dict(zip(theSameKeys, map(data.get, theSameKeys)) + [('title', data.get('nazev')),] )
        book = createContentInContainer(self.context, 'edeposit.content.book', **dataForFactory)
        return book
    
    @button.buttonAndHandler(u"Odeslat", name='save')
    def handleAdd(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return

        self.checkISBN(data)

        newBook = self.addBook(data)
        
        authors = filter(bool, map(data.get,['author1','author2','author3']))
        for author in authors:
            createContentInContainer(newBook, 'edeposit.content.author', fullname=author, title=author)

        wft = api.portal.get_tool('portal_workflow')
        if newBook.isbn or newBook.file:
            transition = (newBook.isbn and 'submitDeclarationToISBNValidation') or \
                         (newBook.file and 'submitDeclarationToAntivirus')
            if transition:
                wft.doActionFor(newBook, transition)

        messages = IStatusMessage(self.request)
        messages.addStatusMessage(u"Kniha / tisková předloha byla ohlášena.", type="info")
        self.request.response.redirect(newBook.absolute_url())
