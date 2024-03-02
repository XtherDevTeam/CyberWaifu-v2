import threading
import dataProvider
import memory
import uuid
import time
import instance
import exceptions


class chatbotManager:
    def __init__(self, dProvider: dataProvider.DataProvider) -> None:
        self.pool = {}
        self.dataProvider = dProvider
        self.clearTh = threading.Thread(
            target=self.clearSessonThread, args=(self, ))
        self.clearTh.run()

    def createSession(self, charName: str) -> str:
        sessionName = uuid.uuid4().hex
        sessionChatbot = instance.Chatbot(memory.Memory(
            charName, False), self.dataProvider.getUserName())
        self.pool[sessionName] = {
            'expireTime': time.time() + 60 * 10,
            'bot': sessionChatbot,
            'history': []
        }

    def getSession(self, sessionName: str) -> instance.Chatbot:
        if sessionName in self.pool:
            r: instance.Chatbot = self.pool[sessionName]['bot']
            self.pool[sessionName]['expireTime'] = time.time() + 60 * 10
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
            self.appendToSessionHistory(f)
            result = self.dataProvider.parseModelResponse(self.getSession(
                sessionName).begin(self.dataProvider.convertMessageHistoryToModelInput(f)))
            self.appendToSessionHistory(result)
            return result
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def sendMessage(self, sessionName: str, msgChain: list[str]) -> list[dict[str, str | int | bool]]:
        if sessionName in self.pool:
            f = self.dataProvider.parseMessageChain(msgChain)
            self.appendToSessionHistory(f)
            result = self.dataProvider.parseModelResponse(self.getSession(
                sessionName).chat(self.dataProvider.convertMessageHistoryToModelInput(f)))
            self.appendToSessionHistory(result)
            return result
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def terminateSession(self, sessionName: str) -> None:
        if sessionName in self.pool:
            self.pool[sessionName]['bot'].terminateChat()
            del self.pool[sessionName]
        else:
            raise exceptions.SessionNotFound(
                f'{__name__}: Session {sessionName} not found or expired')

    def clearSessonThread(self) -> None:
        while True:
            for i in self.pool.keys():
                if time.time() > self.pool[i]['expireTime']:
                    self.terminateSession(i)

            time.sleep(5 * 60)
