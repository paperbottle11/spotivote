function create_song_div(song_data) {
    let playlist_id = song_data['playlist_id'];
    let song_id = song_data['id'];
    
    let song_div = document.createElement('div');
    song_div.className = "song";
    song_div.id = song_id;
    
    // Song Number
    let num_div = document.createElement('div');
    num_div.className = "song-num";
    num_div.textContent = song_data["number"];
    song_div.appendChild(num_div);

    // Vote Button Container
    let vote_container = document.createElement('div');
    vote_container.className = "vote-container";
    song_div.appendChild(vote_container);

    // Upvote Button
    let up_button = document.createElement('span');
    up_button.id = "upvote";
    up_button.className = "novote";
    up_button.title = "Upvote song";
    up_button.addEventListener('click', () => upvote(playlist_id, song_id));
    vote_container.appendChild(up_button);

    // Downvote Button
    let down_button = document.createElement('span');
    down_button.id = "downvote";
    down_button.className = "novote";
    down_button.title = "Downvote song"
    down_button.addEventListener('click', () => downvote(playlist_id, song_id));
    vote_container.appendChild(down_button);

    // Song Cover Image
    let song_img = document.createElement('img');
    song_img.className = "song-picture";
    song_img.src = song_data['cover_url'];
    song_img.alt = song_data['album'] + " cover";
    song_div.appendChild(song_img);

    // Song Info
    let song_info_div = document.createElement('div');
    song_info_div.className = "song-info";
    
    // Song Name
    let song_name_div = document.createElement('div');
    song_name_div.className = "song-name";
    song_name_div.textContent = song_data['name'];
    
    // Explicit Icon
    if (song_data['explicit']) {
        let explicit_icon = document.createElement('img');
        explicit_icon.className = 'explicit-icon';
        explicit_icon.src = "static/explicit.png";
        explicit_icon.alt = "(explicit)";
        explicit_icon.title = "Explicit";
        song_name_div.appendChild(explicit_icon);
    }
    song_info_div.appendChild(song_name_div);

    // Song Artist
    let song_artist_div = document.createElement('div');
    song_artist_div.className = "song-artist";
    song_artist_div.textContent = song_data['artist'];
    song_info_div.appendChild(song_artist_div);
    song_div.appendChild(song_info_div);

    // Song Album
    let song_album_div = document.createElement('div');
    song_album_div.className = "song-album";
    song_album_div.textContent = song_data['album'];
    song_div.appendChild(song_album_div);

    // Date Added
    let date_added = new Date(song_data['added_at'] * 1000);
    let date_added_div = document.createElement('div');
    date_added_div.className = "date-added";
    date_added_div.textContent = date_added.toLocaleDateString()
    song_div.appendChild(date_added_div);

    // Add User Name and Profile Picture
    let user_info_div = document.createElement('div');
    user_info_div.className = "user-info";

    // Only display user info if available
    let song_add_user_name = song_data['add_user_name'];
    if (song_add_user_name !== undefined && song_add_user_name !== "") {
        let user_name = document.createElement('p');
        user_name.textContent = song_add_user_name;
        user_info_div.appendChild(user_name);
    }

    // Only display profile picture if available
    let song_add_profile_picture = song_data['add_profile_picture'];
    if (song_add_profile_picture !== undefined && song_add_profile_picture !== "") {
        let user_img = document.createElement('img');
        user_img.className = "user-image";
        user_img.src = song_add_profile_picture;
        user_img.alt = song_add_user_name + " profile picture";
        user_info_div.appendChild(user_img);
    }
    song_div.appendChild(user_info_div);

    // Only create delete button if user added the song
    if (song_data["user_added"]) {
        let trash_can_icon = document.createElement("img");
        trash_can_icon.className = "delete-button";
        trash_can_icon.src = "static/trash.png";
        trash_can_icon.alt = "(delete)";
        trash_can_icon.title = "Delete song";
        trash_can_icon.addEventListener('click', (e) => {
            show_delete_confirm(e.currentTarget, playlist_id, song_id);
        });
        song_div.appendChild(trash_can_icon);
    }
    
    // Apply vote button styling based user's vote
    if (song_data['vote'] === 1) {
        up_button.className = "upvote";
    } else if (song_data['vote'] === -1) {
        down_button.className = "downvote";
    }

    return song_div
}

async function update(playlist_id) {
    try {
        if (playlist_id === "") {
            return;
        }
        
        // Show loader while fetching songs
        document.getElementById("songs-loader").style.display = "block";
        let song_list = document.getElementById('songs-container');
        song_list.style.display = "none";
        
        // Get songs from playlist
        const response = await fetch('/songs?playlist-id=' + playlist_id);
        if (response.ok) {
            const data = await response.json();
            song_list.innerHTML = "";

            let song_list_headers = document.createElement('div');
            song_list_headers.id = "song-list-headers";
            song_list_headers.innerHTML = `
                <div id="header-number">#</div>
                <div id="header-title">Title</div>
                <div id="header-album">Album</div>
                <div id="header-date">Date Added</div>
                <div id="header-added-by">Added By</div>
            `;
            song_list.appendChild(song_list_headers);

            for (let i = 0; i < data.length; i++) {
                let song_data = data[i];
                song_data["number"] = i+1;
                song_data["playlist_id"] = playlist_id;
                song_list.appendChild(create_song_div(song_data));
            }
        } else {
            console.error(`Error fetching data. Status: ${response.status}`);
        }
    } catch (error) {
        console.error('An error occurred:', error);
    }

    // Show songs
    document.getElementById("songs-loader").style.display = "none";
    document.getElementById("songs-container").style.display = "flex";

    initializePlaylistSearch();
}

