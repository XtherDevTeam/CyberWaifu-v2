import models
import instance
import flask
from flask_cors import CORS, cross_origin
import webFrontend.config
import time
import chatbotManager
import dataProvider
import config

app = flask.Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['SECRET_KEY'] = webFrontend.config.SECRET_KEY
dProvider = dataProvider.DataProvider(f'{config.BLOB_URL}/data.db')
chatbotManager = chatbotManager.chatbotManager(dProvider)


def authenticateSession() -> int:
    try:
        return flask.session['user']
    except:
        return -1


@app.route("/api/v1/user/login", methods=["POST"])
def userLogin():
    pwd = ''

    try:
        data = flask.request.get_json()
        pwd = data['password']
    except Exception as e:
        return {'data': 'invalid form', 'status': False}

    if dProvider.authenticate(pwd):
        flask.session['user'] = int(time.time())
        return {'data': 'success', 'status': True}
    else:
        return {'data': 'invalid password', 'status': False}


@app.route("/api/v1/char_list", methods=["POST"])
def charList():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}

    return {'data': dProvider.getCharacterList(), 'status': True}


@app.route("/api/v1/chat/establish", methods=["POST"])
def chatEstablish():
    charName = ''
    beginMsg = ''

    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}
    try:
        data = flask.request.get_json()
        charName = data['charName']
        beginMsg = data['beginMsg']
    except:
        return {'data': 'invalid form', 'status': False}

    session = chatbotManager.createSession(charName)
    return {'response': dProvider.parseModelResponse(chatbotManager.getSession(session).begin(beginMsg)),
            'session': session,
            'status': True}


@app.route("/api/v1/chat/message", methods=["POST"])
def chatMessage():
    session = ''
    msgChain = []
    
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}
    try:
        data = flask.request.get_json()
        session = data['session']
        msgChain = data['msgChain']
    except:
        return {'data': 'invalid form', 'status': False}
    
    parsedMsg = dProvider.parseMessageChain(msgChain)
    
    return {'response': dProvider.parseModelResponse(chatbotManager.getSession(session).chat(parsedMsg)),
            'session': session,
            'status': True}


@app.route("/api/v1/chat/terminate", methods=["POST"])
def chatTerminate():
    session = ''
    
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}
    try:
        data = flask.request.get_json()
        session = data['session']
    except:
        return {'data': 'invalid form', 'status': False}
    
    chatbotManager.terminateSession(session)
    
    return {'data': 'success', 'status': True}


@app.route("/api/v1/attachment/upload/audio", methods=["POST"])
def chatTerminate():
    if not authenticateSession():
        return {'data': 'not authenticated', 'status': False}
    if not dProvider.checkIfInitialized():
        return {'data': 'not initialized', 'status': False}
    
    
    for i in flask.request.files:
        flask.request.files[i].
    
    return {'data': 'success', 'status': True}


def invoke(pBot: instance.Chatbot):
    global bot
    bot = pBot
    app.run(webFrontend.config.APP_HOST,
            webFrontend.config.APP_PORT, debug=False)
