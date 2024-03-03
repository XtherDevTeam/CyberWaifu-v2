import sqlite3
import logging
import time
import config
import hashlib
import exceptions
import models
import typing
import uuid


class AttachmentType:
    """
    Enum class representing different types of attachment entries.

    Attributes:
        IMG: Image attachment.
        AUDIO: Audio attachment.
    """
    AUDIO = 0
    IMG = 1


class ChatHistoryType:
    """
    Enum class representing different types of chat history entries.

    Attributes:
        TEXT: Text message entry.
        IMG: Image message entry.
        AUDIO: Audio message entry.
        EMOTION: Emotion message entry.
        INSTRUCTION: Instruction message entry.
    """
    TEXT = 0
    IMG = 1
    AUDIO = 2
    EMOTION = 3
    INSTRUCTION = 4


class ChatHistoryRole:
    """
    Enum class representing different roles in chat history.

    Attributes:
        BOT: Bot role.
        USER: User role.
    """
    BOT = 0
    USER = 1


class DatabaseObject:
    """
    Class representing a database connection object.

    Args:
        dbPath (str): Path to the SQLite database file.

    Methods:
        query(query, args=(), one=False):
            Execute an SQL query on the database.
        runScript(query):
            Execute an SQL script on the database.
        close():
            Close the database connection.
    """

    def __init__(self, dbPath: str) -> None:
        self.db = sqlite3.connect(dbPath, check_same_thread=False)

    def query(self, query, args=(), one=False) -> list[dict[str | typing.Any]] | dict[str | typing.Any]:
        """
        Execute an SQL query on the database.

        Args:
            query (str): The SQL query to be executed.
            args (tuple, optional): Query parameters. Defaults to ().
            one (bool, optional): Return only one result. Defaults to False.

        Returns:
            list[dict[str | typing.Any]] | dict[str | typing.Any]: Query result.
        """
        cur = self.db.execute(query, args)
        rv = [dict((cur.description[idx][0], value)
                   for idx, value in enumerate(row)) for row in cur.fetchall()]
        lastrowid = cur.lastrowid
        cur.close()
        if query.startswith('insert'):
            return lastrowid
        else:
            return (rv[0] if rv else None) if one else rv

    def runScript(self, query: str):
        """
        Execute an SQL script on the database.

        Args:
            query (str): The SQL script to be executed.
        """
        self.db.executescript(query)
        self.db.commit()
        return None

    def close(self):
        """Close the database connection."""
        self.db.close()


