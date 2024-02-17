"""
conversation.py
Provides packages for model operating
"""

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import config
import time


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
        model=config.USE_MODEL, convert_system_message_to_human=True)


def MemoryMergingModel(userName: str, charName: str, summary: str, pastMemories: str) -> AIMessage:
    llm = BaseModelProvider()
    return llm.invoke([
        SystemMessage(content=PreprocessPrompt(
            config.MEMORY_MERGING_PROMPT,
            {
                'userName': userName,
                'charName': charName,
                'summary': summary,
                'summaryDate': DateProider(),
                'pastMemories': pastMemories
            }
        )),
        HumanMessage("")
    ])
    
def ImageParsingModelProvider():
    return ChatGoogleGenerativeAI(
        model=config.USE_MODEL_IMAGE_PARSING, convert_system_message_to_human=True)
    
def ImageParsingModel(image: str) -> str:
    llm = ImageParsingModelProvider()
    return llm.invoke([
        SystemMessage("You are received a image, your task is to descibe this image and output text prompt"),
        HumanMessage({"type": "image_url", "image_url": image})
    ]).content
