var curSearchJSON = [];
$("#search").keypress(function(){
    var search = $(this).val();
    $.get("/search?q="+search, function(data, status){
        curSearchJSON = JSON.parse(data);
        $("#songList").html("");
        $.each(curSearchJSON, function(i, item) {
            $("#songList").append('<div class="track_item" data-track-id="'+item['id']+'"> <img src="'+item['cover_img']+'" class="search-item-cover"> <div class="track_item_details"> <p class="track_item_title">'+item['name']+'</p><p class="track_item_artist">'+item['artist']+'</p></div></div>');
        });
        $("#songList").slideDown();
    });
});

$("#search").keyup(function() {
    var search = $(this).val();
    if (search.length === 0) {
        // Clear the list if search is empty
        $("#songList").html("");
    }
});

$(document).click(function(event) {
    // Check if the clicked element is not the search box
    if (!$(event.target).closest('#search').length) {
        // Clear the search box
        $('#search').val('');
        $("#songList").html("");
    }
});

$(document).on( "click", ".track_item", function() {
    // alert("hi")
    updateCurrentPlaylistId();
    var trackId = $(this).attr("data-track-id");
    $.get("/add?playlist_id=" + playlist_id + "&track_id=" + trackId, function(data) {
    // This function is called when the request is successful
        console.log('Song Added');
        update(playlist_id);
    // You can work with the data here
    }).fail(function(jqXHR, textStatus, errorThrown) {
    // This function is called if an error occurs
        console.error('Error:', errorThrown);
        update(playlist_id);
    });
});