import mimetypes
from re import I
import models
import chatModel
import config
import memory
import conversation
import chatModel
from langchain_core.messages import SystemMessage, HumanMessage
import google.generativeai as genai
import google.ai.generativelanguage as glm


class Chatbot:
    def __init__(self, memory: memory.Memory, userName: str) -> None:
        self.llm = models.ChatModelProvider(
            memory.createCharPromptFromCharacter(userName))
        self.memory = memory
        self.userName = userName
        self.inChatting = False
        self.conversation = conversation.ConversationMemory(
            userName, self.memory)

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
            elif i['content_type'] == 'image':
                r += f'(image {models.ImageParsingModel(i["content"])})\n'

        return r

    def begin(self, userInput: None | list[dict[str, str]]) -> str:
        if userInput is not None or userInput == '(OPT_NO_RESPOND)':
            self.conversation.storeUserInput(chatModel.HumanMessage(
                chatModel.HumanMessage(self.getRefText(userInput))))

        modelInput = self.convertMessageListToInput(userInput)

        msg = self.llm.initiate(modelInput)
        self.conversation.storeBotInput(chatModel.AIMessage(msg))
        print(msg)
        return msg

    def getAvailableStickers(self) -> list[str]:
        return [i['name'] for i in self.memory.getAvailableStickers()]

    def convertMessageToInput(self, message: dict[str, str]) -> str | glm.File:
        print(message)
        if message['content_type'] == 'text':
            return message['content']
        elif message['content_type'] == 'image':
            mime, binary = self.memory.dataProvider.getAttachment(
                message['content'])

            fp = self.memory.dataProvider.tempFilePathProvider(
                mimetypes.guess_extension(mime))
            with open(fp, 'wb+') as f:
                f.write(binary)

            return genai.upload_file(fp, mime_type=mime)
        elif message['content_type'] == 'audio':
            mime, binary = self.memory.dataProvider.getAttachment(
                message['content'])

            fp = self.memory.dataProvider.tempFilePathProvider('m4a')
            with open(fp, 'wb+') as f:
                f.write(binary)

            return genai.upload_file(fp, mime_type=mime)
        else:
            raise ValueError(f'{__name__}: Unknown message type: {
                message["type"]}')

    def convertMessageListToInput(self, messages: list[dict[str, str]]) -> list[str | glm.File]:
        return [self.convertMessageToInput(i) for i in messages]

    def chat(self, userInput: list[dict[str, str]]) -> str:
        self.conversation.storeUserInput(
            chatModel.HumanMessage(self.getRefText(userInput)))

        modelInput = self.convertMessageListToInput(userInput)

        msg = self.llm.chat(modelInput)
        self.conversation.storeBotInput(chatModel.AIMessage(msg))
        print(msg)
        return msg

    def termination(self) -> None:
        summary = self.llm.chat(f'Ignore the previous output format, summarize this conversation IN A FORM OF DIARY in FIRST-PERSON narration as {self.memory.getCharName()} in accordance with the personality and stories of {self.userName}. Starts with `On, {models.TimeProider()}`')
        self.memory.storeMemory(self.userName, summary)

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