class DataProvider:
    """
    Class providing data-related functionality for the application.

    Args:
        databasePath (str): Path to the SQLite database file.

    Methods:
        checkIfInitialized():
            Check if the database is initialized.
        initialize(userName, password, avatarPath):
            Initialize the database with user information.
        getUserName():
            Get the username from the database.
        authenticate(pwd):
            Authenticate a user based on the provided password.
        getCharacter(id):
            Get information about a character from the database.
        createCharacter(name, prompt, initalMemory, exampleChats, avatarPath):
            Create a new character in the database.
        checkIfCharacterExist(name):
            Check if a character with the given name exists in the database.
        updateCharacter(id, name, prompt, pastMemories):
            Update character information in the database.
        getCharacterId(name):
            Get the ID of a character from the database.
        chatMsgToTextOnly(f):
            Convert a chat message to text-only representation.
        fetchLatestChatHistory(id):
            Fetch the latest chat history entry for a character.
        getCharacterList():
            Get a list of characters with their latest messages.
        parseMessageChain(chain):
            Parse a message chain and return formatted text.
        parseModelResponse(plain):
            Parse a model response and return a list of formatted messages.
    """

    def __init__(self, databasePath: str) -> None:
        self.db = DatabaseObject(databasePath)
        if not self.checkIfInitialized():
            logging.getLogger(__name__).warning('Database is not initialized')

        pass

    def checkIfInitialized(self) -> bool:
        """
        Check if the database is initialized.

        Returns:
            bool: True if initialized, False otherwise.
        """
        r = self.db.query(
            'select 1 from sqlite_master where type = "table" and name = ?', ('config', ))
        if len(r) == 0:
            logging.getLogger(__name__).info('Running initialization script')
            with open(f'{config.BLOB_URL}/init.sql', 'r') as file:
                self.db.runScript(file.read())

        return len(self.db.query("select 1 from config")) != 0

    def initialize(self, userName: str, password: str, avatar: bytes | None = None) -> None:
        """
        Initialize the database with user information.

        Args:
            userName (str): User's username.
            password (str): User's password.
            avatarPath (str, optional): Path to the user's avatar. Defaults to f'{config.BLOB_URL}/avatar.png'.
        """
        password = hashlib.md5(
            f'_@YoimiyaIsMyWaifu_{password}'.encode('utf-8')).hexdigest()
        if avatar is None:
            with open(f'{config.BLOB_URL}/avatar.png', 'rb') as file:
                avatar = file.read()

        self.db.query('insert into config (userName, passwordSalted, avatar) values (?, ?, ?)',
                      (userName, password, avatar))

    def getUserName(self) -> None | str:
        """
        Get the username from the database.

        Returns:
            None | str: Username if exists, None otherwise.
        """
        f = self.db.query('select userName from config', one=True)
        if f is None:
            return None
        else:
            return f['userName']

    def authenticate(self, pwd: str) -> None | bool:
        """
        Authenticate a user based on the provided password.

        Args:
            pwd (str): User's password.

        Returns:
            None | bool: True if authentication is successful, None otherwise.
        """
        f = self.db.query('select passwordSalted from config', one=True)
        if f is None:
            return None
        else:
            return hashlib.md5(f'_@YoimiyaIsMyWaifu_{pwd}'.encode('utf-8')).hexdigest() == f['passwordSalted']

    def getCharacter(self, id: int) -> None | dict[str, str | int]:
        """
        Get information about a character from the database.

        Args:
            id (int): Character ID.

        Returns:
            None | dict[str, str | int]: Character information if exists, None otherwise.
        """
        return self.db.query('select id, charName, exampleChats, prompt, pastMemories, creationTime from personalCharacter where id = ?', (id, ), one=True)

    def createCharacter(self, name: str, prompt: str, initalMemory: str, exampleChats: str, avatarPath: str = f'{config.BLOB_URL}/avatar_2.png') -> None:
        """
        Create a new character in the database.

        Args:
            name (str): Character name.
            prompt (str): Character prompt.
            initalMemory (str): Initial memory for the character.
            exampleChats (str): Example chats for the character.
            avatarPath (str, optional): Path to the character's avatar. Defaults to f'{config.BLOB_URL}/avatar_2.png'.
        """
        with open(avatarPath, 'rb') as file:
            return self.db.query('insert into personalCharacter (charName, charPrompt, initialMemories, pastMemories, avatar, exampleChats, creationTime) values (?, ?, ?, ?, ?, ?, ?)',
                                 (name, prompt, initalMemory, initalMemory, file.read(), exampleChats, models.DateProider()))

    def checkIfCharacterExist(self, name: int) -> bool:
        """
        Check if a character with the given name exists in the database.

        Args:
            name (int): Character name.

        Returns:
            bool: True if character exists, False otherwise.
        """
        return bool(len(self.db.query('select count(*) from personalCharacter where name = ?')), (name, ))

    def updateCharacter(self, id: int, name: str, prompt: str, pastMemories: str) -> None:
        """
        Update character information in the database.

        Args:
            id (int): Character ID.
            name (str): New character name.
            prompt (str): New character prompt.
            pastMemories (str): New past memories for the character.
        """
        self.db.query('update personalCharacter set charName = ?, prompt = ?, pastMemories = ? where id = ?',
                      (name, prompt, pastMemories, id))

    def getCharacterId(self, name: str) -> int:
        """
        Get the ID of a character from the database.

        Args:
            name (str): Character name.

        Raises:
            exceptions.CharacterNotFound: If character is not found.

        Returns:
            int: Character ID.
        """
        f = self.db.query(
            'select id from personalCharacter where charName = ?', (name, ))
        if f is None:
            raise exceptions.CharacterNotFound(
                f'{__name__}: Character {name} not found')

    def chatMsgToTextOnly(f: dict[str, str | int]) -> str:
        """
        Convert a chat message to text-only representation.

        Args:
            f (dict[str, str | int]): Chat message information.

        Returns:
            str: Text-only representation of the chat message.
        """
        if f['type'] == ChatHistoryType.TEXT:
            return f['text']
        elif f['type'] == ChatHistoryType.IMG:
            return '🌄'
        elif f['type'] == ChatHistoryType.EMOTION:
            if f['text'] == '(EMO_ANGRY)':
                return '😡'
            elif f['text'] == '(EMO_GUILITY)':
                return '🙁'
            elif f['text'] == '(EMO_HAPPY)':
                return '😊'
            elif f['text'] == '(EMO_SAD)':
                return '😢'
            elif f['text'] == '(EMO_NOT_UNDERSTAND)':
                return '🙋'
            else:
                return '？'

    def fetchLatestChatHistory(self, id: int) -> str | None:
        """
        Fetch the latest chat history entry for a character.

        Args:
            id (int): Character ID.

        Returns:
            str | None: Latest chat history entry if exists, None otherwise.
        """
        f = self.db.query(
            'select role, type, text from chatHistory where id = ? and text != "(OPT_NO_RESPOND)" order by timestamp desc limit 1', (id, ), one=True)
        return None if f is None else self.chatMsgToTextOnly(f)

    def getCharacterList(self) -> int:
        """
        Get a list of characters with their latest messages.

        Returns:
            int: List of characters with their latest messages.
        """
        l = self.db.query(
            'select id, charName, creationTime from personalCharacter')
        for i in range(len(l)):
            l[i]['latestMsg'] = self.fetchLatestChatHistory(l[i]['id'])
            l[i]['latestMsg'] = 'No chats' if l[i]['latestMsg'] is None else l[i]['latestMsg']
        return l

    def parseMessageChain(self, chain: list[str]) -> list[dict[str | int]]:
        """
        Parse a message chain and return formatted text.

        Args:
            chain (list[str]): List of messages in the chain.

        Returns:
            str: Formatted text representation of the message chain.
        """
        r = []
        for i in chain:
            i = i.strip()
            if i.startswith('image:'):
                url = i[i.find(':')+1:]
                r.append({
                    'type': ChatHistoryType.IMG,
                    'text': url,
                    'timestamp': models.TimeProider(),
                    'role': 'user'
                })
            elif i.startswith('audio:'):
                url = i[i.find(':')+1:]
                r.append({
                    'type': ChatHistoryType.AUDIO,
                    'text': url,
                    'timestamp': models.TimeProider(),
                    'role': 'user'
                })
            elif i.startswith('(EMO_'):
                r.append({
                    'type': ChatHistoryType.EMOTION,
                    'text': i,
                    'timestamp': models.TimeProider(),
                    'role': 'user'
                })
            elif i.startswith('('):
                r.append({
                    'type': ChatHistoryType.INSTRUCTION,
                    'text': i,
                    'timestamp': models.TimeProider(),
                    'role': 'user'
                })
            else:
                r.append({
                    'type': ChatHistoryType.TEXT,
                    'text': i,
                    'timestamp': models.TimeProider(),
                    'role': 'user'
                })

        return r

    def parseModelResponse(self, plain: str) -> list[dict[str | int]]:
        """
        Parse a model response and return a list of formatted messages.

        Args:
            plain (str): Plain model response.

        Returns:
            list[dict[str | int]]: List of formatted messages.
        """
        l: list[str] = plain.strip().split('(CMD_MULTI_MSG)')
        r: list[dict[str | int]] = []
        for i in l:
            i = i.strip()
            if i.startswith('(EMO_'):
                r.append({
                    'type': ChatHistoryType.EMOTION,
                    'text': i,
                    'timestamp': models.TimeProider(),
                    'role': 'model'
                })
            elif i == '(CMD_NO_RESPONSE)':
                pass
            elif i == '(CMD_EXIT_NORMAL)' or i == '(CMD_EXIT_ROLE)':
                r.append({
                    'type': ChatHistoryType.INSTRUCTION,
                    'text': i,
                    'timestamp': models.TimeProider(),
                    'role': 'model'
                })
            else:
                r.append({
                    'type': ChatHistoryType.TEXT,
                    'text': i,
                    'timestamp': models.TimeProider(),
                })

        return r

    def convertMessageHistoryToModelInput(self, chain: list[dict[str, str | int]]) -> str:
        r = ""

        for i in chain:
            if i['type'] == ChatHistoryType.TEXT or i['type'] == ChatHistoryType.EMOTION:
                r += i['text'].strip() + '\n'
            elif i['type'] == ChatHistoryType.IMG:
                r += f'(CMD_IMAGE {models.ImageParsingModel(i['text'])})\n'
            elif i['type'] == ChatHistoryType.AUDIO:
                r += f'(CMD_AUDIO {models.AudioToTextModel(i['text'])})\n'

        return r

    def saveAudioAttachment(self, file: bytes, mime: str) -> str:
        id = uuid.uuid4().hex
        self.db.query(
            'insert into attachments (id, timestamp, type, blobMsg, contentType) values (?, ?, ?, ?)', (id, int(time.time()), AttachmentType.AUDIO, file, mime))
        return id

    def saveImageAttachment(self, file: bytes, mime: str) -> str:
        id = uuid.uuid4().hex
        self.db.query(
            'insert into attachments (id, timestamp, type, blobMsg, contentType) values (?, ?, ?, ?)', (id, int(time.time()), AttachmentType.AUDIO, file, mime))
        return id

    def getAttachment(self, attachmentId: str) -> tuple[str, bytes] | None:
        f = self.db.query(
            'select blobMsg, contentType from attachments where id = ?', (attachmentId, ), one=True)
        if f is None:
            return f
        else:
            return (f['contentType'], f['blobMsg'])

    def saveChatHistory(self, charName: str, msgHistory: list[dict[str, int | str]]) -> None:
        for i in msgHistory:
            self.db.query('insert into chatHistory (charName, role, type, text, timestamp) values (?, ?, ?, ?, ?)',
                          (charName, i['role'], i['type'], i['text'], i['timestamp']))

    def fetchChatHistory(self, charId: int, offset: int = 0) -> list[dict[str, int | str]]:
        # fetch latest 30 days history
        time30days = 60 * 60 * 24 * 30
        data = self.db.query('select * from chatHistory where id = ?, timestamp < ?, timestamp > ? order by timestamp desc',
                             (charId, int(time.time() - offset * time30days), int(time.time() - offset * time30days - time30days)))
        return data

    def getCharacterAvatar(self, charId: int) -> tuple[str, bytes] | None:
        f = self.db.query(
            "select avatar, avatarMime from personalCharacter where id = ?", (charId, ), one=True)
        if f is None:
            return f
        return (f['avatarMime'], f['avatar'])
