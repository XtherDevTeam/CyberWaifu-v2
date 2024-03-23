drop table if exists config;
drop table if exists sharedTemplate;
drop table if exists emotionPacks;
drop table if exists personalCharacter;

create table config (
    userName        string DEFAULT 'Jerry Chou',
    passwordSalted  string NOTNULL,
    avatar          blob NOTNULL,
    avatarMime      string NOTNULL
);

create table stickerSets (
    id              integer PRIMARY KEY AUTOINCREMENT,
    setName         string NOTNULL
);

create table stickers (
    id              integer PRIMARY KEY AUTOINCREMENT,
    setId           integer NOTNULL,
    name            string NOTNULL,
    image           blob NOTNULL,
    mime            string NOTNULL
);

create table personalCharacter (
    id                      integer PRIMARY KEY AUTOINCREMENT,
    charName                string NOTNULL,
    charPrompt              string NOTNULL,
    initialMemories         string NOTNULL,
    exampleChats            string NOTNULL,
    pastMemories            string NOTNULL,
    avatar                  blob NOTNULL,
    avatarMime              string default 'image/png',
    emotionPack             integer default 0,
    creationTime            string NOTNULL
);

create table chatHistory (
    id                      integer PRIMARY KEY AUTOINCREMENT,
    charName                string NOTNULL,
    role                    integer NOTNULL,
    type                    integer NOTNULL,
    text                    string NOTNULL,
    timestamp               string NOTNULL
);

create table attachments (
    id                      string PRIMARY KEY,
    timestamp               integer NOTNULL,
    type                    integer NOTNULL,
    contentType             string default 'application/octet-stream',
    blobMsg                 blob    NOTNULL
);