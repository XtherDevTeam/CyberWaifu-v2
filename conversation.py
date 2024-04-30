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
    @brief accept userName, and character memory object, and initialize converation history for chatbot instance
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
        """
        for i in input.content.split('(OPT_MULTI_CUR_MSG_END)'):
            self.memory.append(AIMessage(i.strip()))
        """
        self.memory.append(input)
            
