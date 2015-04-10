from plone.formwidget.namedfile.interfaces import INamedFileWidget
from z3c.form.interfaces import ITextWidget

class IVoucherFileWidget(INamedFileWidget):
    pass

class IOriginalFileSourceWidget(INamedFileWidget):
    pass

class IProducentTextWidget(ITextWidget):
    pass
