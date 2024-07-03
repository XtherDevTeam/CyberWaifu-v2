"""
memory.py
@biref Provides a interface to access and interact with multi-character's memories.    
"""

import os
import json
import config
import logger
import models
import dataProvider
import tools


class Memory:
    """
    @biref Provides a interface to access and interact with multi-character's memories.
    """

    def __init__(self, dProvider: dataProvider.DataProvider, char: str, rtSession: bool = False):
        # create if not exist
        self.dataProvider = dProvider
        self.rtSession = rtSession
        # read character messages
        logger.Logger.log(char, self.dataProvider.getCharacterId(char), '114514')
        self.char = self.dataProvider.getCharacter(
            self.dataProvider.getCharacterId(char))

    def getExampleChats(self) -> str:
        return self.char['exampleChats']

    def getCharName(self) -> str:
        return self.char['charName']

    def getPastMemories(self) -> str:
        return self.char['pastMemories']

    def getCharPrompt(self) -> str:
        return self.char['charPrompt']
    
    def getCharTTSServiceId(self) -> int:
        return self.char['ttsServiceId']

    def getAvailableStickers(self) -> list[dict[str, str | int]]:
        return self.dataProvider.getStickerList(self.char['emotionPack'])

    def storeCharPrompt(self, prompt: str) -> None:
        self.char['charPrompt'] = prompt
        self.save()
        
    def getCharStickerSet(self) -> int:
        return self.char['emotionPack']
    
    def getCharExampleChats(self) -> int:
        return self.char['exampleChats']

    def save(self) -> None:
        self.dataProvider.updateCharacter(self.dataProvider.getCharacterId(
            self.getCharName()), self.getCharName(), self.getCharTTSServiceId(), self.getCharStickerSet(), self.getCharPrompt(), self.getPastMemories(), exampleChats=self.getExampleChats())

    def storeMemory(self, userName: str, conversation: str) -> None:
        self.char['pastMemories'] = self.char['pastMemories'].strip() + \
            '\n' + conversation
        if models.TokenCounter(self.char['pastMemories']) > config.MEMORY_SUMMARIZING_LIMIT:
            self.char['pastMemories'] = models.MemorySummarizingModel(
                self.getCharName(), self.char['pastMemories']).content
        self.save()

    def createCharPromptFromCharacter(self, userName):
        if self.rtSession:
            # TODO: implement real-time prompt generation
            return models.PreprocessPrompt(config.VOICE_CHAT_INITIAL_PROMPT, {
                'charName': self.getCharName(),
                'userName': userName,
                'datePrompt': tools.TimeProvider(),
                'charPrompt': self.getCharPrompt(),
                'memoryPrompt': self.getPastMemories(),
                'exampleChats': self.getExampleChats()
            })
        else:
            availableStickers = ''
            for i in self.getAvailableStickers():
                availableStickers += f'({i['name']}), '
            availableStickers = availableStickers[0: -2]
            return models.PreprocessPrompt(config.INITIAL_PROMPT, {
                'charName': self.getCharName(),
                'userName': userName,
                'datePrompt': tools.TimeProvider(),
                'charPrompt': self.getCharPrompt(),
                'memoryPrompt': self.getPastMemories(),
                'exampleChats': self.getExampleChats(),
                'availableStickers': availableStickers
            })
