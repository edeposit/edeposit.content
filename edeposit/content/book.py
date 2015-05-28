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
from edeposit.content.bookfolder import IBookFolder
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage
from functools import partial
from plone.dexterity.utils import createContentInContainer, addContentToContainer, createContent
from edeposit.content.printingfile import IPrintingFile
from edeposit.content.browser.contribute import (
    LoadFromSimilarForBookForm,
    LoadFromSimilarForBookView,
    LoadFromSimilarForBookSubView,
)

from edeposit.content import MessageFactory as _

from edeposit.content.utils import loadFromAlephByISBN
from edeposit.content.utils import is_valid_isbn
from edeposit.content.utils import getISBNCount

# import edeposit.content.mock
# getAlephRecord = edeposit.content.mock.getAlephRecord
# loadFromAlephByISBN = partial(edeposit.content.mock.loadFromAlephByISBN, num_of_records=1)
# is_valid_isbn = partial(edeposit.content.mock.is_valid_isbn,result=True)
# getISBNCount = partial(edeposit.content.mock.getISBNCount,result=0)

from .author import IAuthor
from plone import api

# Interface class; used to define content-type schema.

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

    rok_vydani = schema.Int (
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

    file = NamedBlobFile(
        title=u"Připojit tiskovou předlohu",
        required = False,
        )

    can_be_modified = schema.Bool(
        title = u'Může být upravena pro vnitřní potřeby knihovny?',
        required = False,
        default = False,
        missing_value = False,
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
                pass
            else:
                try:
                    appearedAtAleph = getISBNCount(isbn)
                    if appearedAtAleph:
                        # duplicity error
                        errors += (getErrorView(isbnWidget, zope.interface.Invalid(u'ISBN je již použito. Použijte jiné, nebo nahlašte opravu.')),)
                except:
                    print "some exception with edeposit.amqp.aleph.aleph.getISBNCount"
                    pass
            pass
        return (data,errors)

    def addBook(self, data):
        theSameKeys = frozenset(IBook.names()).intersection(data.keys())
        dataForFactory = dict(zip(theSameKeys, map(data.get, theSameKeys)) + [('title', data.get('nazev')),] )
        book = createContentInContainer(self.context, 'edeposit.content.book', **dataForFactory)
        return book
    
    def addPrintingFile(self, book, data):
        theSameKeys = frozenset(IPrintingFile.names()).intersection(data.keys())
        dataForFactory = dict(zip(theSameKeys, map(data.get, theSameKeys)))
        printingFile = createContentInContainer(book, 'edeposit.content.printingfile', **dataForFactory)
        return printingFile

    @button.buttonAndHandler(u"Odeslat", name='save')
    def handleAdd(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return

        self.checkISBN(data)

        newBook = self.addBook(data)
        newPrintingFile = self.addPrintingFile(newBook, data)
        
        authors = [data[key] for key in ['author1','author2','author3'] if data[key]]
        for author in authors:
            createContentInContainer(newBook, 'edeposit.content.author', fullname=author, title=author)

        messages = IStatusMessage(self.request)
        messages.addStatusMessage(u"Kniha / tisková předloha byla ohlášena.", type="info")

        self.request.response.redirect(newBook.absolute_url())
