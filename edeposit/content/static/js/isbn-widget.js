(function($){
        $(document).ready(function(){
                $('.change-isbn').prepOverlay({
                        subtype:'ajax',
                        filter:common_content_filter,
                        formselector:'form#changeform',
                        noform: function(el){
                                return 'reload'; 
                        },
                });
        });
}(jQuery));
