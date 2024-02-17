"""
conversation.py
Provides packages for model operating
"""

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from google.generativeai.types.safety_types import HarmBlockThreshold, HarmCategory
import config
import time

# No need to handle by users, so not in config.py
MODEL_SAFETY_SETTING = {
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
}


def TimeProider() -> str:
    return time.strftime('%Y-%m-%d %I:%M', time.localtime())


def DateProider() -> str:
    return time.strftime('%Y-%m-%d', time.localtime())


def PreprocessPrompt(originalPrompt: str, tVars):
    for i in tVars:
        originalPrompt = originalPrompt.replace('{{' + i + '}}', tVars[i])

    return originalPrompt


def BaseModelProvider() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=config.USE_MODEL, convert_system_message_to_human=True,
        safety_settings=MODEL_SAFETY_SETTING)


def MemoryMergingModel(userName: str, charName: str, summary: str, pastMemories: str) -> AIMessage:
    llm = BaseModelProvider()
    preprocessed = PreprocessPrompt(
        config.MEMORY_MERGING_PROMPT,
        {
            'userName': userName,
            'charName': charName,
            'summary': summary,
            'summaryDate': DateProider(),
            'pastMemories': pastMemories
        }
    )
    return llm.invoke([
        SystemMessage(content=preprocessed),
        HumanMessage("")
    ])


def ImageParsingModelProvider():
    return ChatGoogleGenerativeAI(
        model=config.USE_MODEL_IMAGE_PARSING, convert_system_message_to_human=True, safety_settings=MODEL_SAFETY_SETTING)


def ImageParsingModel(image: str) -> str:
    llm = ImageParsingModelProvider()
    return llm.invoke([
        SystemMessage(
            "You are received a image, your task is to descibe this image and output text prompt"),
        HumanMessage({"type": "image_url", "image_url": image})
    ]).content
