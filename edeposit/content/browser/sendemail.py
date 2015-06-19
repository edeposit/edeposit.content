# -*- coding: utf-8 -*-
from plone.memoize.view import memoize
from zope.component import getMultiAdapter
from zope.deprecation.deprecation import deprecate
from zope.i18n import translate
from zope.interface import implements, alsoProvides, Interface
from zope.viewlet.interfaces import IViewlet
from zope.interface import Invalid
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.utils import safe_unicode
from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.CMFPlone import PloneMessageFactory as _
from plone.directives import form
from plone.app.layout.globals.interfaces import IViewView
from plone.app.layout.viewlets.interfaces import (
    IContentViews, 
    IBelowContent, 
    IAboveContentBody, 
    IBelowContentBody
)
from plone.app.layout.viewlets import ViewletBase
from z3c.form.interfaces import ActionExecutionError

from plone import api

from plone.z3cform.layout import FormWrapper
from edeposit.content.originalfile import IOriginalFile
from edeposit.content.book import IBook
import os.path
from plone.dexterity.interfaces import IDexterityContent

from zope.publisher.interfaces import NotFound
import json
from five import grok

from zope import schema
from z3c.form import group, button

from operator import itemgetter
from Products.statusmessages.interfaces import IStatusMessage

class ISendEmail(form.Schema):
    sender = schema.TextLine(
        title = u"From",
        required = True,
    )
    to = schema.TextLine(
        title = u"To",
        required = True,
    )
    subject = schema.TextLine (
        title = u"Subject",
        required = True,
    )
    text = schema.Text(
        title = u"Text",
        required = True
    )

class SendEmailForm(form.SchemaForm):
    grok.context(IDexterityContent)
    grok.name('send-email')
    grok.require('zope2.View')

    label=u"Email editorovi"
    schema = ISendEmail
    ignoreContext = True
    prefix = "send-email."

    def updateWidgets(self):
        super(SendEmailForm,self).updateWidgets()
        self.widgets['text'].value = self.context.absolute_url()

        owners = map(itemgetter(0), filter(lambda item: 'Owner' in item[1], self.context.get_local_roles()))
        member = owners and api.user.get(username=owners[0])
        self.widgets['to'].value = member and member.getProperty('email') or ""

        self.widgets['sender'].value = api.user.get_current().getProperty('email')

        self.widgets['text'].cols = 80
        self.widgets['text'].rows = 20
        
    @button.buttonAndHandler(u"Odeslat", name='send')
    def handleSend(self, action):
        data, errors = self.extractData()
        if errors:
            return
            
        api.portal.send_email(recipient=data['to'], sender=data['sender'],
                              subject=data['subject'], body=data['text'])
        IStatusMessage(self.request).addStatusMessage(u"Email jsme poslali.",type="info")
        url = os.path.join(self.context.absolute_url(),"email-sent")
        self.response.redirect(url)


# LoadFromSimilarView = wrap_form(LoadFromSimilarForm)

# class LoadFromSimilarSubView(FormWrapper):
#      """ Form view which renders z3c.forms embedded in a portlet.
#      Subclass FormWrapper so that we can use custom frame template. """
#      index = ViewPageTemplateFile("formwrapper.pt")
