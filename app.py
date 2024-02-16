import config
import memory
import os
import instance
import argparse
import cmdlineFrontend

parser = argparse.ArgumentParser(description='A realistic anime waifu chatbot based on Google Gemini and Langchain library.')

parser.add_argument('-k', '--apiKey', dest='apiKey', default=config.GOOGLE_API_TOKEN, type=str, help='Google API Access Token')
parser.add_argument('-f', '--frontend', action=argparse.BooleanOptionalAction, dest='frontend', type=bool, help='Start command line interative frontend')
parser.add_argument('-c', '--char', dest='char', type=str, help='The character you want to chat with')
parser.add_argument('-n', '--new', action=argparse.BooleanOptionalAction, dest='new', type=bool, help='To create a new character through command line')
parser.add_argument('-u', '--user', dest='user', default='Traveller', type=str, help='Your user name you chat as')

args = parser.parse_args()

def do_initialize():
    if "GOOGLE_API_KEY" not in os.environ:
        os.environ["GOOGLE_API_KEY"] = args.apiKey
    
if __name__ == "__main__":
    do_initialize()
    
    if args.frontend:
        cmdlineFrontend.interactiveFrontend(instance.Chatbot(memory.Memory(args.char, False), args.user))
    elif args.new:
        cmdlineFrontend.createNewCharacter()
    else:
        parser.print_help()