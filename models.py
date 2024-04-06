"""
conversation.py
Provides packages for model operating
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from google.generativeai.types.safety_types import HarmBlockThreshold, HarmCategory
from google.generativeai import configure as gemini_configure
import google.generativeai as genai
import torch
import whisper
import config
import time
import os

from google_login import load_creds


# mps is not available for whisper
interfereDevice = 'cuda' if torch.cuda.is_available() else 'cpu'
audioModel = whisper.load_model(
    'medium', torch.device(interfereDevice), in_memory=True)


def initialize():
    if config.AUTHENTICATE_METHOD == 'oauth':
        os.environ.pop('GOOGLE_API_KEY')
        gemini_configure(credentials=load_creds(), api_key=None)
        print('Authenticated Google OAuth 2 session.')
        print('Available base models:', [
            m.name for m in genai.list_tuned_models()])
        print('My tuned models:', [m.name for m in genai.list_tuned_models()])


# No need to handle by users, so not in config.py
MODEL_SAFETY_SETTING = {
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
}


# google did not provide the fucking interface for counting token.
# well, now I get it
def TokenCounter(string: str) -> int:
    return ChatGoogleGenerativeAI(model=config.USE_MODEL).get_num_tokens(string)


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
        model=config.USE_MODEL,
        convert_system_message_to_human=True,
        temperature=0.9,
        safety_settings=MODEL_SAFETY_SETTING,
        google_api_key=None,
        credentials=load_creds() if config.AUTHENTICATE_METHOD == 'oauth' else None)


def MemorySummarizingModel(charName: str, pastMemories: str) -> AIMessage:
    llm = ChatGoogleGenerativeAI(
        model=config.USE_MODEL_IMAGE_PARSING,
        convert_system_message_to_human=True,
        temperature=0.9,
        safety_settings=MODEL_SAFETY_SETTING,
        credentials=load_creds() if config.AUTHENTICATE_METHOD == 'oauth' else None)

    preprocessed = PreprocessPrompt(
        config.MEMORY_MERGING_PROMPT,
        {
            'charName': charName,
            'pastMemories': pastMemories
        }
    )
    return llm.invoke([
        SystemMessage(content=preprocessed),
        HumanMessage("")
    ])


def ImageParsingModelProvider():
    return ChatGoogleGenerativeAI(
        model=config.USE_MODEL_IMAGE_PARSING, convert_system_message_to_human=True, temperature=1, safety_settings=MODEL_SAFETY_SETTING, credentials=load_creds() if config.AUTHENTICATE_METHOD == 'oauth' else None)


def ImageParsingModel(image: str) -> str:
    print(image)
    llm = ImageParsingModelProvider()
    return llm.invoke([
        HumanMessage(
            ["You are received a image, your task is to descibe this image and output text prompt",
             {"type": "image_url", "image_url": image}]
        )
    ]).content


def AudioToTextModel(audioPath: str) -> str:
    result = audioModel.transcribe(audioPath)
    return result['text']
