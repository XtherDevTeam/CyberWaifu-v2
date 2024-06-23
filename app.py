import config
from dataProvider import DataProvider
import logger
import memory
import os
import instance
import argparse
import cmdlineFrontend
import models
import webFrontend.web

parser = argparse.ArgumentParser(description='A realistic anime waifu chatbot based on Google Gemini and Langchain library.')

parser.add_argument('-k', '--apiKey', dest='apiKey', default=config.GOOGLE_API_TOKEN, type=str, help='Google API Access Token')
parser.add_argument('-f', '--frontend', action=argparse.BooleanOptionalAction, dest='frontend', type=bool, help='Start command line interative frontend')
parser.add_argument('-c', '--char', dest='char', type=str, help='The character you want to chat with')
parser.add_argument('-n', '--new', action=argparse.BooleanOptionalAction, dest='new', type=bool, help='To create a new character through command line')
parser.add_argument('-u', '--user', dest='user', default='Traveller', type=str, help='Your user name you chat as')
parser.add_argument('-s', '--server', action=argparse.BooleanOptionalAction, dest='server', type=bool, help='To start webFrontend backend server')

args = parser.parse_args()

def do_initialize():
    if "GOOGLE_API_KEY" not in os.environ:
        os.environ["GOOGLE_API_KEY"] = args.apiKey
    
if __name__ == "__main__":
    do_initialize()
    models.initialize()
    dProvider = DataProvider(f'{config.BLOB_URL}/data.db')
    if args.frontend:
        cmdlineFrontend.interactiveFrontend(instance.Chatbot(memory.Memory(dProvider, args.char), args.user))
    if args.server:
        logger.Logger.log('WDNMD')
        webFrontend.web.invoke()
    elif args.new:
        cmdlineFrontend.createNewCharacter(dProvider)
    else:
        parser.print_help()