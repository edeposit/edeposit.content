# -*- coding: utf-8 -*-
from five import grok
from z3c.form import group, field, button
from zope.interface import implements
from zope.component import adapts
from plone.directives import dexterity, form
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from edeposit.content.eperiodical import IePeriodical
from edeposit.app.fields import PeriodicityChoice
from edeposit.content.eperiodical import periodicityChoicesSource

class IChangePeriodicityForm(form.Schema):
    cetnost_vydani = PeriodicityChoice( title=u"Četnost (periodicita) vydání", 
                                        required = True,
                                        source = periodicityChoicesSource,
                                        )
    
class ChangeISBNView(form.SchemaForm):
    grok.context(IePeriodical)
    grok.require('zope2.View')
    grok.name('change-periodicity')

    schema = IChangePeriodicityForm
    ignoreContext = False
    enable_form_tabbing = False
    autoGroups = False
    template = ViewPageTemplateFile('titlelessform.pt')
    prefix = 'changeform'

    @button.buttonAndHandler(u"Odeslat", name="save")
    def handleAdd(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return
        self.context.cetnost_vydani = data['cetnost_vydani']
        self.request.response.redirect(self.context.absolute_url())

class EPeriodicalChangePeriodicity(object):
    implements(IChangePeriodicityForm)
    adapts(IePeriodical)

    def __init__(self, context):
        self.context = context
    
    @property
    def cetnost_vydani(self):
        return self.context.cetnost_vydani

