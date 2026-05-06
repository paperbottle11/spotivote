let playlist_id = document.getElementById('playlist-id').value;
function updateCurrentPlaylistId() {
    playlist_id = document.getElementById('playlist-id').value;
}

async function update(playlist_id) {
    try {
        updateCurrentPlaylistId();
        // Get songs from playlist
        const response = await fetch('/songs?playlist_id=' + playlist_id);
        if (response.ok) {
            const data = await response.json();

            let songList = document.getElementById('songs-container');
            songList.innerHTML = "";

            for (let i = 0; i < data.length; i++) {
                let song_data = data[i];
                let song_id = song_data['id'];
                let song_name = song_data['name'];
                let song_artist = song_data['artist'];
                let song_album = song_data['album'];
                let song_cover_url = song_data['cover_url'];
                let date_added = new Date(song_data['date_added'] * 1000);
                let song_vote = song_data['vote'];
                let song_add_sub = song_data['add_sub'];
                let song_add_user_name = song_data['add_user_name'];
                let song_add_profile_picture = song_data['add_profile_picture'];
                
                let song_div = document.createElement('div');
                song_div.className = "song-info";
                song_div.id = song_id;
                
                // Song Number
                let num_div = document.createElement('div');
                num_div.id = "num";
                num_div.textContent = i + 1;
                song_div.appendChild(num_div);

                // Upvote Button
                let up_button = document.createElement('button');
                up_button.id = "upvote";
                up_button.className = "vote";
                up_button.textContent = "↑";
                up_button.addEventListener('click', () => upvote(playlist_id, song_id));
                song_div.appendChild(up_button);

                // Downvote Button
                let down_button = document.createElement('button');
                down_button.id = "downvote";
                down_button.className = "vote";
                down_button.textContent = "↓";
                down_button.addEventListener('click', () => downvote(playlist_id, song_id));
                song_div.appendChild(down_button);

                // Song Cover Image
                let song_img = document.createElement('img');
                song_img.id = "song-picture";
                song_img.src = song_cover_url;
                song_img.alt = song_album + " cover";
                song_div.appendChild(song_img);

                // Song Info
                let song_info_div = document.createElement('div');
                song_info_div.id = "song";
                
                // Song Name
                let song_name_div = document.createElement('div');
                song_name_div.id = "song-name";
                song_name_div.textContent = song_name;
                song_info_div.appendChild(song_name_div);

                // Song Artist
                let song_artist_div = document.createElement('div');
                song_artist_div.id = "song-artist";
                song_artist_div.textContent = song_artist;
                song_info_div.appendChild(song_artist_div);

                song_div.appendChild(song_info_div);

                let song_album_div = document.createElement('div');
                song_album_div.id = "song-album";
                song_album_div.textContent = song_album;
                song_div.appendChild(song_album_div);

                let date_added_div = document.createElement('div');
                date_added_div.id = "date-added";
                date_added_div.textContent = date_added.toLocaleDateString()
                song_div.appendChild(date_added_div);

                // Add User Name and Profile Picture
                let user_info_div = document.createElement('div');
                user_info_div.id = "user-info";

                if (song_add_user_name !== undefined && song_add_user_name !== "") {
                    let user_name = document.createElement('p');
                    user_name.textContent = song_add_user_name;
                    user_info_div.appendChild(user_name);
                }

                if (song_add_profile_picture !== undefined && song_add_profile_picture !== "") {
                    let user_img = document.createElement('img');
                    user_img.id = "user";
                    user_img.src = song_add_profile_picture;
                    user_img.alt = song_add_user_name + " profile picture";
                    user_info_div.appendChild(user_img);
                }

                song_div.appendChild(user_info_div);

                // Apply styling based user's vote
                if (song_vote === 1) {
                    up_button.className = "upvote";
                } else if (song_vote === -1) {
                    down_button.className = "downvote";
                }

                songList.appendChild(song_div);
            }
        } else {
            console.error(`Error fetching data. Status: ${response.status}`);
        }
    } catch (error) {
        console.error('An error occurred:', error);
    }
}

async function upvote(playlist_id, song_id) {
    try {
        const response = await fetch('/upvote?playlist_id=' + playlist_id + '&track_id=' + song_id);
        if (response.ok) {
            const data = await response.text();
            console.log(data);
            let song_div = document.getElementById(song_id);
            let up_button = song_div.querySelector('#upvote');
            let down_button = song_div.querySelector('#downvote');
            if (up_button.className === "upvote") {
                up_button.className = "";
            } else {
                up_button.className = "upvote";
                down_button.className = "";
            }
        } else {
            console.error(`Error upvoting. Status: ${response.status}`);
        }
    } catch (error) {
        console.error('An error occurred:', error);
    }
}

async function downvote(playlist_id, song_id) {
    try {
        const response = await fetch('/downvote?playlist_id=' + playlist_id + '&track_id=' + song_id);
        if (response.ok) {
            const data = await response.text();
            console.log(data);
            let song_div = document.getElementById(song_id);
            let up_button = song_div.querySelector('#upvote');
            let down_button = song_div.querySelector('#downvote');
            if (down_button.className === "downvote") {
                down_button.className = "";
            } else {
                down_button.className = "downvote";
                up_button.className = "";
            }
        } else {
            console.error(`Error downvoting. Status: ${response.status}`);
        }
    } catch (error) {
        console.error('An error occurred:', error);
    }
}