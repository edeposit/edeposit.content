
class IChangeISBNForm(form.Schema):
    file = NamedBlobFile(
        title=u"Připojit soubor s ePublikací",
        required = False,
        )
    
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

