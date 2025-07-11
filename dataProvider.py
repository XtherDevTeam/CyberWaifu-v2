import json
import mimetypes
import re
import sqlite3
import logging
import time
from AIDubMiddlewareAPI import AIDubMiddlewareAPI
from GPTSoVits import GPTSoVitsAPI
import config
import hashlib
import exceptions
import logger
import models
import typing
import uuid
import threading
import os
import chatModel
import langchain_core.messages

import tools


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
        VOICE_CHAT: Voice chat message entry.
    """
    TEXT = 0
    IMG = 1
    AUDIO = 2
    EMOTION = 3
    INSTRUCTION = 4
    VOICE_CHAT = 5


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
        self.lock = threading.Lock()

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

        with self.lock:
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

        convertMessageHistoryToModelInput(chain):
            Convert a message history chain to model input format.

        saveAudioAttachment(file, mime):
            Save an audio attachment to the database.

        saveImageAttachment(file, mime):
            Save an image attachment to the database.

        getAttachment(attachmentId):
            Retrieve an attachment from the database.

        saveChatHistory(charName, msgHistory):
            Save chat history to the database.

        fetchChatHistory(charId, offset):
            Fetch chat history for a character with optional offset.

        getCharacterAvatar(charId):
            Retrieve a character's avatar from the database.

        updateCharacterAvatar(charId, image):
            Update a character's avatar in the database.

        updateAvatar(image):
            Update the user's avatar in the database.

        getAvatar():
            Retrieve the user's avatar from the database.

        createStickerSet(name):
            Create a new sticker set.

        renameStickerSet(setId, newSetName):
            Rename an existing sticker set.

        addSticker(setId, stickerName, sticker):
            Add a sticker to a sticker set.

        deleteSticker(id):
            Delete a sticker from a sticker set.

        deleteStickerSet(name):
            Delete a sticker set and its associated stickers.

        getSticker(setId, name):
            Retrieve a specific sticker from a sticker set.

        getStickerSetList():
            Retrieve a list of all sticker sets with preview information.

        getStickerSetInfo(setId):
            Retrieve detailed information about a specific sticker set.

        getStickerList(setId):
            Retrieve a list of stickers within a specific sticker set.

        parseAudio(audioPath):
            Parse audio from a given path and return text.

        tempFilePathProvider(extension):
            Generate a temporary file path with the specified extension.

        getStickerInfo(setId, name):
            Retrieve detailed information about a specific sticker.

        getSticker(setId, name):
            Retrieve a specific sticker from a sticker set.

        getStickerSetList():
            Retrieve a list of all sticker sets with preview information.

        getStickerSetInfo(setId):
            Retrieve detailed information about a specific sticker set.
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
        try:
            return len(self.db.query("select 1 from config")) != 0
        except:
            logging.getLogger(__name__).info('Running initialization script')
            with open(f'{config.BLOB_URL}/init.sql', 'r') as file:
                self.db.runScript(file.read())

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

        self.db.query('insert into config (userName, passwordSalted, avatar, avatarMime) values (?, ?, ?, ?)',
                      (userName, password, avatar, 'image/png'))

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

    def getUserPersona(self) -> None | str:
        """
        Get the persona of the user from the database.

        Returns:
            None | str: Persona if exists, None otherwise.
        """
        f = self.db.query('select persona from config', one=True)
        if f is None:
            return None
        else:
            return f['persona']

    def updateUserPersona(self, persona: str) -> None:
        """
        Update the persona of the user in the database.

        Args:
            persona (str): New persona.
        """
        self.db.query('update config set persona = ?', (persona, ))
        
    
    def getGPTSoVITsMiddleware(self) -> str:
        """
        Get the GPTSoVITs middleware API key from the database.

        Returns:
            str: GPTSoVITs middleware API url.
        """
        f = self.db.query('select gptSoVitsMiddleware from config', one=True)
        if f is None:
            return ''
        else:
            return f['gptSoVitsMiddleware']
        
    
    def setGPTSoVITsMiddleware(self, middlewareUrl: str) -> None:
        """
        Set the GPTSoVITs middleware API key in the database.

        Args:
            middlewareUrl (str): GPTSoVITs middleware API url.
        """
        self.db.query('update config set gptSoVitsMiddleware = ?', (middlewareUrl, ))

    

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
        return self.db.query('select id, charName, emotionPack, exampleChats, charPrompt, pastMemories, creationTime, ttsServiceId, AIDubUseModel from personalCharacter where id = ?', (id, ), one=True)

    def createCharacter(self, name: str, useTTSModel: str, useStickerSet: int, prompt: str, initalMemory: str, exampleChats: str, avatarPath: str = f'{config.BLOB_URL}/avatar_2.png') -> None:
        """
        Create a new character in the database.

        Args:
            name (str): Character name.
            useTTSModel (str): TTS model to use.
            useStickerSet (int): Sticker set ID.
            prompt (str): Character prompt.
            initalMemory (str): Initial memory for the character.
            exampleChats (str): Example chats for the character.
            avatarPath (str, optional): Path to the character's avatar. Defaults to f'{config.BLOB_URL}/avatar_2.png'.
        """
        with open(avatarPath, 'rb') as file:
            return self.db.query('insert into personalCharacter (charName, AIDubUseModel, emotionPack, charPrompt, initialMemories, pastMemories, avatar, exampleChats, creationTime) values (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                                 (name, useTTSModel, useStickerSet, prompt, initalMemory, initalMemory, file.read(), exampleChats, tools.DateProvider()))

    def checkIfCharacterExist(self, name: int) -> bool:
        """
        Check if a character with the given name exists in the database.

        Args:
            name (int): Character name.

        Returns:
            bool: True if character exists, False otherwise.
        """
        return bool(len(self.db.query('select count(*) from personalCharacter where name = ?')), (name, ))

    def updateCharacter(self, id: int, name: str, useTTSModel: str, useStickerSet: int, prompt: str, pastMemories: str, exampleChats: str) -> None:
        """
        Update character information in the database.

        Args:
            id (int): Character ID.
            useTTSModel (str): TTS model to use.
            name (str): New character name.
            prompt (str): New character prompt.
            pastMemories (str): New past memories for the character.
        """
        print(useTTSModel)
        self.db.query('update personalCharacter set charName = ?, AIDubUseModel = ?, emotionPack = ?, charPrompt = ?, pastMemories = ?, exampleChats = ? where id = ?',
                      (name, useTTSModel, useStickerSet, prompt, pastMemories, exampleChats, id))

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
            'select id from personalCharacter where charName = ?', (name, ), one=True)
        if f is None:
            raise exceptions.CharacterNotFound(
                f'{__name__}: Character {name} not found')

        return f['id']

    def chatMsgToTextOnly(self, f: dict[str, str | int]) -> str:
        """
        Convert a chat message to text-only representation.

        Args:
            f (dict[str, str | int]): Chat message information.

        Returns:
            str: Text-only representation of the chat message.
        """
        trans = {'angry': '😡', 'guility': '🙁',
                 'happy': '😊', 'sad': '😢', 'awkward': '😳'}
        for i in trans:
            f['text'] = f['text'].replace(f'({i})', trans[i])

        if f['type'] == ChatHistoryType.TEXT:
            return f['text']
        elif f['type'] == ChatHistoryType.IMG:
            return '🌄'
        elif f['type'] == ChatHistoryType.AUDIO:
            return 'Voice'

    def fetchLatestChatHistory(self, id: int) -> str | None:
        """
        Fetch the latest chat history entry for a character.

        Args:
            id (int): Character ID.

        Returns:
            str | None: Latest chat history entry if exists, None otherwise.
        """
        f = self.db.query(
            'select role, type, text from chatHistory where charName = ? and text != "(OPT_NO_RESPOND)" order by timestamp desc limit 1', (self.getCharacter(id)['charName'], ), one=True)
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
                    'timestamp': int(time.time()),
                    'role': 'user'
                })
            elif i.startswith('audio:'):
                url = i[i.find(':')+1:]
                r.append({
                    'type': ChatHistoryType.AUDIO,
                    'text': url,
                    'timestamp': int(time.time()),
                    'role': 'user'
                })
            else:
                r.append({
                    'type': ChatHistoryType.TEXT,
                    'text': i,
                    'timestamp': int(time.time()),
                    'role': 'user'
                })

        return r

    def parseModelResponse(self, plain: str, isRTVC: bool = False) -> list[dict[str | int]]:
        """
        Parses a model response and returns a list of formatted messages.

        Args:
            plain (str): Plain model response.
            isRTVC (bool): Whether the response is from an real-time voice chat or not.

        Returns:
            list[dict[str | int]]: List of formatted messages.
        """

        l: list[str] = [i.strip() for i in plain.strip().split('|<spliter>|')] if isRTVC else [
            i.strip() for i in plain.strip().split('---')]

        # workaround for splitter
        emotion = None
        if isRTVC:
            emotion = l[0][:l[0].find(':') + 1]
            l[0] = l[0][l[0].find(':')+1:]

        r: list[dict[str | int]] = []
        for i in l:
            i = i.strip()
            if i == '':
                continue

            r.append({
                'type': ChatHistoryType.TEXT,
                'text': f'{emotion if emotion is not None and not isRTVC else ""}{i}',
                'timestamp': int(time.time()),
                'role': 'model'
            })

        return r

    def convertMessageHistoryToModelInput(self, chain: list[dict[str, str | int]]) -> list[dict[str, str]]:
        """
        Converts a message history chain to model input format.

        Args:
            chain (list[dict[str, str | int]]): Message history chain.

        Returns:
            list[dict[str, str]]: Message represtation in new api format.
        """
        r = []

        for i in chain:
            if i['type'] == ChatHistoryType.TEXT or i['type'] == ChatHistoryType.EMOTION:
                r.append(chatModel.HumanMessage(i['text'].strip()))
            elif i['type'] == ChatHistoryType.IMG:
                r.append(chatModel.HumanMessage(i['text'], 'image'))
            elif i['type'] == ChatHistoryType.AUDIO:
                r.append(chatModel.HumanMessage(i['text'], 'audio'))

        return r

    def saveAudioAttachment(self, file: bytes, mime: str) -> str:
        """
        Saves an audio attachment to the database.

        Args:
            file (bytes): Audio data.
            mime (str): Mime type of the audio.

        Returns:
            str: ID of the saved attachment.
        """
        id = uuid.uuid4().hex
        self.db.query(
            'insert into attachments (id, timestamp, type, blobMsg, contentType) values (?, ?, ?, ?, ?)', (id, int(time.time()), AttachmentType.AUDIO, file, mime))
        return id

    def saveImageAttachment(self, file: bytes, mime: str) -> str:
        """
        Saves an image attachment to the database.

        Args:
            file (bytes): Image data.
            mime (str): Mime type of the image.

        Returns:
            str: ID of the saved attachment.
        """
        id = uuid.uuid4().hex
        self.db.query(
            'insert into attachments (id, timestamp, type, blobMsg, contentType) values (?, ?, ?, ?, ?)', (id, int(time.time()), AttachmentType.IMG, file, mime))
        return id

    def getAttachment(self, attachmentId: str) -> tuple[str, bytes] | None:
        """
        Retrieves an attachment from the database.

        Args:
            attachmentId (str): ID of the attachment.

        Returns:
            tuple[str, bytes] | None: Tuple containing mime type and data of the attachment if found, None otherwise.
        """
        f = self.db.query(
            'select blobMsg, contentType from attachments where id = ?', (attachmentId, ), one=True)
        if f is None:
            return f
        else:
            return (f['contentType'], f['blobMsg'])

    def saveChatHistory(self, charName: str, msgHistory: list[dict[str, int | str]]) -> None:
        """
        Saves chat history to the database.

        Args:
            charName (str): Character name.
            msgHistory (list[dict[str, int | str]]): List of chat messages.
        """
        for i in msgHistory:
            self.db.query('insert into chatHistory (charName, role, type, text, timestamp) values (?, ?, ?, ?, ?)',
                          (charName, i['role'], i['type'], i['text'], i['timestamp']))

    def fetchChatHistory(self, charId: int, offset: int = 0) -> list[dict[str, int | str]]:
        """
        Fetches chat history for a character with an optional offset.

        Args:
            charId (int): Character ID.
            offset (int, optional): Offset for fetching older chat history. Defaults to 0.

        Returns:
            list[dict[str, int | str]]: List of chat messages.
        """
        # fetch latest 24 history
        time = 24
        charName = self.getCharacter(charId)['charName']

        data = self.db.query(
            "select * from (select * from chatHistory where charName = ? order by timestamp desc limit ?, 24) order by timestamp", (charName, offset * time))
        return data

    def getCharacterAvatar(self, charId: int) -> tuple[str, bytes] | None:
        """
        Retrieves a character's avatar from the database.

        Args:
            charId (int): Character ID.

        Returns:
            tuple[str, bytes] | None: Tuple containing mime type and data of the avatar if found, None otherwise.
        """
        f = self.db.query(
            "select avatar, avatarMime from personalCharacter where id = ?", (charId, ), one=True)
        if f is None:
            return f
        return (f['avatarMime'], f['avatar'])

    def updateCharacterAvatar(self, charId: int, image: tuple[str, bytes]) -> tuple[str, bytes] | None:
        """
        Updates a character's avatar in the database.

        Args:
            charId (int): Character ID.
            image (tuple[str, bytes]): Tuple containing mime type and data of the new avatar.

        Returns:
            tuple[str, bytes] | None: Tuple containing mime type and data of the updated avatar.
        """
        self.db.query("update personalCharacter set avatarMime = ?, avatar = ? where id = ?",
                      (image[0], image[1], charId))

    def updateAvatar(self, image: tuple[str, bytes]):
        """
        Updates the user's avatar in the database.

        Args:
            image (tuple[str, bytes]): Tuple containing mime type and data of the new avatar.
        """
        self.db.query(
            'update config set avatarMime = ?, avatar = ?', (image[0], image[1]))

    def getAvatar(self) -> tuple[str, bytes] | None:
        """
        Retrieves the user's avatar from the database.

        Returns:
            tuple[str, bytes] | None: Tuple containing mime type and data of the avatar if found, None otherwise.
        """
        f = self.db.query(
            "select avatar, avatarMime from config", (), one=True)
        if f is None:
            return f

        return (f['avatarMime'], f['avatar'])

    def createStickerSet(self, name: str) -> None:
        """
        Creates a new sticker set.

        Args:
            name (str): Name of the sticker set.
        """
        self.db.query("insert into stickerSets (setName) values (?)", (name, ))

    def renameStickerSet(self, setId: int, newSetName: str) -> None:
        """
        Renames an existing sticker set.

        Args:
            setId (int): ID of the sticker set.
            newSetName (str): New name for the sticker set.
        """
        self.db.query(
            "update stickerSets set setName = ? where id = ?", (newSetName, setId))

    def addSticker(self, setId: int, stickerName: str, sticker: tuple[str, bytes]) -> None:
        """
        Adds a sticker to a sticker set.

        Args:
            setId (int): ID of the sticker set.
            stickerName (str): Name of the sticker.
            sticker (tuple[str, bytes]): Tuple containing mime type and data of the sticker.
        """
        self.db.query("insert into stickers (setId, name, image, mime) values (?, ?, ?, ?)",
                      (setId, stickerName, sticker[1], sticker[0]))

    def deleteSticker(self, id: str) -> None:
        """
        Deletes a sticker from a sticker set.

        Args:
            id (str): ID of the sticker.
        """
        self.db.query("delete from stickers where id = ?", (id, ))

    def deleteStickerSet(self, name: str) -> None:
        """
        Deletes a sticker set and its associated stickers.

        Args:
            name (str): Name of the sticker set.
        """
        self.db.query("delete from stickerSets where setName = ?", (name, ))
        self.db.query("delete from stickers where setName = ?", (name, ))

    def getSticker(self, setId: int, name: str) -> tuple[str, bytes]:
        """
        Retrieves a specific sticker from a sticker set.

        Args:
            setId (int): ID of the sticker set.
            name (str): Name of the sticker.

        Raises:
            exceptions.StickerNotFound: If the sticker is not found.

        Returns:
            tuple[str, bytes]: Tuple containing mime type and data of the sticker.
        """
        d = self.db.query(
            "select mime, image from stickers where name = ? and setId = ?", (name, setId), one=True)
        if d is None:
            raise exceptions.StickerNotFound(
                f'{__name__}: Sticker {setId} of sticker set {setId} not exist')
        return (d['mime'], d['image'])

    def getStickerSetList(self) -> list[dict[str, str | int]]:
        """
        Retrieves a list of all sticker sets with preview information.

        Returns:
            list[dict[str, str | int]]: List of sticker sets with their IDs, names, and preview sticker names.
        """
        d = self.db.query('select * from stickerSets')
        r = []
        for i in d:
            n = self.db.query(
                'select * from stickers where setId = ? limit 1', (i['id'], ), one=True)
            r.append({
                'id': i['id'],
                'setName': i['setName'],
                'previewSticker': n['name'] if n is not None else 'none'
            })
        return r

    def getStickerSetInfo(self, setId: int) -> dict[str, str | int] | None:
        """
        Retrieves detailed information about a specific sticker set.

        Args:
            setId (int): ID of the sticker set.

        Returns:
            dict[str, str | int] | None: Dictionary containing information about the sticker set if found, None otherwise.
        """
        i = self.db.query(
            'select * from stickerSets where id = ?', (setId, ), one=True)
        if i is None:
            return None
        n = self.db.query(
            'select * from stickers where setId = ? limit 1', (i['id'], ), one=True)
        return {
            'id': i['id'],
            'setName': i['setName'],
            'previewSticker': n['name'] if n is not None else 'none'
        }

    def getStickerList(self, setId: int) -> list[dict[str, str | int]]:
        """
        Retrieves a list of stickers within a specific sticker set.

        Args:
            setId (int): ID of the sticker set.

        Returns:
            list[dict[str, str | int]]: List of stickers with their IDs, set IDs, and names.
        """
        return self.db.query('select id, setId, name from stickers where setId = ?', (setId, ), )

    def parseAudio(self, audioPath: str) -> str:
        """
        Parses audio from a given path and returns text.

        Args:
            audioPath (str): Path to the audio file.

        Returns:
            str: Text representation of the audio content.
        """
        return models.AudioToTextModel(audioPath)

    def tempFilePathProvider(self, extension: str) -> str:
        """
        Generates a temporary file path with the specified extension.

        Args:
            extension (str): File extension.

        Returns:
            str: Temporary file path.
        """
        return config.generateTempPath(extension)

    def addGPTSoVitsService(self, name: str, url: str, description: str, ttsInferYamlPath: str) -> None:
        """
        Adds a new GPT-SoVits service to the database.

        Args:
            name (str): Name of the service.
            url (str): URL of the service.
            description (str): Description of the service.
            ttsInferYamlPath (str): Path to the TTS inference YAML file.
        """

        self.db.query("insert into GPTSoVitsServices (name, url, description, ttsInferYamlPath) values (?,?,?,?)",
                      (name, url, description, ttsInferYamlPath))

    def addGPTSoVitsReferenceAudio(self, serviceId: int, name: str, text: str, path: str, language: str) -> None:
        """
        Adds a new GPT-SoVits reference audio to a GPT-SoVits service.

        Args:
            serviceId (int): ID of the GPT-SoVits service.
            name (str): Name of the reference audio, usually the emotion to represent.
            text (str): Text representation of the reference audio.
            path (str): Path to the audio file.
            language (str): Language of the audio file.
        """

        self.db.query("insert into GPTSoVitsReferenceAudios (serviceId, name, text, path, language) values (?,?,?,?,?)",
                      (serviceId, name, text, path, language))

    def deleteGPTSoVitsReferenceAudio(self, refAudioId: int) -> None:
        """
        Deletes a GPT-SoVits reference audio from a GPT-SoVits service.

        Args:
            refAudioId (int): ID of the reference audio.
        """

        self.db.query("delete from GPTSoVitsReferenceAudios where id = ?",
                      (refAudioId, ))

    def getGPTSoVitsServices(self) -> list[dict[str, str | int]]:
        """
        Retrieves a list of all GPT-SoVits services.

        Returns:
            list[dict[str, str | int]]: List of GPT-SoVits services with their IDs, names, and descriptions.
        """

        return self.db.query('select id, name, description, url, ttsInferYamlPath from GPTSoVitsServices')

    def getGPTSoVitsService(self, serviceId: int) -> dict[str, str | int] | None:
        """
        Retrieves detailed information about a specific GPT-SoVits service.

        Args:
            serviceId (int): ID of the GPT-SoVits service.

        Returns:
            dict[str, str | int] | None: Dictionary containing information about the GPT-SoVits service if found, None otherwise.
        """

        i = self.db.query(
            'select * from GPTSoVitsServices where id = ?', (serviceId, ), one=True)
        if i is None:
            return None

        # retrive reference audios
        j = self.db.query(
            'select * from GPTSoVitsReferenceAudios where serviceId = ?', (serviceId, ))

        return {
            'id': i['id'],
            'name': i['name'],
            'url': i['url'],
            'description': i['description'],
            'ttsInferYamlPath': i['ttsInferYamlPath'],
            'reference_audios': j
        }

    def deleteGPTSoVitsService(self, serviceId: int) -> None:
        """
        Deletes a GPT-SoVits service.

        Args:
            serviceId (int): ID of the GPT-SoVits service.
        """

        self.db.query(
            "delete from GPTSoVitsServices where id = ?", (serviceId, ))

        # bugfix: delete reference audios
        self.db.query(
            "delete from GPTSoVitsReferenceAudios where serviceId = ?", (serviceId, ))

    def updateGPTSoVitsService(self, serviceId: int, name: str, url: str, description: str, ttsInferYamlPath: str) -> None:
        """
        Updates a GPT-SoVits service.

        Args:
            serviceId (int): ID of the GPT-SoVits service.
            name (str): Name of the service.
            url (str): URL of the service.
            description (str): Description of the service.
            ttsInferYamlPath (str): Path to the TTS inference YAML file.
        """

        self.db.query("update GPTSoVitsServices set name = ?, url = ?, description = ?, ttsInferYamlPath = ? where id = ?",
                      (name, url, description, ttsInferYamlPath, serviceId))

    def getAvailableTTSReferenceAudio(self, serviceId: int) -> list[str]:
        """
        Retrieves a list of available reference audio for a GPT-SoVits service.

        Args:
            serviceId (int): ID of the GPT-SoVits service.

        Returns:
            list[str]: List of available reference audio for the GPT-SoVits service.
        """

        return [i['name'] for i in self.db.query(
            "select name from GPTSoVitsReferenceAudios where serviceId = ?", (serviceId, ))]

    def convertModelResponseToTTSInput(self, response: list[dict[str, str]], availableEmotions: list[str]):
        """
        Converts a model response to a TTS input.

        Args:
            response (list[dict[str, str]]): Model response.
            chat_history (list[dict[str, str]]): Chat history.

        Returns:
            list[dict[str, str]]: TTS input.
        """

        for _ in range(config.MAX_CHAT_RETRY_COUNT):
            try:
                prompt = models.PreprocessPrompt(config.TEXT_TO_SPEECH_EMOTION_MAPPING_PROMPT, {
                    'availableEmotions': ', '.join(i['name'] for i in availableEmotions),
                    'messageJSON': json.dumps(response)
                })
                logger.Logger.log(prompt)
                s = models.BaseModelProvider(1).invoke([langchain_core.messages.HumanMessage(
                    prompt
                )]).content

                # force to retrieve json response
                s = s[s.find('['): s.rfind(']')+1]
                logger.Logger.log(s)
                s = json.loads(s)

                for i in s:
                    if i['emotion'] not in [j['name'] for j in availableEmotions]:
                        raise RuntimeError(f'Invalid emotion: {i["emotion"]}')
                return s
            except Exception as e:
                logger.Logger.log(str(e))
                time.sleep(5)
                pass

    def getReferenceAudioByName(self, serviceId: int, name: str):
        """
        Retrieves a reference audio by its name.

        Args:
            serviceId (int): ID of the GPT-SoVits service.
            name (str): Name of the reference audio, usually the emotion to represent.

        Returns:
            dict[str, str] | None: Dictionary containing information about the reference audio if found, None otherwise.
        """

        i = self.db.query(
            'select * from GPTSoVitsReferenceAudios where serviceId = ? and name = ?', (serviceId, name), one=True)
        if i is None:
            return None
        return {
            'id': i['id'],
            'name': i['name'],
            'text': i['text'],
            'path': i['path'],
            'language': i['language']
        }

    def convertModelResponseToAudio(self, serviceId: int, response: list[dict[str, str]]) -> list[dict[str, str]]:
        """
        Converts a model response to audio. Deprecated.

        Args:
            response (list[dict[str, str]]): Model response.

        Returns:
            list[dict[str, str]]: Audio.
        """
        serviceInfo = self.getGPTSoVitsService(serviceId)
        logger.Logger.log(serviceInfo)
        GPTSoVitsEndpoint = GPTSoVitsAPI(
            serviceInfo['url'], serviceInfo['ttsInferYamlPath'])
        logger.Logger.log(response)

        r = self.convertModelResponseToTTSInput(
            response, serviceInfo['reference_audios'])
        result = []

        logger.Logger.log(r)
        for i in r:
            refAudio = self.getReferenceAudioByName(serviceId, i['emotion'])
            if refAudio is None:
                raise exceptions.ReferenceAudioNotFound(
                    f'Could not find reference audio for emotion {i["emotion"]}')

            resp = GPTSoVitsEndpoint.tts(
                refAudio['path'], refAudio['text'], i['text'], refAudio['language'])
            logger.Logger.log(resp.ok, resp.status_code)
            attachment = self.saveAudioAttachment(resp.content, 'audio/aac')
            result.append({
                'type': ChatHistoryType.AUDIO,
                'role': 'model',
                'text': attachment,
                'timestamp': int(time.time()),
            })

        return result


    def convertModelResponseToAudioV2(self, useModel: str, response: list[dict[str, str]]) -> list[dict[str, str]]:
        """
        Converts a model response to audio.

        Args:
            useModel (str): Name of the model to use.
            response (list[dict[str, str]]): Model response.

        Returns:
            list[dict[str, str]]: Audio.
        """
        # i['text']
        result = []

        for i in response:
            API = AIDubMiddlewareAPI(self.getGPTSoVITsMiddleware())
            logger.Logger.log('Using model: ', useModel)
            resp = API.dub(i['text'], useModel)
            attachment = self.saveAudioAttachment(resp.content, 'audio/aac')
            logger.Logger.log(attachment)
            result.append({
                'type': ChatHistoryType.AUDIO,
                'role': 'model',
                'text': attachment,
                'timestamp': int(time.time()),
            })

        return result
    

    def updateUsername(self, username: str) -> None:
        """
        Updates the username of a user.

        Args:
            username (str): New username.
        """

        self.db.query("update config set userName = ?",
                      (username, ))

    def updatePassword(self, password: str) -> None:
        """
        Updates the password of a user.

        Args:          
            password (str): New password.
        """

        password = hashlib.md5(
            f'_@YoimiyaIsMyWaifu_{password}'.encode('utf-8')).hexdigest()

        self.db.query("update config set passwordSalted = ?",
                      (password, ))
        
    def createExtraInfo(self, name: str, description: str, author: str, content: str, enabled: bool = True):
        """
        Create an extra info in database.

        Args:
            name (str): Name of the extra info.
            description (str): Description of the extra info.
            author (str): Author of the extra info.
            content (str): Content of the extra info.
            enabled (bool, optional): Whether the extra info is enabled. Defaults to True.
        """

        self.db.query("insert into extraInfos (name, description, author, content, enabled) values (?,?,?,?,?)",
                      (name, description, author, content, enabled))
        return self.db.query("select last_insert_rowid()")[0]['last_insert_rowid()']

    def getExtraInfo(self, id: int) -> dict[str, str]:
        """
        Get an extra info from database.

        Args:
            id (int): ID of the extra info.

        Returns:
            dict[str, str]: Extra info.
        """
        r = self.db.query(
            "select * from extraInfos where id = ?", (id,), one=True)
        if r is None:
            return None
        return r

    def getExtraInfoList(self) -> list[dict[str, str]]:
        """
        Get all extra info from database.

        Returns:
            list[dict[str, str]]: List of extra info.
        """
        return self.db.query("select name, description, author, enabled, id, content from extraInfos")

    def updateExtraInfo(self, id: int, name: str, description: str, author: str, content: str, enabled: bool):
        """
        Update an extra info in database.

        Args:
            id (int): ID of the extra info.
            name (str): Name of the extra info.
            description (str): Description of the extra info.
            author (str): Author of the extra info.
            content (str): Content of the extra info.
            enabled (bool): Whether the extra info is enabled.
        """
        self.db.query("update extraInfos set name = ?, description = ?, author = ?, content = ?, enabled = ? where id = ?",
                      (name, description, author, content, enabled, id))
        return self.db.query("select last_insert_rowid()")[0]['last_insert_rowid()']

    def deleteExtraInfo(self, id: int):
        """
        Delete an extra info from database.

        Args:
            id (int): ID of the extra info.
        """
        self.db.query("delete from extraInfos where id = ?", (id,))
        return self.getExtraInfoList()

    def createUserScript(self, name: str, author: str, description: str, content: str, enabled: bool = True):
        """
        Create a user script in database.

        Args:
            name (str): Name of the user script.
            author (str): Author of the user script.
            description (str): Description of the user script.
            content (str): Content of the user script.
            enabled (bool, optional): Whether the user script is enabled. Defaults to True.
        """

        self.db.query("insert into userScripts (name, author, description, content, enabled) values (?,?,?,?,?)",
                      (name, author, description, content, enabled))
        return self.db.query("select last_insert_rowid()")[0]['last_insert_rowid()']

    def getUserScript(self, id: int) -> dict[str, str]:
        """
        Get a user script from database.

        Args:
            id (int): ID of the user script.

        Returns:
            dict[str, str]: User script.
        """
        r = self.db.query(
            "select * from userScripts where id = ?", (id,), one=True)
        if r is None:
            return None
        return r

    def getUserScriptList(self) -> list[dict[str, str]]:
        """
        Get all user script from database.

        Returns:
            list[dict[str, str]]: List of user script.
        """
        return self.db.query("select name, enabled, id, content, description, author from userScripts")

    def updateUserScript(self, id: int, name: str, content: str, author: str, description: str, enabled: bool):
        """
        Update a user script in database.

        Args:
            id (int): ID of the user script.
            name (str): Name of the user script.
            content (str): Content of the user script.
            enabled (bool): Whether the user script is enabled.
        """
        self.db.query("update userScripts set name = ?, content = ?, author = ?, description = ?, enabled = ? where id = ?",
                      (name, content, author, description, enabled, id))
        return self.db.query("select last_insert_rowid()")[0]['last_insert_rowid()']

    def deleteUserScript(self, id: int):
        """
        Delete a user script from database.

        Args:
            id (int): ID of the user script.
        """
        self.db.query("delete from userScripts where id = ?", (id,))
        return self.getUserScriptList()
    
    
    def getAllEnabledExtraInfos(self) -> list[dict[str, str]]:
        """
        Get all enabled extra infos from database.

        Returns:
            list[dict[str, str]]: List of enabled extra infos.
        """
        return self.db.query("select name, description, author, content, id from extraInfos where enabled = 1")

    def getAllEnabledUserScripts(self) -> list[dict[str, str]]:
        """
        Get all enabled user scripts from database.

        Returns:
            list[dict[str, str]]: List of enabled user scripts.
        """
        return self.db.query("select name, content, id from userScripts where enabled = 1")
