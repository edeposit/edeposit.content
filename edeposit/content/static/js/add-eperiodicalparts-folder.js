(function($){
        $(document).ready(function(){
                $('.add-next-eperiodicalpartsfolder').prepOverlay({
                    subtype:'ajax',
                    filter:common_content_filter,
                    formselector:'form#changeform',
                    noform: function(el,responseText){  return 'redirect';  },
		    redirect: function(el,responseText){ 
			return $.plonepopups.redirectbasehref(el,responseText);
		    }
                });
        });
}(jQuery));