async function upvote(playlist_id, song_id) {
    try {
        const response = await fetch("/upvote", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                playlist_id: playlist_id,
                track_id: song_id
            })
        });
        const data = await response.json();
        console.log(data.message);
        if (response.ok) {
            let song_div = document.getElementById(song_id);
            let up_button = song_div.querySelector('#upvote');
            let down_button = song_div.querySelector('#downvote');
            if (up_button.className === "upvote") {
                up_button.className = "novote";
            } else {
                up_button.className = "upvote";
                down_button.className = "novote";
            }
        }
    } catch (error) {
        console.error('An error occurred:', error);
    }
}

async function downvote(playlist_id, song_id) {
    try {
        const response = await fetch("/downvote", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                playlist_id: playlist_id,
                track_id: song_id
            })
        });

        const data = await response.json();
        console.log(data.message);
        if (response.ok) {
            let song_div = document.getElementById(song_id);
            let up_button = song_div.querySelector('#upvote');
            let down_button = song_div.querySelector('#downvote');

            if (down_button.className === "downvote") {
                down_button.className = "novote";
            } else {
                down_button.className = "downvote";
                up_button.className = "novote";
            }
        }
    } catch (error) {
        console.error('An error occurred:', error);
    }
}

function show_delete_confirm(icon, playlist_id, song_id) {
    const song = icon.closest(".song");

    // remove existing popup
    document.querySelectorAll(".confirm-popup").forEach(el => el.remove());

    let popup = document.createElement("div");
    popup.className = "confirm-popup";
    popup.innerHTML = `
        <span>Delete?</span>
        <button class="confirm">Yes</button>
        <button class="cancel">No</button>
    `;

    song.appendChild(popup);

    // position (your existing logic)
    popup.style.position = "absolute";
    popup.style.top = `${icon.offsetTop + icon.offsetHeight / 2}px`;
    popup.style.left = `${icon.offsetLeft}px`;
    popup.style.transform = "translate(-100%, -50%)";

    // --- CLOSE ON OUTSIDE CLICK ---
    const handleOutsideClick = (e) => {
        if (!popup.contains(e.target) && e.target !== icon) {
            popup.remove();
            document.removeEventListener("click", handleOutsideClick);
        }
    };

    // delay so the current click doesn’t instantly close it
    setTimeout(() => {
        document.addEventListener("click", handleOutsideClick);
    }, 0);

    // YES
    popup.querySelector(".confirm").addEventListener("click", async () => {
        popup.remove();
        document.removeEventListener("click", handleOutsideClick);
        await delete_song(playlist_id, song_id);
    });

    // NO
    popup.querySelector(".cancel").addEventListener("click", () => {
        popup.remove();
        document.removeEventListener("click", handleOutsideClick);
    });
}

async function delete_song(playlist_id, song_id) {
    try {
        const response = await fetch("/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                playlist_id: playlist_id,
                track_id: song_id,
                validate: false
            })
        });

        const data = await response.json();
        console.log(data.message);
        if (response.ok) {
            document.getElementById(song_id).remove();
        }
    } catch (error) {
        console.error('An error occurred:', error);
    }
}

async function play(playlist_id, device_id) {
    try {
        document.getElementById("play-loader").style.display = "block";
        const response = await fetch("/play", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                playlist_id: playlist_id,
                device_id: device_id,
                shuffle_state: document.getElementById("shuffle-checkbox").checked
            })
        });

        const data = await response.json();
        console.log(data.message);
        if (response.status == 404 && data.message.toLowerCase().includes("device")) {
            alert("The selected device was not found or there are no active devices. Open Spotify on a device (if you haven't already) and refresh the page.")
        }
        
    } catch (error) {
        console.error('An error occurred:', error);
    } finally {
        document.getElementById("play-loader").style.display = "none";
    }
}

async function create_playlist(playlist_id, playlist_name) {
    try {
        const response = await fetch("/create-playlist", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                playlist_id: playlist_id,
                playlist_name: playlist_name
            })
        });

        const data = await response.json();
        console.log(data.message);
        if (response.ok) {
            alert("This may take a while depending on the length of the playlist! Do not refresh or leave the page until the songs have loaded.")
            window.location.reload()
        }
    } catch (error) {
        console.error('An error occurred:', error);
    }
}

function debounce(fn, delay) {
    let timeout;
    return (...args) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => fn(...args), delay);
    };
}

function initializePlaylistSearch() {
    const searchInput = document.getElementById("playlist-search");
    const songs = document.querySelectorAll(".song");

    searchInput.addEventListener("input", debounce(() => {
        const query = searchInput.value.toLowerCase().trim();

        songs.forEach(song => {
            const title = song.querySelector(".song-name")?.textContent.toLowerCase() || "";
            const artist = song.querySelector(".song-artist")?.textContent.toLowerCase() || "";

            song.style.display = (title.includes(query) || artist.includes(query)) ? "grid" : "none";
        });
    }, debounceTimerDelay));
}