"""
memory.py
@biref Provides a interface to access and interact with multi-character's memories.    
"""

import os
import json
import config
import models


class Memory:
    """
    __init__ function provides a constructor for this class
    @param char the character name that storage in `characters` directory
    @param user the user presented in the memories and conversation
    @param createIfNotExist decide whether to create a new character when this character not exist
    """

    def __init__(self, char: str, createIfNotExist: bool = False):
        # create if not exist
        self.path = os.path.join(config.CHARACTERS_PATH, char)
        if createIfNotExist and not os.path.exists(self.path):
            with open(self.path, 'w+') as file:
                file.write(json.dumps({
                    'charName': char,
                    'pastMemories': '',
                    'charPrompt': '',
                    'exampleChats': '',
                }))
        # read character messages
        with open(self.path, 'r') as file:
            self.char = json.loads(file.read())

    def getExampleChats(self) -> str:
        return self.char['exampleChats']

    def getCharName(self) -> str:
        return self.char['charName']

    def getPastMemories(self) -> str:
        return self.char['pastMemories']

    def getCharPrompt(self) -> str:
        return self.char['charPrompt']

    def storeCharPrompt(self, prompt: str) -> None:
        self.char['charPrompt'] = prompt
        self.save()

    def save(self) -> None:
        with open(self.path, 'w') as file:
            file.write(json.dumps(self.char))

    def storeMemory(self, userName: str, conversation: str) -> None:
        self.char['pastMemories'] = models.MemoryMergingModel(
            userName, self.getCharName(), conversation, self.getPastMemories()).content
        self.save()

    def createCharPromptFromCharacter(self, userName):
        return models.PreprocessPrompt(config.INITIAL_PROMPT, {
            'charName': self.getCharName(),
            'userName': userName,
            'datePrompt': models.TimeProider(),
            'charPrompt': self.getCharPrompt(),
            'memoryPrompt': self.getPastMemories(),
            'exampleChats': self.getExampleChats()
        })
