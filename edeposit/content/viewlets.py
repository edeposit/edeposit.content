from cgi import escape
from datetime import date
from urllib import unquote

from plone.memoize.view import memoize
from zope.component import getMultiAdapter
from zope.deprecation.deprecation import deprecate
from zope.i18n import translate
from zope.interface import implements, alsoProvides, Interface
from zope.viewlet.interfaces import IViewlet

from AccessControl import getSecurityManager
from Acquisition import aq_base, aq_inner, aq_parent

from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.utils import safe_unicode
from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.CMFPlone import PloneMessageFactory as _
from plone.directives import form
from five import grok
from plone.app.layout.globals.interfaces import IViewView
from plone.app.layout.viewlets.interfaces import IContentViews, IBelowContent, IAboveContentBody, IBelowContentBody
from plone.app.layout.viewlets import ViewletBase
from Products.CMFCore.permissions import ModifyPortalContent, ReviewPortalContent

from plone import api
from originalfile import IOriginalFile
from epublication import IePublication, IMainMetadata, MainMetadataForm
from epublicationfolder import IePublicationFolder
from edeposit.content.book import IBook

from plone.app.contentmenu import menu
from plone.app.contentmenu.interfaces import IWorkflowSubMenuItem
from plone.z3cform.layout import FormWrapper
from plone.dexterity.interfaces import IDexterityContent

import plone.app.content
import plone.app.layout

class CustomContentActions(plone.app.layout.viewlets.common.ContentActionsViewlet):
    pass

class ContentState(grok.Viewlet):
    grok.name('edeposit.contentstate')
    grok.require('zope2.View')
    grok.viewletmanager(IContentViews)
    grok.view(IViewView)
    grok.context(IOriginalFile)

    def update(self):
        super(ContentState,self).update()
        context = aq_inner(self.context)
        plone_utils = api.portal.get_tool('plone_utils')
        wft = api.portal.get_tool('portal_workflow')
        state = api.content.get_state(obj=context)
        stateTitle = wft.getTitleForStateOnType(state,context.portal_type)

        self.wf_state = dict( state = state, 
                              title = stateTitle,
                              stateClass = 'contentstate-'+plone_utils.normalizeString(state),
                              href = context.absolute_url() + "/content_status_history",
                              )
        wf_tool = getToolByName(self.context, 'portal_workflow')
        infos = filter(lambda info: info.get('available',None) and info.get('category',None) == 'workflow', wf_tool.listActionInfos(object=self.context))
        self.transitions = infos
        return


class ContentStateForEPublication(ContentState):
    grok.name('edeposit.contentstateforepublication')
    grok.require('zope2.View')
    grok.viewletmanager(IContentViews)
    grok.context(IePublication)
    grok.template('viewlets_templates/contentstate.pt')

class ContentStateForBook(ContentState):
    grok.name('edeposit.contentstateforbook')
    grok.require('zope2.View')
    grok.viewletmanager(IContentViews)
    grok.context(IBook)
    grok.template('viewlets_templates/contentstate.pt')

class ContentHistory(grok.Viewlet):
    grok.name('edeposit.contenthistory')
    grok.require('zope2.View')
    grok.viewletmanager(IBelowContent)
    grok.context(IOriginalFile)

class ContentHistoryForBook(grok.Viewlet):
    grok.name('edeposit.contenthistoryforbook')
    grok.require('zope2.View')
    grok.viewletmanager(IBelowContent)
    grok.context(IBook)
    #grok.template('viewlets_templates/contenthistory.pt')

class MainMetadataFormWrapper(FormWrapper):
    index = ViewPageTemplateFile("viewlets_templates/formwrapper.pt")

class EBookMetadata(grok.Viewlet):
    grok.name('edeposit.ebookmetadata')
    grok.require('zope2.View')
    grok.viewletmanager(IAboveContentBody)
    grok.context(IOriginalFile)

    def update(self):
        ebook = aq_parent(aq_inner(self.context))
        view = MainMetadataFormWrapper(ebook, self.request)
        view.__of__(ebook)
        view.form_instance = MainMetadataForm(ebook, self.request)
        self.main_metadata_form = view
        self.ebook = ebook


