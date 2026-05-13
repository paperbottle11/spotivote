let debounceTimer;
let debounceTimerDelay = 250; // milliseconds
let currentRequest = null;

$("#song-search").on("input", function() {
    const search = $(this).val().trim();

    // If empty: cancel requests and clear UI
    if (search === "") {
        clearTimeout(debounceTimer);

        if (currentRequest) {
            currentRequest.abort();
            currentRequest = null;
        }

        $("#songList").slideUp().html("");
        curSearchJSON = [];
        return;
    }

    // Debounce search requests
    clearTimeout(debounceTimer);

    debounceTimer = setTimeout(function() {

        // Cancel previous request if still running
        if (currentRequest) {
            currentRequest.abort();
        }

        currentRequest = $.ajax({
            url: "/search",
            method: "GET",
            data: { q: search },
            success: function(data) {
                const results = JSON.parse(data);

                if ("message" in results) {
                    console.error("Error fetching search results: " + results["message"]);
                    return;
                }

                $("#songList").html("");

                $.each(results, function(i, item) {
                    let explicitImageTag = item['explicit'] == true ? '<img class="explicit-icon" src="static/explicit.png" alt="(explicit)">' : '';
                    $("#songList").append(
                        '<div class="track_item" data-track-id="' + item['id'] + '">' +
                        '<img src="' + item['cover_img'] + '" class="search-item-cover">' +
                        '<div class="track_item_details">' +
                        '<div class="track_item_name">' + '<p class="track_item_title">' + item['name'] + '</p>' + explicitImageTag + '</div>' +
                        '<p class="track_item_artist">' + item['artist'] + '</p>' +
                        '</div></div>'
                    );
                });

                $("#songList").slideDown();
            },
            error: function(xhr, status) {
                if (status !== "abort") {
                    console.error("Request failed:", status);
                }
            },
            complete: function() {
                currentRequest = null;
            }
        });
    }, debounceTimerDelay);
});

$(document).click(function(event) {
    // Check if the clicked element is not the search box
    if (!$(event.target).closest('#song-search').length) {
        // Clear the search box
        $('#song-search').val('');
        $("#songList").html("");
    }
});