# -*- coding: utf-8 -*-

def StatesGenerator(obj):
    """ It simulates workflow steps. It starts from the beginning and continues till
    conditions given aleph records permit

    First state is: acquisition
    """

    related_aleph_record = obj.related_aleph_record and getattr(obj.related_aleph_record,'to_object',None)
    summary_aleph_record = obj.summary_aleph_record and getattr(obj.summary_aleph_record,'to_object',None)
    generated_isbn = obj.generated_isbn
    shouldBeFullyCatalogized = obj.shouldBeFullyCatalogized

    def check_closedDescriptiveCataloguingReview():
        return

    def check_descriptiveCataloguingReview():
        return

    def check_descriptiveCataloguingReviewPreparing():
        if self.context.getAssignedDescriptiveCataloguingReviewer():
            return check_descriptiveCataloguingReview
        return

    def check_closedDescriptiveCataloguingReviewPreparing():
        if self.context.getAssignedDescriptiveCataloguingReviewer():
            return check_closedDescriptiveCataloguingReview
        return

    def check_closedDescriptiveCataloguing():
        if related_aleph_record.hasDescriptiveCataloguingFields:
            return check_closedDescriptiveCataloguingReviewPreparing

    def check_descriptiveCataloguing():
        if related_aleph_record.hasDescriptiveCataloguingFields:
            return check_descriptiveCataloguingReviewPreparing

    def check_descriptiveCataloguingPreparing():
        if obj.getAssignedDescriptiveCataloguer():
            if related_aleph_record.isClosed:
                return check_closedDescriptiveCataloguing
            else:
                return check_DescriptiveCataloguing
            
    def check_isbnSubjectValidation():
        if related_aleph_record.hasISBNAgencyFields:
            return check_descriptiveCataloguingPreparing

    def check_isbnGeneration():
        if related_aleph_record.hasISBNAgencyFields:
            return check_chooseProperAlephRecord

    def check_acquisition():
        if related_aleph_record.hasAcquisitionFields:
            if generated_isbn:
                return check_isbnGeneration
            else:
                return check_isbnSubjectValidation

    def check_chooseProperAlephRecord():
        if related_aleph_record:
            return check_acquisition
    
    start_check = check_chooseProperAlephRecord

    def tryNext(last_checked, check):
        print "... last checked:", last_checked
        if not check:
            return None
        next_state = check()
        if not next_state:
            return last_checked

        return tryNext(check.__name__, next_state)

    def start():
        return tryNext("", start_check)

    return start