class Contact(grok.Viewlet):
    grok.name('edeposit.contact')
    grok.require('zope2.View')
    grok.viewletmanager(IBelowContentBody)
    grok.context(IOriginalFile)

class WellFormedForLTP(grok.Viewlet):
    grok.name('edeposit.wellformedforltp')
    grok.require('zope2.View')
    grok.viewletmanager(IContentViews)
    grok.context(IOriginalFile)
    #grok.template('viewlets_template/wellformedforltp.pt')
    
    
class SendEmail(grok.Viewlet):
    grok.name('edeposit.sendemail')
    grok.require('zope2.View')
    grok.viewletmanager(IContentViews)
    grok.context(IDexterityContent)

class RedirectToUUIDLinkCopy(grok.Viewlet):
    grok.name('edeposit.redirecttouuidlinkcopy')
    grok.require('zope2.View')
    grok.viewletmanager(IContentViews)
    grok.context(IDexterityContent)

class SysNumberCopy(plone.app.layout.viewlets.common.ContentActionsViewlet):
    def available(self):
        result = bool(getattr(self.context, 'related_aleph_record',None))
        return result

    def render(self):
        if not self.available():
            return ""
        return super(SysNumberCopy,self).render()

class SummarySysNumberCopy(plone.app.layout.viewlets.common.ContentActionsViewlet):
    def available(self):
        result = bool(getattr(self.context, 'summary_aleph_record',None))
        return result

    def render(self):
        if not self.available():
            return ""
        return super(SummarySysNumberCopy,self).render()

class SendToAcquisitionButton(plone.app.layout.viewlets.common.ContentActionsViewlet):
    def available(self):
        return (api.content.get_state(self.context) in ('declarationWithError',
                                                        'fileProblem',
                                                        'onlyCzechISBNAcceptedError',
                                                        'zpracovatelIsRequiredError',
                                                        'DatumVydaniIsRequiredError',
                                                        'isbnAlreadyExistsError',
                                                        'wrongISBNError',
                                                        'unknownError',
                                                    ) \
                and getSecurityManager().checkPermission(ModifyPortalContent, self.context)\
                and self.context.file
        )

    def submitDeclarationURL(self):
        baseUrl = "/".join([self.context.absolute_url(),"content_status_comment"])
        transition = (self.context.isbn and (self.context.isbnAppearsAtRelatedAlephRecord and 'submitDeclarationSkipISBNValidation' or 'submitDeclarationToISBNValidation')) or ('submitDeclarationToAntivirus')
        #transition = self.context.isbn and 'submitDeclarationToISBNValidation'  or "submitDeclarationToAntivirus"
        return baseUrl + "?workflow_action=" + transition


    def render(self):
        if not self.available():
            return ""
        return super(SendToAcquisitionButton,self).render()


class BackToAcquisitionButton(plone.app.layout.viewlets.common.ContentActionsViewlet):
    def available(self):
        roles = api.user.get_roles(obj=self.context)
        """ backend roles: - roles for National Library members. """
        backendRoles = filter(lambda role: 'E-Deposit: Descriptive' in role, roles) \
            + filter(lambda role: 'E-Deposit: Subject' in role, roles) \
            + filter(lambda role: 'E-Deposit: Acquisition' in role, roles) \
            + filter(lambda role: 'E-Deposit: System' in role, roles) \
            + filter(lambda role: 'Site Administrator' in role, roles) \
            + filter(lambda role: 'Manager' in role, roles)
            

        return getSecurityManager().checkPermission(ReviewPortalContent, self.context) and backendRoles

    def submitDeclarationURL(self):
        baseUrl = "/".join([self.context.absolute_url(),"content_status_comment"])
        transition = "unknownError"
        return baseUrl + "?workflow_action=" + transition


    def render(self):
        if not self.available():
            return ""
        return super(BackToAcquisitionButton,self).render()
