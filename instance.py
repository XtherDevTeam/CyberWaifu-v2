import models
import config
import memory
import conversation
from langchain_core.messages import SystemMessage, HumanMessage


class Chatbot:
    def __init__(self, memory: memory.Memory, userName: str) -> None:
        self.llm = models.BaseModelProvider()
        self.memory = memory
        self.userName = userName
        self.inChatting = False
        self.conversation = conversation.ConversationMemory(userName, self.memory, SystemMessage(
            self.memory.createCharPromptFromCharacter(self.userName)
        ))

    def __enter__(self):
        return None

    def switchUser(self, name: str) -> None:
        if self.inChatting:
            print('Unable to perform this action: Character is chatting!')
        else:
            self.userName = name

    def begin(self, userInput: None | str) -> str:
        if userInput is not None or userInput == '(OPT_NO_RESPOND)':
            self.conversation.storeUserInput(HumanMessage(userInput))

        msg = self.llm.invoke(self.conversation.getConversation())
        self.conversation.storeBotInput(msg)
        print(msg.content)
        return msg.content

    def chat(self, userInput: str) -> str:
        self.conversation.storeUserInput(HumanMessage(userInput))
        msg = self.llm.invoke(self.conversation.getConversation())
        self.conversation.storeBotInput(msg)
        print(msg.content)
        return msg.content

    def termination(self) -> None:
        self.memory.storeMemory(self.userName, self.conversation.summarize())
        
    def terminateChat(self, force=False) -> None:
        self.inChatting = False
        if not force:
            self.termination()

    def __exit__(self, type, value, traceback) -> None:
        self.inChatting = False
        if value is None:
            self.termination()
        else:
            # ignoring the process
            pass
