import json
import instance
import os
import config


def interactiveFrontend(bot: instance.Chatbot) -> None:
    print('Entering command-line interactive frontend...')
    print('Enter (OPT_EXIT) to quit. Enter (OPT_NO_RESPOND) to skip the first input.')
    with bot:
        u = input(f'({bot.userName})> ')
        print(f'<({bot.memory.getCharName()})')
        print(bot.begin(u))
        while True:
            u = input(f'({bot.userName})> ')
            if u == '(OPT_EXIT)':
                return None
            o = bot.chat(u).strip()
            if o == '(OPT_NORM_EXIT)':
                print(f'{bot.memory.getCharName()} left the chat...')
                return None
            elif o == '(OPT_OUT_OF_CHAR_EXIT)':
                print('Out of character behavior detected!')
                raise RuntimeError('OUT_OF_CHAR_EXIT')
            else:
                for i in o.split('(OPT_MULTI_CUR_MSG_END)'):
                    print(f'<({bot.memory.getCharName()})')
                    print(i.strip())


def createNewCharacter():
    print('CyberWaifu-v2 Character Creator')
    print('When the script ask for character prompt, and character initial memories, provide the path to plain text that contains information in need.')
    charName = input('(Character Name) ')
    pastMemories = input('(Path to character initial memories) ')
    charPrompt = input('(Path to character prompt) ')
    exampleChats = input('(Path to character example chats) ')
    dest = input('(Filename of character profile) ')

    with open(pastMemories, 'r') as file:
        pastMemories = file.read()

    with open(charPrompt, 'r') as file:
        charPrompt = file.read()

    with open(exampleChats, 'r') as file:
        exampleChats = file.read()

    with open(os.path.join(config.CHARACTERS_PATH, dest), 'w') as file:
        file.write(json.dumps({
            'charName': charName,
            'pastMemories': pastMemories,
            'charPrompt': charPrompt,
            'exampleChats': exampleChats
        }))

    print(f'Successfully written character {charName} to {dest}.')
