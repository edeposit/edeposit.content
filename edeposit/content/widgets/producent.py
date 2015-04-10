from zope.interface import implementer, implements, implementsOnly
from zope.component import adapter
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

from z3c.form.interfaces import IFieldWidget, IFormLayer, IDataManager, NOVALUE
from z3c.form.widget import FieldWidget
from z3c.form.browser.text import TextWidget
from .interfaces import IProducentTextWidget
from edeposit.content.epublication import IProducentTextField

class ProducentTextWidget(TextWidget):
    implements(IProducentTextWidget)
    pass

@implementer(IFieldWidget)
@adapter(IProducentTextField, IFormLayer)
def ProducentTextFieldWidget(field, request):
    return FieldWidget(field, ProducentTextWidget(request))
