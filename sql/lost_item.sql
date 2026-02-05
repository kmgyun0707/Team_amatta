CREATE TABLE item(
    id INTEGER NOT NULL PRIMARY KEY autoincrement,
    category TEXT not NULL,
    color TEXT null,
    time datetime not null default current_timestamp,
    location_x REAL not NULL,
    location_y REAL not NULL,
    image_path TEXT,
    state TEXT not null DEFAULT '보관중'
);

CREATE TABLE item_lost(
    id INTEGER NOT NULL PRIMARY KEY autoincrement,
    name text not null,
    phone text not null,
    category TEXT not NULL,
    color TEXT null,
    losttime datetime DEFAULT current_timestamp,
    state TEXT not null DEFAULT '탐색중'
);

CREATE TABLE location(
    loc_id integer PRIMARY KEY,
    loc_name TEXT NOT NULL
);

CREATE TABLE lost_location_map (
    lost_id INTEGER,
    loc_id INTEGER,
    Foreign Key (lost_id) REFERENCES item_lost(id),
    Foreign Key (loc_id) REFERENCES location(loc_id)
)
