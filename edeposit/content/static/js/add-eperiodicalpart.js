(function($){
        $(document).ready(function(){
                $('.add-next-eperiodicalpart').prepOverlay({
                    subtype:'ajax',
                    filter:common_content_filter,
                    formselector:'form#changeform',
		    noform: function(el){
			return 'reload';
		    },
                });
        });
}(jQuery));
