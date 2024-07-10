drop table if exists config;
drop table if exists sharedTemplate;
drop table if exists emotionPacks;
drop table if exists personalCharacter;

create table config (
    userName        string DEFAULT 'Jerry Chou',
    passwordSalted  string NOT NULL,
    avatar          blob NOT NULL,
    avatarMime      string NOT NULL,
    persona         string NOT NULL default 'A high-school student, who loves playing video games and watching anime.'
);

create table stickerSets (
    id              integer PRIMARY KEY AUTOINCREMENT,
    setName         string NOT NULL
);

create table stickers (
    id              integer PRIMARY KEY AUTOINCREMENT,
    setId           integer NOT NULL,
    name            string NOT NULL,
    image           blob NOT NULL,
    mime            string NOT NULL
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
    ttsServiceId            integer default 0,
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

create table GPTSoVitsServices (
    id                      integer PRIMARY KEY AUTOINCREMENT,
    name                    string NOT NULL,
    url                     string NOT NULL,
    description             string NOT NULL,
    ttsInferYamlPath        string NOT NULL default 'GPT_SoVITS/configs/tts_infer.yaml',
);

create table GPTSoVitsReferenceAudios (
    id                      integer PRIMARY KEY AUTOINCREMENT,
    name                    string NOT NULL,
    text                    string NOT NULL,
    serviceId               integer NOT NULL,
    path                    string NOT NULL,
    language                string NOT NULL
);