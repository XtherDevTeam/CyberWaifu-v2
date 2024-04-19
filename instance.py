from re import I
import models
import config
import memory
import conversation
import chatModel
from langchain_core.messages import SystemMessage, HumanMessage


class Chatbot:
    def __init__(self, memory: memory.Memory, userName: str) -> None:
        self.llm = models.ChatModelProvider(memory.createCharPromptFromCharacter(userName))
        self.memory = memory
        self.userName = userName
        self.inChatting = False
        self.conversation = conversation.ConversationMemory(userName, self.memory)

    def __enter__(self):
        return None

    def switchUser(self, name: str) -> None:
        if self.inChatting:
            print('Unable to perform this action: Character is chatting!')
        else:
            self.userName = name

    def getRefText(self, userInput: None | list[dict[str, str]]) -> str:
        r = ""

        for i in userInput:
            if i['content_type'] == 'text':
                r += i['content'] + "\n"
            elif i['content_type'] =='image':
                r += f'(image {models.ImageParsingModel(i["content"])})\n'

        return r

    def begin(self, userInput: None | list[dict[str, str]]) -> str:
        if userInput is not None or userInput == '(OPT_NO_RESPOND)':
            self.conversation.storeUserInput(chatModel.HumanMessage(chatModel.HumanMessage(self.getRefText(userInput))))

        msg = self.llm.initiate(userInput)
        self.conversation.storeBotInput(chatModel.AIMessage(msg))
        print(msg)
        return msg

    def getAvailableStickers(self) -> list[str]:
        return [i['name'] for i in self.memory.getAvailableStickers()]

    def chat(self, userInput: list[dict[str, str]]) -> str:
        self.conversation.storeUserInput(chatModel.HumanMessage(self.getRefText(userInput)))
        msg = self.llm.chat(userInput)
        self.conversation.storeBotInput(chatModel.AIMessage(msg))
        print(msg)
        return msg

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
