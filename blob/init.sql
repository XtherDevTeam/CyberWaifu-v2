drop table if not exists config;
drop table if not exists sharedTemplate;
drop table if not exists emotionPacks;
drop table if not exists personalCharacter;

create table config (
    userName        string DEFAULT 'Jerry Chou',
    passwordSalted  string NOTNULL,
    avatar          blob NOTNULL,
    
);

create table emotionPacks (
    id              integer PRIMARY KEY AUTOINCREMENT,
    name            string NOTNULL,
    happy           blob NOTNULL,
    sad             blob NOTNULL,
    angry           blob NOTNULL,
    guilty          blob NOTNULL
);

create table personalCharacter (
    id                      integer PRIMARY KEY AUTOINCREMENT,
    charName                string NOTNULL,
    charPrompt              string NOTNULL,
    initialMemories         string NOTNULL,
    exampleChats            string NOTNULL,
    pastMemories            string NOTNULL,
    avatar                  blob NOTNULL,
    emotionPack             int default 0,
    creationTime            string NOTNULL
);

create table chatHistory (
    id                      integer PRIMARY KEY AUTOINCREMENT,
    charName                string NOTNULL,
    --- available: bot = 0, user = 1
    role                    integer NOTNULL,
    --- available: TEXT = 0, IMG = 1, AUDIO = 2, EMOTION = 3
    type                    integer NOTNULL,
    text                    string NOTNULL,
    timestamp               string NOTNULL
);

create table attachments (
    id                      string PRIMARY KEY,
    timestamp               integer NOTNULL,
    --- available: AUDIO = 0, IMG = 1
    type                    integer NOTNULL,
    contentType             string default 'application/octet-stream',
    blobMsg                 blob    NOTNULL
);