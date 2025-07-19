import mimetypes
import os
from pyexpat import model
from re import I
from typing import Any, Optional
import typing
import logger
import models
import chatModel
import config
import memory
import conversation
import chatModel
from langchain_core.messages import SystemMessage, HumanMessage
import google.genai as genai
import google.ai.generativelanguage as glm
import io
import workflowTools
import webFrontend.extensionHandler


class Chatbot:
    def __init__(self, memory: memory.Memory, userName: str, enabled_tools: list[typing.Callable] = workflowTools.AvailableTools(), enabled_user_scripts: list[dict[str, str]] = [], enabled_extra_infos: list[dict[str, str]] = [], rtSession: bool = False) -> None:
        if rtSession:
            logger.Logger.log(
                'Real time session detected, LLM initialization skipped.')
        self.toolsHandler = None if rtSession else webFrontend.extensionHandler.ToolsHandler(
            None, memory.dataProvider, enabled_tools, enabled_user_scripts)
        self._prompt = models.PreprocessPrompt(memory.createCharPromptFromCharacter(userName), {
            'generated_tool_descriptions': self.toolsHandler.generated_tool_descriptions,
            'extra_info': self.toolsHandler.generated_extra_infos
        }) if not rtSession else None
        logger.Logger.log(f'Prompt: {self._prompt}')
        self.llm = None if rtSession else models.ChatModelProvider(
            self._prompt)
        self.memory = memory
        self.userName = userName
        self.inChatting = False
        self.conversation = conversation.ConversationMemory(
            userName, self.memory)
        self.memoryExtractor = conversation.MemoryExtractor(
            self.conversation, self.memory)

        self.toolsHandler.bindLLM(self.llm) if self.toolsHandler else None

    def __enter__(self):
        return None

    def switchUser(self, name: str) -> None:
        if self.inChatting:
            logger.Logger.log(
                'Unable to perform this action: Character is chatting!')
        else:
            self.userName = name

    def begin(self, userInput: None | list[dict[str, str]]) -> str:
        modelInput = self.convertMessageListToInput(userInput)
        self.conversation.storeUserInput({
            'role': 'user',
            'message': i,
        } for i in modelInput)
        referenceMemory = self.memoryExtractor.extractMemory({
            'role': 'user',
            'message': i,
        } for i in modelInput)
        modelInput.append(f"Reference memory: {referenceMemory.strip()}")
        msg = self.toolsHandler.handleRawResponse(
            self.llm.initiate(modelInput))
        self.conversation.storeBotInput(msg)
        self.memoryExtractor.setPendingBotMessage(msg)
        logger.Logger.log(msg)
        return msg

    def getAvailableStickers(self) -> list[str]:
        return [i['name'] for i in self.memory.getAvailableStickers()]

    def convertMessageToInput(self, message: dict[str, str]) -> str | glm.File:
        logger.Logger.log(message)
        if message['content_type'] == 'text':
            return message['content']
        elif message['content_type'] == 'image':
            mime, binary = self.memory.dataProvider.getAttachment(
                message['content'])

            return {
                'data': binary,
                'mime_type': mime
            }
        elif message['content_type'] == 'audio':
            mime, binary = self.memory.dataProvider.getAttachment(
                message['content'])

            return {
                'data': binary,
                'mime_type': mime
            }
        else:
            raise ValueError(f'{__name__}: Unknown message type: {
                message["type"]}')

    def convertMessageListToInput(self, messages: list[dict[str, str]]) -> list[str | glm.File]:
        return [self.convertMessageToInput(i) for i in messages]

    def chat(self, userInput: list[dict[str, str]]) -> str:
        modelInput = self.convertMessageListToInput(userInput)
        self.conversation.storeUserInput({
            'role': 'user',
            'message': i,
        } for i in modelInput)
        referenceMemory = self.memoryExtractor.extractMemory({
            'role': 'user',
            'message': i,
        } for i in modelInput)
        modelInput.append(f"Reference memory: {referenceMemory.strip()}")
        msg = self.toolsHandler.handleRawResponse(self.llm.chat(modelInput))
        self.conversation.storeBotInput(msg)
        self.memoryExtractor.setPendingBotMessage(msg)
        logger.Logger.log(msg)
        return msg

    def termination(self) -> None:
        summary = self.llm.chat(f'EOF')
        self.memory.storeMemory(self.userName, summary)
        
    def terminationWithSummary(self, summary: str) -> None:
        self.memory.storeMemory(self.userName, summary)
        
    def terminateChatWithSummary(self, summary: str) -> None:
        self.inChatting = False
        self.terminationWithSummary(summary)

    def terminationWithSummary(self, summary: str) -> None:
        self.memory.storeMemory(self.userName, summary)

    def terminateChatWithSummary(self, summary: str) -> None:
        self.inChatting = False
        self.terminationWithSummary(summary)

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
