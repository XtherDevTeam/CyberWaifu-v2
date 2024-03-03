drop table if exists config;
drop table if exists sharedTemplate;
drop table if exists emotionPacks;
drop table if exists personalCharacter;

create table config (
    userName        string DEFAULT 'Jerry Chou',
    passwordSalted  string NOT NULL,
    avatar          blob NOT NULL
);

create table emotionPacks (
    id              integer PRIMARY KEY AUTOINCREMENT,
    name            string NOT NULL,
    happy           blob NOT NULL,
    sad             blob NOT NULL,
    angry           blob NOT NULL,
    guilty          blob NOT NULL
);

create table personalCharacter (
    id                      integer PRIMARY KEY AUTOINCREMENT,
    charName                string NOT NULL,
    charPrompt              string NOT NULL,
    initialMemories         string NOT NULL,
    exampleChats            string NOT NULL,
    pastMemories            string NOT NULL,
    avatar                  blob NOT NULL,
    avatarMime              string default 'image/png',
    emotionPack             integer default 0,
    creationTime            string NOT NULL
);

create table chatHistory (
    id                      integer PRIMARY KEY AUTOINCREMENT,
    charName                string NOT NULL,
    role                    integer NOT NULL,
    type                    integer NOT NULL,
    text                    string NOT NULL,
    timestamp               string NOT NULL
);

create table attachments (
    id                      string PRIMARY KEY,
    timestamp               integer NOT NULL,
    type                    integer NOT NULL,
    contentType             string default 'application/octet-stream',
    blobMsg                 blob    NOT NULL
);