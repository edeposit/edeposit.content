# -*- coding: utf-8 -*-

from plone import api
from zope.interface import Interface, Attribute, implements, classImplements
from zope.component import getUtility, getAdapter, getMultiAdapter
from Acquisition import aq_parent, aq_inner
from plone.namedfile.file import NamedBlobFile
from base64 import b64encode, b64decode
from plone.dexterity.utils import createContentInContainer, addContentToContainer, createContent
import transaction
from functools import wraps
from collections import namedtuple
from functools import wraps

class INextStep(Interface):
    """
    There is one step you can doActionFor automaticaly.
    """
    
    def doActionFor(self,*args,**kwargs):
        return False


def withRelatedAlephRecord(f):
    @wraps(f)
    def wrapper(self, related_aleph_record=None, *args, **kwargs):
        related_aleph_record = self.context.related_aleph_record and \
                               getattr(self.context.related_aleph_record,'to_object',None)
        return f(self, related_aleph_record=related_aleph_record, *args, **kwargs)

    return wrapper

def withSummaryAlephRecord(f):
    @wraps(f)
    def wrapper(self, summary_aleph_record=None, *args, **kwargs):
        summary_aleph_record = self.context.summary_aleph_record and \
                               getattr(self.context.summary_aleph_record,'to_object',None)
        return f(self, summary_aleph_record=summary_aleph_record, *args, **kwargs)

    return wrapper

