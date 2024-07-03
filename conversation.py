"""
conversation.py
Provides class ConversationMemory
"""

import config
import models
import memory
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


class ConversationMemory:
    """
    ConversationMemory
    accept userName, and character memory object, and initialize converation history for chatbot instance
    
    Attributes:
        memory: list of messages in conversation
        userName: user name of the conversation
        char: character memory object for the conversation
    
    
    Methods:
        getConversation: return the conversation history
        storeUserInput: store user input message in conversation history
        storeBotInput: store bot input message in conversation history
    """

    def __init__(self, userName, char: memory.Memory) -> None:
        self.memory = []
        self.userName = userName
        self.char = char

    def getConversation(self) -> list[(HumanMessage | AIMessage | SystemMessage)]:
        return self.memory

    def storeUserInput(self, input: HumanMessage) -> str:
        self.memory.append(input)

    def storeBotInput(self, input: AIMessage) -> None:
        self.memory.append(input)
            
