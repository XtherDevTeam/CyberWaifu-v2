from mirai import Mirai, WebSocketAdapter, FriendMessage, Plain, Image
import miraiConfig
import instance
import models
import asyncio

chatbot: None | instance.Chatbot = None
inTalking = None

def inquireUserName(userName: str) -> str:
    return userName if userName not in miraiConfig.QQ_CHAR_MAPPING.keys() else miraiConfig.QQ_CHAR_MAPPING[userName]

bot : Mirai = Mirai(
    qq=miraiConfig.QQ_ACCOUNT_NUM,  # 改成你的机器人的 QQ 号
    adapter=WebSocketAdapter(
        verify_key=miraiConfig.MIRAI_VERIFY_TOKEN,
        host=miraiConfig.MIRAI_BACKEND_HOST,
        port=miraiConfig.MIRAI_BACKEND_PORT
    )
)


@bot.on(FriendMessage)
async def on_friend_message(event: FriendMessage):
    # output for chatbot.begin() and chatbot.chat()
    o = ''
    if inTalking is not None and inTalking != event.sender.id:
        return bot.send(event, 'Character is being occupied by other person. Please wait...')
    if inTalking is None:
        inTalking = event.sender.id
        chatbot.switchUser(event.sender.get_name())
        msg = ''
        for i in event.message_chain:
            if i.type == 'Image':
                # check if image input is enabled
                if miraiConfig.ACCEPT_IMAGE_INPUT:
                    await i.download(filename='./temp/tempImg')
                    msg += f'(OPT_IMAGE {models.ImageParsingModel("./temp/tempImg")})\n'
                else:
                    continue
            elif i.type == 'Plain':
                msg += f'{i.text}'

        o = chatbot.begin(msg).strip()
    else:
        o = chatbot.chat(event).strip()
    
    l = [i.strip() for i in o.split('(OPT_MULTI_CUR_MSG_END)')]
        
    for i in l:
        if i == '(OPT_NORM_EXIT)':
            bot.send(event, f'{bot.memory.getCharName()} left the chat...')
            inTalking = None
            chatbot.terminateChat()
            return None
        elif i == '(OPT_OUT_OF_CHAR_EXIT)':
            bot.send(event, 'Terminating... Out of character behavior detected!')
            inTalking = None
            chatbot.terminateChat(force=True)
            return None
        await asyncio.sleep(len(i) * 0.1)
        bot.send(i)
    

def invoke(pChatbot: instance.Chatbot):
    global chatbot
    chatbot = pChatbot
    bot.run()
