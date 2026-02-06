CREATE TABLE item(
    id INTEGER NOT NULL PRIMARY KEY autoincrement,
    category TEXT not NULL,
    color TEXT null,
    time datetime not null default current_timestamp,
    location_x REAL not NULL,
    location_y REAL not NULL,
    image BLOB,
    image_path TEXT,
    state TEXT not null
);

CREATE TABLE item_lost(
    id INTEGER NOT NULL PRIMARY KEY,
    name text not null,
    phone text not null,
    category TEXT not NULL,
    color TEXT null,
    time TEXT null,
    gate INTEGER not null,
    state TEXT not null
);

CREATE TABLE location(
    id INTEGER PRIMARY KEY not null,
    toiletm BOOLEAN,
    toiletw BOOLEAN,
    bench1 BOOLEAN,
    bench2 BOOLEAN,
    bank BOOLEAN,
    dutyfree BOOLEAN
);
