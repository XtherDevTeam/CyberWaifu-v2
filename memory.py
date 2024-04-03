"""
memory.py
@biref Provides a interface to access and interact with multi-character's memories.    
"""

import os
import json
import config
import models
import dataProvider


class Memory:
    """
    __init__ function provides a constructor for this class
    @param dProvider dataProvider object
    @param char the character name
    """

    def __init__(self, dProvider: dataProvider.DataProvider, char: str):
        # create if not exist
        self.dataProvider = dProvider
        # read character messages
        print(char, self.dataProvider.getCharacterId(char), '114514')
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

    def getAvailableStickers(self) -> list[dict[str, str | int]]:
        return self.dataProvider.getStickerList(self.char['emotionPack'])

    def storeCharPrompt(self, prompt: str) -> None:
        self.char['charPrompt'] = prompt
        self.save()

    def save(self) -> None:
        self.dataProvider.updateCharacter(self.dataProvider.getCharacterId(
            self.getCharName()), self.getCharName(), self.getCharPrompt(), self.getPastMemories())

    def storeMemory(self, userName: str, conversation: str) -> None:
        self.char['pastMemories'] = self.char['pastMemories'].strip() + \
            '\n' + conversation
        if models.TokenCounter(self.char['pastMemories']) > config.MEMORY_SUMMARIZING_LIMIT:
            self.char['pastMemories'] = models.MemorySummarizingModel(
                self.getCharName(), self.char['pastMemories']).content
        self.save()

    def createCharPromptFromCharacter(self, userName):
        availableStickers = ''
        for i in self.getAvailableStickers():
            availableStickers += f'({i['name']}), '
        availableStickers = availableStickers[0: -2]
        return models.PreprocessPrompt(config.INITIAL_PROMPT, {
            'charName': self.getCharName(),
            'userName': userName,
            'datePrompt': models.TimeProider(),
            'charPrompt': self.getCharPrompt(),
            'memoryPrompt': self.getPastMemories(),
            'exampleChats': self.getExampleChats(),
            'availableStickers': availableStickers
        })
