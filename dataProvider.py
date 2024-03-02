import sqlite3
import logging
import config
import hashlib
import exceptions
import models
import typing

class ChatHistoryType:
    TEXT = 0
    IMG = 1
    AUDIO = 2
    EMOTION = 3
    INSTRUCTION = 4

class ChatHistoryRole:
    BOT = 0
    USER = 1


# code from XmediaCenter2 project
class databaseObject:
    def __init__(self, dbPath: str) -> None:
        self.db = sqlite3.connect(dbPath, check_same_thread=False)

    def query(self, query, args=(), one=False) -> list[dict[str | typing.Any]] | dict[str | typing.Any]:
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
        self.db.executescript(query)
        self.db.commit()
        return None

    def close(self):
        self.db.close()


class DataProvider:
    def __init__(self, databasePath: str) -> None:
        self.db = databaseObject(databasePath)
        if not self.checkIfInitialized():
            logging.getLogger(__name__).warning('Database is not initialized')

        pass
    
    def checkIfInitialized(self) -> bool:
        if len(self.db.query('select count(*) from sqlite_master where type = "table" and name = ?', ('config', ))) == 0:
            logging.getLogger(__name__).info('Running initialization script')
            with open(f'{config.BLOB_URL}/init.sql', 'r') as file:
                self.db.runScript(file.read())
            
        return len(self.db.query("select count(*) from config")) != 0
    
    def initialize(self, userName: str, password: str, avatarPath: str = f'{config.BLOB_URL}/avatar.png') -> None:
        password = hashlib.md5(f'_@YoimiyaIsMyWaifu_{password}').hexdigest()
        with open(avatarPath, 'rb') as avatar:
            self.db.query('insert into config (userName, passwordSalted, avatar) values (?, ?, ?)', (userName, password, avatar.read()))
            
    def getUserName(self) -> None | str:
        f = self.db.query('select userName from config', one=True)
        if f is None:
            return None
        else:
            return f['userName']
        
    def authenticate(self, pwd: str) -> None | bool:
        f = self.db.query('select passwordSalted from config', one=True)
        if f is None:
            return None
        else:
            return hashlib.md5(f'_@YoimiyaIsMyWaifu_{pwd}').hexdigest() == f['passwordSalted']
        
    def getCharacter(self, id: int) -> None | dict[str, str | int]:
        return self.db.query('select id, charName, exampleChats, prompt, pastMemories, creationTime from personalCharacter where id = ?', (id, ), one=True)
    
    def createCharacter(self, name: str, prompt: str, initalMemory: str, exampleChats: str, avatarPath: str = f'{config.BLOB_URL}/avatar_2.png') -> None:
        with open(avatarPath, 'rb') as file:
            return self.db.query('insert into personalCharacter (charName, prompt, initialMemory, pastMemories, avatar, exampleChats, creationTime) values (?, ?, ?, ?, ?, ?, ?)',
                                 (name, prompt, initalMemory, initalMemory, file.read(), exampleChats, models.DateProider()))
    
    def checkIfCharacterExist(self, name: int) -> bool:
        return bool(len(self.db.query('select count(*) from personalCharacter where name = ?')), (name, ))
    
    def updateCharacter(self, id: int, name: str, prompt: str, pastMemories: str) -> None:
        self.db.query('update personalCharacter set charName = ?, prompt = ?, pastMemories = ? where id = ?',
                      (name, prompt, pastMemories, id))
    
    def getCharacterId(self, name: str) -> int:
        f = self.db.query('select id from personalCharacter where charName = ?', (name, ))
        if f is None:
            raise exceptions.CharacterNotFound(f'{__name__}: Character {name} not found')

    def chatMsgToTextOnly(f: dict[str, str | int]) -> str:
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
        f = self.db.query('select role, type, text from chatHistory where id = ? and text != "(OPT_NO_RESPOND)" order by timestamp desc limit 1', id, one=True)
        return None if f is None else self.chatMsgToTextOnly(f)
            

    def getCharacterList(self) -> int:
        l = self.db.query('select id, charName, creationTime from personalCharacter where id = ?')
        for i in range(len(l)):
            l[i]['latestMsg'] = self.fetchLatestChatHistory(l[i]['id'])
        return l
    
    
    def parseMessageChain(self, chain: list[str]) -> str:
        r = ""
        for i in chain:
            i = i.strip()
            if i.startswith('image:'):
                url = i[i.find(':')+1:]
                r += f'(CMD_IMAGE {models.ImageParsingModel(url)})\n'
            elif i.startswith('audio:'):
                url = i[i.find(':')+1:]
                r += f'(CMD_AUDIO {models.ImageParsingModel(url)})\n'
            else:
                r += i + '\n'
        
        return r
    
    def parseModelResponse(self, plain: str) -> list[str]:
        l: list[str] = plain.strip().split('(CMD_MULTI_MSG)')
        r: list[dict[str | int]] = []
        for i in l:
            i = i.strip()
            if i.startswith('(EMO_'):
                r.append({
                    'type': ChatHistoryType.EMOTION,
                    'text': i,
                    'timestamp': models.TimeProider(),
                })
            elif i == '(CMD_NO_RESPONSE)':
                pass
            elif i == '(CMD_EXIT_NORMAL)' or i == '(CMD_EXIT_ROLE)':
                r.append({
                    'type': ChatHistoryType.INSTRUCTION,
                    'text': i,
                    'timestamp': models.TimeProider(),
                })
            else:
                r.append({
                    'type': ChatHistoryType.TEXT,
                    'text': i,
                    'timestamp': models.TimeProider(),
                })

        return r