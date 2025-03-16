"""
conversation.py
Provides class ConversationMemory
"""

import chatModel
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

    def getConversation(self) -> list[(HumanMessage | AIMessage | SystemMessage | str)]:
        return self.memory

    def storeUserInput(self, input: HumanMessage) -> str:
        self.memory.append({'role': 'user', 'message': input})

    def storeBotInput(self, input: AIMessage) -> None:
        self.memory.append({'role': 'bot', 'message': input})
            

class MemoryExtractor:
    """
    A class for extracting memory from a chat session.
    """

    def __init__(self, conversation: ConversationMemory, memory: memory.Memory) -> None:
        self.chat_session = conversation
        self.memory = memory
        self.llm = chatModel.ChatGoogleGenerativeAI(config.USE_LEGACY_MODEL, temperature=0.9, system_prompt=self.getPrompt(), tools=[])
        self.isInitiated = False
        
        
    def getPrompt(self) -> str:
        """
        Returns the prompt for the memory extraction.
        """
        prompt = models.PreprocessPrompt(config.MEMORY_EXTRACTION_PROMPT, {
            'charName': self.memory.getCharName(),
            'memories': self.memory.getPastMemories(),
            'userName': self.chat_session.userName
        })
        return prompt
        
        
    
    def extractMemory(self, messages: list[dict[str, str]]) -> str:
        """
        Extracts memory from the chat session.
        
        Parameters:
            messages: the result of convertMessageListToInput method
        
        Returns:
            the extracted memory as a string
        """
        # Extract the memory from the chat session
        memory_list = []
        for message in messages:
            if message['role'] == 'user':
                memory_list.append(f'{self.chat_session.userName}: ')
                memory_list.append(message['message'])
            elif message['role'] == 'bot':
                memory_list.append(f'{self.memory.getCharName()}: ')
                memory_list.append(message['message'])
        
        res = self.llm.chat(memory_list) if self.isInitiated else self.llm.initiate(memory_list)
        self.isInitiated = True
        return res
    