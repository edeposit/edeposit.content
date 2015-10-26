from zope.interface import implementer, implements, implementsOnly
from zope.component import adapter
from edeposit.content.eperiodicalpart import IEPeriodicalPartFileField
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from z3c.form.interfaces import IFieldWidget, IFormLayer, IDataManager, NOVALUE
from z3c.form.widget import FieldWidget
from plone.formwidget.namedfile.widget import NamedFileWidget
from interfaces import IEPeriodicalPartFileWidget
from plone.z3cform.layout import FormWrapper
from plone import api

class EPeriodicalPartFileWidget(NamedFileWidget):
    implements(IEPeriodicalPartFileWidget)

    @property
    def can_change(self):
        mtool = api.portal.get_tool('portal_membership')
        return mtool.checkPermission('Modify portal content', self.context)

    @property
    def is_public(self):
        return self.context.is_public

    @property
    def can_download(self):
        return self.context.is_public or self.can_change
        # TODO doplnit rozhodnuti, zda muze stahovat i na vlastnika
        # tem muze stahovat i kdyz nema opravneni upravovat.

    @property
    def storage_download_url(self):
        return getattr(self.context,'storage_download_url',None)

    @property
    def storage_filename(self):
        return getattr(self.context,'storage_download_url',None)

    @property
    def filename(self):
        return super(EPeriodicalPartFileWidget,self).filename or self.storage_filename

    @property
    def download_url(self):
        return super(EPeriodicalPartFileWidget,self).download_url or self.storage_download_url

@implementer(IFieldWidget)
@adapter(IEPeriodicalPartFileField, IFormLayer)
def OriginalFileSourceFieldWidget(field, request):
    return FieldWidget(field, PeriodicalPartFileWidget(request))
