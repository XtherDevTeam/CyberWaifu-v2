import re
import threading

from numpy import char
from sympy import rem
import dataProvider
import memory
import uuid
import time
import instance
import exceptions
import random

from models import EmojiToStickerInstrctionModel, TokenCounter

import emoji

def removeEmojis(text):
    return emoji.replace_emoji(text, '')


class chatbotManager:
    def __init__(self, dProvider: dataProvider.DataProvider) -> None:
        self.pool = {}
        self.dataProvider = dProvider
        self.clearTh = threading.Thread(
            target=self.clearSessonThread, args=())
        self.clearTh.start()

    def createSession(self, charName: str) -> str:
        # chat session reusing
        for i in self.pool.keys():
            if self.pool[i]['charName'] == charName:
                return i

        sessionName = uuid.uuid4().hex
        sessionChatbot = instance.Chatbot(memory.Memory(
            self.dataProvider, charName), self.dataProvider.getUserName())
        self.pool[sessionName] = {
            'expireTime': time.time() + 60 * 5,
            'bot': sessionChatbot,
            'history': [],
            'charName': charName
        }

        return sessionName

    def getSession(self, sessionName: str, doRenew: bool = True) -> instance.Chatbot:
        if sessionName in self.pool:
            r: instance.Chatbot = self.pool[sessionName]['bot']
            if doRenew:
                self.pool[sessionName]['expireTime'] = time.time() + 60 * 5
                print('Session renewed: ',
                      self.pool[sessionName]['expireTime'])
            return r
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def getSessionHistory(self, sessionName: str) -> list[dict[str, str | int | bool]]:
        if sessionName in self.pool:
            r: list[dict[str, str | int | bool]
                    ] = self.pool[sessionName]['history']
            return r
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def appendToSessionHistory(self, sessionName: str, newMsg: list[dict[str, str | int | bool]]) -> None:
        if sessionName in self.pool:
            self.pool[sessionName]['history'] += newMsg
            return None
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def beginChat(self, sessionName: str, msgChain: list[str]) -> list[dict[str, str | int | bool]]:
        if sessionName in self.pool:
            f = self.dataProvider.parseMessageChain(msgChain)
            self.appendToSessionHistory(sessionName, f)

            plain = self.getSession(
                sessionName).begin(self.dataProvider.convertMessageHistoryToModelInput(f))

            result = []

            print('TTS available: ', 'True' if (TokenCounter(plain) < 621 and self.getSession(
                sessionName).memory.getCharTTSServiceId() != 0) else 'False')
            if TokenCounter(plain) < 621 and self.getSession(sessionName).memory.getCharTTSServiceId() != 0 and random.randint(0, 1) == 0:
                # remove all emojis in `plain`
                plain = removeEmojis(plain)

                result = self.dataProvider.convertModelResponseToAudio(
                    self.getSession(
                        sessionName).memory.getCharTTSServiceId(),
                    self.dataProvider.parseModelResponse(plain),
                    # self.getSession(sessionName).memory.getAvailableStickers()
                )
            else:
                plain = EmojiToStickerInstrctionModel(plain, ''.join(
                    f'({i}) ' for i in self.getSession(sessionName).getAvailableStickers()))
                for i in self.getSession(sessionName).getAvailableStickers():
                    # fuck unicode parentheses
                    plain = plain.replace(f'（{i}）', f'({i})')
                result = self.dataProvider.parseModelResponse(plain)

            self.appendToSessionHistory(sessionName, result)

            self.dataProvider.saveChatHistory(
                self.pool[sessionName]['charName'], f + result)
            return result
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def sendMessage(self, sessionName: str, msgChain: list[str]) -> list[dict[str, str | int | bool]]:
        if sessionName in self.pool:
            f = self.dataProvider.parseMessageChain(msgChain)
            self.appendToSessionHistory(sessionName, f)

            result = None
            retries = 0
            while result == None:
                try:
                    plain = self.getSession(
                        sessionName).chat(userInput=self.dataProvider.convertMessageHistoryToModelInput(f))

                    if TokenCounter(plain) < 621 and self.getSession(sessionName).memory.getCharTTSServiceId() != 0 and random.randint(0, 1) == 0:
                        # remove all emojis in `plain`
                        plain = removeEmojis(plain)

                        result = self.dataProvider.convertModelResponseToAudio(
                            self.getSession(
                                sessionName).memory.getCharTTSServiceId(),
                            self.dataProvider.parseModelResponse(plain),
                            # self.getSession(sessionName).memory.getAvailableStickers()
                        )
                    else:
                        plain = EmojiToStickerInstrctionModel(plain, ''.join(
                            f'({i}) ' for i in self.getSession(sessionName).getAvailableStickers()))

                        result = self.dataProvider.parseModelResponse(plain)

                except Exception as e:
                    retries += 1
                    if retries > dataProvider.config.MAX_CHAT_RETRY_COUNT:
                        raise exceptions.MaxRetriesExceeded(
                            f'{__name__}: Invalid response. Max retries exceeded.')
                    continue
            self.appendToSessionHistory(sessionName, result)
            self.dataProvider.saveChatHistory(
                self.pool[sessionName]['charName'], f + result)
            return result
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def terminateSession(self, sessionName: str) -> None:
        if sessionName in self.pool:
            charName = self.getSession(sessionName, False).memory.getCharName()
            self.getSession(sessionName, False).terminateChat()
            del self.pool[sessionName]
            print(f'Terminated session {sessionName}')
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def clearSessonThread(self) -> None:
        while True:
            for i in [k for k in self.pool.keys()]:
                print(i, time.time(), self.pool[i]['expireTime'])
                if time.time() > self.pool[i]['expireTime']:
                    self.terminateSession(i)

            time.sleep(1 * 60)
