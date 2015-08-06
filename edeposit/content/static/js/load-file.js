(function($) {
        var checkLoadingState = function (base_href, numOfRetries) {
                if( numOfRetries <= 0 ) return;
                var handler = function(){
                        $.ajax(base_href + "/has-file").done(function(data){
                                if( data.has_file ){
                                        $('#formfield-form-widgets-file').html(
                                                data['file_widget_html']
                                        );
                                        $('.file-download')[0].click();
                                } else {
                                        checkLoadingState(base_href, numOfRetries - 1);
                                };
                                
                        });
                };
                setTimeout(handler,1000);
        };
        var submitLoadFileFromStorage = function(event){
                event.preventDefault();
                var href = $(this).attr('href');
                var element = $(this);
                $.ajax(href).done(function(data){
                        $(element).hide();
                        $('.file-is-loading').fadeIn();
                        $('.not-file-spinner').fadeIn();
                        checkLoadingState(document.location.href, 20);
                });
                return false;
        };

        $(function(){
                $(".load-file-from-storage").click(submitLoadFileFromStorage);
        });
})(jQuery);
