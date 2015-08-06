# -*- coding: utf-8 -*-
from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zope.publisher.interfaces import NotFound
from plone.namedfile.utils import set_headers, stream_data
import json
from five import grok
from lxml import html
from plone import api
from .voucher import OriginalFileDisplayForm, OriginalFileFormView

class FileDownload(BrowserView):
    def __call__(self):
        if not self.context.file:
            raise NotFound(self, 'original.pdf', self.request)
        set_headers(self.context.file, self.request.response, filename=self.context.file.filename)
        return stream_data(self.context.file)

class LoadFileFromStorage(BrowserView):
    def __call__(self):
        with api.env.adopt_user(username="system"):
            wft = api.portal.get_tool('portal_workflow')
            wft.doActionFor(self.context,'loadFileFromStorage')
            
        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps(dict(done = True))

class HasFile(BrowserView):
    def __call__(self):
        file_ = self.context.file
        widgetHTML = ""
        if file_:
            view = OriginalFileFormView(self.context, self.request)
            view = view.__of__(self.context)
            view.form_instance = OriginalFileDisplayForm(self.context, self.request)
            root = html.fromstring(view())
            widget = root.get_element_by_id('formfield-form-widgets-file')
            widgetHTML = html.tostring(widget).replace('/has-file/','/view/')

        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps(dict(has_file = bool(file_),
                               file_widget_html = widgetHTML,
                           ))
        

