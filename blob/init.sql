drop table if exists config;
drop table if exists sharedTemplate;
drop table if exists emotionPacks;
drop table if exists personalCharacter;

create table config (
    userName            string DEFAULT 'Jerry Chou',
    passwordSalted      string NOT NULL,
    avatar              blob NOT NULL,
    avatarMime          string NOT NULL,
    persona             string NOT NULL default 'A high-school student, who loves playing video games and watching anime.',
    gptSoVitsMiddleware string NOT NULL default 'http://localhost:5000'
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
    AIDubUseModel           string default 'None',
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

create table tasks (
    id                      integer PRIMARY KEY AUTOINCREMENT,
    stagesDescription       string NOT NULL default '[]',
    status                  string not null default 'pending',
    creationTime            string NOT NULL DEFAULT 'N/A',
    completionTime          string default NULL default 'N/A',
    log                     string default NULL default '""'
);

create table extraInfos (
    id integer primary key autoincrement,
    name string not null,
    description string not null,
    enabled integer not null default 1,
    content string not null,
    author string not null
);

create table userScripts (
    id integer primary key autoincrement,
    name string not null,
    content string not null,
    enabled integer not null default 1,
    description string not null,
    author string not null
);