class OriginalFileNextStep(namedtuple("OriginalFileNextStep",['context',])):
    def doActionFor(self,*args,**kwargs):
        self.wft = api.portal.get_tool('portal_workflow')
        review_state = api.content.get_state(self.context)
        fname="nextstep_for_%s" % (str(review_state),)
        print "... %s" % (fname,)
        fun = getattr(self,fname,None)
        if fun is None:
            print "no action for: %s" % (fname, )

        
        wasNextStep = fun and fun(self,*args,**kwargs)
        return wasNextStep
    
    @withRelatedAlephRecord
    def nextstep_for_acquisition(self, related_aleph_record=None, *args, **kwargs):
        lastExportToAleph = self.context.lastProcessingStart
        if related_aleph_record and related_aleph_record.fieldIsYoungerThan('acquisitionFields',lastExportToAleph):
            self.wft.doActionFor(self.context,'submitAcquisition')
            return True
        return False

    @withRelatedAlephRecord
    def nextstep_for_ISBNGeneration(self, related_aleph_record=None,  *args, **kwargs):
        lastExportToAleph = self.context.lastProcessingStart
        if related_aleph_record and related_aleph_record.fieldIsYoungerThan('ISBNAgencyFields',lastExportToAleph):
            self.wft.doActionFor(self.context,'submitISBNGeneration')
            return True
        return False

    def nextstep_for_waitingForAleph(self, *args, **kwargs):
        alephRecords = self.context.listFolderContents(contentFilter={'portal_type':'edeposit.content.alephrecord'})
        alephRecordsThatRefersToThis = filter(lambda rr: self.context.refersToThisOriginalFile(rr), alephRecords)
        if not alephRecordsThatRefersToThis:
            comment = u"v Alephu není žádný záznam.  ISBN: %s" % (self.context.isbn, )
            self.wft.doActionFor(self.context,'noAlephRecordLoaded')
            return False

        comment = u"výsledek dotazu do Alephu ISBN(%s): zaznamu: %s" % (self.context.isbn, 
                                                                        str(len(alephRecordsThatRefersToThis)))
        
        self.wft.doActionFor(self.context, 'alephRecordsLoaded')
        return True

    def nextstep_for_chooseProperAlephRecord(self, *args, **kwargs):
        if not self.context.properAlephRecordsChoosen():
            return False

        self.wft.doActionFor(self.context,'properAlephRecordChoosen')
        return True

    def nextstep_for_descriptiveCataloguingPreparing(self, *args, **kwargs):
        if self.context.getAssignedDescriptiveCataloguer():
            self.wft.doActionFor(self.context,'submitDescriptiveCataloguingPreparing')
            return True

        return False

    @withRelatedAlephRecord
    def nextstep_for_descriptiveCataloguing(self, related_aleph_record=None, *args, **kwargs):
        lastExportToAleph = self.context.lastProcessingStart
        if related_aleph_record and related_aleph_record.isClosed:
            if related_aleph_record.fieldIsYoungerThan('descriptiveCataloguingFields',lastExportToAleph):
                # rozezname, jestli existuje nejaky nezamceny zaznam
                # pokud ne a tento original je prvni pro dany souborny
                # zaznam, musi projit plnou katalogizaci
                if not self.context.fully_catalogized_closed_originalfile_exists():
                    if not self.context.some_not_closed_originalfile_exists():
                        self.context.shouldBeFullyCatalogized = True
                        self.context.reindexObject(idxs=['shouldBeFullyCatalogized',])

                self.wft.doActionFor(self.context,'submitClosedDescriptiveCataloguing')
                return True
            else:
                return False

        if related_aleph_record and related_aleph_record.fieldIsYoungerThan('descriptiveCataloguingFields',lastExportToAleph):
            self.wft.doActionFor(self.context,'submitDescriptiveCataloguing')
            return True

        return False

    def nextstep_for_descriptiveCataloguingReviewPreparing(self, *args, **kwargs):
        if self.context.getAssignedDescriptiveCataloguingReviewer():
            self.wft.doActionFor(self.context,'submitDescriptiveCataloguingReviewPreparing')
            return True

        return False

    def nextstep_for_closedDescriptiveCataloguingReviewPreparing(self, *args, **kwargs):
        if self.context.shouldBeFullyCatalogized:
            if self.context.getAssignedDescriptiveCataloguingReviewer():
                self.wft.doActionFor(self.context,'submitClosedDescriptiveCataloguingReviewPreparing')
                return True
        else:
            lastExportToAleph = self.context.lastProcessingStart
            summary_aleph_record =  self.context.summary_aleph_record \
                and getattr(self.context.summary_aleph_record,'to_object',None)

            if summary_aleph_record and summary_aleph_record.fieldIsYoungerThan('descriptiveCataloguingReviewFields',lastExportToAleph):
                self.wft.doActionFor(self.context,'submitClosedDescriptiveCataloguingReviewPreparing')
                return True

        return False

    def nextstep_for_subjectCataloguingReviewPreparing(self, *args, **kwargs):
        if self.context.getAssignedSubjectCataloguingReviewer():
            self.wft.doActionFor(self.context,'submitSubjectCataloguingReviewPreparing')
            return True

        return False

    def nextstep_for_closedSubjectCataloguingReviewPreparing(self, *args, **kwargs):
        if self.context.shouldBeFullyCatalogized:
            if self.context.getAssignedSubjectCataloguingReviewer():
                self.wft.doActionFor(self.context,'submitClosedSubjectCataloguingReviewPreparing')
                return True
        else:
            lastExportToAleph = self.context.lastProcessingStart
            summary_aleph_record =  self.context.summary_aleph_record \
                and getattr(self.context.summary_aleph_record,'to_object',None)
            if summary_aleph_record and summary_aleph_record.fieldIsYoungerThan('subjectCataloguingReviewFields',lastExportToAleph):
                self.wft.doActionFor(self.context,'submitClosedSubjectCataloguingReviewPreparing')
                return True

        return False
        

    def nextstep_for_subjectCataloguingPreparing(self, *args, **kwargs):
        if self.context.getAssignedSubjectCataloguer():
            self.wft.doActionFor(self.context,'submitSubjectCataloguingPreparing')
            return True

        return False

    def nextstep_for_closedSubjectCataloguingPreparing(self, *args, **kwargs):
        if self.context.shouldBeFullyCatalogized:
            if self.context.getAssignedSubjectCataloguer():
                self.wft.doActionFor(self.context,'submitClosedSubjectCataloguingPreparing')
                return True
        else:
            lastExportToAleph = self.context.lastProcessingStart
            summary_aleph_record = self.context.summary_aleph_record and getattr(self.context.summary_aleph_record,'to_object',None)
            if summary_aleph_record and summary_aleph_record.fieldIsYoungerThan('subjectCataloguingFields',lastExportToAleph):
                self.wft.doActionFor(self.context,'submitClosedSubjectCataloguingPreparing')
                return True

        return False

    @withRelatedAlephRecord
    def nextstep_for_descriptiveCataloguingReview(self,related_aleph_record=None, *args,**kwargs):
        lastExportToAleph = self.context.lastProcessingStart
        if related_aleph_record and related_aleph_record.fieldIsYoungerThan('descriptiveCataloguingReviewFields',lastExportToAleph):
            self.wft.doActionFor(self.context,'submitDescriptiveCataloguingReview')
            return True

        return False

    @withSummaryAlephRecord
    def nextstep_for_closedDescriptiveCataloguingReview(self,summary_aleph_record=None, *args,**kwargs):
        lastExportToAleph = self.context.lastProcessingStart
        if summary_aleph_record and summary_aleph_record.fieldIsYoungerThan('descriptiveCataloguingReviewFields',lastExportToAleph):
            self.wft.doActionFor(self.context,'submitClosedDescriptiveCataloguingReview')
            return True

        return False

    @withRelatedAlephRecord
    def nextstep_for_subjectCataloguing(self,related_aleph_record=None, *args, **kwargs):
        lastExportToAleph = self.context.lastProcessingStart
        if related_aleph_record and related_aleph_record.fieldIsYoungerThan('subjectCataloguingFields',lastExportToAleph):
            self.wft.doActionFor(self.context,'submitSubjectCataloguing')
            return True
        return False

    @withSummaryAlephRecord
    def nextstep_for_closedSubjectCataloguing(self, summary_aleph_record=None,*args,**kwargs):
        lastExportToAleph = self.context.lastProcessingStart
        if summary_aleph_record and summary_aleph_record.fieldIsYoungerThan('subjectCataloguingFields',lastExportToAleph):
            self.wft.doActionFor(self.context,'submitClosedSubjectCataloguing')
            return True

        return False

    @withRelatedAlephRecord
    def nextstep_for_subjectCataloguingReview(self, related_aleph_record=None,*args,**kwargs):
        lastExportToAleph = self.context.lastProcessingStart
        if related_aleph_record and related_aleph_record.fieldIsYoungerThan('subjectCataloguingReviewFields',lastExportToAleph):
            self.wft.doActionFor(self.context,'submitSubjectCataloguingReview')
            return True
        return False

    @withSummaryAlephRecord
    def nextstep_for_closedSubjectCataloguingReview(self,summary_aleph_record=None, *args,**kwargs):
        lastExportToAleph = self.context.lastProcessingStart
        if summary_aleph_record and summary_aleph_record.fieldIsYoungerThan('subjectCataloguingReviewFields',lastExportToAleph):
            self.wft.doActionFor(self.context,'submitClosedSubjectCataloguingReview')
            return True

        return False

    @withRelatedAlephRecord
    def nextstep_for_ISBNSubjectValidation(self, related_aleph_record=None, *args, **kwargs):
        lastExportToAleph = self.context.lastProcessingStart
        if related_aleph_record and related_aleph_record.fieldIsYoungerThan('ISBNAgencyFields',lastExportToAleph):
            self.wft.doActionFor(self.context,'submitISBNSubjectValidation')
            return True

        return False


class BookNextStep(OriginalFileNextStep):
    pass
