# -*- coding: utf-8 -*-
from five import grok
from z3c.form import group, field, button
from zope.interface import implements
from zope.component import adapts
from plone.directives import dexterity, form
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from edeposit.content.originalfile import IOriginalFile
from edeposit.app.fields import ISBNLine

class IChangeISBNForm(form.Schema):
    isbn = ISBNLine( title=u"ISBN", required = True)
    
class ChangeISBNView(form.SchemaForm):
    grok.context(IOriginalFile)
    grok.require('cmf.ModifyPortalContent')
    grok.name('change-isbn')

    schema = IChangeISBNForm
    ignoreContext = False
    enable_form_tabbing = False
    autoGroups = False
    template = ViewPageTemplateFile('titlelessform.pt')
    prefix = 'changeform'

    @button.buttonAndHandler(u"Odeslat", name="save")
    def handleAdd(self, action):
        # validaci na spravnost ISBN si provadi field ISBNLine sam
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return
        self.context.isbn = data['isbn']
        self.request.response.redirect(self.context.absolute_url())


class OriginalFileChangeISBN(object):
    implements(IChangeISBNForm)
    adapts(IOriginalFile)

    def __init__(self, context):
        self.context = context
    
    @property
    def isbn(self):
        return self.context.isbn

